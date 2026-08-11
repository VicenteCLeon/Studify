"""Material de prueba compartido por los tests de la Fase 3.

No es un módulo de tests: lo importan `test_generacion_contrato.py`,
`test_prompt_maestro.py` y `test_generador.py`, que necesitan exactamente la
misma cápsula y los mismos fragmentos. Duplicarlo en cada archivo haría que un
cambio en el contrato hubiera que replicarlo tres veces, y que dejar uno atrás
pasara inadvertido.

El contenido es real en su forma —una cápsula de normalización de bases de
datos, dentro del rango de 150–300 palabras del cap. 11.1 y en español— porque
varias reglas del validador (extensión, idioma) solo se pueden ejercitar con
texto que las cumpla de verdad.
"""

from studify.db.models import ObjetivoAprendizaje
from studify.rag.retriever import FragmentoRecuperado

PARRAFO = (
    "La normalización es el proceso que organiza los atributos de una base de "
    "datos relacional para reducir la redundancia y evitar anomalías al "
    "insertar, actualizar o eliminar filas. Cada forma normal agrega una "
    "condición sobre la anterior, de modo que una tabla en tercera forma "
    "normal cumple también las dos primeras. El objetivo no es tener muchas "
    "tablas, sino que cada dato quede almacenado una sola vez y en el lugar "
    "donde realmente pertenece, junto a la clave que lo determina."
)

EXPLICACION = (
    "Una dependencia parcial aparece cuando un atributo no clave depende solo "
    "de una parte de la clave primaria compuesta, y no de la clave completa. "
    "Mientras exista una dependencia parcial, la tabla no está en segunda "
    "forma normal y el mismo valor se repetirá en muchas filas. Al separar ese "
    "atributo en su propia tabla, cualquier corrección se hace una vez y queda "
    "reflejada en todas las consultas que la usan, porque ya no hay copias "
    "que puedan quedar desactualizadas entre sí."
)

DOCUMENTO = "Apunte Unidad 3 — Normalización"

OBJETIVO = ObjetivoAprendizaje(
    id_objetivo=42,
    codigo_objetivo="BD-U3-01",
    asignatura="Bases de Datos",
    unidad="Unidad 3: Normalización",
    tema="Segunda forma normal",
    descripcion="Reconocer y eliminar dependencias parciales.",
)

FRAGMENTOS = [
    FragmentoRecuperado(
        id_fragmento=161,
        texto=PARRAFO,
        tipo="texto",
        documento=DOCUMENTO,
        id_documento=7,
        pagina_inicio=12,
        pagina_fin=12,
        etiqueta_tematica="normalizacion",
    ),
    FragmentoRecuperado(
        id_fragmento=162,
        texto=EXPLICACION,
        tipo="tabla",
        documento=DOCUMENTO,
        id_documento=7,
        pagina_inicio=13,
        pagina_fin=14,
        etiqueta_tematica="normalizacion",
    ),
]


def capsula_valida() -> dict:
    """Cápsula bien formada de referencia; los tests la modifican por copia."""
    return {
        "titulo": "Segunda forma normal y dependencias parciales",
        "objetivo_aprendizaje": (
            "Identificar dependencias parciales en una tabla relacional y "
            "corregirlas."
        ),
        "contenido": [
            {"tipo": "parrafo", "encabezado": None, "cuerpo": PARRAFO},
            {"tipo": "parrafo", "encabezado": "Dependencia parcial", "cuerpo": EXPLICACION},
        ],
        "actividad": {
            "tipo": "quiz_mc",
            "pregunta": "¿Cuándo una tabla incumple la segunda forma normal?",
            "alternativas": [
                "Cuando un atributo no clave depende de parte de la clave compuesta",
                "Cuando la tabla tiene más de cinco columnas",
                "Cuando la clave primaria es un número entero",
                "Cuando existen dos índices sobre la misma columna",
            ],
            "indice_correcta": 0,
            "retroalimentacion": (
                "La segunda forma normal exige que todo atributo no clave "
                "dependa de la clave completa."
            ),
        },
        "fuentes": [{"id_fragmento": 161, "documento": DOCUMENTO, "pagina": 12}],
    }
