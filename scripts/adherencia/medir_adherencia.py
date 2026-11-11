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
from studify.rag import prompts  # noqa: E402
from studify.rag.orchestrator import (  # noqa: E402
    ACTIVIDAD_POR_DIRECTIVA,
    MARGEN_PALABRAS_OBJETIVO,
    _redondear_palabras,
    bloque_formato,
    bloque_perfil,
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
REGISTRO_APP = RAIZ / "logs" / "studify.log"

# Cuentas del equipo que aparecen en la prueba de usuario: un id_estudiante por
# línea (lo que sigue a «#» es comentario). Es un archivo local, fuera del repo
# (data/* está en .gitignore), para no versionar datos de personas. Sus cápsulas
# quedan en detalle.csv con `cuenta_equipo = si` pero fuera de todo agregado.
ARCHIVO_CUENTAS_EQUIPO = DIR_SALIDA / "cuentas_equipo.txt"

# Brazos de los experimentos H1/H3 (scripts/h1h3/correr_brazo.py) tal como
# quedan en `resumen.json["comando"]`; rep_A/rep_B son repeticiones de esos brazos.
BRAZOS_EXPERIMENTALES = {"A", "B", "B_topes", "A_obj", "E", "prefijo"}
BRAZO_POR_CARPETA = {"rep_A": "A", "rep_B": "B"}

# Modelo de las corridas cuyo resumen.json no lo registra. Fuente documental,
# no del artefacto: se declara en la columna `modelo_fuente`.
MODELO_SIN_REGISTRO = {
    "_1c_K": ("deepseek-flash", "AVANCE.md: verificación 1c del 05-nov (scripts/verificar_1c_k.py)"),
    "_rep_": ("deepseek-chat", "inferido por fecha: corrida anterior a la migración del 11-oct (AVANCE.md §5.30)"),
}

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


def cuentas_equipo() -> set[int]:
    if not ARCHIVO_CUENTAS_EQUIPO.exists():
        return set()
    ids = set()
    for linea in ARCHIVO_CUENTAS_EQUIPO.read_text(encoding="utf-8").splitlines():
        valor = linea.split("#", 1)[0].strip()
        if valor:
            ids.add(int(valor))
    return ids


def cargar_usuario() -> tuple[list[dict], list[dict], dict[int, dict]]:
    """Cápsulas de las pruebas de usuario, con SELECT en una transacción de solo lectura.

    Devuelve también el último vector de cada estudiante, para leer el registro
    de la aplicación (estudiantes con generaciones fallidas y sin cápsula).
    """
    import psycopg

    sql_vectores = """
        SELECT DISTINCT ON (id_estudiante) id_estudiante,
               porcentaje_v, porcentaje_a, porcentaje_r, porcentaje_k
        FROM diagnostico_vark
        ORDER BY id_estudiante, fecha_diagnostico DESC, id_diagnostico DESC
    """
    sql = """
        SELECT m.id_capsula, m.id_estudiante, e.rol, o.codigo_objetivo, m.modelo_llm,
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
            cur.execute(sql_vectores)
            vectores = {f[0]: {"V": f[1], "A": f[2], "R": f[3], "K": f[4]} for f in cur.fetchall()}
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
            "modelo": f["modelo_llm"] or "no registrado",
            "modelo_fuente": "microcapsula_generada.modelo_llm",
            "brazo": "produccion",
            "prompt": None,
        })
    return capsulas, excluidas, vectores


def cargar_bateria() -> tuple[list[dict], list[dict]]:
    capsulas, excluidas = [], []
    objetivos: dict[str, str] = {}
    codigo_por_tema: dict[str, str] = {}
    modelos: dict[str, str] = {}
    brazos: dict[str, str] = {}
    for resumen in sorted(DIR_BATERIA.glob("*/resumen.json")):
        datos = json.loads(resumen.read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            continue
        corrida = resumen.parent.name
        obj = datos.get("objetivo")
        if isinstance(obj, dict):
            objetivos[corrida] = obj.get("codigo")
            codigo_por_tema[obj.get("tema")] = obj.get("codigo")
        if datos.get("modelo"):
            modelos[corrida] = datos["modelo"]
        m = re.search(r"\.py\s+(\S+)", datos.get("comando") or "")
        if m and m.group(1) in BRAZOS_EXPERIMENTALES | {"base"}:
            brazos[corrida] = m.group(1)

    def _modelo(corrida: str) -> tuple[str, str]:
        if corrida in modelos:
            return modelos[corrida], "resumen.json de la corrida"
        for clave, (modelo, fuente) in MODELO_SIN_REGISTRO.items():
            if clave in corrida:
                return modelo, fuente
        return "no registrado", ""

    def _brazo(corrida: str) -> str:
        for sufijo, brazo in BRAZO_POR_CARPETA.items():
            if corrida.endswith(sufijo):
                return brazo
        return brazos.get(corrida, "sin rotulo")

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
            pcts = {c: Decimal(str(r["pcts"].get(c, 0))) for c in "VARK"}
            cfg = aplicar_reglas(PerfilVark(v=pcts["V"], a=pcts["A"], r=pcts["R"], k=pcts["K"]))
            excluidas.append({"id": ident, "origen": "bateria",
                              "motivo": "sin capsula.json: falló el contrato tras agotar los reintentos",
                              "detalle": f"V{pcts['V']:.0f}-A{pcts['A']:.0f}-R{pcts['R']:.0f}-K{pcts['K']:.0f}"
                                         f" ({cfg.jerarquia.etiqueta}); {corto}",
                              "p_R": pcts["R"], "etiqueta": cfg.jerarquia.etiqueta})
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
            "modelo": _modelo(corrida)[0],
            "modelo_fuente": _modelo(corrida)[1],
            "brazo": _brazo(corrida),
            "prompt": (res.parent / "prompt.txt").read_text(encoding="utf-8")
            if (res.parent / "prompt.txt").exists() else "",
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


def _prompt_vigente(c: dict, cfg, palabras_prompt: int) -> str:
    """¿El prompt guardado contiene, al pie de la letra, las instrucciones que hoy arma el código?

    Compara el mensaje de sistema, la secuencia pedagógica, el bloque de perfil
    (pesos, extensión, cantidades, tono y una instrucción por directiva) y el
    bloque de formato que produce `rag/orchestrator.py` para este vector. Solo
    el material (fragmentos) y el objetivo pueden diferir. Distingue las
    corridas con el prompt de producción de los brazos experimentales H1/H3 y de
    las versiones anteriores del prompt, que comparten nombres de directivas.
    Las cápsulas de usuario no guardan su prompt: no verificable.
    """
    if c["prompt"] is None:
        return NO_VERIF
    t = c["prompt"]
    piezas = (prompts.SISTEMA, prompts.SECUENCIA, bloque_perfil(cfg, palabras_objetivo=palabras_prompt),
              bloque_formato())
    return "si" if all(pieza.strip() in t for pieza in piezas) else "no"


def evaluar(c: dict, equipo: set[int]) -> dict:
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
    prompt_vigente = _prompt_vigente(c, cfg, palabras_prompt)
    es_equipo = c["origen"] == "usuario" and c["id_estudiante"] in equipo
    if c["origen"] == "usuario":
        principal = not es_equipo
    else:
        principal = prompt_vigente == "si"
    return {
        "id": c["id"],
        "origen": c["origen"],
        "referencia": c["referencia"],
        "objetivo": c["objetivo"],
        "modelo": c["modelo"],
        "modelo_fuente": c["modelo_fuente"],
        "id_estudiante": c["id_estudiante"],
        "cuenta_equipo": "si" if es_equipo else "no",
        "corrida": c["corrida"],
        "brazo": c["brazo"],
        "prompt_vigente": prompt_vigente,
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
        "abs_dif_palabras_reglas": abs(palabras - cfg.palabras_texto),
        "tipos_bloque": "|".join(t or "?" for t in tipos),
        "tablas_filasxcols": "|".join(f"{f}x{k}" for f, k in tablas),
        "tipo_actividad": tipo_act,
        "pregunta_en_concepto_central": "si" if pregunta_cc else "no",
        "pregunta_en_prosa_amplia": "si" if pregunta_amplia else "no",
        "tiene_tabla_o_esquema": "si" if rv_entregados else "no",
        "tiene_analogia": "si" if "analogia" in tipos else "no",
        "tiene_glosario": "si" if "glosario" in tipos else "no",
        # Elemento característico de K: lista_pasos o flashcards_y_quiz. El
        # ejemplo_resuelto va aparte porque aparece casi siempre, también con
        # p_K < 25 (lo pide la regla multimodal y lo inducen los fragmentos), y no
        # discrimina entre tramos.
        "tiene_practico_k": "si" if ("lista_pasos" in tipos or tipo_act == "flashcards_y_quiz") else "no",
        "tiene_ejemplo_resuelto": "si" if "ejemplo_resuelto" in tipos else "no",
        "esquema_vigente_valida": "si" if esquema_ok else "no",
        "directivas_historicas": "" if hist is None else "|".join(hist),
        "directivas_coinciden_con_vigentes": ("" if hist is None
                                              else "si" if tuple(hist) == cfg.directivas else "no"),
        "en_conjunto_principal": "si" if principal else "no",
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
           "Dif. media vs reglas | Error absoluto medio vs reglas | Dif. media vs prompt | "
           "Dif. mín / máx vs reglas |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for clase in ("unimodal", "bimodal", "multimodal", "todas"):
        g = filas if clase == "todas" else [f for f in filas if f["clase"] == clase]
        if not g:
            continue
        difs = [int(f["dif_palabras_reglas"]) for f in g]
        out.append(f"| {clase} | {len(g)}{_marca(len(g))} | {_media(g, 'palabras_objetivo_reglas'):.0f} | "
                   f"{_media(g, 'palabras_objetivo_prompt'):.0f} | {_media(g, 'palabras_entregadas'):.0f} | "
                   f"{_media(g, 'dif_palabras_reglas'):+.1f} | {_media(g, 'abs_dif_palabras_reglas'):.1f} | "
                   f"{_media(g, 'dif_palabras_prompt'):+.1f} | {min(difs):+d} / {max(difs):+d} |")
    return out


PRESENCIA = {"V": "tiene_tabla_o_esquema", "A": "tiene_analogia", "R": "tiene_glosario", "K": "tiene_practico_k"}
NOMBRE_PRESENCIA = {"V": "tabla o esquema", "A": "bloque analogia", "R": "bloque glosario",
                    "K": "lista_pasos o actividad flashcards_y_quiz (sin contar ejemplo_resuelto)"}


def _dosis(filas) -> list[str]:
    out = []
    for canal in "VARK":
        dirs = [d for d in DIRECTIVAS if CANAL_DE_DIRECTIVA[d] == canal]
        extra_k = canal == "K"
        out += [f"**Canal {canal}** — directivas del canal: {', '.join(f'`{d}`' for d in dirs)}; "
                f"elemento característico = {NOMBRE_PRESENCIA[canal]}.", "",
                "| Tramo p_" + canal + " | n cápsulas | Directivas del canal exigidas (verificables) | "
                "Cumplidas | Adherencia % | Presencia del elemento característico (exigido o no) |"
                + (" Presencia de ejemplo_resuelto (no discrimina; aparte) |" if extra_k else ""),
                "|---|---:|---:|---:|---:|---:|" + ("---:|" if extra_k else "")]
        for tramo in ("<25", "25-40", ">=40"):
            g = [f for f in filas if f[f"tramo_{canal}"] == tramo]
            exig = [(f, d) for f in g for d in dirs if f[f"dir_{d}"] in (CUMPLE, NO_CUMPLE)]
            ok = sum(f[f"dir_{d}"] == CUMPLE for f, d in exig)
            pres = sum(f[PRESENCIA[canal]] == "si" for f in g)
            fila = (f"| {tramo.replace('>=', '≥').replace('-', '–')} | {len(g)}{_marca(len(g))} | "
                    f"{len(exig)}{_marca(len(exig))} | {ok} | {_pct(ok, len(exig))} | {_celda(pres, len(g))} |")
            if extra_k:
                er = sum(f["tiene_ejemplo_resuelto"] == "si" for f in g)
                fila += f" {_celda(er, len(g))} |"
            out.append(fila)
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
    """Palabras entregadas vs. objetivo, por perfil (etiqueta del código)."""
    out = ["| Perfil (etiqueta) | Clase | n total | Objetivo reglas medio | Entregadas medio | "
           "Dif. media vs reglas | Error absoluto medio vs reglas | Dif. media vs prompt | n usuario | "
           "Dif. usuario vs reglas | n batería | Dif. batería vs reglas |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    perfiles = sorted({(f["etiqueta"], f["clase"]) for f in filas}, key=lambda e: (len(e[0]), e[0]))
    for etiqueta, clase in perfiles + [("todas", "—")]:
        g = filas if etiqueta == "todas" else [f for f in filas if f["etiqueta"] == etiqueta]
        u = [f for f in g if f["origen"] == "usuario"]
        b = [f for f in g if f["origen"] == "bateria"]
        dif = lambda x: f"{_media(x, 'dif_palabras_reglas'):+.1f}" if x else "—"  # noqa: E731
        out.append(f"| {etiqueta} | {clase} | {len(g)}{_marca(len(g))} | "
                   f"{_media(g, 'palabras_objetivo_reglas'):.0f} | {_media(g, 'palabras_entregadas'):.0f} | "
                   f"{_media(g, 'dif_palabras_reglas'):+.1f} | {_media(g, 'abs_dif_palabras_reglas'):.1f} | "
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


def _modelos_y_objetivos(filas_todas) -> list[str]:
    cuenta = defaultdict(int)
    for f in filas_todas:
        cuenta[(f["origen"], f["cuenta_equipo"], f["en_conjunto_principal"], f["modelo"], f["modelo_fuente"])] += 1
    out = ["| Origen | Cuenta del equipo | En conjunto principal | Modelo | Fuente del dato | Cápsulas |",
           "|---|---|---|---|---|---:|"]
    for (origen, eq, pr, modelo, fuente), n in sorted(cuenta.items()):
        out.append(f"| {origen} | {eq} | {pr} | {modelo} | {fuente} | {n} |")
    obj = defaultdict(int)
    for f in filas_todas:
        obj[(f["origen"], f["objetivo"])] += 1
    out += ["", "| Origen | Objetivo de aprendizaje | Cápsulas |", "|---|---|---:|"]
    for (origen, objetivo), n in sorted(obj.items()):
        out.append(f"| {origen} | {objetivo} | {n} |")
    return out


def _versiones_bateria(bateria) -> list[str]:
    cuenta = defaultdict(lambda: [0, 0])
    for f in bateria:
        cuenta[f["brazo"]][0 if f["prompt_vigente"] == "si" else 1] += 1
    out = ["| Brazo / rótulo de la corrida | Prompt idéntico al vigente | Prompt distinto | Total |",
           "|---|---:|---:|---:|"]
    for brazo, (si, no) in sorted(cuenta.items()):
        out.append(f"| {brazo} | {si} | {no} | {si + no} |")
    return out


RE_LOG = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\S* (\w+) (\S+): (.*)$")


def _registro_app(vectores: dict, equipo: set[int]) -> list[str]:
    """Lectura del registro de la aplicación (logs/studify.log), sin modificarlo."""
    L = ["## Registro de la aplicación (prueba de usuario)", ""]
    if not REGISTRO_APP.exists():
        return L + ["No hay registro de la aplicación (`logs/studify.log` no existe).", ""]
    lineas = [m.groups() for m in map(RE_LOG.match, REGISTRO_APP.read_text(encoding="utf-8").splitlines()) if m]
    if not lineas:
        return L + ["El registro está vacío.", ""]
    rechazos = defaultdict(int)
    motivos = defaultdict(int)
    agotadas = defaultdict(list)
    borrados = []
    for ts, nivel, origen, msg in lineas:
        m = re.match(r"cápsula rechazada \(intento (\d)/(\d)", msg)
        if m:
            rechazos[m.group(1)] += 1
            motivos["exceso de palabras" if "el máximo es" in msg
                    else "falta de palabras" if "el mínimo es" in msg else "otro"] += 1
            continue
        m = re.match(r"generación agotada para estudiante=(\d+) objetivo=\d+ \(([^)]+)\)", msg)
        if m:
            agotadas[int(m.group(1))].append(m.group(2))
            continue
        m = re.match(r"estudiante (\d+) eliminó sus datos \((\d+) cápsulas\)", msg)
        if m:
            borrados.append((int(m.group(1)), int(m.group(2))))
    L += [f"Ventana cubierta por el registro: {lineas[0][0]} a {lineas[-1][0]} (hora local). El registro "
          "**no anota las generaciones exitosas** ni identifica al estudiante en los rechazos por intento, así "
          "que no hay denominador para calcular una tasa de fallo por perfil; las cifras son conteos.", "",
          "| Evento | Conteo |", "|---|---:|"]
    for k in sorted(rechazos):
        L.append(f"| Rechazo del validador en el intento {k} | {rechazos[k]} |")
    for k, n in sorted(motivos.items()):
        L.append(f"| Rechazos por {k} (todos los intentos) | {n} |")
    L.append(f"| Generaciones agotadas (3 intentos rechazados) | {sum(len(v) for v in agotadas.values())} |")
    L.append(f"| Estudiantes que eliminaron sus datos | {len(borrados)} "
             f"(con {sum(n for _, n in borrados)} cápsulas eliminadas) |")
    L += ["", "| id_estudiante | Cuenta del equipo | Perfil (etiqueta, último diagnóstico) | Generaciones agotadas | "
          "Objetivos |", "|---|---|---|---:|---|"]
    for est, objs in sorted(agotadas.items()):
        v = vectores.get(est)
        if v is None:
            etiqueta = "sin diagnóstico en la BD (datos eliminados)"
        else:
            p = {k: Decimal(str(x)) for k, x in v.items()}
            etiqueta = aplicar_reglas(PerfilVark(v=p["V"], a=p["A"], r=p["R"], k=p["K"])).jerarquia.etiqueta
        L.append(f"| {est} | {'si' if est in equipo else 'no'} | {etiqueta} | {len(objs)} | "
                 f"{', '.join(sorted(set(objs)))} |")
    return L + [""]


def escribir_resumen(filas_todas: list[dict], excluidas: list[dict], destino: Path,
                     vectores: dict, equipo: set[int]) -> None:
    # Las cápsulas de cuentas del equipo quedan en detalle.csv pero fuera de todo agregado.
    filas = [f for f in filas_todas if f["cuenta_equipo"] == "no"]
    equipo_filas = [f for f in filas_todas if f["cuenta_equipo"] == "si"]
    usuario = [f for f in filas if f["origen"] == "usuario"]
    bateria = [f for f in filas if f["origen"] == "bateria"]
    comparables = [f for f in bateria if f["prompt_vigente"] == "si"]
    experimentales = [f for f in bateria if f["prompt_vigente"] != "si"]
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
          "- Todos los agregados excluyen las filas con `cuenta_equipo = si`.",
          "- Filtros: `origen` (usuario / bateria), `prompt_vigente` (batería comparable = `si`), "
          "`en_conjunto_principal` (usuario sin cuentas del equipo + batería comparable), `clase` "
          "(unimodal / bimodal / multimodal, según `studify.vark.hierarchy.derivar`), `tramo_<canal>` para "
          "la dosis-respuesta.",
          "- Recursos visuales y componentes prácticos usan `recursos_visuales_cumple` y "
          "`componentes_practicos_cumple`; extensión, `dif_palabras_reglas`, `abs_dif_palabras_reglas` y "
          "`dif_palabras_prompt`.", "",
          "**Batería comparable.** Una cápsula de la batería es comparable si su `prompt.txt` contiene, al pie "
          "de la letra, el mensaje de sistema, la secuencia pedagógica, el bloque de perfil y el bloque de "
          "formato que hoy arma `rag/orchestrator.py` para su vector (`prompt_vigente = si`). Así quedan fuera "
          "los brazos experimentales H1/H3 (prompts parchados) y las versiones anteriores del prompt, aunque "
          "compartan los nombres de las directivas.", "",
          "**Clase del perfil.** Se usa la del código (`hierarchy.derivar`): canales activos = los que "
          "quedan a ≤ 10 puntos del máximo; 1 activo = unimodal, 2 = bimodal, ≥ 3 = multimodal. No es lo "
          "mismo que «un canal ≥ 40 %»: la columna `canales_ge40` del CSV permite el corte alternativo. En "
          "los multimodales `rules._directivas` suma las directivas de equilibrio (estructura_jerarquica, "
          "analogias_cotidianas, definiciones_exactas, ejemplo_resuelto).", "",
          "**Muestras pequeñas.** Toda celda con denominador menor que 10 lleva la marca «(n<10)».", "",
          "## Tamaño de muestra", ""] + _n_por_celda(
              [("usuario", usuario), ("batería comparable", comparables), ("total principal", principal),
               ("batería con prompt distinto del vigente", experimentales), ("batería completa", bateria),
               ("total completo", filas)]) + [""]
    L += [f"Prueba de usuario: {len(usuario)} cápsulas de {len({f['id_estudiante'] for f in usuario})} "
          f"estudiantes; se excluyen además {len(equipo_filas)} cápsulas de "
          f"{len({f['id_estudiante'] for f in equipo_filas})} cuenta(s) del equipo.", ""]

    L += ["## Modelo y objetivo de aprendizaje", ""] + _modelos_y_objetivos(filas_todas) + [""]
    L += ["## Versiones del prompt en la batería", "",
          "Rótulo tomado de `resumen.json[\"comando\"]` (`base` = prompt de producción de la época; `A`, `B`, "
          "`A_obj`, `E`, `prefijo` = brazos experimentales H1/H3; `sin rotulo` = corridas anteriores al "
          "05-oct, que no lo registran). La clasificación que usa el análisis es `prompt_vigente`.", ""]
    L += _versiones_bateria(bateria) + [""]

    nota_comp = ("**Conjunto principal de la batería**: cápsulas con `prompt_vigente = si` (ver arriba).")
    nota_exp = ("Brazos experimentales y versiones anteriores del prompt (`prompt_vigente = no`). No representan "
                "al sistema en producción; se muestran para explicar la diferencia con la batería completa.")
    nota_bat = "Secundaria: todas las cápsulas de la batería, cualquiera sea su prompt."
    L += _seccion("Prueba de usuario", usuario,
                  "Sin las cuentas del equipo. Las cápsulas de usuario no guardan su prompt "
                  "(`prompt_vigente = no_verificable`); se generaron con el código de producción del 08 al 11-nov.")
    L += _seccion("Batería comparable (principal)", comparables, nota_comp)
    L += _seccion("Total principal (usuario + batería comparable)", principal,
                  "Filtro en el CSV: `en_conjunto_principal = si`.")
    L += _seccion("Batería con prompt distinto del vigente (no comparable)", experimentales, nota_exp)
    L += _seccion("Batería completa (secundaria)", bateria, nota_bat)
    L += _seccion("Total completo (usuario + batería completa)", filas)

    L += ["## Extensión por perfil — conjunto principal", "",
          f"Las {len(principal)} cápsulas del conjunto principal, agrupadas por la etiqueta de "
          "`hierarchy.derivar`. Diferencia con signo = entregadas − objetivo (positivo: se pasó); error "
          "absoluto medio = media de |entregadas − objetivo|, que no cancela excesos con faltas. "
          "«Objetivo reglas» = `palabras_texto` de `rules.py`; «objetivo prompt» = lo que vio el modelo "
          "(redondeado a la decena, tope 270).", ""]
    L += _palabras_por_perfil(principal) + [""]
    L += ["## Extensión por perfil — todas las cápsulas", "",
          f"Las {len(filas)} cápsulas evaluadas (usuario sin cuentas del equipo + batería completa).", ""]
    L += _palabras_por_perfil(filas) + [""]

    L += ["## Dosis-respuesta", "",
          "Para cada canal, por tramo de su porcentaje: adherencia a las directivas de ese canal donde "
          "fueron exigidas (pares cápsula×directiva verificables) y presencia del elemento característico "
          "del canal en todas las cápsulas del tramo, se haya exigido o no. Bajo 25 % solo se exigen "
          "directivas del canal por la regla multimodal o por la de respaldo. Para K el elemento "
          "característico es `lista_pasos` o la actividad `flashcards_y_quiz`; `ejemplo_resuelto` se informa "
          "en una columna aparte porque aparece en casi todos los tramos y no discrimina.", ""]
    for titulo, g in (("Prueba de usuario", usuario), ("Batería comparable (principal)", comparables),
                      ("Total principal", principal), ("Batería completa (secundaria)", bateria)):
        L += [f"### {titulo} (n = {len(g)}{_marca(len(g))})", ""] + (_dosis(g) if g else ["Sin cápsulas.", ""])

    L += _registro_app(vectores, equipo)

    v_bat = sum(f["p_V"] != "0.00" for f in bateria)
    no_valida = [f for f in filas if f["esquema_vigente_valida"] == "no"]
    excl_b = [e for e in excluidas if e["origen"] == "bateria"]
    L += ["## Advertencias", "",
          f"1. **Muestras pequeñas.** Prueba de usuario: {len(usuario)} cápsulas de "
          f"{len({f['id_estudiante'] for f in usuario})} estudiantes (varias cápsulas por estudiante comparten "
          "vector, no son independientes). Ver la tabla «Tamaño de muestra» y el *n* de cada celda; con n < 10 "
          "un porcentaje es poco más que anecdótico.",
          f"2. **Batería sesgada en V.** {len(bateria) - v_bat} de {len(bateria)} cápsulas de la batería tienen "
          "p_V = 0: las directivas visuales casi no se ejercitan en ese conjunto.",
          "3. **Fragmentos rotulados de BD-U3-02.** La batería usa un único objetivo, BD-U3-02, cuyos "
          "fragmentos vienen rotulados por perfil; eso puede inflar la presencia de `analogia` o "
          "`ejemplo_resuelto` (el modelo copia la forma del material, no necesariamente la directiva).",
          f"4. **Versiones del prompt.** {len(experimentales)} de {len(bateria)} cápsulas de la batería se "
          "generaron con un prompt distinto del vigente (brazos experimentales H1/H3 o versiones anteriores), "
          "aunque sus nombres de directivas coincidan con los vigentes. Por eso la batería principal es la "
          "comparable (`prompt_vigente = si`).",
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
          f"8. **Cuentas del equipo.** {len(equipo_filas)} cápsulas de la prueba de usuario pertenecen a "
          "cuentas del equipo (`cuenta_equipo = si`, lista local en `data/adherencia/cuentas_equipo.txt`) y "
          "quedan fuera de los agregados. Solo se pudo identificar con certeza la cuenta listada; no se puede "
          "descartar que otra cuenta sea de un integrante.",
          f"9. **Supervivencia.** Las {len(excl_b)} corridas de la batería sin cápsula, las generaciones "
          "agotadas del registro y las cápsulas de estudiantes que eliminaron sus datos no entran al análisis; "
          "la adherencia se mide solo sobre cápsulas que pasaron el validador.", "",
          f"### Cápsulas excluidas ({len(excluidas) + len(equipo_filas)})", ""]
    if excl_b:
        pr49 = sum(e["p_R"] >= 49 for e in excl_b)
        pr40 = sum(e["p_R"] >= UMBRAL_ALTO for e in excl_b)
        por_etiqueta = defaultdict(int)
        for e in excl_b:
            por_etiqueta[e["etiqueta"]] += 1
        exceso = sum("máximo" in e.get("detalle", "") for e in excl_b)
        falta = sum("mínimo" in e.get("detalle", "") for e in excl_b)
        L += [f"Batería, sin cápsula: {len(excl_b)} (por exceder el máximo de palabras: {exceso}; por no "
              f"alcanzar el mínimo: {falta}; otro motivo: {len(excl_b) - exceso - falta}); con p_R ≥ 40: {pr40}; "
              f"con p_R ≥ 49: {pr49}. Por perfil: "
              + ", ".join(f"{k} {n}" for k, n in sorted(por_etiqueta.items(), key=lambda kv: (-kv[1], kv[0])))
              + ".", ""]
    if equipo_filas:
        L.append(f"- usuario — cuenta del equipo: {len(equipo_filas)}")
        L += [f"  - `{f['id']}`" for f in equipo_filas]
    motivos = defaultdict(list)
    for e in excluidas:
        motivos[(e["origen"], e["motivo"])].append(e)
    for (origen, motivo), es in sorted(motivos.items()):
        L.append(f"- {origen} — {motivo}: {len(es)}")
        L += [f"  - `{e['id']}`" + (f" — {e['detalle']}" if e.get("detalle") else "") for e in es]
    if not excluidas and not equipo_filas:
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

    usuario, excl_u, vectores = cargar_usuario()
    equipo = cuentas_equipo()
    bateria, excl_b = cargar_bateria()
    capsulas = usuario + bateria
    excluidas = excl_u + excl_b
    filas = [evaluar(c, equipo) for c in capsulas]

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
    escribir_resumen(filas, excluidas, DIR_SALIDA / "resumen.md", vectores, equipo)
    print(f"{len(usuario)} usuario + {len(bateria)} batería = {len(filas)} cápsulas; "
          f"{len(excluidas)} excluidas. Salidas en {DIR_SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
