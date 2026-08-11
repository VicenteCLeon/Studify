"""Detección de deriva de idioma (regla 6 del plan §3).

El riesgo que cubre está declarado en `PLAN_DESARROLLO.md` §5: «Deriva de idioma
(inglés/chino) en prompts largos». Los tres modelos candidatos —DeepSeek, Qwen y
GLM— están entrenados mayoritariamente en inglés y chino, y con un prompt largo
en español tienden a responder en otro idioma, sobre todo en las partes que
redactan al final.

**Por qué no se usa `langdetect` ni otra librería.** `langdetect` es
probabilístico y, salvo que se fije `DetectorFactory.seed`, **devuelve
resultados distintos entre corridas sobre el mismo texto**. Meter una fuente de
no-determinismo dentro del validador contradiría el argumento central del
proyecto (cap. 13: recuperación determinista, sin factor probabilístico) y haría
que un mismo JSON pudiera aceptarse o rechazarse según la corrida — imposible de
depurar y de reportar en el informe. El problema real acá es mucho más acotado
que "identificar cualquier idioma": basta distinguir español de inglés y de
chino, y para eso un conteo de palabras funcionales es exacto, reproducible y
explicable.

**Cómo decide.** Tres condiciones de rechazo, en orden de contundencia:

1. Aparecen caracteres CJK → el modelo derivó al chino. No admite discusión.
2. Hay más marcadores del inglés que del español → derivó al inglés.
3. Hay muy poco español y tampoco ortografía española (tildes, ñ, ¿, ¡) → no
   hay evidencia suficiente de que el texto esté en español.

La tercera es la que necesita el escape por ortografía: una cápsula para un
perfil visual puede ser casi toda tabla y glosario, con muy pocas palabras
funcionales, y sería un falso rechazo contarla como "poco español".
"""

import re
import unicodedata
from dataclasses import dataclass

# Palabras funcionales del español que **no** son también palabras del inglés.
# Quedan fuera a propósito "a", "no", "me", "he", "sin", "solo", "son" y "van":
# todas existen en inglés y contaminarían el conteo con falsos positivos.
MARCADORES_ESPANOL = frozenset(
    """
    de la el que en y los las un una por con para del al es se su sus lo como
    más pero sobre entre cuando también cada todo todos toda todas esta este
    estos estas esa ese esos esas ni unos unas le les nos donde porque aunque
    mientras según además así cual cuales otro otra otros otras mismo misma
    puede pueden debe deben tiene tienen hay ser estar hacer permite requiere
    ejemplo decir tanto cuyo cuya siempre nunca antes después dentro fuera
    """.split()  # noqa: SIM905 — la lista se mantiene a mano; en una línea es ilegible
)

# Palabras funcionales del inglés, **filtradas de palabras clave técnicas**.
# Se excluyen deliberadamente "from", "where", "select", "in", "on", "as",
# "not", "all", "and", "or", "by", "for", "if", "set", "table", "key", "null",
# "true", "false": aparecen en cualquier cápsula en español que hable de SQL,
# programación o lógica, y las contarían como evidencia de inglés. Lo que queda
# es suficiente —"the" solo representa ~7% de un texto en inglés— y no dispara
# con contenido técnico redactado en español.
MARCADORES_INGLES = frozenset(
    """
    the of to is that with are this be it which can has have will you we they
    their there these those but at when more other than then into each such
    also may must should would could been being was were about through between
    during after before however therefore because its his her our your who
    what how why does did while both any some most only very
    """.split()  # noqa: SIM905 — ídem
)

# Bloques Unicode que delatan una respuesta en chino/japonés/coreano.
RANGOS_CJK: tuple[tuple[int, int], ...] = (
    (0x3000, 0x303F),  # puntuación CJK (、。「」)
    (0x3040, 0x30FF),  # hiragana y katakana
    (0x3400, 0x4DBF),  # ideogramas, extensión A
    (0x4E00, 0x9FFF),  # ideogramas unificados
    (0xAC00, 0xD7AF),  # hangul
    (0xFF00, 0xFFEF),  # formas de ancho completo (１２３，．)
)

# Signos ortográficos que en la práctica solo aparecen en español.
ORTOGRAFIA_ESPANOLA = frozenset("áéíóúüñÁÉÍÓÚÜÑ¿¡")

