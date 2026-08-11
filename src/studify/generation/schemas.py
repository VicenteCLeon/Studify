"""Contrato estructural de la microcápsula (PLAN_DESARROLLO.md §3).

Es el punto de acuerdo entre el motor LLM y la UI: lo que el generador promete
producir y lo que `web/templates/viewer.html` sabe renderizar. Por eso se define
**antes** que el generador y no después.

Este módulo implementa la mitad *estructural* de la validación de la Fase 4 del
cap. 18 —la que se puede decidir mirando solo el JSON— y deja en
`generation/validator.py` la mitad *contextual*, que necesita saber qué se
inyectó en el prompt:

    Regla del plan §3          Dónde vive          Por qué
    ------------------------   -----------------   ---------------------------
    1. parsea y cumple esquema  aquí (Pydantic)    es el esquema
    3. título ≤ 10 palabras     aquí               función del propio campo
    4. actividad obligatoria    aquí               campo requerido
    2. contenido 150–300 pal.   validator.py       el rango depende del perfil
    5. citas no alucinadas      validator.py       exige los fragmentos reales
    6. idioma español           validator.py       exige analizar el texto

**Tolerancia deliberada:** los campos desconocidos se ignoran en vez de
rechazarse. Un modelo que agrega `"dificultad": "media"` no rompe nada y forzar
un reintento por eso gasta una llamada; en cambio, si renombra `alternativas` a
`opciones`, el campo requerido falta y el bucle de reparación sí se activa, que
es cuando debe hacerlo.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Tipos de bloque que la UI sabe renderizar. La lista sale del plan §3 y está
# alineada con las directivas estructurales de `vark/rules.py`: cada directiva
# del perfil pide uno de estos bloques (p. ej. `tabla_comparativa` → "tabla",
# `ejemplo_resuelto` → "ejemplo_resuelto", `glosario` → "glosario").
TipoBloque = Literal[
    "parrafo",
    "lista_pasos",
    "tabla",
    "esquema",
    "analogia",
    "ejemplo_resuelto",
    "glosario",
]

TipoActividad = Literal["quiz_mc", "intentalo_tu"]

# Cuántas alternativas admite un ítem de selección múltiple. El prompt pide 4
# (es lo que muestra el plan §3), pero se aceptan 3–5 para no gastar un reintento
# en una diferencia irrelevante. Bajo 3 deja de ser un ítem de opción múltiple
# —con 2 la respuesta correcta se acierta la mitad de las veces por azar— y sobre
# 5 no cabe en una cápsula de 3–7 minutos.
MIN_ALTERNATIVAS = 3
MAX_ALTERNATIVAS = 5

MAX_PALABRAS_TITULO = 10

# El objetivo de aprendizaje declarado es «1 oración» (plan §3). No se cuentan
# puntos —las abreviaturas y los decimales harían fallar esa cuenta— sino que se
# acota la extensión, que es lo que la restricción realmente busca.
MAX_PALABRAS_OBJETIVO = 40


def contar_palabras(texto: str) -> int:
    """Palabras separadas por espacios en blanco.

    Se cuenta por `split()` y no por tokens `\\w+` a propósito: "paso-a-paso" o
    "150-300" son **una** unidad de lectura, y el rango 150–300 del cap. 11.1
    describe cuánto lee el estudiante, no cuántos lexemas hay.
    """
    return len(texto.split())


class BloqueContenido(BaseModel):
    """Un bloque del cuerpo de la cápsula.

    `cuerpo` admite tres formas porque los bloques no son homogéneos: un párrafo
    es texto corrido, una lista de pasos es una secuencia y una tabla es una
    matriz de filas. Mantenerlos en un solo campo polimórfico —en vez de tres
    campos opcionales— hace que el orden de lectura de la cápsula sea
    exactamente el orden del arreglo, que es lo que la UI necesita para
    renderizar sin reordenar nada.
    """

    model_config = ConfigDict(extra="ignore")

    tipo: TipoBloque
    encabezado: str | None = None
    cuerpo: str | list[str] | list[list[str]]

    @model_validator(mode="after")
    def cuerpo_no_vacio(self) -> "BloqueContenido":
        if isinstance(self.cuerpo, str):
            if not self.cuerpo.strip():
                raise ValueError(f"el bloque '{self.tipo}' tiene el cuerpo vacío")
        elif not self.cuerpo:
            raise ValueError(f"el bloque '{self.tipo}' tiene el cuerpo vacío")
        return self

    @model_validator(mode="after")
    def tabla_es_matriz(self) -> "BloqueContenido":
        """Una tabla tiene que llegar como filas, no como prosa.

        Es la única forma de cuerpo que se exige estrictamente. Los demás tipos
        se renderizan igual si llegan como texto o como lista, pero un bloque
        declarado `tabla` con el cuerpo en un string deja a la UI sin filas ni
        columnas que dibujar — y la tabla comparativa es justamente el recurso
        que la tabla 11.1 exige para el perfil visual (`p_V ≥ 40%`).
        """
        if self.tipo != "tabla":
            return self

        filas = self.cuerpo
        if not isinstance(filas, list) or not all(isinstance(f, list) for f in filas):
            raise ValueError(
                "un bloque 'tabla' necesita el cuerpo como lista de filas "
                '(p. ej. [["Concepto", "Definición"], ["1FN", "valores atómicos"]]); '
                f"llegó como {type(self.cuerpo).__name__}"
            )
        if len({len(f) for f in filas}) > 1:
            raise ValueError(
                "las filas de la tabla tienen distinto número de columnas: "
                f"{[len(f) for f in filas]}"
            )
        return self

    def palabras(self) -> int:
        """Cuántas palabras aporta este bloque al total de la cápsula.

        El encabezado cuenta: el estudiante lo lee, y el rango 150–300 del
        cap. 11.1 mide tiempo de consumo, no solo prosa.
        """
        total = contar_palabras(self.encabezado or "")
        if isinstance(self.cuerpo, str):
            return total + contar_palabras(self.cuerpo)
        for elemento in self.cuerpo:
            if isinstance(elemento, str):
                total += contar_palabras(elemento)
            else:
                total += sum(contar_palabras(celda) for celda in elemento)
        return total


class Actividad(BaseModel):
    """La actividad de cierre, obligatoria (regla 4 del plan §3).

    Dos formas, según el perfil: `quiz_mc` para comprobar comprensión y
    `intentalo_tu` para el componente aplicado que pide la tabla 11.1 cuando
    `p_K ≥ 40%` (directiva `actividad_aplicada` de `vark/rules.py`).
    """

    model_config = ConfigDict(extra="ignore")

    tipo: TipoActividad
    pregunta: str = Field(min_length=1)
    alternativas: list[str] = Field(default_factory=list)
    indice_correcta: int | None = None
    retroalimentacion: str = Field(min_length=1)

    @model_validator(mode="after")
    def coherente_con_el_tipo(self) -> "Actividad":
        """Cada tipo de actividad usa un subconjunto distinto de los campos.

        Se rechaza la mezcla en vez de ignorar los campos sobrantes porque
        significa que el modelo se confundió de formato, y eso el bucle de
        reparación sí lo puede corregir con el error a la vista. Dejarlo pasar
        produciría un `intentalo_tu` con alternativas que la UI mostraría como
        quiz sin respuesta correcta.
        """
        if self.tipo == "quiz_mc":
            if not (MIN_ALTERNATIVAS <= len(self.alternativas) <= MAX_ALTERNATIVAS):
                raise ValueError(
                    f"un 'quiz_mc' necesita entre {MIN_ALTERNATIVAS} y "
                    f"{MAX_ALTERNATIVAS} alternativas; llegaron "
                    f"{len(self.alternativas)}"
                )
            normalizadas = [a.strip().lower() for a in self.alternativas]
            if len(set(normalizadas)) != len(normalizadas):
                # Dos alternativas iguales significan dos respuestas correctas:
                # el estudiante puede marcar la "incorrecta" y tener razón.
                raise ValueError(f"el quiz tiene alternativas repetidas: {self.alternativas}")
            if self.indice_correcta is None:
                raise ValueError("un 'quiz_mc' necesita 'indice_correcta'")
            if not 0 <= self.indice_correcta < len(self.alternativas):
                raise ValueError(
                    f"'indice_correcta' = {self.indice_correcta} está fuera del "
                    f"rango de las {len(self.alternativas)} alternativas (0–"
                    f"{len(self.alternativas) - 1})"
                )
        else:
            if self.alternativas:
                raise ValueError(
                    "un 'intentalo_tu' es de respuesta abierta: no lleva "
                    "'alternativas'. Si la actividad es de selección múltiple, "
                    "el tipo debe ser 'quiz_mc'"
                )
            if self.indice_correcta is not None:
                raise ValueError("un 'intentalo_tu' no lleva 'indice_correcta'")
        return self


class Fuente(BaseModel):
    """Una cita al material curado que fundamentó la cápsula.

    `id_fragmento` es lo que hace verificable la trazabilidad del cap. 13: no es
    una referencia bibliográfica que el modelo redacta, es la clave primaria de
    la fila de `fragmento` que se le pasó en el prompt. `validator.py` la
    contrasta contra los fragmentos realmente inyectados (regla 5) y reescribe
    `documento` y `pagina` con los valores de la base, para que la procedencia
    la afirme el sistema y no el modelo.
    """

    model_config = ConfigDict(extra="ignore")

    id_fragmento: int
    documento: str = ""
    pagina: int | None = None


class Microcapsula(BaseModel):
    """El artefacto que produce el sistema; se persiste en `contenido_json`.

    Un modelo Pydantic y no un dict suelto porque este esquema es literalmente
    «la capa de validación estructural» de la Fase 4 del cap. 18: si el JSON del
    LLM no encaja acá, no llega ni a la base de datos ni a la pantalla.
    """

    model_config = ConfigDict(extra="ignore")

    titulo: str = Field(min_length=1)
    objetivo_aprendizaje: str = Field(min_length=1)
    contenido: list[BloqueContenido] = Field(min_length=1)
    actividad: Actividad
    # Al menos una fuente: una cápsula sin material citado no es RAG, es el
    # modelo respondiendo de memoria — exactamente lo que el cap. 13 descarta.
    fuentes: list[Fuente] = Field(min_length=1)

    @model_validator(mode="after")
    def titulo_breve(self) -> "Microcapsula":
        """Regla 3 del plan §3."""
        palabras = contar_palabras(self.titulo)
        if palabras > MAX_PALABRAS_TITULO:
            raise ValueError(
                f"el título tiene {palabras} palabras y el máximo es "
                f"{MAX_PALABRAS_TITULO}: «{self.titulo}»"
            )
        return self

    @model_validator(mode="after")
    def objetivo_es_una_oracion(self) -> "Microcapsula":
        palabras = contar_palabras(self.objetivo_aprendizaje)
        if palabras > MAX_PALABRAS_OBJETIVO:
            raise ValueError(
                f"'objetivo_aprendizaje' debe ser una sola oración; tiene "
                f"{palabras} palabras (máximo {MAX_PALABRAS_OBJETIVO})"
            )
        return self

    def palabras_contenido(self) -> int:
        """Extensión de la cápsula según el cap. 11.1.

        Cuenta **solo** los bloques de `contenido`. El título tiene su propio
        límite y la actividad de cierre se mide aparte: el rango 150–300 describe
        el cuerpo que el estudiante lee, no el quiz que responde después.
        """
        return sum(bloque.palabras() for bloque in self.contenido)

    def texto_plano(self) -> str:
        """Todo el texto legible de la cápsula, para analizar el idioma.

        Incluye la actividad: la deriva al inglés suele empezar justamente en
        las partes que el modelo redacta al final, cuando ya lleva mucho
        contexto en español encima.
        """
        partes: list[str] = [self.titulo, self.objetivo_aprendizaje]
        for bloque in self.contenido:
            if bloque.encabezado:
                partes.append(bloque.encabezado)
            if isinstance(bloque.cuerpo, str):
                partes.append(bloque.cuerpo)
            else:
                for elemento in bloque.cuerpo:
                    partes.extend([elemento] if isinstance(elemento, str) else elemento)
        partes.append(self.actividad.pregunta)
        partes.extend(self.actividad.alternativas)
        partes.append(self.actividad.retroalimentacion)
        return "\n".join(partes)
