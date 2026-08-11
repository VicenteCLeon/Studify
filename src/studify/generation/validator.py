"""Validación de la microcápsula y realimentación para el bucle de reparación.

Es la «capa de validación estructural» de la Fase 4 del cap. 18 y la barrera que
separa lo que el modelo dijo de lo que el sistema publica. Implementa las seis
reglas de rechazo de `PLAN_DESARROLLO.md` §3; las tres estructurales viven en
`generation/schemas.py` y acá se ejecutan las tres que necesitan contexto:

    2. `contar_palabras(contenido)` fuera de 150–300 (cap. 11.1).
    5. algún `id_fragmento` citado no está entre los inyectados en el prompt.
    6. el idioma detectado no es español.

**La regla 5 es la que justifica todo el diseño del proyecto.** Es la detección
de citas alucinadas que advierte Hashiyada et al. (cap. 13): un modelo que
inventa una referencia produce material que *parece* institucional y no lo es.
Como la recuperación es determinista y sabemos exactamente qué fragmentos se
inyectaron, la comprobación es exacta y no heurística — que es precisamente lo
que un RAG vectorial no puede afirmar.

Sobre esa misma regla, `documento` y `pagina` se **reescriben** con los valores
de la base en vez de confiar en los que redactó el modelo. Si la cápsula cita el
fragmento 161, la procedencia que se muestra al estudiante la afirma el sistema
consultando `fragmento`/`documento_fuente`, no el LLM. Así la trazabilidad del
cap. 13 es verificable por construcción y no depende de que el modelo copie bien
un número de página.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from pydantic import ValidationError

from studify.config import get_settings
from studify.generation import idioma
from studify.generation.schemas import Microcapsula
from studify.rag.retriever import FragmentoRecuperado

# Cercas de bloque Markdown: los modelos envuelven el JSON en ```json … ``` con
# mucha frecuencia, incluso cuando se les pide JSON crudo.
_CERCAS = re.compile(r"^\s*```(?:json|JSON)?\s*|\s*```\s*$", re.MULTILINE)

# Coma colgante antes de un cierre: `[1, 2, ]`. Es el error de sintaxis más
# común de los modelos y se repara sin ambigüedad.
_COMA_COLGANTE = re.compile(r",(\s*[}\]])")

# Traducción de los tipos de error de Pydantic más frecuentes. El mensaje se
# reinyecta en el prompt de reparación, y meter texto en inglés ahí empuja al
# modelo justamente hacia la deriva de idioma que la regla 6 persigue.
_MENSAJES_PYDANTIC = {
    "missing": "falta este campo obligatorio",
    "string_type": "debe ser una cadena de texto",
    "int_type": "debe ser un número entero",
    "int_parsing": "debe ser un número entero",
    "list_type": "debe ser una lista",
    "dict_type": "debe ser un objeto JSON",
    "bool_type": "debe ser true o false",
    "too_short": "tiene menos elementos de los exigidos",
    "too_long": "tiene más elementos de los admitidos",
    "string_too_short": "no puede estar vacío",
    "literal_error": "tiene un valor que no está entre los permitidos",
    "extra_forbidden": "no es un campo del esquema",
}


class ErrorFormatoJSON(ValueError):
    """El texto devuelto por el modelo no contiene un JSON recuperable."""


def _quitar_cercas(texto: str) -> str:
    return _CERCAS.sub("", texto).strip()


def _bloque_balanceado(texto: str) -> str:
    """Extrae el primer objeto JSON completo, ignorando lo que lo rodee.

    Hace falta porque los modelos anteponen frases como «Aquí está el JSON
    solicitado:» pese a la instrucción de responder solo con JSON. Se recorre
    llevando la cuenta de llaves, saltando las que caen dentro de una cadena
    —una llave en `"cuerpo": "el conjunto {a, b}"` no abre nivel— y respetando
    los escapes.
    """
    inicio = texto.find("{")
    if inicio == -1:
        raise ErrorFormatoJSON(
            "la respuesta del modelo no contiene ningún objeto JSON (no hay '{')"
        )

    profundidad = 0
    en_cadena = False
    escapado = False

    for posicion in range(inicio, len(texto)):
        caracter = texto[posicion]

        if escapado:
            escapado = False
            continue
        if caracter == "\\":
            escapado = True
            continue
        if caracter == '"':
            en_cadena = not en_cadena
            continue
        if en_cadena:
            continue

        if caracter == "{":
            profundidad += 1
        elif caracter == "}":
            profundidad -= 1
            if profundidad == 0:
                return texto[inicio : posicion + 1]

    raise ErrorFormatoJSON(
        "el objeto JSON quedó sin cerrar: probablemente la respuesta se truncó "
        "por límite de tokens"
    )


def extraer_json(crudo: str) -> dict:
    """Texto del modelo → diccionario. Tolerante, pero sin adivinar contenido.

    Las dos únicas reparaciones que aplica son sintácticas y no ambiguas:
    quitar las cercas de Markdown y las comas colgantes. La segunda se intenta
    **solo si el parseo normal ya falló**, para no tocar un JSON que estaba
    bien. Cualquier otro problema se devuelve como error y lo resuelve el bucle
    de reparación, que es quien puede pedirle al modelo que lo corrija.
    """
    bloque = _bloque_balanceado(_quitar_cercas(crudo))

    try:
        datos = json.loads(bloque)
    except json.JSONDecodeError as exc:
        try:
            datos = json.loads(_COMA_COLGANTE.sub(r"\1", bloque))
        except json.JSONDecodeError:
            raise ErrorFormatoJSON(
                f"el JSON no se puede parsear: {exc.msg} (línea {exc.lineno})"
            ) from exc

    if not isinstance(datos, dict):
        raise ErrorFormatoJSON(
            f"se esperaba un objeto JSON y llegó {type(datos).__name__}"
        )
    return datos


def _formatear_errores_pydantic(exc: ValidationError) -> list[str]:
    """Errores de Pydantic → frases en español, ubicadas en el campo."""
    mensajes: list[str] = []
    for error in exc.errors():
        ruta = ".".join(str(parte) for parte in error["loc"]) or "(raíz)"
        tipo = error["type"]
        if tipo == "value_error":
            # Los validadores propios ya escriben el mensaje en español;
            # Pydantic les antepone "Value error, ".
            detalle = error["msg"].removeprefix("Value error, ")
        else:
            detalle = _MENSAJES_PYDANTIC.get(tipo, error["msg"])
        mensajes.append(f"campo '{ruta}': {detalle}")
    return mensajes


@dataclass(slots=True)
class ResultadoValidacion:
    """Veredicto, cápsula saneada y métricas de la corrida.

    Las métricas no son adorno: la Fase 3 del plan pide una tabla comparativa
    de modelos con «% de JSON válido al primer intento, adherencia al rango de
    palabras, calidad del español, latencia y costo». Este objeto entrega las
    tres primeras por cápsula, y `eval_runner.py` las agrega.
    """

    capsula: Microcapsula | None = None
    errores: list[str] = field(default_factory=list)
    metricas: dict[str, object] = field(default_factory=dict)

    @property
    def es_valida(self) -> bool:
        return self.capsula is not None and not self.errores

    def mensaje_para_reparacion(self) -> str:
        """Realimentación que se reinyecta en el prompt del reintento.

        Se enumeran **todos** los defectos y no solo el primero: cada reintento
        cuesta una llamada al modelo, y corregir de a uno agotaría los dos
        intentos disponibles en una cápsula que tenía tres problemas menores.
        """
        listado = "\n".join(f"{i}. {e}" for i, e in enumerate(self.errores, start=1))
        return (
            "La respuesta anterior fue rechazada por estos motivos:\n"
            f"{listado}\n\n"
            "Corrige exclusivamente esos puntos y vuelve a entregar el objeto "
            "JSON completo, en español y sin texto adicional fuera del JSON."
        )


def validar(
    crudo: str | dict,
    *,
    fragmentos: Sequence[FragmentoRecuperado],
    palabras_objetivo: int | None = None,
) -> ResultadoValidacion:
    """Aplica las seis reglas del plan §3 a la respuesta del modelo.

    `fragmentos` son los que se inyectaron en el prompt: son la verdad contra la
    que se contrastan las citas (regla 5), así que tienen que ser exactamente
    los mismos que vio el modelo. `palabras_objetivo` es el `palabras_texto` del
    perfil; se usa para medir la adherencia, no para rechazar.
    """
    ajustes = get_settings()

    # --- Regla 1: parsea y cumple el esquema ---------------------------------
    if isinstance(crudo, str):
        try:
            datos = extraer_json(crudo)
        except ErrorFormatoJSON as exc:
            return ResultadoValidacion(errores=[str(exc)], metricas={"parseo": False})
    else:
        datos = crudo

    try:
        capsula = Microcapsula.model_validate(datos)
    except ValidationError as exc:
        return ResultadoValidacion(
            errores=_formatear_errores_pydantic(exc),
            metricas={"parseo": True, "esquema": False},
        )

    errores: list[str] = []

    # --- Regla 2: extensión del contenido (cap. 11.1) ------------------------
    palabras = capsula.palabras_contenido()
    if palabras < ajustes.capsula_min_palabras:
        errores.append(
            f"el contenido tiene {palabras} palabras y el mínimo es "
            f"{ajustes.capsula_min_palabras}: hay que desarrollarlo más"
        )
    elif palabras > ajustes.capsula_max_palabras:
        errores.append(
            f"el contenido tiene {palabras} palabras y el máximo es "
            f"{ajustes.capsula_max_palabras}: hay que recortarlo"
        )

    # --- Regla 5: citas verificables -----------------------------------------
    disponibles = {f.id_fragmento: f for f in fragmentos}
    citados = list(dict.fromkeys(f.id_fragmento for f in capsula.fuentes))
    inventados = [i for i in citados if i not in disponibles]

    if inventados:
        errores.append(
            f"las fuentes citan fragmentos que no se entregaron: {inventados}. "
            f"Solo se pueden citar estos identificadores: {sorted(disponibles)}"
        )

    citas_corregidas = 0
    if not inventados:
        # Se reconstruye la lista completa: deduplicada, en el orden en que el
        # modelo las citó, y con la procedencia tomada de la base.
        saneadas = []
        for id_fragmento in citados:
            fragmento = disponibles[id_fragmento]
            fuente = next(f for f in capsula.fuentes if f.id_fragmento == id_fragmento)
            if fuente.documento != fragmento.documento or fuente.pagina != fragmento.pagina_inicio:
                citas_corregidas += 1
            fuente.documento = fragmento.documento
            fuente.pagina = fragmento.pagina_inicio
            saneadas.append(fuente)
        capsula.fuentes = saneadas

    # --- Regla 6: idioma ------------------------------------------------------
    analisis = idioma.analizar(capsula.texto_plano())
    if not analisis.es_espanol:
        errores.append(
            f"la cápsula debe estar íntegramente en español: {analisis.motivo}"
        )

    return ResultadoValidacion(
        capsula=capsula,
        errores=errores,
        metricas={
            "parseo": True,
            "esquema": True,
            "palabras_contenido": palabras,
            "palabras_objetivo": palabras_objetivo,
            "desviacion_palabras": (
                None if palabras_objetivo is None else palabras - palabras_objetivo
            ),
            "fragmentos_inyectados": len(disponibles),
            "fragmentos_citados": len(citados),
            "citas_inventadas": len(inventados),
            "citas_corregidas": citas_corregidas,
            "idioma_ok": analisis.es_espanol,
            "ratio_espanol": round(analisis.ratio_espanol, 4),
        },
    )