# Piso de palabras funcionales del español sobre el total de palabras. Un texto
# en prosa española ronda el 30–40%; uno en inglés no llega al 1% en esta
# escala. El 5% deja un margen amplio para cápsulas muy esquemáticas (tablas y
# glosarios, donde casi no hay palabras funcionales) sin dejar pasar otro idioma.
RATIO_MINIMO = 0.05

# Cuántos signos con ortografía española alcanzan como evidencia alternativa
# cuando el ratio queda bajo. Tres tildes en 150–300 palabras es un piso muy
# holgado: un texto en español difícilmente baja de ahí.
MIN_SIGNOS_ORTOGRAFICOS = 3

_PALABRAS = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class AnalisisIdioma:
    """Veredicto y la evidencia que lo sustenta.

    Se devuelve la evidencia y no solo un booleano para que el mensaje de error
    del bucle de reparación sea accionable ("aparecen 12 caracteres CJK" es
    reparable; "idioma incorrecto" no lo es) y para que el bake-off de la Fase 3
    pueda tabular *cómo* falla cada modelo, no solo cuántas veces.
    """

    es_espanol: bool
    motivo: str
    palabras_totales: int
    marcadores_espanol: int
    marcadores_ingles: int
    caracteres_cjk: int
    signos_ortograficos: int

    @property
    def ratio_espanol(self) -> float:
        if not self.palabras_totales:
            return 0.0
        return self.marcadores_espanol / self.palabras_totales


def _es_cjk(caracter: str) -> bool:
    punto = ord(caracter)
    return any(inicio <= punto <= fin for inicio, fin in RANGOS_CJK)


def _normalizar(palabra: str) -> str:
    """Quita las tildes para que "más" y "mas" cuenten como el mismo marcador.

    Los modelos omiten tildes con frecuencia y no por eso están escribiendo en
    otro idioma; penalizarlo convertiría un problema ortográfico en un rechazo.
    """
    descompuesta = unicodedata.normalize("NFD", palabra.lower())
    return "".join(c for c in descompuesta if unicodedata.category(c) != "Mn")


# Los marcadores se comparan sin tildes, así que la tabla también se guarda así.
_ESPANOL_SIN_TILDES = frozenset(_normalizar(p) for p in MARCADORES_ESPANOL)


def analizar(texto: str) -> AnalisisIdioma:
    """Analiza si `texto` está redactado en español."""
    palabras = [_normalizar(p) for p in _PALABRAS.findall(texto)]
    total = len(palabras)

    cjk = sum(1 for c in texto if _es_cjk(c))
    signos = sum(1 for c in texto if c in ORTOGRAFIA_ESPANOLA)
    en_espanol = sum(1 for p in palabras if p in _ESPANOL_SIN_TILDES)
    en_ingles = sum(1 for p in palabras if p in MARCADORES_INGLES)

    def veredicto(ok: bool, motivo: str) -> AnalisisIdioma:
        return AnalisisIdioma(
            es_espanol=ok,
            motivo=motivo,
            palabras_totales=total,
            marcadores_espanol=en_espanol,
            marcadores_ingles=en_ingles,
            caracteres_cjk=cjk,
            signos_ortograficos=signos,
        )

    if cjk:
        return veredicto(
            False,
            f"el texto contiene {cjk} caracteres CJK (chino/japonés/coreano): "
            f"el modelo derivó de idioma",
        )

    if not total:
        return veredicto(False, "el texto no contiene palabras")

    if en_ingles > en_espanol:
        return veredicto(
            False,
            f"predominan marcadores del inglés sobre los del español "
            f"({en_ingles} contra {en_espanol} en {total} palabras)",
        )

    ratio = en_espanol / total
    if ratio < RATIO_MINIMO and signos < MIN_SIGNOS_ORTOGRAFICOS:
        return veredicto(
            False,
            f"evidencia insuficiente de español: solo {en_espanol} palabras "
            f"funcionales en {total} ({ratio:.1%}, mínimo {RATIO_MINIMO:.0%}) y "
            f"{signos} signos de ortografía española",
        )

    return veredicto(True, "español")


def es_espanol(texto: str) -> bool:
    """Atajo booleano para cuando no interesa la evidencia."""
    return analizar(texto).es_espanol
