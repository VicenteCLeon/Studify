"""Adherencia de las cápsulas ya generadas a las directivas VARK vigentes.

SOLO LECTURA. Para el informe de título: para cada cápsula guardada calcula,
con las reglas vigentes de `studify.vark.rules`, qué directivas le
correspondían a su vector P_usuario = {p_V, p_A, p_R, p_K} y comprueba si el
contenido guardado las cumple.

Qué NO hace (y no debe hacer nunca):
- No escribe en la base de datos: la conexión se abre con
  `default_transaction_read_only=on`, `conn.read_only = True`, solo ejecuta
  SELECT, termina con ROLLBACK y se cierra antes de evaluar nada.
- No llama al LLM, no regenera cápsulas ni audio, no ejecuta migraciones.
- No escribe fuera de `data/adherencia/` (ni siquiera `.pyc`:
  `sys.dont_write_bytecode` se fija antes de importar `studify`).

Fuentes de cápsulas:
- "usuario": tabla `microcapsula_generada` (pruebas de usuario). El vector es
  el del diagnóstico al que apunta `id_config` (el vigente al generar). La
  actividad de cierre está en `mini_quiz_json`.
- "bateria": `data/pruebas_vark/<corrida>/<perfil>/capsula.json` con su
  `resultado.json` (vector en `pcts`, directivas de la época en `config`).

Uso:
    python scripts/adherencia/medir_adherencia.py --solo-ejemplos
    python scripts/adherencia/medir_adherencia.py            # corrida total
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # antes de importar studify: no tocar src/**/__pycache__

import argparse
import csv
import io
import json
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from studify.config import get_settings  # noqa: E402
from studify.generation.schemas import (  # noqa: E402
    BloqueContenido,
    Microcapsula,
    contar_palabras,
)
from studify.rag.orchestrator import (  # noqa: E402
    ACTIVIDAD_POR_DIRECTIVA,
    MARGEN_PALABRAS_OBJETIVO,
    _redondear_palabras,
)
from studify.vark.rules import (  # noqa: E402
    UMBRAL_ALTO,
    UMBRAL_VISUAL_MEDIO,
    _DIRECTIVAS_POR_CANAL,
    aplicar_reglas,
)
from studify.vark.scoring import PerfilVark  # noqa: E402
from studify.web import narracion  # noqa: E402

DIR_BATERIA = RAIZ / "data" / "pruebas_vark"
DIR_SALIDA = RAIZ / "data" / "adherencia"

# --- Estados -----------------------------------------------------------------
CUMPLE, NO_CUMPLE, NO_VERIF, NO_APLICA = "cumple", "no_cumple", "no_verificable", "no_aplica"

# Todas las directivas que puede emitir `rules._directivas`, en el orden de
# `_DIRECTIVAS_POR_CANAL` más la de recurso visual medio. Se derivan del módulo
# para no hardcodear la lista.
DIRECTIVAS = (
    *_DIRECTIVAS_POR_CANAL["V"],
    "recurso_visual_complementario",
    *_DIRECTIVAS_POR_CANAL["A"],
    *_DIRECTIVAS_POR_CANAL["R"],
    *_DIRECTIVAS_POR_CANAL["K"],
)
CANAL_DE_DIRECTIVA = {d: c for c in "VARK" for d in _DIRECTIVAS_POR_CANAL[c]}
CANAL_DE_DIRECTIVA["recurso_visual_complementario"] = "V"

# Directivas cuyo cumplimiento no se puede decidir con certeza desde el JSON.
NO_VERIFICABLES = {
    "definiciones_exactas": (
        "pide definir cada término técnico «usando la formulación del material»; "
        "decidir qué es término técnico y si la definición es exacta exige juicio "
        "experto o comparar con los fragmentos: sin heurística aceptada."
    ),
    "tono_oral": (
        "pide segunda persona y frases cortas, «como una explicación hablada»: es un "
        "rasgo de estilo sin umbral definido en el código."
    ),
}

# Misma definición que scripts/probar_perfiles_vark.py (ACTIVIDADES_PRACTICAS):
# una actividad de cierre que cuenta como componente práctico.
ACTIVIDADES_PRACTICAS = frozenset({"flashcards", "flashcards_y_quiz", "intentalo_tu"})
BLOQUES_PRACTICOS = ("ejemplo_resuelto", "lista_pasos")
BLOQUES_VISUALES = ("tabla", "esquema")
# Bloques de prosa corrida (cuerpo string) para la variante amplia de la pregunta.
BLOQUES_PROSA = ("parrafo", "analogia", "ejemplo_resuelto")


# --- Carga -------------------------------------------------------------------


def _url_psycopg(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def cargar_usuario() -> tuple[list[dict], list[dict]]:
    """Cápsulas de las pruebas de usuario, con SELECT en una transacción de solo lectura."""
    import psycopg

    sql = """
        SELECT m.id_capsula, m.id_estudiante, e.rol, o.codigo_objetivo,
               m.contenido_json, m.mini_quiz_json, m.id_config,
               d.porcentaje_v, d.porcentaje_a, d.porcentaje_r, d.porcentaje_k,
               c.recursos_visuales, c.componentes_practicos, c.palabras_texto,
               c.audio_activo, e.voz_genero, e.voz_modo
        FROM microcapsula_generada m
        JOIN estudiante e USING (id_estudiante)
        JOIN objetivo_aprendizaje o USING (id_objetivo)
        LEFT JOIN configuracion_contenido c USING (id_config)
        LEFT JOIN diagnostico_vark d USING (id_diagnostico)
        ORDER BY m.id_capsula
    """
    opciones = "-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=2000"
    conn = psycopg.connect(_url_psycopg(get_settings().database_url), options=opciones)
    try:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [c.name for c in cur.description]
            filas = [dict(zip(cols, f)) for f in cur.fetchall()]
        conn.rollback()
    finally:
        conn.close()

    capsulas, excluidas = [], []
    for f in filas:
        ident = f"U-{f['id_capsula']}"
        if f["rol"] == "control":
            excluidas.append({"id": ident, "origen": "usuario",
                              "motivo": "grupo control: cápsula básica sin adaptación VARK"})
            continue
        if f["porcentaje_v"] is None:
            excluidas.append({"id": ident, "origen": "usuario",
                              "motivo": "sin configuración/diagnóstico asociado (id_config nulo)"})
            continue
        contenido = dict(f["contenido_json"] or {})
        if "actividad" not in contenido and f["mini_quiz_json"]:
            contenido["actividad"] = f["mini_quiz_json"]
        capsulas.append({
            "id": ident,
            "origen": "usuario",
            "referencia": f"microcapsula_generada.id_capsula={f['id_capsula']}",
            "objetivo": f["codigo_objetivo"],
            "id_estudiante": f["id_estudiante"],
            "corrida": "",
            "pcts": {"V": f["porcentaje_v"], "A": f["porcentaje_a"],
                     "R": f["porcentaje_r"], "K": f["porcentaje_k"]},
            "contenido": contenido,
            "config_guardada": {
                "recursos_visuales": f["recursos_visuales"],
                "componentes_practicos": f["componentes_practicos"],
                "palabras_texto": f["palabras_texto"],
                "audio_activo": f["audio_activo"],
            },
            "directivas_historicas": None,
            "audio_omitido": False,
            "audio_archivo_bateria": None,
        })
    return capsulas, excluidas


def cargar_bateria() -> tuple[list[dict], list[dict]]:
    capsulas, excluidas = [], []
    objetivos: dict[str, str] = {}
    codigo_por_tema: dict[str, str] = {}
    for resumen in sorted(DIR_BATERIA.glob("*/resumen.json")):
        datos = json.loads(resumen.read_text(encoding="utf-8"))
        obj = datos.get("objetivo") if isinstance(datos, dict) else None
        if isinstance(obj, dict):
            objetivos[resumen.parent.name] = obj.get("codigo")
            codigo_por_tema[obj.get("tema")] = obj.get("codigo")

    def _objetivo(corrida: str, prompt: Path) -> str:
        """Del resumen de la corrida; si no lo trae, por la línea «Tema:» del prompt guardado."""
        if corrida in objetivos:
            return objetivos[corrida]
        if prompt.exists():
            for linea in prompt.read_text(encoding="utf-8").splitlines():
                if linea.startswith("Tema:"):
                    tema = linea.removeprefix("Tema:").strip()
                    return f"{codigo_por_tema.get(tema, tema)} (inferido del prompt)"
        return "desconocido"

    for res in sorted(DIR_BATERIA.glob("*/*/resultado.json")):
        corrida, slug = res.parent.parent.name, res.parent.name
        ident = f"B-{corrida}/{slug}"
        r = json.loads(res.read_text(encoding="utf-8"))
        cap = res.parent / "capsula.json"
        if not cap.exists():
            detalle = r.get("criterios", {}).get("contrato", {}).get("detalle", "")
            m = re.search(r"tiene (\d+) palabras y el (máximo|mínimo) es (\d+)", detalle)
            corto = (f"{m.group(1)} palabras, {m.group(2)} {m.group(3)}" if m else detalle[:120])
            excluidas.append({"id": ident, "origen": "bateria",
                              "motivo": "sin capsula.json: falló el contrato tras agotar los reintentos",
                              "detalle": corto})
            continue
        estado_audio = (r.get("criterios", {}).get("audio") or {}).get("estado")
        wav = res.parent / "audio.wav"
        capsulas.append({
            "id": ident,
            "origen": "bateria",
            "referencia": str(cap.relative_to(RAIZ)).replace("\\", "/"),
            "objetivo": _objetivo(corrida, res.parent / "prompt.txt"),
            "id_estudiante": "",
            "corrida": corrida,
            "pcts": {c: Decimal(str(r["pcts"].get(c, 0))) for c in "VARK"},
            "contenido": json.loads(cap.read_text(encoding="utf-8")),
            "config_guardada": r.get("config", {}),
            "directivas_historicas": tuple(r.get("config", {}).get("directivas", [])),
            "audio_omitido": estado_audio in (None, "n/a") and not wav.exists(),
            "audio_archivo_bateria": wav.exists(),
        })
    return capsulas, excluidas


# --- Evaluación ----------------------------------------------------------------


def _bloques(contenido: dict) -> list[dict]:
    bloques = list(contenido.get("representacion_adaptativa") or [])
    if isinstance(contenido.get("ejemplo"), dict):
        bloques.append(contenido["ejemplo"])
    return bloques


def _palabras_bloque(b: dict) -> int:
    return BloqueContenido.palabras(BloqueContenido.model_construct(
        tipo=b.get("tipo"), encabezado=b.get("encabezado"), cuerpo=b.get("cuerpo") or ""))


def _palabras_contenido(contenido: dict) -> int:
    """Igual que `Microcapsula.palabras_contenido`, pero tolera JSON que ya no valida."""
    return (contar_palabras(contenido.get("activacion") or "")
            + contar_palabras(contenido.get("concepto_central") or "")
            + sum(_palabras_bloque(b) for b in _bloques(contenido)))


def _dims_tabla(b: dict) -> tuple[int, int]:
    cuerpo = b.get("cuerpo")
    if not isinstance(cuerpo, list) or not cuerpo or not all(isinstance(f, list) for f in cuerpo):
        return (0, 0)
    return (len(cuerpo), min(len(f) for f in cuerpo))


def _clase(jer) -> str:
    return "multimodal" if jer.es_multimodal else "bimodal" if jer.es_bimodal else "unimodal"


def _tramo(p: Decimal) -> str:
    if p < UMBRAL_VISUAL_MEDIO:
        return "<25"
    if p < UMBRAL_ALTO:
        return "25-40"
    return ">=40"


def _archivo_narracion(c: dict) -> str:
    if c["origen"] == "bateria":
        if c["audio_archivo_bateria"]:
            return "si"
        return NO_VERIF if c["audio_omitido"] else "no"
    nombres = narracion.archivos([narracion.guion(c["contenido"])])
    if any((narracion.DIRECTORIO_AUDIO / n).exists() for n in nombres):
        return "si"
    # El WAV solo se sintetiza cuando el estudiante pulsa «escuchar»: su ausencia
    # no prueba que el sistema no lo ofreciera.
    return NO_VERIF


def evaluar(c: dict) -> dict:
    p = {k: Decimal(str(v)) for k, v in c["pcts"].items()}
    perfil = PerfilVark(v=p["V"], a=p["A"], r=p["R"], k=p["K"])
    cfg = aplicar_reglas(perfil)
    jer = cfg.jerarquia
    ajustes = get_settings()
    palabras_prompt = max(ajustes.capsula_min_palabras,
                          min(_redondear_palabras(cfg.palabras_texto),
                              ajustes.capsula_max_palabras - MARGEN_PALABRAS_OBJETIVO))

    contenido = c["contenido"]
    bloques = _bloques(contenido)
    tipos = [b.get("tipo") for b in bloques]
    actividad = contenido.get("actividad") or {}
    tipo_act = actividad.get("tipo") or ""
    concepto = contenido.get("concepto_central") or ""

    tablas = [_dims_tabla(b) for b in bloques if b.get("tipo") == "tabla"]
    tabla_ok = any(filas >= 3 and cols >= 2 for filas, cols in tablas)
    encabezados_ok = bool(bloques) and all((b.get("encabezado") or "").strip() for b in bloques)
    pregunta_cc = "?" in concepto
    prosa = [concepto] + [b.get("cuerpo") for b in bloques
                          if b.get("tipo") in BLOQUES_PROSA and isinstance(b.get("cuerpo"), str)]
    pregunta_amplia = any("?" in t for t in prosa)

    esquema_ok = True
    try:
        cap = Microcapsula.model_validate(contenido)
        palabras = cap.palabras_contenido()
        assert palabras == _palabras_contenido(contenido)
    except Exception:  # JSON antiguo que el esquema vigente ya no acepta
        esquema_ok = False
        palabras = _palabras_contenido(contenido)

    actividad_exigida = next((ACTIVIDAD_POR_DIRECTIVA[d] for d in cfg.directivas
                              if d in ACTIVIDAD_POR_DIRECTIVA), None)
    chequeo = {
        "incluir_mapa_conceptual": "esquema" in tipos,
        "tabla_comparativa": tabla_ok,
        # Verificable solo en su mitad «encabezado en cada bloque»; el orden
        # general→particular no se comprueba (ver Advertencias).
        "estructura_jerarquica": encabezados_ok,
        "recurso_visual_complementario": any(t in BLOQUES_VISUALES for t in tipos),
        "encabezados_jerarquicos": encabezados_ok,
        "glosario": "glosario" in tipos,
        "analogias_cotidianas": "analogia" in tipos,
        "preguntas_reflexivas": pregunta_cc,
        "ejemplo_resuelto": "ejemplo_resuelto" in tipos,
        "paso_a_paso": "lista_pasos" in tipos,
        "actividad_aplicada": tipo_act == (actividad_exigida or ACTIVIDAD_POR_DIRECTIVA["actividad_aplicada"]),
    }

    estados = {}
    for d in DIRECTIVAS:
        if d not in cfg.directivas:
            estados[d] = NO_APLICA
        elif d in NO_VERIFICABLES:
            estados[d] = NO_VERIF
        else:
            estados[d] = CUMPLE if chequeo[d] else NO_CUMPLE

    rv_entregados = sum(t in BLOQUES_VISUALES for t in tipos)
    cp_entregados = sum(t in BLOQUES_PRACTICOS for t in tipos) + (tipo_act in ACTIVIDADES_PRACTICAS)

    hist = c["directivas_historicas"]
    return {
        "id": c["id"],
        "origen": c["origen"],
        "referencia": c["referencia"],
        "objetivo": c["objetivo"],
        "id_estudiante": c["id_estudiante"],
        "corrida": c["corrida"],
        **{f"p_{k}": f"{p[k]:.2f}" for k in "VARK"},
        "clase": _clase(jer),
        "etiqueta": jer.etiqueta,
        "canales_ge40": sum(p[k] >= UMBRAL_ALTO for k in "VARK"),
        **{f"tramo_{k}": _tramo(p[k]) for k in "VARK"},
        "directivas_esperadas": "|".join(cfg.directivas),
        "directivas_cumplidas": "|".join(d for d in cfg.directivas if estados[d] == CUMPLE),
        "directivas_no_cumplidas": "|".join(d for d in cfg.directivas if estados[d] == NO_CUMPLE),
        "directivas_no_verificables": "|".join(d for d in cfg.directivas if estados[d] == NO_VERIF),
        **{f"dir_{d}": estados[d] for d in DIRECTIVAS},
        "recursos_visuales_pedidos": cfg.recursos_visuales,
        "recursos_visuales_entregados": rv_entregados,
        "recursos_visuales_cumple": (NO_APLICA if cfg.recursos_visuales == 0
                                     else CUMPLE if rv_entregados >= cfg.recursos_visuales else NO_CUMPLE),
        "componentes_practicos_pedidos": cfg.componentes_practicos,
        "componentes_practicos_entregados": cp_entregados,
        "componentes_practicos_cumple": (NO_APLICA if cfg.componentes_practicos == 0
                                         else CUMPLE if cp_entregados >= cfg.componentes_practicos
                                         else NO_CUMPLE),
        "audio_activo": "si" if cfg.audio_activo else "no",
        "archivo_narracion": _archivo_narracion(c),
        "palabras_objetivo_reglas": cfg.palabras_texto,
        "palabras_objetivo_prompt": palabras_prompt,
        "palabras_entregadas": palabras,
        "dif_palabras_reglas": palabras - cfg.palabras_texto,
        "dif_palabras_prompt": palabras - palabras_prompt,
        "tipos_bloque": "|".join(t or "?" for t in tipos),
        "tablas_filasxcols": "|".join(f"{f}x{k}" for f, k in tablas),
        "tipo_actividad": tipo_act,
        "pregunta_en_concepto_central": "si" if pregunta_cc else "no",
        "pregunta_en_prosa_amplia": "si" if pregunta_amplia else "no",
        "tiene_tabla_o_esquema": "si" if rv_entregados else "no",
        "tiene_analogia": "si" if "analogia" in tipos else "no",
        "tiene_glosario": "si" if "glosario" in tipos else "no",
        "tiene_practico_k": "si" if ("lista_pasos" in tipos or "ejemplo_resuelto" in tipos
                                     or tipo_act == "flashcards_y_quiz") else "no",
        "esquema_vigente_valida": "si" if esquema_ok else "no",
        "directivas_historicas": "" if hist is None else "|".join(hist),
        "directivas_coinciden_con_vigentes": ("" if hist is None
                                              else "si" if tuple(hist) == cfg.directivas else "no"),
        "en_conjunto_principal": "si" if hist is None or tuple(hist) == cfg.directivas else "no",
    }


# --- Salidas -------------------------------------------------------------------


def escribir_csv(filas: list[dict], destino: Path) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(filas[0].keys()), lineterminator="\n")
    w.writeheader()
    w.writerows(filas)
    destino.write_text(buf.getvalue(), encoding="utf-8")


def _pct(k: int, n: int) -> str:
    return "—" if n == 0 else f"{100 * k / n:.1f} %"


MUESTRA_PEQUENA = 10


def _marca(n: int) -> str:
    """Marca las celdas con menos de MUESTRA_PEQUENA cápsulas (o pares) en el denominador."""
    return " (n<10)" if 0 < n < MUESTRA_PEQUENA else ""


def _celda(k: int, n: int) -> str:
    return "—" if n == 0 else f"{k}/{n} ({100 * k / n:.0f} %){_marca(n)}"


def _conteo(filas, col):
    """(corresponde, verificables, cumple) para una columna de estado."""
    corresp = [f for f in filas if f[col] != NO_APLICA]
    verif = [f for f in corresp if f[col] in (CUMPLE, NO_CUMPLE)]
    return len(corresp), len(verif), sum(f[col] == CUMPLE for f in verif)


FILAS_RESUMEN = ([(d, f"dir_{d}") for d in DIRECTIVAS]
                 + [("recursos_visuales (entregados ≥ pedidos)", "recursos_visuales_cumple"),
                    ("componentes_practicos (entregados ≥ pedidos)", "componentes_practicos_cumple")])


def _tabla_directivas(filas) -> list[str]:
    out = ["| Directiva | Cápsulas donde correspondía | Cápsulas donde apareció | Adherencia % | n (verificables) |",
           "|---|---:|---:|---:|---:|"]
    for nombre, col in FILAS_RESUMEN:
        corresp, verif, ok = _conteo(filas, col)
        if corresp == 0:
            continue
        if verif == 0:
            out.append(f"| {nombre} | {corresp} | n. v. | no verificable | 0 |")
        else:
            out.append(f"| {nombre} | {corresp} | {ok} | {_pct(ok, verif)} | {verif}{_marca(verif)} |")
    # Variante amplia de la pregunta reflexiva: informativa, no entra en la adherencia.
    pr = [f for f in filas if f["dir_preguntas_reflexivas"] != NO_APLICA]
    if pr:
        k = sum(f["pregunta_en_prosa_amplia"] == "si" for f in pr)
        out.append(f"| *preguntas_reflexivas, variante amplia (informativa)* | {len(pr)} | {k} | "
                   f"*{_pct(k, len(pr))}* | {len(pr)}{_marca(len(pr))} |")
    return out


def _tabla_por_clase(filas) -> list[str]:
    clases = ("unimodal", "bimodal", "multimodal")
    out = ["| Directiva | " + " | ".join(clases) + " | todas |", "|---|" + "---:|" * (len(clases) + 1)]
    for nombre, col in FILAS_RESUMEN:
        celdas, alguna = [], False
        for grupo in [[f for f in filas if f["clase"] == c] for c in clases] + [filas]:
            corresp, verif, ok = _conteo(grupo, col)
            alguna |= corresp > 0
            celdas.append("—" if corresp == 0 else "n. v." if verif == 0 else _celda(ok, verif))
        if alguna:
            out.append(f"| {nombre} | " + " | ".join(celdas) + " |")
    return out


def _palabras(filas) -> list[str]:
    out = ["| Clase | n | Objetivo (reglas) medio | Objetivo (prompt) medio | Entregadas medio | "
           "Dif. media vs reglas | Dif. media vs prompt | Dif. mín / máx vs reglas |",
           "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for clase in ("unimodal", "bimodal", "multimodal", "todas"):
        g = filas if clase == "todas" else [f for f in filas if f["clase"] == clase]
        if not g:
            continue
        m = lambda col: sum(int(f[col]) for f in g) / len(g)  # noqa: E731
        difs = [int(f["dif_palabras_reglas"]) for f in g]
        out.append(f"| {clase} | {len(g)}{_marca(len(g))} | {m('palabras_objetivo_reglas'):.0f} | "
                   f"{m('palabras_objetivo_prompt'):.0f} | {m('palabras_entregadas'):.0f} | "
                   f"{m('dif_palabras_reglas'):+.0f} | {m('dif_palabras_prompt'):+.0f} | "
                   f"{min(difs):+d} / {max(difs):+d} |")
    return out


PRESENCIA = {"V": "tiene_tabla_o_esquema", "A": "tiene_analogia", "R": "tiene_glosario", "K": "tiene_practico_k"}
NOMBRE_PRESENCIA = {"V": "tabla o esquema", "A": "bloque analogia", "R": "bloque glosario",
                    "K": "lista_pasos, ejemplo_resuelto o flashcards_y_quiz"}


def _dosis(filas) -> list[str]:
    out = []
    for canal in "VARK":
        dirs = [d for d in DIRECTIVAS if CANAL_DE_DIRECTIVA[d] == canal]
        out += [f"**Canal {canal}** — directivas del canal: {', '.join(f'`{d}`' for d in dirs)}; "
                f"presencia = {NOMBRE_PRESENCIA[canal]}.", "",
                "| Tramo p_" + canal + " | n cápsulas | Directivas del canal exigidas (verificables) | "
                "Cumplidas | Adherencia % | Presencia del elemento (exigido o no) |",
                "|---|---:|---:|---:|---:|---:|"]
        for tramo in ("<25", "25-40", ">=40"):
            g = [f for f in filas if f[f"tramo_{canal}"] == tramo]
            exig = [(f, d) for f in g for d in dirs if f[f"dir_{d}"] in (CUMPLE, NO_CUMPLE)]
            ok = sum(f[f"dir_{d}"] == CUMPLE for f, d in exig)
            pres = sum(f[PRESENCIA[canal]] == "si" for f in g)
            out.append(f"| {tramo.replace('>=', '≥').replace('-', '–')} | {len(g)}{_marca(len(g))} | "
                       f"{len(exig)}{_marca(len(exig))} | {ok} | "
                       f"{_pct(ok, len(exig))} | {_celda(pres, len(g))} |")
        out.append("")
    return out


def _n_por_celda(conjuntos) -> list[str]:
    out = ["| Conjunto | unimodal | bimodal | multimodal | total |", "|---|---:|---:|---:|---:|"]
    for nombre, g in conjuntos:
        cuenta = [sum(f["clase"] == c for f in g) for c in ("unimodal", "bimodal", "multimodal")]
        out.append(f"| {nombre} | " + " | ".join(f"{n}{_marca(n)}" for n in cuenta)
                   + f" | {len(g)}{_marca(len(g))} |")
    return out


def _media(g, col) -> float:
    return sum(int(f[col]) for f in g) / len(g)


def _palabras_por_perfil(filas) -> list[str]:
    """Palabras entregadas vs. objetivo, por perfil (etiqueta del código), para todas las cápsulas."""
    out = ["| Perfil (etiqueta) | Clase | n total | Objetivo reglas medio | Objetivo prompt medio | "
           "Entregadas medio | Dif. media vs reglas | Dif. media vs prompt | n usuario | "
           "Dif. usuario vs reglas | n batería | Dif. batería vs reglas |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    perfiles = sorted({(f["etiqueta"], f["clase"]) for f in filas}, key=lambda e: (len(e[0]), e[0]))
    for etiqueta, clase in perfiles + [("todas", "—")]:
        g = filas if etiqueta == "todas" else [f for f in filas if f["etiqueta"] == etiqueta]
        u = [f for f in g if f["origen"] == "usuario"]
        b = [f for f in g if f["origen"] == "bateria"]
        dif = lambda x: f"{_media(x, 'dif_palabras_reglas'):+.1f}" if x else "—"  # noqa: E731
        out.append(f"| {etiqueta} | {clase} | {len(g)}{_marca(len(g))} | "
                   f"{_media(g, 'palabras_objetivo_reglas'):.0f} | {_media(g, 'palabras_objetivo_prompt'):.0f} | "
                   f"{_media(g, 'palabras_entregadas'):.0f} | {_media(g, 'dif_palabras_reglas'):+.1f} | "
                   f"{_media(g, 'dif_palabras_prompt'):+.1f} | {len(u)}{_marca(len(u))} | {dif(u)} | "
                   f"{len(b)}{_marca(len(b))} | {dif(b)} |")
    return out


def _seccion(titulo: str, g: list[dict], nota: str = "") -> list[str]:
    L = [f"## {titulo} — n = {len(g)}{_marca(len(g))}", ""]
    if nota:
        L += [nota, ""]
    if not g:
        return L + ["Sin cápsulas.", ""]
    L += ["### Todas las clases", ""] + _tabla_directivas(g) + [""]
    L += ["### Por clase de perfil (cumple / verificables)", ""] + _tabla_por_clase(g) + [""]
    L += ["### Extensión por clase (palabras de activación + concepto + representación + ejemplo)", ""]
    L += _palabras(g) + [""]
    narr = [f for f in g if f["audio_activo"] == "si"]
    L += ["### Narración (audio_activo)", "",
          f"audio_activo = sí en {len(narr)} cápsulas; archivo de narración encontrado en "
          f"{sum(f['archivo_narracion'] == 'si' for f in narr)}, ausente en "
          f"{sum(f['archivo_narracion'] == 'no' for f in narr)}, no verificable en "
          f"{sum(f['archivo_narracion'] == NO_VERIF for f in narr)}. Es descriptivo, no un % de adherencia "
          "(ver Advertencias).", ""]
    return L


def escribir_resumen(filas: list[dict], excluidas: list[dict], destino: Path) -> None:
    usuario = [f for f in filas if f["origen"] == "usuario"]
    bateria = [f for f in filas if f["origen"] == "bateria"]
    comparables = [f for f in bateria if f["directivas_coinciden_con_vigentes"] == "si"]
    principal = [f for f in filas if f["en_conjunto_principal"] == "si"]
    L: list[str] = []
    L += ["# Adherencia de las cápsulas a las directivas VARK vigentes", "",
          "Generado por `scripts/adherencia/medir_adherencia.py` (solo lectura). Detalle por cápsula en "
          "`data/adherencia/detalle.csv`.", "",
          "## Cómo rastrear cada porcentaje", "",
          "- Una directiva *correspondía* a una cápsula si su columna `dir_<directiva>` en `detalle.csv` "
          "es distinta de `no_aplica` (la calcula `studify.vark.rules.aplicar_reglas` sobre `p_V..p_K`).",
          "- *Apareció* = filas con `cumple`. El denominador del % (*n*) son las filas `cumple` + "
          "`no_cumple`; las `no_verificable` quedan fuera del %.",
          "- Filtros: `origen` (usuario / bateria), `en_conjunto_principal` (usuario + batería "
          "comparable), `clase` (unimodal / bimodal / multimodal, según "
          "`studify.vark.hierarchy.derivar`), `tramo_<canal>` para la dosis-respuesta.",
          "- Recursos visuales y componentes prácticos usan `recursos_visuales_cumple` y "
          "`componentes_practicos_cumple`; extensión, `dif_palabras_reglas` y `dif_palabras_prompt`.", "",
          "**Clase del perfil.** Se usa la del código (`hierarchy.derivar`): canales activos = los que "
          "quedan a ≤ 10 puntos del máximo; 1 activo = unimodal, 2 = bimodal, ≥ 3 = multimodal. No es lo "
          "mismo que «un canal ≥ 40 %»: la columna `canales_ge40` del CSV permite el corte alternativo. En "
          "los multimodales `rules._directivas` suma las directivas de equilibrio (estructura_jerarquica, "
          "analogias_cotidianas, definiciones_exactas, ejemplo_resuelto).", "",
          "**Muestras pequeñas.** Toda celda con denominador menor que 10 lleva la marca «(n<10)».", "",
          "## Tamaño de muestra", ""] + _n_por_celda(
              [("usuario", usuario), ("batería comparable", comparables), ("total principal", principal),
               ("batería completa", bateria), ("total completo", filas)]) + [""]

    nota_comp = ("**Conjunto principal de la batería.** Solo las cápsulas cuyas directivas guardadas en "
                 "`resultado.json` coinciden exactamente con las que hoy calcula `rules.py` "
                 "(`directivas_coinciden_con_vigentes = si`): recibieron las mismas instrucciones con que se "
                 "las mide.")
    nota_bat = ("Secundaria: todas las cápsulas de la batería medidas contra las reglas vigentes, incluidas "
                "las generadas con directivas anteriores (ver Advertencia 4).")
    L += _seccion("Prueba de usuario", usuario)
    L += _seccion("Batería comparable (principal)", comparables, nota_comp)
    L += _seccion("Total principal (usuario + batería comparable)", principal,
                  "Filtro en el CSV: `en_conjunto_principal = si`.")
    L += _seccion("Batería completa (secundaria)", bateria, nota_bat)
    L += _seccion("Total completo (usuario + batería completa)", filas)

    L += ["## Extensión por perfil — todas las cápsulas", "",
          f"Las {len(filas)} cápsulas evaluadas (usuario + batería completa), agrupadas por la etiqueta de "
          "`hierarchy.derivar`. Diferencia con signo = entregadas − objetivo (positivo: se pasó). "
          "«Objetivo reglas» = `palabras_texto` de `rules.py`; «objetivo prompt» = lo que vio el modelo "
          "(redondeado a la decena, tope 270). Columnas del CSV: `dif_palabras_reglas`, "
          "`dif_palabras_prompt`.", ""]
    L += _palabras_por_perfil(filas) + [""]

    L += ["## Dosis-respuesta", "",
          "Para cada canal, por tramo de su porcentaje: adherencia a las directivas de ese canal donde "
          "fueron exigidas (pares cápsula×directiva verificables) y presencia del elemento característico "
          "del canal en todas las cápsulas del tramo, se haya exigido o no. Bajo 25 % solo se exigen "
          "directivas del canal por la regla multimodal o por la de respaldo.", ""]
    for titulo, g in (("Prueba de usuario", usuario), ("Batería comparable (principal)", comparables),
                      ("Total principal", principal), ("Batería completa (secundaria)", bateria)):
        L += [f"### {titulo} (n = {len(g)}{_marca(len(g))})", ""] + (_dosis(g) if g else ["Sin cápsulas.", ""])

    hist_distintas = len(bateria) - len(comparables)
    v_bat = sum(f["p_V"] != "0.00" for f in bateria)
    no_valida = [f for f in filas if f["esquema_vigente_valida"] == "no"]
    L += ["## Advertencias", "",
          f"1. **Muestras pequeñas.** Prueba de usuario: {len(usuario)} cápsulas de "
          f"{len({f['id_estudiante'] for f in usuario})} estudiantes (varias cápsulas por estudiante comparten "
          "vector, no son independientes). Ver la tabla «Tamaño de muestra» y el *n* de cada celda; con n < 10 "
          "un porcentaje es poco más que anecdótico.",
          f"2. **Batería sesgada en V.** {len(bateria) - v_bat} de {len(bateria)} cápsulas de la batería tienen "
          "p_V = 0: las directivas visuales casi no se ejercitan en ese conjunto.",
          "3. **Fragmentos rotulados de BD-U3-02.** La batería usa casi solo el objetivo BD-U3-02, cuyos "
          "fragmentos vienen rotulados por perfil; eso puede inflar la presencia de `analogia` o "
          "`ejemplo_resuelto` (el modelo copia la forma del material, no necesariamente la directiva).",
          f"4. **Reglas de otra época.** {hist_distintas} de {len(bateria)} cápsulas de la batería se generaron "
          "con una lista de directivas distinta de la vigente"
          + (", así que la «Batería comparable» (principal) coincide con la «Batería completa». "
             if hist_distintas == 0 else
             "; la sección «Batería comparable» (principal) aísla las que sí recibieron la misma lista. ")
          + "Coincidir en los nombres de las directivas no garantiza que el texto del prompt fuera el mismo: "
          "`INSTRUCCION_POR_DIRECTIVA` y el validador cambiaron después de las corridas de octubre (p. ej., el "
          "validador exige `flashcards_y_quiz` para `actividad_aplicada` desde el 05-nov-2026).",
          "5. **No verificables.** "
          + " ".join(f"`{d}`: {m}" for d, m in NO_VERIFICABLES.items())
          + " `estructura_jerarquica` se verifica solo en su mitad «encabezado en cada bloque»; el orden "
          "general→particular no. `preguntas_reflexivas` usa la heurística acordada (signo «?» en "
          "`concepto_central`, fuera de la activación) y no comprueba que la pregunta se responda después; "
          "la variante amplia (también en párrafos, analogías y ejemplos resueltos) se muestra aparte, "
          "solo informativa.",
          "6. **Narración.** En la prueba de usuario el WAV se sintetiza solo cuando el estudiante pulsa "
          "«escuchar»: su ausencia no prueba que no se ofreciera, por eso queda `no_verificable`. En la "
          "batería la mayoría de las corridas usó `--sin-audio` (también `no_verificable`).",
          f"7. **Esquema vigente.** {len(no_valida)} cápsulas ya no validan contra `Microcapsula` vigente; "
          "se evalúan igual leyendo el JSON crudo y contando palabras con la misma función "
          "(`contar_palabras`).",
          "8. **Prueba de usuario.** Se toman todas las cápsulas de `microcapsula_generada` con rol "
          "`estudiante`; el script no distingue cuentas de prueba del equipo, si las hubiera "
          "(columna `id_estudiante`).", "",
          f"### Cápsulas excluidas ({len(excluidas)})", ""]
    if excluidas:
        motivos = defaultdict(list)
        for e in excluidas:
            motivos[(e["origen"], e["motivo"])].append(e)
        for (origen, motivo), es in sorted(motivos.items()):
            L.append(f"- {origen} — {motivo}: {len(es)}")
            L += [f"  - `{e['id']}`" + (f" — {e['detalle']}" if e.get("detalle") else "") for e in es]
    else:
        L.append("Ninguna.")
    destino.write_text("\n".join(L) + "\n", encoding="utf-8")


# --- Ejemplos --------------------------------------------------------------------


def mostrar(c: dict, fila: dict) -> None:
    print("=" * 100)
    print(f"{fila['id']}  ({fila['referencia']})  objetivo={fila['objetivo']}")
    print(f"vector V={fila['p_V']} A={fila['p_A']} R={fila['p_R']} K={fila['p_K']}  "
          f"clase={fila['clase']} etiqueta={fila['etiqueta']}  canales>=40: {fila['canales_ge40']}")
    print(f"directivas esperadas: {fila['directivas_esperadas'].replace('|', ', ')}")
    if fila["directivas_historicas"]:
        print(f"directivas de la época: {fila['directivas_historicas'].replace('|', ', ')} "
              f"(coinciden: {fila['directivas_coinciden_con_vigentes']})")
    cont = c["contenido"]
    print("-- contenido --")
    print(f"  activacion: {cont.get('activacion')!r}")
    cc = cont.get("concepto_central") or ""
    print(f"  concepto_central ({contar_palabras(cc)} pal.): {cc[:240]!r}{'…' if len(cc) > 240 else ''}")
    for b in _bloques(cont):
        cuerpo = b.get("cuerpo")
        forma = (f"tabla {_dims_tabla(b)[0]}x{_dims_tabla(b)[1]}" if b.get("tipo") == "tabla"
                 else f"lista[{len(cuerpo)}]" if isinstance(cuerpo, list) else f"texto {contar_palabras(cuerpo or '')} pal.")
        print(f"  bloque {b.get('tipo'):<17} encabezado={b.get('encabezado')!r:<45} {forma}")
    print(f"  actividad: {fila['tipo_actividad']}")
    print("-- evaluación por directiva --")
    for d in DIRECTIVAS:
        if fila[f"dir_{d}"] != NO_APLICA:
            print(f"  {d:<32} {fila[f'dir_{d}']}")
    print(f"  recursos_visuales  pedidos={fila['recursos_visuales_pedidos']} entregados="
          f"{fila['recursos_visuales_entregados']} -> {fila['recursos_visuales_cumple']}")
    print(f"  componentes_pract. pedidos={fila['componentes_practicos_pedidos']} entregados="
          f"{fila['componentes_practicos_entregados']} -> {fila['componentes_practicos_cumple']}")
    print(f"  audio_activo={fila['audio_activo']} archivo_narracion={fila['archivo_narracion']}")
    print(f"  palabras: entregadas={fila['palabras_entregadas']} objetivo reglas="
          f"{fila['palabras_objetivo_reglas']} ({fila['dif_palabras_reglas']:+d}) objetivo prompt="
          f"{fila['palabras_objetivo_prompt']} ({fila['dif_palabras_prompt']:+d})")
    print(f"  pregunta en concepto_central={fila['pregunta_en_concepto_central']} "
          f"(variante amplia={fila['pregunta_en_prosa_amplia']})  esquema vigente valida="
          f"{fila['esquema_vigente_valida']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo-ejemplos", action="store_true",
                    help="evalúa y muestra las cápsulas de --ejemplo sin escribir salidas")
    ap.add_argument("--ejemplo", action="append", default=[],
                    help="id de cápsula a mostrar (p. ej. U-8697 o B-<corrida>/<perfil>)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    usuario, excl_u = cargar_usuario()
    bateria, excl_b = cargar_bateria()
    capsulas = usuario + bateria
    excluidas = excl_u + excl_b
    filas = [evaluar(c) for c in capsulas]

    por_id = {c["id"]: (c, f) for c, f in zip(capsulas, filas)}
    for ident in args.ejemplo:
        if ident in por_id:
            mostrar(*por_id[ident])
        else:
            print(f"(no encontrado: {ident})")
    if args.solo_ejemplos:
        print(f"\n{len(usuario)} cápsulas de usuario, {len(bateria)} de batería, {len(excluidas)} excluidas. "
              "Sin escribir salidas (--solo-ejemplos).")
        return

    DIR_SALIDA.mkdir(parents=True, exist_ok=True)
    escribir_csv(filas, DIR_SALIDA / "detalle.csv")
    escribir_resumen(filas, excluidas, DIR_SALIDA / "resumen.md")
    print(f"{len(usuario)} usuario + {len(bateria)} batería = {len(filas)} cápsulas; "
          f"{len(excluidas)} excluidas. Salidas en {DIR_SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
