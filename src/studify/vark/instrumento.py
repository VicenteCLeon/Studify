"""Matriz de puntuación fija del instrumento VARK (cap. 10).

El cap. 10 define la calificación como un mapeo directo: «cada alternativa
seleccionada en las 16 preguntas se mapea con su dimensión sensorial
correspondiente (V, A, R o K)». Este módulo es esa matriz.

Vive en el paquete `vark` y no en `scripts/` porque no es un detalle del
importador: es la definición del instrumento. La entidad `respuesta_vark`
(tabla 17.3) existe justamente para poder **recalcular** los perfiles si esta
matriz cambia, sin volver a aplicar el cuestionario.

**Verificación del mapeo.** La asignación de canal se estableció por dos vías
independientes que coinciden en los 16 ítems:

1. Semántica: cada alternativa describe un canal sensorial sin ambigüedad
   ("ver un diagrama" → V, "escuchar la explicación" → A, "leer un resumen"
   → R, "resolver un ejercicio" → K).
2. Posicional: Google Forms exporta las selecciones múltiples en el orden en
   que las opciones aparecen en el formulario. Reconstruyendo ese orden desde
   las respuestas reales, los 16 ítems presentan sus alternativas en el orden
   V, A, R, K sin excepción.
"""

CANALES_EN_ORDEN = ("V", "A", "R", "K")

# Las 16 preguntas, cada una con sus 4 alternativas en el orden V, A, R, K
# tal como se despliegan en el formulario.
ITEMS: tuple[tuple[str, ...], ...] = (
    (
        "Ver un diagrama, mapa conceptual o figura que lo ilustre",
        "Escuchar la explicación del profesor o un podcast sobre el tema",
        "Leer un resumen o apuntes bien estructurados",
        "Resolver un ejercicio práctico o caso de aplicación directamente",
    ),
    (
        "Pedir que te muestre un ejemplo visual o esquema",
        "Prefiero que lo expliquen verbalmente y escuchar con atención",
        "Leer las instrucciones escritas de forma detenida",
        "Comenzar a intentarlo directamente para entender sobre la marcha",
    ),
    (
        "Creas diagramas, mapas mentales o esquemas visuales",
        "Escuchas grabaciones, repites en voz alta o discutes el tema con alguien",
        "Relees tus apuntes y resumes los puntos clave por escrito",
        "Resuelves muchos ejercicios y problemas de práctica",
    ),
    (
        "Ver un video tutorial o capturas de pantalla paso a paso",
        "Que alguien te explique mientras escuchas cómo funciona",
        "Leer la documentación o el manual de usuario",
        "Abrir el programa directamente y comenzar a explorar",
    ),
    (
        "Visualizas el diagrama, imagen o esquema que usaron en clase",
        "Recuerdas cómo lo explicaron o el tono con que se dijo",
        "Recuerdas lo que leíste o anotaste sobre ese tema",
        "Recuerdas haberlo practicado o aplicado en algún ejercicio",
    ),
    (
        "Dibujar un esquema o mostrarle una figura en el pizarrón o cuaderno",
        "Explicárselo verbalmente con ejemplos hablados",
        "Escribirle un resumen o darle un texto para que lea",
        "Mostrarle cómo hacerlo directamente, paso a paso",
    ),
    (
        "Buscas un diagrama de flujo o representación visual del proceso",
        "Hablas con alguien o buscas videos donde lo expliquen",
        "Buscas libros, artículos o documentación escrita",
        "Empiezas a probar soluciones directamente",
    ),
    (
        "Presentaciones con imágenes, gráficos y esquemas",
        "Podcasts, videos narrados o grabaciones de clases",
        "Resúmenes escritos, libros o artículos",
        "Ejercicios resueltos paso a paso o laboratorios prácticos",
    ),
    (
        "Buscar imágenes, infografías o videos para apoyarte visualmente",
        "Escuchar cómo otros exponen ese tema o explicarlo oralmente a alguien",
        "Leer sobre el tema y tomar notas organizadas",
        "Preparar una demostración o ejemplo real que puedas mostrar",
    ),
    (
        "Diseñar los esquemas visuales o la presentación final",
        "Coordinar las discusiones orales y exponer ante el grupo",
        "Redactar el informe o investigar en fuentes bibliográficas",
        "Construir el prototipo, demo o la parte práctica del proyecto",
    ),
    (
        "Ver documentales, infografías o videos visuales en YouTube",
        "Escuchar podcasts o audiolibros mientras haces otras cosas",
        "Leer artículos, libros o blogs especializados",
        "Probar cosas nuevas, hacer experimentos o pequeños proyectos",
    ),
    (
        "Te enfocas en los esquemas, diapositivas o la pizarra",
        "Escuchas atentamente la voz y las explicaciones del profesor",
        "Tomas apuntes detallados de todo lo que se dice",
        "Relacionas mentalmente la teoría con ejercicios o experiencias previas",
    ),
    (
        "Hacer un diagrama o mapa comparando las opciones visualmente",
        "Hablarlo con compañeros, profesores o familia y escuchar perspectivas",
        "Escribir una lista detallada de pros y contras de cada opción",
        "Basarte en tu experiencia vivida o en haber probado ambas opciones",
    ),
    (
        "Buscas un video o imagen que ilustre el concepto de otra forma",
        "Le preguntas directamente al profesor o a un compañero para escuchar "
        "otra explicación",
        "Buscas la misma información en libros o apuntes y la lees",
        "Intentas aplicarlo en un ejercicio para entenderlo de forma práctica",
    ),
    (
        "Visualizarla escrita o acompañada de un diagrama en una tarjeta",
        "Repetirla en voz alta o escucharla en un audio",
        "Escribirla varias veces y leer sus definiciones",
        "Aplicarla directamente en varios ejercicios hasta comprenderla",
    ),
    (
        "Ver un mapa mental de su sintaxis o un video con visualizaciones del código",
        "Escuchar tutoriales en video con explicaciones orales detalladas",
        "Leer la documentación oficial o un libro especializado",
        "Abrir un entorno de desarrollo y comenzar a escribir código desde el inicio",
    ),
)

