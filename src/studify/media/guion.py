"""Normalización del guion antes de sintetizarlo, igual para cualquier motor.

Kokoro y Piper fonemizan con espeak-ng, que **descarta** los símbolos que no
conoce y lee mal las variables: «Se escribe X → Y» sale como «se escribe équis
i» (la flecha desaparece y la «Y» suena como la conjunción). Las siglas las
deletrea («DF» → «de efe», «RUT» → «erre u te»). Las cápsulas de la batería
traen además restos de LaTeX (`$X \\rightarrow Y$`, `t_1[X]`, `\\subseteq`),
porque el modelo a veces responde con notación matemática.

Por eso el guion se pasa a palabras **antes** de llegar al motor. Las reglas
están en tablas para que se puedan leer y revisar: `REGLAS` es exactamente lo
que se aplica, en orden. El texto que ve el estudiante no cambia; esto solo
afecta lo que se narra.

Las reglas están pensadas para el material del piloto (Bases de Datos):
«→» se lee «determina» porque en ese dominio es una dependencia funcional, que
es como lo leen las propias cápsulas («se lee "X determina Y"»).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

# Nombre de cada letra mayúscula cuando es una variable (RAE: «ye», «uve»).
NOMBRE_LETRA = {
    "A": "a", "B": "be", "C": "ce", "D": "de", "E": "e", "F": "efe", "G": "ge",
    "H": "hache", "I": "i", "J": "jota", "K": "ka", "L": "ele", "M": "eme",
    "N": "ene", "Ñ": "eñe", "O": "o", "P": "pe", "Q": "cu", "R": "erre",
    "S": "ese", "T": "te", "U": "u", "V": "uve", "W": "uve doble", "X": "equis",
    "Y": "ye", "Z": "zeta",
}

NUMERO = {
    "0": "cero", "1": "uno", "2": "dos", "3": "tres", "4": "cuatro",
    "5": "cinco", "6": "seis", "7": "siete", "8": "ocho", "9": "nueve",
}

# Comandos LaTeX que el modelo deja en el texto → el símbolo equivalente, que
# después se lee con `SIMBOLOS`.
LATEX = {
    r"\rightarrow": "→", r"\to": "→", r"\longrightarrow": "→",
    r"\Rightarrow": "⇒", r"\implies": "⇒",
    r"\leftrightarrow": "↔", r"\Leftrightarrow": "⇔", r"\iff": "⇔",
    r"\subseteq": "⊆", r"\subset": "⊂", r"\supseteq": "⊇", r"\in": "∈",
    r"\notin": "∉", r"\cup": "∪", r"\cap": "∩", r"\neq": "≠", r"\ne": "≠",
    r"\leq": "≤", r"\le": "≤", r"\geq": "≥", r"\ge": "≥", r"\times": "×",
    r"\emptyset": "∅", r"\varnothing": "∅",
}

# Símbolo → cómo se lee. Las flechas ASCII (`->`, `=>`) van primero en
# `REGLAS`, antes de que `=` y `>` se lean por separado.
SIMBOLOS = {
    "→": "determina", "⟶": "determina",
    "⇒": "implica", "↔": "si y solo si", "⇔": "si y solo si",
    "≠": "distinto de", "≤": "menor o igual que", "≥": "mayor o igual que",
    "⊆": "es subconjunto de", "⊂": "es subconjunto propio de",
    "⊇": "contiene a", "∈": "pertenece a", "∉": "no pertenece a",
    "∪": "unión", "∩": "intersección", "∅": "conjunto vacío", "×": "por",
    "=": "igual a",
}

# Siglas del dominio → (singular, plural). El plural se usa cuando la sigla va
# después de un determinante plural («las DF») o lleva «s» («DFs»).
SIGLAS = {
    "DF": ("dependencia funcional", "dependencias funcionales"),
    "BD": ("base de datos", "bases de datos"),
    "SGBD": ("sistema gestor de bases de datos", "sistemas gestores de bases de datos"),
    "FNBC": ("forma normal de Boyce-Codd", "formas normales de Boyce-Codd"),
    "1FN": ("primera forma normal", "primeras formas normales"),
    "2FN": ("segunda forma normal", "segundas formas normales"),
    "3FN": ("tercera forma normal", "terceras formas normales"),
    "4FN": ("cuarta forma normal", "cuartas formas normales"),
    "5FN": ("quinta forma normal", "quintas formas normales"),
    "PK": ("clave primaria", "claves primarias"),
    "FK": ("clave foránea", "claves foráneas"),
    # En Chile se dice «rut», no «erre u te».
    "RUT": ("rut", "ruts"),
}

DETERMINANTES_PLURALES = {
    "las", "los", "unas", "unos", "estas", "estos", "esas", "esos", "sus",
    "otras", "otros", "varias", "varios", "muchas", "muchos", "algunas",
    "algunos", "ambas", "ambos", "todas", "todos", "dos", "tres", "cuatro",
    "cinco", "nuestras", "nuestros", "tus", "mis", "dichas", "dichos",
}

# Palabras que, en mayúscula y sueltas, pueden ser una palabra y no una
# variable: «A veces…», «Y luego…», «O bien…», «E igual…», «U otro…».
LETRAS_QUE_SON_PALABRAS = {"A", "E", "O", "U", "Y"}


@dataclass(frozen=True)
class Regla:
    nombre: str
    descripcion: str
    aplicar: Callable[[str], str]


def _latex(texto: str) -> str:
    # Del comando más largo al más corto, para que `\leq` no lo capture `\le`.
    for comando in sorted(LATEX, key=len, reverse=True):
        texto = re.sub(re.escape(comando) + r"(?![A-Za-z])", f" {LATEX[comando]} ", texto)
    texto = texto.replace("$", "")
    # Subíndices: `t_1` → `t1`, `t_{12}` → `t12`.
    texto = re.sub(r"_\{(\w+)\}", r"\1", texto)
    return re.sub(r"(?<=\w)_(?=\w)", "", texto)


def _flechas_ascii(texto: str) -> str:
    texto = re.sub(r"\s*<=>\s*", " ⇔ ", texto)
    texto = re.sub(r"\s*=>\s*", " ⇒ ", texto)
    texto = re.sub(r"\s*-+>\s*", " → ", texto)
    texto = re.sub(r"\s*<=\s*", " ≤ ", texto)
    texto = re.sub(r"\s*>=\s*", " ≥ ", texto)
    return re.sub(r"\s*!=\s*", " ≠ ", texto)


def _cierre(texto: str) -> str:
    # El cierre de un conjunto de atributos, `(X)+` o `X+`, se lee «equis más».
    return re.sub(r"\(\s*([A-Z])\s*\)\s*\+|\b([A-Z])\+", lambda m: f"{m[1] or m[2]} más", texto)


def _tupla_de_atributo(texto: str) -> str:
    # `t1[X]` (el valor de la tupla t1 en los atributos X) → «t1 de X».
    return re.sub(r"\b([a-z]\d*)\[\s*([A-Z]\w*)\s*\]", r"\1 de \2", texto)


def _simbolos(texto: str) -> str:
    for simbolo, lectura in SIMBOLOS.items():
        texto = texto.replace(simbolo, f" {lectura} ")
    # `+` entre operandos: «a + b» → «a más b».
    return re.sub(r"(?<=[\w)])\s*\+\s*(?=[\w(])", " más ", texto)


def _siglas(texto: str) -> str:
    # «Dependencia Funcional (DF)»: la sigla entre paréntesis justo después de
    # su expansión se omite, si no se narraría dos veces lo mismo.
    for sigla, (singular, plural) in SIGLAS.items():
        for expansion in (plural, singular):
            texto = re.sub(
                rf"({re.escape(expansion)})\s*\(\s*{re.escape(sigla)}(s|'s)?\s*\)",
                r"\1",
                texto,
                flags=re.IGNORECASE,
            )

    patron = r"\b(" + "|".join(sorted(SIGLAS, key=len, reverse=True)) + r")(s|'s)?\b"

    def reemplazo(m: re.Match) -> str:
        singular, plural = SIGLAS[m[1]]
        anterior = texto[: m.start()].split()
        es_plural = bool(m[2]) or (
            bool(anterior) and anterior[-1].lower().strip("(,;:") in DETERMINANTES_PLURALES
        )
        return plural if es_plural else singular

    return re.sub(patron, reemplazo, texto)


def _identificador_de_tupla(texto: str) -> str:
    # `t1`, `t2` → «te uno», «te dos»: espeak lee «t1» letra por letra pero el
    # número a veces lo pega.
    return re.sub(
        r"\b([a-z])(\d)\b",
        lambda m: f"{NOMBRE_LETRA.get(m[1].upper(), m[1])} {NUMERO[m[2]]}",
        texto,
    )


def _es_inicio_de_oracion(texto: str, inicio: int) -> bool:
    previo = texto[:inicio].rstrip()
    return not previo or previo[-1] in ".!?¡¿:;\n\"'«“("


def _letras_variables(texto: str) -> str:
    """Una mayúscula suelta es una variable y se lee por su nombre.

    Excepción: A, E, O, U e Y al comienzo de una oración y seguidas de una
    palabra en minúscula son palabras («A veces», «Y luego»), no variables.
    """

    def reemplazo(m: re.Match) -> str:
        letra = m[0]
        if letra in LETRAS_QUE_SON_PALABRAS and _es_inicio_de_oracion(texto, m.start()):
            siguiente = texto[m.end() :].lstrip()
            if siguiente[:1].islower() and not siguiente.startswith(
                tuple(SIMBOLOS.values())
            ):
                return letra
        return NOMBRE_LETRA.get(letra, letra)

    return re.sub(r"(?<![\w-])[A-ZÑ](?![\w-])", reemplazo, texto)


def _espacios(texto: str) -> str:
    texto = re.sub(r"\s+([,.;:)])", r"\1", texto)
    texto = re.sub(r"\(\s+", "(", texto)
    return re.sub(r"\s{2,}", " ", texto).strip()


REGLAS: tuple[Regla, ...] = (
    Regla("latex", "Quita `$`, subíndices `_` y cambia comandos LaTeX por su símbolo.", _latex),
    Regla("flechas_ascii", "`->`, `=>`, `<=>`, `<=`, `>=`, `!=` → su símbolo.", _flechas_ascii),
    Regla("cierre", "`(X)+` o `X+` (cierre de atributos) → «X más».", _cierre),
    Regla("tupla_de_atributo", "`t1[X]` → «t1 de X».", _tupla_de_atributo),
    Regla("simbolos", "Símbolos matemáticos y `+` entre operandos → palabras.", _simbolos),
    Regla("siglas", "Siglas del dominio → su expansión, en singular o plural.", _siglas),
    Regla("identificador_de_tupla", "`t1`, `t2` → «te uno», «te dos».", _identificador_de_tupla),
    Regla("letras_variables", "Mayúscula suelta → nombre de la letra.", _letras_variables),
    Regla("espacios", "Colapsa espacios y los quita antes de la puntuación.", _espacios),
)


def normalizar_guion(texto: str) -> str:
    """El guion listo para narrar: símbolos, siglas y variables pasados a palabras."""
    for regla in REGLAS:
        texto = regla.aplicar(texto)
    return texto
