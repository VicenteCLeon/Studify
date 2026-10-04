"""Batería de pruebas de punta a punta del motor adaptativo VARK.

Ejecuta el pipeline real —retriever → reglas VARK → prompt maestro → LLM con
bucle de reparación → TTS local— sobre **un objetivo fijo** y una batería de
perfiles {V, A, R, K}, y evalúa cada cápsula con criterios objetivos: contrato,
trazabilidad, texto (R), audio (A), ejercicios (K), proporcionalidad y
operación. Los resultados alimentan `docs/PRUEBAS_VARK.md`.

**El canal Visual queda fuera por decisión del equipo (03-oct-2026).** V vale 0
en todos los perfiles, así que `recursos_visuales` es siempre 0, y este script
no importa `studify.media.image` ni `GeneradorMultimedia`: el único módulo
multimedia que toca es `studify.media.audio`.

**No persiste nada en la base.** Llama a las funciones del motor directamente,
sin estudiantes ni diagnósticos, y sin pasar por el caché por huella de
`POST /api/capsulas`, que haría incomparables dos corridas del mismo perfil.

**El guion del audio es el del visor del estudiante** (`activacion` +
`concepto_central`, igual que `POST /student/viewer/{id}/generate-audio`), que
es el que el estudiante escucha. El de `POST /api/capsulas` se registra sin
sintetizarlo, como evidencia del hallazgo documentado en PRUEBAS_VARK.md.

Uso (desde la raíz del repo):

    python scripts/probar_perfiles_vark.py          # solo plan, llamadas y costo
    python scripts/probar_perfiles_vark.py --live --max-runs 3
    python scripts/probar_perfiles_vark.py --live --semilla 7 --n-aleatorias 12
    python scripts/probar_perfiles_vark.py --informe data/pruebas_vark/<corrida>/resumen.json
"""

import argparse
import itertools
import json
import logging
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import wave
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from studify.config import get_settings
from studify.db.models import ObjetivoAprendizaje
from studify.generation.generator import ErrorGeneracion, Mensaje, generar
from studify.generation.schemas import BloqueContenido, Microcapsula, contar_palabras
from studify.rag import orchestrator
from studify.rag.retriever import FragmentoRecuperado
from studify.vark.rules import UMBRAL_ALTO, ConfiguracionGenerada, aplicar_reglas
from studify.vark.scoring import PerfilVark

RAIZ = Path(__file__).resolve().parent.parent

SALIDA_POR_DEFECTO = Path("data/pruebas_vark")
DOC_POR_DEFECTO = Path("docs/PRUEBAS_VARK.md")
OBJETIVO_POR_DEFECTO = "BD-U3-02"
SEMILLA_POR_DEFECTO = 42
ALEATORIAS_POR_DEFECTO = 8

# Los tres canales que se prueban. V queda fijo en 0 (ver docstring).
CANALES_PRUEBA = ("A", "R", "K")

# --- Umbrales de las heurísticas ----------------------------------------------
# Ninguno sale del informe: son criterios de esta batería, explicados en
# PRUEBAS_VARK.md junto con sus límites.

# Ventana de velocidad de habla aceptable para el audio. XTTS en español ronda
# 2,5 palabras/s; fuera de 1,5–4 el audio está truncado o tiene silencios largos.
PALABRAS_POR_SEGUNDO_MIN = 1.5
PALABRAS_POR_SEGUNDO_MAX = 4.0

# Fracción mínima de las raíces léxicas de la cápsula que deben aparecer en los
# fragmentos. Bajo esto se emite una advertencia, no una falla: la cápsula
# reformula, y una analogía cotidiana legítima usa palabras que no están ahí.
COBERTURA_MINIMA = 0.5

# Fracción de preguntas del quiz cuya respuesta correcta tiene que estar
# respaldada léxicamente por los fragmentos (perfiles K ≥ 40%).
RESOLUBLES_MINIMO = 0.8

SEGUNDA_PERSONA_MINIMA = 3
EXTENSION_LARGA = 240

ACTIVIDADES_PRACTICAS = frozenset({"flashcards", "flashcards_y_quiz", "intentalo_tu"})

# --- Estimación de costo (solo para el plan previo) ---------------------------
# Tarifa supuesta de deepseek-chat en USD por millón de tokens. Verificarla en
# la página del proveedor antes de citar el costo: se puede pasar por CLI.
PRECIO_ENTRADA_USD_M = 0.28
PRECIO_SALIDA_USD_M = 0.42
TOKENS_SALIDA_ESTIMADOS = 1500
CARACTERES_POR_TOKEN = 3.5
# Mensaje de reparación que se agrega en cada reintento, en tokens.
TOKENS_REPARACION = 250
# XTTS en CPU recarga el modelo en cada llamada.
SEGUNDOS_AUDIO_ESTIMADOS = (60, 180)

MARCA_INICIO = "<!-- inicio:resultados-generados -->"
MARCA_FIN = "<!-- fin:resultados-generados -->"

logger = logging.getLogger("probar_perfiles_vark")


# --- Batería de perfiles ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Perfil:
    fase: str
    nombre: str
    a: int
    r: int
    k: int
    v: int = 0

    def __post_init__(self) -> None:
        if self.v + self.a + self.r + self.k != 100:
            raise ValueError(f"el perfil {self.nombre} no suma 100")

    @property
    def pcts(self) -> dict[str, int]:
        return {"V": self.v, "A": self.a, "R": self.r, "K": self.k}

    @property
    def slug(self) -> str:
        return f"{self.fase}_{self.nombre}"

    def vark(self) -> PerfilVark:
        return PerfilVark(
            v=Decimal(self.v), a=Decimal(self.a), r=Decimal(self.r), k=Decimal(self.k)
        )


def _perfil(fase: str, dist: dict[str, int], prefijo: str = "") -> Perfil:
    a, r, k = (dist.get(c, 0) for c in CANALES_PRUEBA)
    return Perfil(fase, f"{prefijo}A{a}-R{r}-K{k}", a=a, r=r, k=k)


def fase_a() -> list[Perfil]:
    """Perfiles puros: 100% A, 100% R, 100% K."""
    return [_perfil("A", {c: 100}) for c in CANALES_PRUEBA]


def fase_b() -> list[Perfil]:
    """Mezclas controladas: parejas, dominante + secundarios, equilibrado, extremos."""
    dists: list[dict[str, int]] = [
        {x: 50, y: 50} for x, y in itertools.combinations(CANALES_PRUEBA, 2)
    ]
    for patron in ((70, 20, 10), (60, 30, 10)):
        dists += [dict(zip(orden, patron, strict=True)) for orden in
                  itertools.permutations(CANALES_PRUEBA)]
    dists.append({"A": 34, "R": 33, "K": 33})
    for dominante in CANALES_PRUEBA:
        dists.append({c: 90 if c == dominante else 5 for c in CANALES_PRUEBA})
    return [_perfil("B", d) for d in dists]