assert len(ITEMS) == 16, "el instrumento VARK tiene 16 ítems (cap. 10)"
assert all(len(alts) == 4 for alts in ITEMS), "cada ítem tiene 4 alternativas"


def _construir_matriz() -> dict[str, tuple[int, str, str]]:
    """texto de la alternativa → (num_pregunta, letra, canal)."""
    matriz: dict[str, tuple[int, str, str]] = {}
    for i, alternativas in enumerate(ITEMS, start=1):
        for letra, canal, texto in zip("abcd", CANALES_EN_ORDEN, alternativas, strict=True):
            matriz[texto] = (i, letra, canal)
    return matriz


MATRIZ = _construir_matriz()

assert len(MATRIZ) == 64, (
    "las 64 alternativas deben ser textos distintos; si dos ítems comparten "
    "el texto exacto de una alternativa, el mapeo se vuelve ambiguo"
)

LETRAS = ("a", "b", "c", "d")

# (num_pregunta, letra) → canal. Es el mismo mapeo que MATRIZ pero indexado por
# posición, para el caso en que el cliente identifica la alternativa por su
# letra en vez de por su texto (ver `POST /api/diagnosticos`).
POR_POSICION: dict[tuple[int, str], str] = {
    (num, letra): canal for (num, letra, canal) in MATRIZ.values()
}


def canal_de(alternativa: str) -> tuple[int, str, str] | None:
    """Devuelve (num_pregunta, letra, canal) o None si el texto no está en la matriz."""
    return MATRIZ.get(alternativa.strip())


def canal_por_posicion(num_pregunta: int, letra: str) -> str | None:
    """Canal de la alternativa `letra` del ítem `num_pregunta`, o None si no existe.

    La API expone el cuestionario por posición y no por texto: el cliente marca
    "ítem 3, alternativa b" y es el servidor quien sabe que eso es el canal
    auditivo. Así la matriz de puntuación no se filtra al frontend, que es
    justamente lo que permite recalcular perfiles si la matriz cambia.
    """
    return POR_POSICION.get((num_pregunta, letra.strip().lower()))
