"""Plantillas del prompt maestro, en los tres bloques del plan (Fase 3).

    contexto → los fragmentos curados, cada uno con su `id_fragmento`
    perfil   → qué bloques incluir, derivado de `configuracion_contenido`
    formato  → esquema JSON, extensión y obligación de escribir en español

**El bloque de perfil no describe al estudiante: le dice al modelo qué
construir.** Es la mitigación acordada para el riesgo declarado en
`PLAN_DESARROLLO.md` §5 —«las cuatro cápsulas VARK salen indistinguibles»—, que
ahí mismo se resuelve así: «el prompt debe recibir instrucciones
**estructurales** (qué bloques incluir), no adjetivos de tono». Pedir «redacta
de forma visual» produce la misma cápsula para los cuatro perfiles con distinto
adorno; pedir «incluye un bloque `tabla` de 3 filas y 2 columnas» produce
cápsulas que se distinguen a simple vista, que es lo que la prueba de
diferenciación del criterio de término tiene que poder comprobar.

Por la misma razón el bloque se arma desde `configuracion_contenido`
(`recursos_visuales`, `componentes_practicos`, `palabras_texto`, `directivas`) y
nunca desde la etiqueta del perfil: la etiqueta «visual» no dice cuántos
recursos poner, y el cap. 17.2 además prohíbe persistirla.

Se usa `PromptTemplate` de LlamaIndex y nada más de la librería, según la
decisión de stack registrada en AVANCE.md §2: la orquestación del prompt sí, el
índice vectorial no.
"""

from llama_index.core import PromptTemplate

# --- Rol y reglas duras -------------------------------------------------------

# Va como mensaje de sistema. Todo está en español a propósito: mezclar inglés
# en las instrucciones es una de las causas de la deriva de idioma que el
# validador persigue en su regla 6.
SISTEMA = (
    "Eres un diseñador instruccional que redacta microcápsulas de estudio para "
    "estudiantes universitarios chilenos.\n\n"
    "Reglas que no puedes incumplir:\n"
    "1. Escribes ÍNTEGRAMENTE en español. Ni una palabra en inglés o en chino, "
    "salvo términos técnicos que no tengan traducción establecida.\n"
    "2. Respondes ÚNICAMENTE con un objeto JSON válido. Sin explicaciones antes "
    "ni después, sin bloques de código Markdown.\n"
    "3. Solo puedes afirmar lo que aparece en los fragmentos que se te "
    "entregan. No agregas datos, cifras, autores ni ejemplos que no estén ahí. "
    "Si un fragmento no alcanza para desarrollar un punto, desarrollas otro.\n"
    "4. Cada fuente que cites debe ser uno de los identificadores de fragmento "
    "entregados. Inventar un identificador invalida la respuesta completa."
)

# --- Bloque 1: contexto -------------------------------------------------------

CONTEXTO = PromptTemplate(
    "## Material curado disponible\n\n"
    "Estos son los únicos fragmentos que puedes usar. Cada uno lleva el "
    "identificador con el que debes citarlo en `fuentes`.\n\n"
    "{fragmentos}"
)

FRAGMENTO = PromptTemplate(
    "### id_fragmento: {id_fragmento}\n"
    "Procedencia: {cita}\n"
    "Tipo de material: {tipo}\n\n"
    "{texto}\n"
)

# --- Bloque 2: perfil ---------------------------------------------------------

PERFIL = PromptTemplate(
    "## Cómo debe estar construida esta cápsula\n\n"
    "El estudiante tiene un perfil de aprendizaje diagnosticado. No menciones "
    "el perfil ni lo describas: se refleja en la estructura de la cápsula, no "
    "en un comentario sobre ella.\n\n"
    "Extensión del contenido: aproximadamente {palabras_texto} palabras "
    "(mínimo {palabras_min}, máximo {palabras_max}).\n"
    "Recursos visuales (bloques `tabla` o `esquema`): {recursos_visuales}.\n"
    # No se nombran tipos de bloque acá: con p_K ≥ 40% la tabla 11.1 cuenta
    # tres componentes prácticos —ejemplo aplicado, secuencia paso a paso y
    # actividad «inténtalo tú»—, y el tercero es la actividad de cierre, que no
    # es un bloque de `contenido`. Decir "3 bloques" obligaría al modelo a
    # inventarse uno para cuadrar la cuenta.
    "Componentes prácticos, contando los bloques aplicados y la actividad de "
    "cierre: {componentes_practicos}.\n"
    "Registro de redacción: {tono}.\n\n"
    "Instrucciones estructurales obligatorias:\n{directivas}"
)

# Cómo se redacta cada tono de la tabla 17.4. Es lo único de este bloque que
# habla de estilo; todo lo demás son bloques concretos que hay que construir.
DESCRIPCION_TONO = {
    "oral": (
        "conversacional, dirigiéndote al estudiante de tú, como si lo "
        "explicaras en voz alta"
    ),
    "formal": "preciso y académico, con la terminología exacta de la disciplina",
    "practico": "directo y orientado a la acción, centrado en qué hacer y cómo",
    "espacial": (
        "organizado por relaciones entre conceptos, señalando qué contiene o "
        "depende de qué"
    ),
    "mixto": (
        "equilibrado: explicación clara, terminología precisa y aplicación "
        "concreta en proporciones parecidas"
    ),
}

