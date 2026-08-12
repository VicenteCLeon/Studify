"""Texto que ve el estudiante: enunciados, nombres de canal y glosas.

Vive aparte de los routers porque es **copy**, no lógica: se corrige leyéndolo
en pantalla, sin tocar el flujo. Y vive en `web/` y no en `vark/` porque nada de
esto interviene en la calificación — el motor VARK trabaja con las letras a/b/c/d
y con los canales V/A/R/K, no con estas cadenas.

⚠️ **Los enunciados son provisionales.** `vark/instrumento.py` guarda las 64
alternativas del instrumento (que son las que se puntúan) pero **no** el
enunciado de cada uno de los 16 ítems, porque para calificar no hace falta. Los
enunciados reales están en el encabezado de `data/data_cuestionarios_43.csv`, el
export de Google Forms con el que se aplicó el cuestionario; ese archivo no está
versionado y no existe en todas las máquinas del equipo. Los textos de abajo son
una redacción equivalente, reconstruida desde las alternativas de cada ítem,
para que la UI de la Fase 4 pueda mostrarse. **Hay que reemplazarlos por los
originales del CSV antes de aplicar el instrumento a estudiantes nuevos**, o los
43 diagnósticos ya cargados y los que entren por la web no habrán respondido
exactamente la misma pregunta. Pendiente n.º 6 de AVANCE.md §6.
"""

# Un enunciado por ítem, en el mismo orden que `instrumento.ITEMS`.
ENUNCIADOS: tuple[str, ...] = (
    "Cuando necesitas aprender un concepto nuevo en clases, prefieres:",
    "Cuando el profesor da instrucciones complejas para una tarea, lo primero que haces es:",
    "Para estudiar para un examen difícil, normalmente:",
    "Si tienes que aprender a usar un programa de software nuevo, prefieres:",
    "Cuando recuerdas algo que te enseñaron bien, es porque:",
    "Para explicarle algo a un compañero que no entiende, prefieres:",
    "Cuando tienes que resolver un problema técnico en tu carrera, normalmente:",
    "¿Qué tipo de material de estudio te resulta más útil cuando estudias solo?",
    "Si debes exponer sobre un tema que no manejas bien, lo primero que haces es:",
    "En un trabajo grupal, el rol que adoptas más naturalmente es:",
    "Cuando tienes tiempo libre para aprender algo por curiosidad, prefieres:",
    "Cuando asistes a una clase larga, ¿qué haces para mantener la atención?",
    "Si tienes que tomar una decisión importante de estudio (por ejemplo, elegir una especialidad), prefieres:",
    "Cuando te pierdes en una clase y no entiendes algo, normalmente:",
    "Para memorizar una fórmula o concepto abstracto en ingeniería, prefieres:",
    "Si quisieras aprender un nuevo lenguaje de programación, preferirías:"
)

# --- Cómo se le nombra al estudiante cada pieza de su perfil ------------------

NOMBRE_CANAL = {
    "V": "Visual",
    "A": "Auditivo",
    "R": "Lectura / Escritura",
    "K": "Kinestésico",
}

# Color de la barra de cada canal en la pantalla de perfil. Está acá y no en el
# CSS porque el orden de los canales lo decide el servidor.
COLOR_CANAL = {
    "V": "#3b82f6",
    "A": "#f59e0b",
    "R": "#10b981",
    "K": "#ef4444",
}

# Qué implica cada canal, redactado como lo que el sistema va a hacer con esa
# preferencia y no como un rasgo de personalidad: el perfil VARK describe cómo
# se presenta el material, no cómo es el estudiante.
EXPLICACION_CANAL = {
    "V": (
        "Procesas mejor la información cuando puede verse ordenada en el espacio. "
        "Tus cápsulas incluirán tablas comparativas y esquemas que muestren cómo "
        "se relacionan los conceptos entre sí."
    ),
    "A": (
        "Aprendes mejor cuando la explicación suena a conversación. Tus cápsulas "
        "se redactarán en un registro oral, con analogías cotidianas y preguntas "
        "que te inviten a responder mentalmente."
    ),
    "R": (
        "Prefieres la información presentada en palabras. Tus cápsulas usarán "
        "encabezados jerárquicos, definiciones exactas y un glosario con los "
        "términos clave del tema."
    ),
    "K": (
        "Aprendes haciendo. Tus cápsulas incluirán un ejemplo resuelto, una "
        "secuencia paso a paso y una actividad de aplicación para cerrar."
    ),
}

EXPLICACION_MULTIMODAL = (
    "Además, ningún canal domina con claridad sobre los demás: tus cápsulas "
    "combinarán los distintos registros en proporciones parecidas en vez de "
    "apoyarse en uno solo."
)

# `tono_narrativo` de la tabla 17.4 → cómo describirlo en pantalla.
NOMBRE_TONO = {
    "oral": "conversacional",
    "formal": "formal y preciso",
    "practico": "directo y orientado a la acción",
    "espacial": "organizado por relaciones entre conceptos",
    "mixto": "equilibrado entre los cuatro registros",
}

# Las directivas de `vark/rules.py` son identificadores para el prompt maestro;
# acá se traducen a algo legible. Se consultan con `.get(d, ...)` para que
# agregar una directiva nueva al motor nunca rompa esta pantalla.
GLOSA_DIRECTIVA = {
    "incluir_mapa_conceptual": "Esquema con la jerarquía de conceptos",
    "tabla_comparativa": "Tabla comparativa",
    "estructura_jerarquica": "Contenido ordenado de lo general a lo particular",
    "recurso_visual_complementario": "Un recurso visual de apoyo",
    "encabezados_jerarquicos": "Encabezados en cada bloque",
    "definiciones_exactas": "Definiciones textuales del material",
    "glosario": "Glosario de términos clave",
    "tono_oral": "Redacción conversacional",
    "analogias_cotidianas": "Analogías con situaciones cotidianas",
    "preguntas_reflexivas": "Preguntas para responder mentalmente",
    "ejemplo_resuelto": "Ejemplo resuelto",
    "paso_a_paso": "Secuencia paso a paso",
    "actividad_aplicada": "Actividad de aplicación al cierre",
}


def glosa_directiva(directiva: str) -> str:
    return GLOSA_DIRECTIVA.get(directiva, directiva.replace("_", " ").capitalize())