def redondear_a_100(proporciones: Sequence[float]) -> list[int]:
    """Enteros que suman exactamente 100 (método del resto mayor).

    Desempata por posición para que la misma semilla dé siempre el mismo
    resultado, sin depender de cómo se ordenen restos iguales.
    """
    brutos = [p * 100 for p in proporciones]
    enteros = [math.floor(b) for b in brutos]
    faltan = 100 - sum(enteros)
    orden = sorted(range(len(brutos)), key=lambda i: (-(brutos[i] - enteros[i]), i))
    for i in orden[:faltan]:
        enteros[i] += 1
    return enteros


def fase_c(n: int, semilla: int) -> list[Perfil]:
    """Mezclas aleatorias Dirichlet(1, 1, 1) sobre A, R, K.

    Dirichlet con concentración 1 es uniforme sobre el símplex: cualquier
    reparto es igual de probable. Se muestrea con gammas de la librería estándar
    para no depender de numpy, y con un `Random` propio para que la semilla
    reproduzca la batería sin importar qué más haya consumido el azar global.
    """
    rng = random.Random(semilla)
    perfiles = []
    for i in range(n):
        muestras = [rng.gammavariate(1.0, 1.0) for _ in CANALES_PRUEBA]
        total = sum(muestras)
        enteros = redondear_a_100([m / total for m in muestras])
        dist = dict(zip(CANALES_PRUEBA, enteros, strict=True))
        perfiles.append(_perfil("C", dist, prefijo=f"C{i + 1:02d}_"))
    return perfiles


def construir_bateria(fases: str, n_aleatorias: int, semilla: int) -> list[Perfil]:
    perfiles: list[Perfil] = []
    if "A" in fases:
        perfiles += fase_a()
    if "B" in fases:
        perfiles += fase_b()
    if "C" in fases:
        perfiles += fase_c(n_aleatorias, semilla)
    return perfiles


# --- Utilidades de texto ------------------------------------------------------

_TOKEN = re.compile(r"[a-z0-9]+")
_NUMERO = re.compile(r"\d+(?:[.,\-]\d+)*")
_SEGUNDA_PERSONA = re.compile(
    r"\b(?:tu|tus|te|ti|contigo|imagina|piensa|fijate|puedes|sabes|tienes|"
    r"recuerdas|quieres|necesitas|has)\b"
)
# Palabras largas sin contenido temático; las cortas ya se descartan por largo.
_FUNCIONALES = frozenset(
    {
        "cuando", "porque", "tambien", "entre", "sobre", "donde", "desde", "hasta",
        "durante", "contra", "mientras", "aunque", "siempre", "puede", "pueden",
        "tiene", "tienen", "estos", "estas", "otros", "otras", "todos", "todas",
        "ellos", "nosotros", "cual", "cuales", "segun", "mismo", "misma", "solo",
        "decir", "parte", "forma", "manera", "ejemplo", "puedes", "tienes",
    }
)


def _normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def raices(texto: str) -> set[str]:
    """Raíces de 6 letras de las palabras de contenido (≥5 letras).

    Un stemmer de pobre: «determina» y «determinan» comparten raíz, que es lo
    que hace falta para comparar la cápsula con los fragmentos sin exigir que el
    modelo copie las palabras tal cual.
    """
    return {
        t[:6]
        for t in _TOKEN.findall(_normalizar(texto))
        if len(t) >= 5 and t not in _FUNCIONALES and not t.isdigit()
    }


def cobertura(texto: str, vocabulario: set[str]) -> float | None:
    propias = raices(texto)
    if not propias:
        return None
    return len(propias & vocabulario) / len(propias)


def numeros_ajenos(texto: str, texto_fragmentos: str) -> list[str]:
    """Cifras de 2+ dígitos que la cápsula afirma y los fragmentos no contienen.

    Los de un dígito se ignoran: son numeración de pasos o «1FN», y el modelo
    los produce legítimamente al estructurar.
    """
    return sorted(
        {
            n
            for n in _NUMERO.findall(texto)
            if len(re.sub(r"\D", "", n)) >= 2 and n not in texto_fragmentos
        }
    )


def _texto_bloque(bloque: BloqueContenido) -> str:
    partes = [bloque.encabezado or ""]
    if isinstance(bloque.cuerpo, str):
        partes.append(bloque.cuerpo)
    else:
        for elemento in bloque.cuerpo:
            partes.extend([elemento] if isinstance(elemento, str) else elemento)
    return " ".join(partes)


def _texto_completo(capsula: Microcapsula) -> str:
    """`texto_plano()` más las tarjetas y preguntas, que ese método no incluye."""
    partes = [capsula.texto_plano()]
    for t in capsula.actividad.tarjetas:
        partes += [t.anverso, t.reverso]
    for p in capsula.actividad.preguntas:
        partes += [p.enunciado, *p.alternativas, p.explicacion]
    return "\n".join(partes)


def _items_quiz(capsula: Microcapsula) -> list[tuple[str, str]]:
    """(enunciado, alternativa correcta) de todas las preguntas cerradas."""
    act = capsula.actividad
    items = [(p.enunciado, p.alternativas[p.indice_correcta]) for p in act.preguntas]
    if act.tipo == "quiz_mc" and act.indice_correcta is not None:
        items.append((act.pregunta, act.alternativas[act.indice_correcta]))
    return items


# --- Cliente LLM instrumentado ------------------------------------------------


def _leer_uso(raw: object) -> dict[str, int | None]:
    uso = raw.get("usage") if isinstance(raw, dict) else getattr(raw, "usage", None)
    if uso is None:
        return {}

    def campo(nombre: str) -> int | None:
        return uso.get(nombre) if isinstance(uso, dict) else getattr(uso, nombre, None)

    return {
        "tokens_entrada": campo("prompt_tokens"),
        "tokens_salida": campo("completion_tokens"),
        "tokens_cache": campo("prompt_cache_hit_tokens"),
    }