# Traducción de cada directiva de `vark/rules.py` a una instrucción de
# construcción. Cada una nombra un `tipo` del contrato de `generation/schemas.py`
# y una cantidad, para que sea comprobable en la cápsula resultante y no quede a
# interpretación del modelo.
INSTRUCCION_POR_DIRECTIVA = {
    "incluir_mapa_conceptual": (
        "Incluye un bloque `esquema` cuyo cuerpo sea una lista que muestre la "
        "jerarquía de los conceptos, del más general al más específico."
    ),
    "tabla_comparativa": (
        "Incluye un bloque `tabla` con al menos 2 columnas y 3 filas, donde la "
        "primera fila sean los encabezados de columna."
    ),
    "estructura_jerarquica": (
        "Ordena los bloques de lo general a lo particular y ponle `encabezado` "
        "a cada uno."
    ),
    "recurso_visual_complementario": (
        "Incluye al menos un bloque `tabla` o `esquema` que resuma "
        "visualmente lo explicado en prosa."
    ),
    "encabezados_jerarquicos": (
        "Todos los bloques llevan `encabezado` explícito; ninguno queda en null."
    ),
    "definiciones_exactas": (
        "Define con precisión cada término técnico la primera vez que aparece, "
        "usando la formulación del material entregado."
    ),
    "glosario": (
        "Cierra el contenido con un bloque `glosario` cuyo cuerpo sea una lista "
        "de entradas «término: definición»."
    ),
    "tono_oral": (
        "Redacta en segunda persona y con frases cortas, como una explicación "
        "hablada."
    ),
    "analogias_cotidianas": (
        "Incluye un bloque `analogia` que compare el concepto principal con una "
        "situación cotidiana."
    ),
    "preguntas_reflexivas": (
        "Intercala al menos una pregunta directa al estudiante dentro de la "
        "prosa, y respóndela a continuación."
    ),
    "ejemplo_resuelto": (
        "Incluye un bloque `ejemplo_resuelto` con un caso concreto desarrollado "
        "de principio a fin."
    ),
    "paso_a_paso": (
        "Incluye un bloque `lista_pasos` cuyo cuerpo sea una lista de pasos "
        "ordenados y accionables."
    ),
    "actividad_aplicada": (
        "La actividad de cierre debe ser de tipo `intentalo_tu`: un ejercicio "
        "que el estudiante resuelve por su cuenta, con la resolución esperada "
        "en `retroalimentacion`."
    ),
}

# --- Bloque 3: formato --------------------------------------------------------

# El esquema va como texto y se inyecta como variable, no incrustado en la
# plantilla: `PromptTemplate` interpreta las llaves como marcadores de posición
# y habría que escaparlas todas, que es una fuente de errores silenciosos.
ESQUEMA_JSON = """{
  "titulo": "string, máximo 10 palabras",
  "objetivo_aprendizaje": "string, una sola oración",
  "contenido": [
    {
      "tipo": "parrafo | lista_pasos | tabla | esquema | analogia | ejemplo_resuelto | glosario",
      "encabezado": "string o null",
      "cuerpo": "la forma depende del tipo; ver la lista de más abajo"
    }
  ],
  "actividad": {
    "tipo": "quiz_mc | intentalo_tu",
    "pregunta": "string",
    "alternativas": ["solo en quiz_mc: 4 alternativas distintas"],
    "indice_correcta": "solo en quiz_mc: entero, la primera es 0",
    "retroalimentacion": "string que explica por qué"
  },
  "fuentes": [
    { "id_fragmento": 0, "documento": "string", "pagina": 0 }
  ]
}"""

FORMATO = PromptTemplate(
    "## Formato de la respuesta\n\n"
    "Devuelve exactamente esta estructura JSON:\n\n"
    "{esquema_json}\n\n"
    "La forma de `cuerpo` depende del `tipo` del bloque:\n"
    "- `parrafo`, `analogia`, `ejemplo_resuelto`: un string.\n"
    "- `lista_pasos`, `esquema`, `glosario`: una lista de strings.\n"
    "- `tabla`: una lista de filas, y cada fila una lista de strings con el "
    "mismo número de columnas.\n\n"
    "Antes de responder, verifica:\n"
    "- El JSON parsea y no lleva comas colgantes ni texto fuera del objeto.\n"
    "- `titulo` tiene 10 palabras o menos.\n"
    "- La suma de palabras de `contenido` está entre {palabras_min} y "
    "{palabras_max}.\n"
    "- `actividad` está presente y sus campos corresponden a su `tipo`: "
    "`quiz_mc` lleva `alternativas` e `indice_correcta`; `intentalo_tu` no "
    "lleva ninguno de los dos.\n"
    "- Cada `id_fragmento` de `fuentes` es uno de los entregados arriba.\n"
    "- Todo el texto está en español."
)

# --- Tarea --------------------------------------------------------------------

TAREA = PromptTemplate(
    "## Objetivo de aprendizaje a cubrir\n\n"
    "Asignatura: {asignatura}\n"
    "Unidad: {unidad}\n"
    "Tema: {tema}\n"
    "{descripcion}"
)
