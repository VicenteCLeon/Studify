"""Contrato estructural de la microcápsula (PLAN_DESARROLLO.md §3).

Es el punto de acuerdo entre el motor LLM y la UI: lo que el generador promete
producir y lo que `web/templates/student/_capsula.html` sabe renderizar. Por eso
se define **antes** que el generador y no después.

**Estructura pedagógica de siete pasos (definida por la profesora guía el
14-ago-2026).** Antes la cápsula era una lista de bloques sueltos que el modelo
ordenaba a su criterio; ahora la secuencia es fija y cada paso tiene su propio
campo, de modo que el esqueleto no depende de que el LLM se acuerde de
respetarlo:

    1. OA                        → `objetivo_aprendizaje`
    2. Activación (pregunta)     → `activacion`
    3. Concepto central          → `concepto_central`
    4. Representación adaptativa → `representacion_adaptativa`  (bloques VARK)
    5. Ejemplo / aplicación      → `ejemplo`
    6. Pregunta de comprobación  → `actividad.pregunta`
    7. Retroalimentación         → `actividad.retroalimentacion`

Tener un campo por paso —en vez de una lista con etiquetas— hace que "falta la
activación" sea un error de validación y no algo que haya que descubrir leyendo
la cápsula.

**Dónde vive la adaptación VARK.** El paso 4 es su sede principal: es una lista
de bloques tipados y ahí caben la tabla del perfil visual, el glosario del
lector-escritor y la analogía del auditivo. Pero la adaptación no se agota ahí
(decisión del equipo, 14-ago-2026): `ejemplo` también es un bloque tipado, así
que un perfil kinestésico recibe `lista_pasos` donde otro recibe un párrafo, y
la actividad de cierre cambia a `intentalo_tu` cuando `p_K ≥ 40%`. Concentrar
todo en el paso 4 habría dejado sin destino a varias directivas de
`vark/rules.py` que el informe sí exige (tabla 11.1).

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

# La activación es una pregunta breve que engancha con el conocimiento previo
# antes de explicar nada. Si se alarga deja de activar y pasa a ser exposición,
# que es el paso siguiente.
MAX_PALABRAS_ACTIVACION = 45


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

    Los campos siguen el orden de los siete pasos pedagógicos (ver el docstring
    del módulo). Todos son obligatorios: una cápsula a la que le falte la
    activación o el concepto central no es una cápsula incompleta que se pueda
    mostrar igual, es una que hay que volver a pedirle al modelo.
    """

    model_config = ConfigDict(extra="ignore")

    titulo: str = Field(min_length=1)

    # Paso 1 — OA.
    objetivo_aprendizaje: str = Field(min_length=1)

    # Paso 2 — Activación: pregunta de apertura, antes de explicar nada.
    activacion: str = Field(min_length=1)

    # Paso 3 — Concepto central: la explicación en limpio, la misma para los
    # cuatro perfiles. Es texto y no un bloque tipado a propósito: lo que cambia
    # entre perfiles es *cómo se refuerza* después (paso 4), no la definición.
    concepto_central: str = Field(min_length=1)

    # Paso 4 — Representación adaptativa: el mismo concepto reexpresado en el
    # canal del estudiante. Sede principal de la adaptación VARK, por eso es una
    # lista de bloques tipados y no un solo bloque.
    representacion_adaptativa: list[BloqueContenido] = Field(min_length=1)

    # Paso 5 — Ejemplo / aplicación. Bloque tipado (y no texto plano) para que
    # un perfil kinestésico reciba `lista_pasos` donde otro recibe `parrafo`.
    ejemplo: BloqueContenido

    # Pasos 6 y 7 — pregunta de comprobación y retroalimentación, que viajan
    # juntas porque la segunda solo tiene sentido respecto de la primera.
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

    @model_validator(mode="after")
    def activacion_es_una_pregunta(self) -> "Microcapsula":
        """El paso 2 activa conocimiento previo, y para eso tiene que preguntar.

        Se comprueba el signo de cierre y no el de apertura porque los modelos
        omiten el «¿» inicial con frecuencia; exigir ambos gastaría reintentos
        en un problema ortográfico y no pedagógico.
        """
        if "?" not in self.activacion:
            raise ValueError(
                "'activacion' debe ser una pregunta dirigida al estudiante y no "
                f"lleva signo de interrogación: «{self.activacion}»"
            )
        palabras = contar_palabras(self.activacion)
        if palabras > MAX_PALABRAS_ACTIVACION:
            raise ValueError(
                f"'activacion' tiene {palabras} palabras y el máximo es "
                f"{MAX_PALABRAS_ACTIVACION}: es una pregunta breve de apertura, "
                f"no la explicación"
            )
        return self

    def palabras_contenido(self) -> int:
        """Extensión de la cápsula según el cap. 11.1.

        Suma los cuatro pasos que el estudiante lee de corrido: activación,
        concepto central, representación adaptativa y ejemplo. El título tiene
        su propio límite y la actividad de cierre se mide aparte — el rango
        150–300 describe el cuerpo, no el quiz que se responde después.
        """
        return (
            contar_palabras(self.activacion)
            + contar_palabras(self.concepto_central)
            + sum(bloque.palabras() for bloque in self.representacion_adaptativa)
            + self.ejemplo.palabras()
        )

    def bloques_legibles(self) -> list[BloqueContenido]:
        """Los bloques tipados de la cápsula, en orden de lectura.

        Lo usan la UI y los tests para recorrer la parte tipada sin repetir el
        orden de los pasos en cada sitio.
        """
        return [*self.representacion_adaptativa, self.ejemplo]

    def texto_plano(self) -> str:
        """Todo el texto legible de la cápsula, para analizar el idioma.

        Incluye la actividad: la deriva al inglés suele empezar justamente en
        las partes que el modelo redacta al final, cuando ya lleva mucho
        contexto en español encima.
        """
        partes: list[str] = [
            self.titulo,
            self.objetivo_aprendizaje,
            self.activacion,
            self.concepto_central,
        ]
        for bloque in self.bloques_legibles():
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