class ClienteMedido:
    """Envuelve un `ClienteLLM` y registra latencia, tokens y respuesta cruda.

    `ClienteOpenAILike.responder` devuelve solo el texto, así que para leer el
    `usage` se repite aquí su llamada a `_llm.chat` en vez de modificar el
    cliente de producción (la batería no toca lógica de negocio). Con un
    cliente falso, sin `_llm`, se delega en `responder` y no hay tokens.
    """

    def __init__(self, base: object) -> None:
        self._base = base
        self.modelo = base.modelo
        self.llamadas: list[dict[str, object]] = []

    def responder(self, mensajes: Sequence[Mensaje]) -> str:
        registro: dict[str, object] = {}
        inicio = time.perf_counter()
        try:
            llm = getattr(self._base, "_llm", None)
            if llm is None:
                texto = self._base.responder(mensajes)
            else:
                from llama_index.core.base.llms.types import ChatMessage

                respuesta = llm.chat(
                    [ChatMessage(role=m.rol, content=m.contenido) for m in mensajes]
                )
                texto = respuesta.message.content or ""
                registro.update(_leer_uso(respuesta.raw))
            registro["respuesta"] = texto
            return texto
        finally:
            registro["segundos"] = round(time.perf_counter() - inicio, 2)
            self.llamadas.append(registro)

    def totales(self) -> dict[str, object]:
        def suma(clave: str) -> int | None:
            valores = [ll.get(clave) for ll in self.llamadas]
            return None if any(v is None for v in valores) else sum(valores)

        return {
            "llamadas": len(self.llamadas),
            "segundos_por_llamada": [ll["segundos"] for ll in self.llamadas],
            "tokens_entrada": suma("tokens_entrada"),
            "tokens_salida": suma("tokens_salida"),
            "tokens_cache": suma("tokens_cache"),
        }


# --- Audio --------------------------------------------------------------------


def inspeccionar_audio(ruta: Path) -> dict[str, object]:
    """Formato y duración, y si el archivo se decodifica completo.

    Con ffprobe/ffmpeg si están en el PATH (decodificar todo el archivo detecta
    un WAV truncado que la cabecera sola no delata); si no, con `wave`.
    """
    if shutil.which("ffprobe") and shutil.which("ffmpeg"):
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-of", "json",
                "-show_entries",
                "format=format_name,duration:stream=codec_name,sample_rate,channels",
                str(ruta),
            ],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if proc.returncode != 0:
            return {"herramienta": "ffprobe", "decodificable": False,
                    "error": proc.stderr.strip()[:200]}
        datos = json.loads(proc.stdout or "{}")
        formato = datos.get("format", {})
        flujo = (datos.get("streams") or [{}])[0]
        decod = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(ruta), "-f", "null", "-"],
            capture_output=True, text=True, timeout=120, check=False,
        )
        return {
            "herramienta": "ffprobe+ffmpeg",
            "decodificable": decod.returncode == 0 and not decod.stderr.strip(),
            "formato": formato.get("format_name"),
            "codec": flujo.get("codec_name"),
            "sample_rate": int(flujo.get("sample_rate") or 0),
            "canales": flujo.get("channels"),
            "duracion": round(float(formato.get("duration") or 0), 2),
        }
    try:
        with wave.open(str(ruta), "rb") as w:
            frames = w.getnframes()
            w.readframes(frames)
            return {
                "herramienta": "wave",
                "decodificable": True,
                "formato": "wav",
                "codec": f"pcm_{w.getsampwidth() * 8}",
                "sample_rate": w.getframerate(),
                "canales": w.getnchannels(),
                "duracion": round(frames / w.getframerate(), 2),
            }
    except (wave.Error, EOFError, OSError) as exc:
        return {"herramienta": "wave", "decodificable": False, "error": str(exc)[:200]}


def _producir_audio(
    capsula: Microcapsula,
    config: ConfiguracionGenerada,
    sintetizar: Callable[[str, Path], object] | None,
    dir_perfil: Path,
) -> dict[str, object]:
    guion = f"{capsula.activacion} {capsula.concepto_central}".strip()
    datos: dict[str, object] = {
        "guion": guion,
        "palabras_guion": contar_palabras(guion),
        # Lo que narraría POST /api/capsulas (capsules.py → GeneradorMultimedia):
        # los primeros 250 caracteres del JSON serializado. No se sintetiza.
        "guion_ruta_api": json.dumps(capsula.model_dump(), ensure_ascii=False)[:250],
    }
    if not config.audio_activo:
        datos["estado"] = "no_aplica"
        return datos
    if sintetizar is None:
        datos["estado"] = "omitido"
        return datos

    ruta = dir_perfil / "audio.wav"
    inicio = time.perf_counter()
    try:
        sintetizar(guion, ruta)
        datos["estado"] = "generado"
    except Exception as exc:  # el TTS puede fallar de muchas formas; se registra
        datos["estado"] = "error"
        datos["error"] = f"{type(exc).__name__}: {exc}"[:300]
    datos["segundos"] = round(time.perf_counter() - inicio, 2)
    datos["ruta"] = str(ruta)
    if ruta.exists():
        datos["bytes"] = ruta.stat().st_size
        datos["inspeccion"] = inspeccionar_audio(ruta)
    return datos


# --- Evaluación ---------------------------------------------------------------


def _criterio(estado: str, detalle: str) -> dict[str, str]:
    return {"estado": estado, "detalle": detalle}


def marcadores(capsula: Microcapsula, *, audio_generado: bool) -> dict[str, dict[str, bool]]:
    """Señales observables de cada canal en la cápsula (heurística de proporción).

    Cada marcador corresponde a una directiva de `vark/rules.py` que solo pide
    ese canal, así que su presencia es evidencia de que el canal pesó en la
    salida. V se mide aunque esté al 0% para detectar que no aparezca.
    """
    bloques = capsula.bloques_legibles()
    tipos = {b.tipo for b in bloques}
    prosa = " ".join([capsula.concepto_central, *(_texto_bloque(b) for b in bloques)])
    voz = _SEGUNDA_PERSONA.findall(_normalizar(f"{capsula.activacion} {prosa}"))
    return {
        "R": {
            "glosario": "glosario" in tipos,
            "encabezados_completos": all((b.encabezado or "").strip() for b in bloques),
            "extension_larga": capsula.palabras_contenido() >= EXTENSION_LARGA,
        },
        "A": {
            "analogia": "analogia" in tipos,
            "segunda_persona": len(voz) >= SEGUNDA_PERSONA_MINIMA,
            "pregunta_en_prosa": "?" in prosa,
            "audio": audio_generado,
        },
        "K": {
            "ejemplo_resuelto": "ejemplo_resuelto" in tipos,
            "lista_pasos": "lista_pasos" in tipos,
            "actividad_practica": capsula.actividad.tipo in ACTIVIDADES_PRACTICAS,
        },
        "V": {"tabla": "tabla" in tipos, "esquema": "esquema" in tipos},
    }


def puntajes(marcas: dict[str, dict[str, bool]]) -> dict[str, float]:
    return {c: round(sum(m.values()) / len(m), 2) for c, m in marcas.items()}


def evaluar_proporcion(
    perfil: Perfil, punt: dict[str, float], marcas: dict[str, dict[str, bool]]
) -> tuple[dict[str, str], list[str]]:
    """Cada canal ≥40% tiene que puntuar más que cada canal bajo 40%.

    Todos los canales que alcanzan el umbral reciben sus directivas completas
    (`vark/rules.py`), así que con dos sobre 40% —50/50, o 41/46— ambos son
    dominantes y se exige que superen al tercero, no que uno le gane al otro.
    Sin canal ≥40% el motor no pide directivas propias de ningún canal (o pide
    las de equilibrio multimodal), así que no hay proporción que exigir.
    """
    pcts = {c: perfil.pcts[c] for c in CANALES_PRUEBA}
    dominantes = [c for c in CANALES_PRUEBA if pcts[c] >= UMBRAL_ALTO]
    resto = [c for c in CANALES_PRUEBA if c not in dominantes]
    detalle = " · ".join(f"{c} {punt[c]:.2f}" for c in CANALES_PRUEBA)

    advertencias = [
        f"canal {c} al 0% con marcadores: {', '.join(k for k, v in marcas[c].items() if v)}"
        for c in ("V", *CANALES_PRUEBA)
        if perfil.pcts[c] == 0 and punt[c] > 0
    ]

    if not dominantes or not resto:
        return _criterio("n/a", f"{detalle} (sin canal dominante ≥40%)"), advertencias

    tope = max(punt[c] for c in resto)
    ok = all(punt[d] > tope for d in dominantes)
    return _criterio("pasa" if ok else "falla", detalle), advertencias


def evaluar(
    perfil: Perfil,
    capsula: Microcapsula,
    metricas: dict[str, object],
    fragmentos: Sequence[FragmentoRecuperado],
    config: ConfiguracionGenerada,
    palabras_objetivo: int,
    audio: dict[str, object],
) -> tuple[dict[str, dict[str, str]], list[str], dict[str, object]]:
    """Criterios de una cápsula válida. Devuelve criterios, advertencias y extras."""
    ajustes = get_settings()
    criterios: dict[str, dict[str, str]] = {}
    advertencias: list[str] = []
    texto_frag = "\n".join(f.texto for f in fragmentos)
    vocabulario = raices(texto_frag)
    texto = _texto_completo(capsula)
    bloques = capsula.bloques_legibles()
    tipos = [b.tipo for b in bloques]

    # Trazabilidad: se recalcula contra los fragmentos inyectados en vez de
    # confiar solo en la métrica del validador.
    inyectados = {f.id_fragmento for f in fragmentos}
    citados = [f.id_fragmento for f in capsula.fuentes]
    fuera = [i for i in citados if i not in inyectados]
    sin_pagina = [f.id_fragmento for f in capsula.fuentes if f.pagina is None]
    ok = bool(citados) and not fuera and not sin_pagina and not metricas.get("citas_inventadas")
    paginas = ", ".join(f"{f.id_fragmento}→p.{f.pagina}" for f in capsula.fuentes)
    criterios["trazabilidad"] = _criterio(
        "pasa" if ok else "falla",
        f"{len(set(citados))}/{len(inyectados)} citados ({paginas})"
        + (f"; fuera del prompt: {fuera}" if fuera else "")
        + (f"; sin página: {sin_pagina}" if sin_pagina else ""),
    )

    # Texto (R): extensión, idioma, cifras ajenas, cobertura léxica.
    palabras = capsula.palabras_contenido()
    en_rango = ajustes.capsula_min_palabras <= palabras <= ajustes.capsula_max_palabras
    idioma_ok = bool(metricas.get("idioma_ok", True))
    ajenos = numeros_ajenos(texto, texto_frag)
    cob = cobertura(texto, vocabulario)
    fallos_texto = []
    if not en_rango:
        fallos_texto.append("fuera de rango")
    if not idioma_ok:
        fallos_texto.append("idioma")
    if ajenos:
        fallos_texto.append(f"cifras ajenas {ajenos}")
    marcas_r = []
    if perfil.r >= UMBRAL_ALTO:
        if "glosario" not in tipos:
            fallos_texto.append("falta glosario (p_R≥40)")
        if not all((b.encabezado or "").strip() for b in bloques):
            fallos_texto.append("bloques sin encabezado (p_R≥40)")
        marcas_r.append("glosario+encabezados exigidos")
    if cob is not None and cob < COBERTURA_MINIMA:
        advertencias.append(f"cobertura léxica baja ({cob:.0%}): revisar contenido inventado")
    criterios["texto"] = _criterio(
        "falla" if fallos_texto else "pasa",
        f"{palabras} pal. (objetivo {palabras_objetivo}); cobertura "
        f"{'—' if cob is None else f'{cob:.0%}'}"
        + (f"; {'; '.join(marcas_r)}" if marcas_r else "")
        + (f"; FALLA: {', '.join(fallos_texto)}" if fallos_texto else ""),
    )

    # Audio (A).
    criterios["audio"] = _evaluar_audio(audio, vocabulario)

    # Ejercicios (K).
    criterios["ejercicios"], adv_k = _evaluar_ejercicios(perfil, capsula, config, vocabulario)
    advertencias += adv_k

    # Proporcionalidad.
    marcas = marcadores(capsula, audio_generado=audio.get("estado") == "generado")
    punt = puntajes(marcas)
    criterios["proporcion"], adv_p = evaluar_proporcion(perfil, punt, marcas)
    advertencias += adv_p

    extras = {
        "marcadores": marcas,
        "puntajes": punt,
        "cobertura_lexica": None if cob is None else round(cob, 3),
        "guion_ruta_api_es_json": str(audio.get("guion_ruta_api", "")).startswith("{"),
        "tipos_bloque": tipos,
        "tipo_actividad": capsula.actividad.tipo,
    }
    return criterios, advertencias, extras


def _evaluar_audio(audio: dict[str, object], vocabulario: set[str]) -> dict[str, str]:
    estado = audio.get("estado")
    if estado == "no_aplica":
        return _criterio("n/a", "p_A<25: sin audio, como corresponde")
    if estado == "omitido":
        return _criterio("n/a", "omitido (--sin-audio)")
    if estado == "error":
        return _criterio("falla", f"TTS: {audio.get('error')}")

    insp = audio.get("inspeccion") or {}
    palabras = int(audio.get("palabras_guion") or 0)
    dur = float(insp.get("duracion") or 0)
    fallos = []
    if not audio.get("bytes"):
        fallos.append("archivo vacío o inexistente")
    if not insp.get("decodificable"):
        fallos.append(f"no decodificable ({insp.get('error', '?')})")
    if dur <= 0:
        fallos.append("duración 0")
    elif palabras:
        minimo = palabras / PALABRAS_POR_SEGUNDO_MAX
        maximo = palabras / PALABRAS_POR_SEGUNDO_MIN
        if not minimo <= dur <= maximo:
            fallos.append(f"duración {dur:.1f}s fuera de [{minimo:.0f}, {maximo:.0f}]s")
    guion = str(audio.get("guion") or "")
    if not guion.strip() or guion.lstrip().startswith("{"):
        fallos.append("guion vacío o JSON")
    cob = cobertura(guion, vocabulario)

    detalle = (
        f"{insp.get('codec')} {insp.get('sample_rate')} Hz, {dur:.1f}s, "
        f"{palabras} pal. ({(palabras / dur) if dur else 0:.1f} pal/s), "
        f"{int(audio.get('bytes') or 0) // 1024} KB; cobertura guion "
        f"{'—' if cob is None else f'{cob:.0%}'}"
    )
    if fallos:
        detalle += f"; FALLA: {', '.join(fallos)}"
    return _criterio("falla" if fallos else "pasa", detalle)


def _evaluar_ejercicios(
    perfil: Perfil, capsula: Microcapsula, config: ConfiguracionGenerada, vocabulario: set[str]
) -> tuple[dict[str, str], list[str]]:
    act = capsula.actividad
    tipos = [b.tipo for b in capsula.bloques_legibles()]
    contados = sum(t in ("ejemplo_resuelto", "lista_pasos") for t in tipos) + (
        act.tipo in ACTIVIDADES_PRACTICAS
    )
    esperados = config.componentes_practicos

    items = _items_quiz(capsula)
    evaluables = [cobertura(correcta, vocabulario) for _, correcta in items]
    evaluables = [c for c in evaluables if c is not None]
    resolubles = sum(c >= COBERTURA_MINIMA for c in evaluables)
    detalle = (
        f"{act.tipo}: {len(act.tarjetas)} tarjetas, {len(act.preguntas)} preguntas; "
        f"prácticos {contados}/{esperados}; resolubles {resolubles}/{len(evaluables)}"
    )
    advertencias = []
    if evaluables and resolubles < len(evaluables) and perfil.k < UMBRAL_ALTO:
        advertencias.append(
            f"quiz con respuestas sin respaldo léxico en los fragmentos "
            f"({resolubles}/{len(evaluables)})"
        )

    if perfil.k == 0:
        return _criterio("n/a", detalle), advertencias

    fallos = []
    if contados < esperados:
        fallos.append(f"componentes prácticos {contados} < {esperados}")
    if perfil.k >= UMBRAL_ALTO:
        if act.tipo != "flashcards_y_quiz":
            fallos.append(f"actividad '{act.tipo}' en vez de flashcards_y_quiz")
        else:
            if not 3 <= len(act.tarjetas) <= 5 or not 3 <= len(act.preguntas) <= 5:
                fallos.append("cantidad de tarjetas/preguntas fuera de 3–5")
            if not all(t.reverso.strip() for t in act.tarjetas):
                fallos.append("tarjeta sin reverso")
            if not all(p.explicacion.strip() for p in act.preguntas):
                fallos.append("pregunta sin explicación")
        for requerido in ("ejemplo_resuelto", "lista_pasos"):
            if requerido not in tipos:
                fallos.append(f"falta bloque {requerido}")
        if evaluables and resolubles / len(evaluables) < RESOLUBLES_MINIMO:
            fallos.append("respuestas no respaldadas por los fragmentos")
    if fallos:
        detalle += f"; FALLA: {', '.join(fallos)}"
    return _criterio("falla" if fallos else "pasa", detalle), advertencias


# --- Ejecución de un perfil ---------------------------------------------------


def _resumen_config(config: ConfiguracionGenerada, palabras_objetivo: int) -> dict[str, object]:
    return {
        "pesos": {k: float(v) for k, v in config.pesos.como_dict().items()},
        "recursos_visuales": config.recursos_visuales,
        "componentes_practicos": config.componentes_practicos,
        "palabras_texto": config.palabras_texto,
        "palabras_objetivo_prompt": palabras_objetivo,
        "audio_activo": config.audio_activo,
        "tono": config.tono_narrativo,
        "canal_primario": config.jerarquia.canal_primario,
        "etiqueta": config.jerarquia.etiqueta,
        "directivas": list(config.directivas),
    }


def _guardar_json(ruta: Path, datos: object) -> None:
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=str), "utf-8")


def ejecutar_perfil(
    perfil: Perfil,
    *,
    objetivo: ObjetivoAprendizaje,
    obtener_fragmentos: Callable[[ConfiguracionGenerada], Sequence[FragmentoRecuperado]],
    cliente: object,
    sintetizar: Callable[[str, Path], object] | None,
    dir_corrida: Path,
    modelo: str,
) -> dict[str, object]:
    """Corre el pipeline completo para un perfil y devuelve su resultado evaluado.

    Nunca levanta: cualquier fallo queda registrado en el resultado, para que
    un perfil roto no tumbe la batería y se pueda tabular igual que un éxito.
    """
    config = aplicar_reglas(perfil.vark())
    dir_perfil = dir_corrida / perfil.slug
    dir_perfil.mkdir(parents=True, exist_ok=True)
    fragmentos = list(obtener_fragmentos(config))
    prompt = orchestrator.construir(
        objetivo=objetivo, fragmentos=fragmentos, config=config, modelo=modelo
    )
    (dir_perfil / "prompt.txt").write_text(
        f"### SISTEMA\n{prompt.sistema}\n\n### USUARIO\n{prompt.usuario}\n", "utf-8"
    )

    resultado: dict[str, object] = {
        "fase": perfil.fase,
        "perfil": perfil.nombre,
        "slug": perfil.slug,
        "pcts": perfil.pcts,
        "config": _resumen_config(config, prompt.palabras_objetivo),
        "fragmentos_inyectados": [f.id_fragmento for f in fragmentos],
        "criterios": {},
        "advertencias": [],
        "artefactos": {
            "directorio": str(dir_perfil),
            "resultado": str(dir_perfil / "resultado.json"),
            "prompt": str(dir_perfil / "prompt.txt"),
        },
    }
    medido = ClienteMedido(cliente)

    try:
        generado = generar(prompt, cliente=medido)
    except ErrorGeneracion as exc:
        resultado["criterios"]["contrato"] = _criterio(
            "falla", f"agotó {len(exc.errores_por_intento)} intentos: {exc.errores_por_intento[-1]}"
        )
        resultado["errores_por_intento"] = exc.errores_por_intento
        resultado["veredicto"] = "falla"
    except Exception as exc:  # red, timeout, credencial: fallo operativo, no de contrato
        resultado["error"] = {
            "tipo": type(exc).__name__,
            "mensaje": str(exc)[:300],
            "timeout": "timeout" in type(exc).__name__.lower(),
        }
        resultado["criterios"]["contrato"] = _criterio("falla", f"error {type(exc).__name__}")
        resultado["veredicto"] = "error"
    else:
        capsula = generado.capsula
        _guardar_json(dir_perfil / "capsula.json", capsula.model_dump())
        resultado["artefactos"]["capsula"] = str(dir_perfil / "capsula.json")
        resultado["intentos"] = generado.intentos
        resultado["errores_por_intento"] = generado.errores_por_intento
        resultado["metricas_validador"] = generado.metricas
        resultado["criterios"]["contrato"] = _criterio(
            "pasa", f"intento {generado.intentos} ({generado.intentos - 1} reparaciones)"
        )
        resultado["segundos_llm"] = round(generado.segundos, 2)

        audio = _producir_audio(capsula, config, sintetizar, dir_perfil)
        resultado["audio"] = {k: v for k, v in audio.items() if k != "guion"}
        resultado["audio"]["guion"] = audio["guion"]
        if audio.get("estado") == "generado":
            resultado["artefactos"]["audio"] = audio["ruta"]

        criterios, advertencias, extras = evaluar(
            perfil, capsula, generado.metricas, fragmentos, config,
            prompt.palabras_objetivo, audio,
        )
        resultado["criterios"].update(criterios)
        resultado["advertencias"] = advertencias
        resultado.update(extras)
        estados = [c["estado"] for c in resultado["criterios"].values()]
        resultado["veredicto"] = "falla" if "falla" in estados else "pasa"

    resultado["operativo"] = medido.totales()
    _guardar_json(dir_perfil / "respuestas_crudas.json", medido.llamadas)
    resultado["artefactos"]["respuestas_crudas"] = str(dir_perfil / "respuestas_crudas.json")
    _guardar_json(dir_perfil / "resultado.json", resultado)
    return resultado


# --- Plan previo (dry-run) ----------------------------------------------------


def planificar(
    perfiles: Sequence[Perfil],
    prompts: dict[str, orchestrator.PromptMaestro],
    *,
    reintentos: int,
    precio_entrada: float,
    precio_salida: float,
    con_audio: bool,
) -> str:
    """Tabla del plan y estimación de llamadas, tokens, costo y tiempo de audio."""
    lineas = [
        f"{'perfil':<22} {'prim':>4} {'pal':>4} {'prác':>4} {'audio':>5} {'tok_in':>6}  directivas",
    ]
    tok_min = tok_max = 0.0
    salida_min = salida_max = 0
    audios = 0
    for p in perfiles:
        config = aplicar_reglas(p.vark())
        prompt = prompts[p.slug]
        tin = (len(prompt.sistema) + len(prompt.usuario)) / CARACTERES_POR_TOKEN
        audios += config.audio_activo
        lineas.append(
            f"{p.slug:<22} {config.jerarquia.canal_primario:>4} {prompt.palabras_objetivo:>4} "
            f"{config.componentes_practicos:>4} {'sí' if config.audio_activo else 'no':>5} "
            f"{tin:>6.0f}  {','.join(config.directivas)}"
        )
        tok_min += tin
        salida_min += TOKENS_SALIDA_ESTIMADOS
        # En cada reintento el historial crece con la respuesta rechazada y el
        # mensaje de reparación, así que la entrada del intento n es mayor.
        for n in range(reintentos + 1):
            tok_max += tin + n * (TOKENS_SALIDA_ESTIMADOS + TOKENS_REPARACION)
            salida_max += TOKENS_SALIDA_ESTIMADOS

    def costo(entrada: float, salida: float) -> float:
        return entrada / 1e6 * precio_entrada + salida / 1e6 * precio_salida

    n = len(perfiles)
    lineas += [
        "",
        f"Perfiles: {n}",
        f"Llamadas al LLM: mínimo {n} (todas válidas al primer intento), "
        f"máximo {n * (reintentos + 1)} (todas agotan {reintentos} reparaciones)",
        f"Tokens estimados: entrada {tok_min:,.0f}–{tok_max:,.0f}, "
        f"salida {salida_min:,}–{salida_max:,}",
        f"Costo estimado: US$ {costo(tok_min, salida_min):.3f}–{costo(tok_max, salida_max):.3f} "
        f"(tarifa supuesta {precio_entrada}/{precio_salida} USD por 1M tokens; verificarla)",
        f"Audios XTTS (local, sin costo): {audios if con_audio else 0}"
        + (
            f", ~{audios * SEGUNDOS_AUDIO_ESTIMADOS[0] / 60:.0f}–"
            f"{audios * SEGUNDOS_AUDIO_ESTIMADOS[1] / 60:.0f} min en CPU"
            if con_audio and audios
            else ""
        ),
    ]
    return "\n".join(lineas)


# --- Informe ------------------------------------------------------------------

_ICONO = {"pasa": "✅", "falla": "❌", "n/a": "—", "error": "💥"}


def _rel(ruta: str, doc: Path) -> str:
    try:
        return Path(os.path.relpath(Path(ruta).resolve(), doc.resolve().parent)).as_posix()
    except ValueError:  # otra unidad en Windows
        return Path(ruta).as_posix()


def _celda(resultado: dict, criterio: str) -> str:
    c = resultado.get("criterios", {}).get(criterio)
    if not c:
        return "—"
    icono = _ICONO[c["estado"]]
    if criterio == "contrato" and c["estado"] == "pasa":
        return f"{icono} {resultado.get('intentos')}"
    if criterio == "proporcion":
        return f"{icono} {c['detalle'].split(' (')[0]}"
    return icono


def _p95(valores: list[float]) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, math.ceil(0.95 * len(ordenados)) - 1)]


def renderizar_resultados(resumen: dict, doc: Path) -> str:
    res = resumen["resultados"]
    n = len(res)
    pasan = sum(r["veredicto"] == "pasa" for r in res)
    validas = [r for r in res if "intentos" in r]
    primer = sum(r["intentos"] == 1 for r in validas)
    reparaciones = sum(r["intentos"] - 1 for r in validas)
    lat = [r["segundos_llm"] for r in validas]
    tin = [r["operativo"]["tokens_entrada"] for r in res if r["operativo"]["tokens_entrada"]]
    tout = [r["operativo"]["tokens_salida"] for r in res if r["operativo"]["tokens_salida"]]
    audios = [r for r in res if r.get("audio", {}).get("estado") in ("generado", "error")]
    audios_ok = sum(r["criterios"].get("audio", {}).get("estado") == "pasa" for r in audios)
    lat_audio = [r["audio"]["segundos"] for r in audios if "segundos" in r["audio"]]
    precios = resumen.get("precios", {})
    costo = (
        sum(tin) / 1e6 * precios.get("entrada", PRECIO_ENTRADA_USD_M)
        + sum(tout) / 1e6 * precios.get("salida", PRECIO_SALIDA_USD_M)
    )
    obj = resumen["objetivo"]

    lineas = [
        f"### Corrida `{resumen['corrida']}`",
        "",
        f"- **Fecha:** {resumen['fecha']}",
        f"- **Objetivo fijo:** {obj['codigo']} — {obj['tema']} (id {obj['id']}, "
        f"{obj['fragmentos']} fragmentos validados)",
        f"- **Modelo:** `{resumen['modelo']}` · **semilla Fase C:** `{resumen['semilla']}` "
        f"({resumen['n_aleatorias']} mezclas) · **fases:** {resumen['fases']}",
        f"- **Comando:** `{resumen['comando']}`",
        f"- **Artefactos:** `{Path(resumen['directorio']).as_posix()}/` (ignorado por git; "
        "los enlaces solo funcionan en la máquina que corrió la batería)",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Perfiles que pasan todos los criterios | {pasan}/{n} |",
        f"| Cápsulas válidas | {len(validas)}/{n} ({primer} al primer intento) |",
        f"| Reparaciones totales | {reparaciones} |",
        f"| Citas inventadas (cápsulas válidas) | "
        f"{sum(int(r['metricas_validador'].get('citas_inventadas', 0)) for r in validas)} |",
    ]
    if lat:
        lineas.append(
            f"| Latencia LLM (media / p95 / máx) | {sum(lat) / len(lat):.1f} / "
            f"{_p95(lat):.1f} / {max(lat):.1f} s |"
        )
    if tin:
        lineas.append(
            f"| Tokens entrada / salida (total) | {sum(tin):,} / {sum(tout):,} "
            f"(≈ US$ {costo:.3f}) |"
        )
    if audios:
        lineas.append(f"| Audios válidos | {audios_ok}/{len(audios)} |")
    if lat_audio:
        lineas.append(
            f"| Latencia XTTS (media / máx) | {sum(lat_audio) / len(lat_audio):.0f} / "
            f"{max(lat_audio):.0f} s |"
        )
    errores = [r for r in res if r["veredicto"] == "error"]
    if errores:
        lineas.append(
            f"| Errores operativos | {len(errores)} "
            f"({sum(r['error']['timeout'] for r in errores)} timeouts) |"
        )

    titulos = {
        "A": "Fase A — perfiles puros",
        "B": "Fase B — mezclas controladas",
        "C": "Fase C — mezclas aleatorias",
    }
    for fase, titulo in titulos.items():
        filas = [r for r in res if r["fase"] == fase]
        if not filas:
            continue
        lineas += [
            "",
            f"#### {titulo}",
            "",
            "| Perfil (A/R/K) | Contrato | Traz. | Texto | Audio | K | Proporción "
            "(A · R · K) | Veredicto | LLM s | Tokens in/out | Audio s | Artefactos |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in filas:
            op = r["operativo"]
            arte = r["artefactos"]
            enlaces = [f"[resultado]({_rel(arte['resultado'], doc)})"]
            if "capsula" in arte:
                enlaces.append(f"[cápsula]({_rel(arte['capsula'], doc)})")
            if "audio" in arte:
                enlaces.append(f"[wav]({_rel(arte['audio'], doc)})")
            p = r["pcts"]
            lineas.append(
                f"| {r['perfil']} ({p['A']}/{p['R']}/{p['K']}) | {_celda(r, 'contrato')} | "
                f"{_celda(r, 'trazabilidad')} | {_celda(r, 'texto')} | {_celda(r, 'audio')} | "
                f"{_celda(r, 'ejercicios')} | {_celda(r, 'proporcion')} | "
                f"{_ICONO[r['veredicto']]} | {r.get('segundos_llm', '—')} | "
                f"{op['tokens_entrada'] or '—'}/{op['tokens_salida'] or '—'} | "
                f"{r.get('audio', {}).get('segundos', '—')} | {' · '.join(enlaces)} |"
            )

    lineas += ["", "#### Detalle de fallos y advertencias", ""]
    hay = False
    for r in res:
        malos = {k: c for k, c in r.get("criterios", {}).items() if c["estado"] == "falla"}
        if not malos and not r.get("advertencias") and "error" not in r:
            continue
        hay = True
        partes = [f"❌ **{k}**: {c['detalle']}" for k, c in malos.items()]
        if "error" in r:
            partes.append(f"💥 {r['error']['tipo']}: {r['error']['mensaje']}")
        partes += [f"⚠️ {a}" for a in r.get("advertencias", [])]
        lineas.append(f"- `{r['slug']}` — " + "; ".join(partes))
    if not hay:
        lineas.append("Sin fallos ni advertencias.")

    lineas += ["", "#### Detalle por criterio (todas las ejecuciones)", "", "<details>", ""]
    for r in res:
        lineas.append(f"**`{r['slug']}`**")
        lineas.append("")
        for k, c in r.get("criterios", {}).items():
            lineas.append(f"- {_ICONO[c['estado']]} {k}: {c['detalle']}")
        lineas.append("")
    lineas.append("</details>")
    return "\n".join(lineas)


def reevaluar_proporcion(resumen: dict) -> int:
    """Recalcula la proporcionalidad desde los marcadores guardados, sin el LLM.

    Sirve para aplicar una corrección de la heurística a una corrida ya hecha:
    los marcadores son observaciones de la cápsula y no cambian, solo cambia
    cómo se juzgan. Devuelve cuántos veredictos cambiaron.
    """
    cambios = 0
    for r in resumen["resultados"]:
        if "marcadores" not in r:
            continue
        p = r["pcts"]
        perfil = Perfil(r["fase"], r["perfil"], a=p["A"], r=p["R"], k=p["K"], v=p["V"])
        r["criterios"]["proporcion"], adv_p = evaluar_proporcion(
            perfil, r["puntajes"], r["marcadores"]
        )
        r["advertencias"] = [a for a in r["advertencias"] if "al 0%" not in a] + adv_p
        estados = [c["estado"] for c in r["criterios"].values()]
        veredicto = "falla" if "falla" in estados else "pasa"
        cambios += veredicto != r["veredicto"]
        r["veredicto"] = veredicto
    return cambios


def escribir_informe(resumen: dict, doc: Path) -> None:
    """Reemplaza solo el bloque generado del documento; el análisis escrito queda."""
    bloque = f"{MARCA_INICIO}\n\n{renderizar_resultados(resumen, doc)}\n\n{MARCA_FIN}"
    if doc.exists():
        actual = doc.read_text("utf-8")
        if MARCA_INICIO not in actual or MARCA_FIN not in actual:
            raise SystemExit(f"{doc} no tiene las marcas {MARCA_INICIO} / {MARCA_FIN}")
        antes, resto = actual.split(MARCA_INICIO, 1)
        _, despues = resto.split(MARCA_FIN, 1)
        doc.write_text(antes + bloque + despues, "utf-8")
    else:
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(f"# Pruebas del motor adaptativo VARK\n\n{bloque}\n", "utf-8")


# --- CLI ----------------------------------------------------------------------


def _argumentos(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Batería VARK de punta a punta. Sin --live solo muestra el plan, las "
            "llamadas y el costo estimado. El canal Visual (Fase D) está excluido."
        )
    )
    parser.add_argument("--live", action="store_true", help="llama al LLM y al TTS reales")
    parser.add_argument("--max-runs", type=int, default=None, help="corta la batería a N perfiles")
    parser.add_argument("--fases", default="ABC", help="subconjunto de A, B, C (p. ej. 'AB')")
    parser.add_argument("--n-aleatorias", type=int, default=ALEATORIAS_POR_DEFECTO)
    parser.add_argument("--semilla", type=int, default=SEMILLA_POR_DEFECTO)
    parser.add_argument("--objetivo", default=OBJETIVO_POR_DEFECTO, help="codigo_objetivo")
    parser.add_argument("--salida", type=Path, default=SALIDA_POR_DEFECTO)
    parser.add_argument("--doc", type=Path, default=DOC_POR_DEFECTO)
    parser.add_argument("--sin-audio", action="store_true", help="no sintetiza con XTTS")
    parser.add_argument("--precio-entrada", type=float, default=PRECIO_ENTRADA_USD_M)
    parser.add_argument("--precio-salida", type=float, default=PRECIO_SALIDA_USD_M)
    parser.add_argument(
        "--informe", type=Path, default=None,
        help="regenera el informe desde un resumen.json sin ejecutar nada",
    )
    args = parser.parse_args(argv)
    args.fases = args.fases.upper().replace(",", "")
    if not set(args.fases) <= set("ABC"):
        parser.error("--fases solo admite A, B y C (la Fase D, Visual, está excluida)")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _argumentos(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    if Path.cwd().resolve() != RAIZ:
        # `.env`, `tests/referencia.wav` (XTTS) y las rutas relativas del
        # informe se resuelven contra el directorio de trabajo.
        print(f"Ejecuta el script desde la raíz del repo: {RAIZ}", file=sys.stderr)
        return 2

    if args.informe:
        resumen = json.loads(args.informe.read_text("utf-8"))
        cambios = reevaluar_proporcion(resumen)
        _guardar_json(args.informe, resumen)
        escribir_informe(resumen, args.doc)
        print(f"Informe regenerado en {args.doc} ({cambios} veredictos cambiaron)")
        return 0

    perfiles = construir_bateria(args.fases, args.n_aleatorias, args.semilla)
    if args.max_runs is not None:
        perfiles = perfiles[: args.max_runs]

    from sqlalchemy import select

    from studify.db.session import SessionLocal, engine
    from studify.rag.retriever import recuperar

    engine.echo = False  # en APP_ENV=dev el engine imprime cada consulta
    ajustes = get_settings()

    with SessionLocal() as db:
        objetivo = db.scalar(
            select(ObjetivoAprendizaje).where(ObjetivoAprendizaje.codigo_objetivo == args.objetivo)
        )
        if objetivo is None:
            print(f"No existe el objetivo {args.objetivo}", file=sys.stderr)
            return 1

        cache: dict[str, list[FragmentoRecuperado]] = {}

        def obtener_fragmentos(config: ConfiguracionGenerada) -> list[FragmentoRecuperado]:
            canal = config.jerarquia.canal_primario
            if canal not in cache:
                cache[canal] = recuperar(db, id_objetivo=objetivo.id_objetivo, canal_primario=canal)
            return cache[canal]

        if not obtener_fragmentos(aplicar_reglas(perfiles[0].vark())):
            print(f"El objetivo {args.objetivo} no tiene fragmentos validados", file=sys.stderr)
            return 1

        print(
            f"Objetivo {objetivo.codigo_objetivo} — {objetivo.tema} "
            f"(id {objetivo.id_objetivo}) · modelo {ajustes.llm_model} · "
            f"semilla {args.semilla} · fases {args.fases}\n"
        )

        if not args.live:
            prompts = {}
            for p in perfiles:
                config = aplicar_reglas(p.vark())
                prompts[p.slug] = orchestrator.construir(
                    objetivo=objetivo, fragmentos=obtener_fragmentos(config),
                    config=config, modelo=ajustes.llm_model,
                )
            print(
                planificar(
                    perfiles, prompts, reintentos=ajustes.llm_max_repair_attempts,
                    precio_entrada=args.precio_entrada, precio_salida=args.precio_salida,
                    con_audio=not args.sin_audio,
                )
            )
            print("\nSin --live no se llamó a nada. Agrega --live (y --max-runs N) para ejecutar.")
            return 0

        from studify.generation.generator import ClienteOpenAILike

        cliente = ClienteOpenAILike()
        sintetizar = None
        if not args.sin_audio:
            from studify.media.audio import generar_audio

            sintetizar = generar_audio

        corrida = f"{datetime.now():%Y%m%d-%H%M%S}_semilla{args.semilla}"
        dir_corrida = args.salida / corrida
        dir_corrida.mkdir(parents=True, exist_ok=True)
        resumen: dict[str, object] = {
            "corrida": corrida,
            "fecha": f"{datetime.now():%Y-%m-%d %H:%M}",
            "directorio": str(dir_corrida),
            "objetivo": {
                "codigo": objetivo.codigo_objetivo,
                "tema": objetivo.tema,
                "id": objetivo.id_objetivo,
                "fragmentos": len(obtener_fragmentos(aplicar_reglas(perfiles[0].vark()))),
            },
            "modelo": ajustes.llm_model,
            "semilla": args.semilla,
            "n_aleatorias": args.n_aleatorias,
            "fases": args.fases,
            "comando": "python scripts/probar_perfiles_vark.py " + " ".join(sys.argv[1:]),
            "precios": {"entrada": args.precio_entrada, "salida": args.precio_salida},
            "resultados": [],
        }

        for i, perfil in enumerate(perfiles, start=1):
            print(f"[{i}/{len(perfiles)}] {perfil.slug} …", flush=True)
            r = ejecutar_perfil(
                perfil, objetivo=objetivo, obtener_fragmentos=obtener_fragmentos,
                cliente=cliente, sintetizar=sintetizar, dir_corrida=dir_corrida,
                modelo=ajustes.llm_model,
            )
            resumen["resultados"].append(r)
            # Se reescribe en cada vuelta: si la batería se corta, lo corrido queda.
            _guardar_json(dir_corrida / "resumen.json", resumen)
            estados = " ".join(
                f"{k}={_ICONO[c['estado']]}" for k, c in r["criterios"].items()
            )
            print(
                f"    {_ICONO[r['veredicto']]} {estados} · LLM {r.get('segundos_llm', '—')}s"
                f" · audio {r.get('audio', {}).get('segundos', '—')}s",
                flush=True,
            )

    escribir_informe(resumen, args.doc)
    print(f"\nResultados: {dir_corrida / 'resumen.json'}\nInforme: {args.doc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
