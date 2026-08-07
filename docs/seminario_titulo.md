# GENERACIÓN DE MICRO-APRENDIZAJE EDUCATIVO MEDIANTE IA GENERATIVA, BASADO EN ESTILOS DE APRENDIZAJE DEL ESTUDIANTE

**Patricio Elías Hernández Vergara**
**Vicente Antonio Cisternas León**

**Profesor Guía:** Sandra Patricia Cano Mazuera

*Informe de Avance Seminario de Título*
*Ingeniería en Informática*
*Escuela de Ingeniería Informática — Pontificia Universidad Católica de Valparaíso*
*Abril 2026*

---

## Resumen

Las plataformas de aprendizaje en línea tradicionales se basan mayoritariamente en modelos de enseñanza que son rígidos y homogéneos, empleando un enfoque de "talla única" lo que obliga a los estudiantes a adaptarse al sistema. Esta omisión de las características individuales de cada persona y estilos de aprendizaje genera una sobrecarga cognitiva y una pérdida de interés en los alumnos. Adicionalmente, intentar superar esta inflexibilidad pedagógica mediante la creación manual de recursos adaptativos representa un proceso logístico desproporcionado e inescalable para los equipos docentes.

Para abordar estos desafíos, este trabajo propone el diseño de una arquitectura tecnológica orientada a la generación automatizada de micro-aprendizaje educativo, apoyada por Inteligencia Artificial Generativa. La solución integra un módulo de diagnóstico basado en el modelo VARK para perfilar al estudiante y adaptar dinámicamente el formato y la estrategia instruccional del contenido. Para garantizar la exactitud de la información y mitigar las alucinaciones algorítmicas, el sistema implementa una arquitectura de Generación Aumentada por Recuperación (RAG), la cual ancla la generación de material exclusivamente a las fuentes oficiales e institucionales del curso.

Las conclusiones preliminares y el análisis empírico indican que la integración de micro-aprendizaje adaptativo se espera que el sistema contribuya a mejorar la retención del conocimiento y fomentar el aprendizaje autónomo de manera efectiva. Se espera que la implementación del prototipo funcional diseñado reduzca significativamente la carga operativa de los profesores, al tiempo que transforma la entrega de contenidos hacia una experiencia educativa altamente personalizada, escalable y tecnológicamente confiable.

**Palabras clave:** Micro-aprendizaje, Inteligencia Artificial Generativa, Arquitectura RAG, Estilos de Aprendizaje, Personalización Educativa.

## Abstract

Traditional online learning platforms are largely based on rigid, one-size-fits-all teaching models, forcing students to adapt to the system. This failure to account for individual characteristics and learning styles leads to cognitive overload and a loss of interest among students. Additionally, attempting to overcome this pedagogical inflexibility by manually creating adaptive resources represents a disproportionate and unscalable logistical process for teaching teams.

To address these challenges, this work proposes the design of a technological architecture geared toward the automated generation of educational micro-learning, supported by Generative Artificial Intelligence. The solution integrates a diagnostic module based on the VARK model to profile the student and dynamically adapt the format and instructional strategy of the content. To ensure the accuracy of the information and mitigate algorithmic hallucinations, the system implements a Retrieval-Augmented Generation (RAG) architecture, which anchors the generation of material exclusively to the course's official and institutional sources.

Preliminary findings and empirical analysis indicate that the integration of adaptive micro-learning effectively improves knowledge retention and promotes self-directed learning. The implementation of the designed functional prototype is expected to significantly reduce the operational burden on teachers, while transforming content delivery into a highly personalized, scalable, and technologically reliable educational experience.

**Keywords:** Microlearning, Generative Artificial Intelligence, RAG Architecture, Learning Styles, Educational Personalization.

---

## Índice General

1. Introducción
2. Descripción del Problema
3. Justificación
   3.1 Escalabilidad Técnica y Operativa
   3.2 Pertinencia y Adaptabilidad Pedagógica
   3.3 Calidad, Control y Mitigación de Riesgos
   3.4 Relevancia y Respaldo Empírico
4. Definición de Objetivos
   4.1 Objetivo General
   4.2 Objetivos Específicos
5. Planificación
6. Marco Teórico y Estado del Arte
   6.1 Marco Conceptual (Conceptos Claves)
   6.2 Estado del Arte
7. Diseño de la Arquitectura Tecnológica Propuesta
   7.1 Visión General del Sistema
   7.2 Módulo de Caracterización del Estudiante
   7.3 Arquitectura RAG: Recuperación de Información
   7.4 Motor de Generación Adaptativa (LLM & Prompting)
   7.5 Stack Tecnológico Preliminar
8. Metodología de Evaluación y Validación
   8.1 Evaluación de la Calidad Técnica del Contenido (Métricas RAG)
   8.2 Validación de la Adaptabilidad Pedagógica (Alineación VARK)
   8.3 Evaluación de la Experiencia de Usuario (Modelo TAM)
   8.4 Impacto en la Carga Docente
   8.5 Plan de evaluación del prototipo funcional
   8.6 Limitaciones del estudio
9. Caracterización de la Muestra y Datos Sociodemográficos
10. Flujo de Diagnóstico y Procesamiento del Modelo VARK
11. Definición de Estándares Estructurales de la Microcápsula y Reglas de Mapeo VARK
    11.1 Estándares del micro-contenido
    11.2 Reglas de mapeo del perfil VARK y tipos de micro-contenidos
12. Definición de la Base de Conocimiento
13. Justificación del Modelo de Base de Datos
14. Herramientas y Librerías (Stack Tecnológico)
15. Flujo de LlamaIndex en el RAG Estructurado
16. Análisis de Resultados del Diagnóstico VARK
    16.1 Definición sociodemográfica de la muestra
    16.2 Distribución de perfiles VARK
    16.3 Análisis de puntajes promedio por dimensión
    16.4 Implicaciones para el parámetro por defecto del sistema RAG
17. Modelo Lógico de la Base de Datos Relacional
    17.1 Entidades de caracterización del estudiante
    17.2 Representación Derivada de la Jerarquía de Canales
    17.3 Vinculación con la Generación de Contenido y Trazabilidad
    17.4 Diccionario de datos
18. Arquitectura de la Solución y Modelo de Procesos
19. Conclusiones

---

## 1. Introducción

Este documento tiene como enfoque principal estructurar el desarrollo de un modelo tecnológico para la creación de micro-aprendizaje educativo apoyado por Inteligencia Artificial generativa, diseñado específicamente para adaptarse a los estilos de aprendizaje de cada estudiante.

A través de esta propuesta, se busca dar respuesta a la creciente necesidad de contar con materiales de estudio que sean breves, frecuentes y focalizados, estos tienen como foco principal el fomentar el aprendizaje autónomo. Para ello, el informe plantea abordar estratégicamente dos grandes desafíos actuales:

- Actualmente la producción manual de cápsulas educativas personalizadas es un proceso costoso, poco escalable y difícil de mantener actualizado. El enfoque del proyecto es utilizar IA generativa para automatizar la creación de múltiples recursos adaptados a las preferencias pedagógicas del alumno, resolviendo el cuello de botella de la producción manual.
- Resolver el problema crítico de la exactitud del contenido generado por IA —como las alucinaciones o la falta de coherencia— el proyecto se enfoca en la implementación de una arquitectura RAG (Retrieval-Augmented Generation). Esto asegurará que el micro-aprendizaje se ancle estrictamente en las bases de conocimiento oficiales del curso, garantizando la calidad y trazabilidad de la información.

En síntesis, este informe traza una hoja de ruta metodológica que busca ser clara, la que abarca desde el diseño de la arquitectura y la caracterización del estudiante, hasta la implementación y evaluación de un prototipo funcional. El objetivo final es sentar las bases para una herramienta que transforme la entrega de contenidos, pasando de un modelo estático a una experiencia educativa que sea altamente personalizada, dinámica y tecnológicamente confiable.

---

## 2. Descripción del Problema

En los últimos años, el acceso y la distribución de contenidos educativos digitales han experimentado un crecimiento exponencial; sin embargo, la inmensa mayoría de las plataformas e-learning continúan basándose en modelos de enseñanza rígidos y homogéneos. En estos esquemas tradicionales de "talla única", todos los estudiantes reciben exactamente los mismos contenidos, expuestos en idénticos formatos y secuencias, obligándolos a adaptarse a la plataforma en lugar de que la tecnología se adapte a ellos. Como advierte la literatura reciente, "los sistemas educativos tradicionales suelen adoptar un enfoque de 'talla única', que no logra satisfacer las diversas necesidades y ritmos de aprendizaje de cada estudiante" (Suazo-Galdames and Chaple-Gil, 2025). Esta omisión de las características individuales, de los conocimientos previos y de los ritmos de progreso limita severamente la efectividad del proceso educativo, ya que "a todos los estudiantes se les suele dar los mismos materiales de clase, independientemente de su comprensión, ritmo de aprendizaje o estilo de aprendizaje personal" (Hashiyada et al., 2025).

Como consecuencia se genera una sobrecarga cognitiva o, por el contrario, una pérdida de interés, escenarios especialmente críticos en la era post-pandemia donde los formatos extensos han demostrado su ineficiencia. Se ha observado que los formatos tradicionales fallan al retener la atención, pues "los estudiantes a menudo muestran desinterés en ver conferencias grabadas que duran de 50 a 75 minutos, y los vídeos de conferencias más largos provocan tasas de deserción más altas" (Saha et al., 2025). Como respuesta a estas limitaciones, enfoques como el micro-aprendizaje han emergido y demostrado ser altamente efectivos para mejorar tanto la retención de conocimiento como la motivación del alumno. Al presentar la información estructurada en unidades pequeñas, modulares y focalizadas, se facilita la asimilación de conceptos. No obstante, en su implementación práctica actual, la arquitectura de estos sistemas suele ser estática, predefinida y carente de verdadera interactividad adaptativa. Los flujos de estudio son cerrados, lo que restringe drásticamente la capacidad de la plataforma para responder de forma dinámica y reconfigurar la ruta de enseñanza según el rendimiento en tiempo real o las necesidades específicas de cada estudiante.

Superar esta barrera de inflexibilidad y lograr una personalización auténtica representa un desafío de ingeniería sustancial. Requiere la capacidad de generar, curar y adaptar masivamente el material educativo para que responda a múltiples perfiles y estilos de aprendizaje. Sin embargo, depender exclusivamente de la creación y actualización manual de todas estas variaciones de contenido resulta ser un proceso completamente inescalable a nivel de desarrollo de software, dado que "la creación de materiales de microaprendizaje puede consumir mucho tiempo para los educadores" (Saha et al., 2025). Este enfoque tradicional exige un esfuerzo logístico desproporcionado y supone una carga de trabajo inasumible para los equipos docentes, haciendo evidente la necesidad de incorporar arquitecturas tecnológicas automatizadas que puedan estructurar y entregar el conocimiento de manera dinámica, mitigando riesgos técnicos como la desactualización o la falta de profundidad en los materiales base.

---

## 3. Justificación

El desarrollo de un modelo tecnológico para la generación de micro-aprendizaje adaptativo se fundamenta en cuatro pilares críticos que abordan tanto las deficiencias pedagógicas actuales como los desafíos de la ingeniería de software educativo:

### 3.1 Escalabilidad Técnica y Operativa

La creación manual de recursos educativos diversificados (tales como explicaciones breves, quizzes, ejemplos, videos, audios o tarjetas de estudio) representa un cuello de botella logístico insostenible para los equipos docentes. La integración de Inteligencia Artificial generativa resuelve este problema al permitir la producción automatizada y rápida de múltiples cápsulas de contenido. Tal como señala la literatura de investigación, "la creación de materiales de microaprendizaje puede consumir mucho tiempo para los educadores. Sin embargo, la IA generativa [...] puede agilizar este proceso generando resúmenes personalizados, tarjetas didácticas y cuestionarios adaptados a temas específicos" (Saha et al., 2025). Esto democratiza el acceso a material de apoyo constante y personalizado sin sobrecargar los limitados recursos de tiempo del profesorado, ya que el uso de estas plataformas tecnológicas "proporciona retroalimentación y evaluación en tiempo real, lo que ha demostrado reducir la carga de trabajo de los profesores en casi un 40%, permitiendo interacciones más significativas entre estudiante y profesor" (Suazo-Galdames and Chaple-Gil, 2025).

### 3.2 Pertinencia y Adaptabilidad Pedagógica

El modelo tradicional de aprendizaje homogéneo no atiende la diversidad cognitiva de los alumnos. Como advierten investigaciones recientes, "en la educación escolar moderna, a todos los estudiantes se les suele dar los mismos materiales de clase, independientemente de su comprensión, ritmo de aprendizaje o estilo de aprendizaje personal", lo cual se traduce en un "enfoque uniforme que no satisface las necesidades de todos los estudiantes" (Hashiyada et al., 2025). Al incorporar la variable de los estilos o preferencias de aprendizaje (por ejemplo, priorizando aproximaciones visuales o verbales), el sistema propuesto permite que el contenido se ajuste dinámicamente en su formato y estrategia instruccional. Esta personalización aumenta significativamente la relevancia percibida por el estudiante y aborda la carga cognitiva, puesto que "este enfoque implica desglosar temas complejos en fragmentos pequeños y manejables, lo que facilita que los estudiantes los absorban y retengan" (Saha et al., 2025).

### 3.3 Calidad, Control y Mitigación de Riesgos

El uso de modelos de lenguaje en la educación conlleva el riesgo inherente de las alucinaciones algorítmicas, un fenómeno donde "los LLM a veces crean información incorrecta" (Hashiyada et al., 2025). La implementación de una arquitectura RAG (Retrieval-Augmented Generation) justifica este proyecto desde la perspectiva de la seguridad y exactitud de la información. Al anclar el proceso generativo exclusivamente en las fuentes oficiales del curso (apuntes, guías y bibliografía validada), se disminuyen drásticamente los errores factuales. Esto se fundamenta en que, "a diferencia de los LLM estándar, que dependen únicamente de su conocimiento preentrenado, RAG primero recupera documentos relevantes de una base de conocimientos externa antes de generar respuestas" (Li et al., 2025). Al respecto, los estudios aseguran que "este enfoque mejora la precisión de los hechos, la frescura del conocimiento y la transparencia, haciéndolo particularmente adecuado para aplicaciones educativas donde la información precisa y verificable es crucial" (Li et al., 2025).

### 3.4 Relevancia y Respaldo Empírico

El consumo de micro-aprendizaje vinculado a herramientas de IA generativa es un fenómeno que está en constante crecimiento en los medios digitales, y existe evidencia reciente que lo relaciona positivamente con las tasas de adopción tecnológica. Estudios basados empíricamente en el Modelo de Aceptación de la Tecnología revelan que "una mayor calidad percibida del contenido de microaprendizaje se asocia positivamente con la utilidad percibida y la facilidad de uso percibida de la IA generativa" (Liu and Mao, 2026). Es fundamental fomentar una alta calidad en los materiales, dado que estas percepciones "contribuyen a actitudes más favorables hacia la IA generativa, lo que a su vez predice intenciones de comportamiento más fuertes de usar y recomendar la tecnología" (Liu and Mao, 2026). Por lo tanto, resulta imperativo estudiar y mejorar su diseño desde un enfoque académico formal. Este proyecto no solo responde a una tendencia del mercado, sino que aporta un marco estructurado para garantizar que esta adopción tecnológica se traduzca en mejoras que sean medibles en el rendimiento educativo.

---

## 4. Definición de Objetivos

### 4.1 Objetivo General

Desarrollar un prototipo funcional de generación de micro-aprendizaje educativo mediante IA generativa, adaptado a los perfiles de aprendizaje VARK del estudiante y sustentado en una arquitectura RAG estructurada con fuentes institucionales trazables.

### 4.2 Objetivos Específicos

1. Realizar una revisión bibliográfica de conceptos relacionados con micro-aprendizaje, IA generativa, estilos de aprendizaje y arquitectura RAG.
2. Diseñar una arquitectura que permita la generación de contenido basado en los estilos de aprendizaje del estudiante.
3. Definir el método de caracterización del estudiante (instrumento y variables): selección y adaptación de un cuestionario/estrategia para capturar estilo/preferencia de aprendizaje, y reglas de mapeo de ese perfil a tipos de micro-contenidos (formato, tono, nivel de dificultad, tipo de actividad).
4. Implementar un prototipo funcional de generación de micro-aprendizaje compuesto por una base de conocimiento relacional, un mecanismo de recuperación estructurada mediante consultas SQL, un motor de generación basado en LLM, plantillas de microcápsulas, reglas de adaptación VARK y registro de fuentes para trazabilidad.
5. Evaluar el prototipo mediante métricas de calidad (exactitud en base a las fuentes, coherencia pedagógica, legibilidad) y una validación con usuarios (docentes y estudiantes) para medir utilidad percibida y adecuación al estilo de aprendizaje.

---

## 5. Planificación

Este apartado da a conocer la planificación estratégica del proyecto, estableciendo las fases clave y los hitos fundamentales del proyecto. Mediante la Carta Gantt, se visualiza la secuencia de actividades, permitiendo una gestión eficiente de los tiempos para así garantizar el cumplimiento de los objetivos en los plazos previstos.

| # | Nombre | Duración | Inicio | Terminado |
|---|--------|----------|--------|-----------|
| 1 | **Estudio del estado del arte** | 68 days? | 08-01-26, 07:00 | 14-04-26, 08:00 |
| 2 | Lectura de papers científicos | 17 days? | 08-01-26, 07:00 | 30-01-26, 17:00 |
| 3 | Reunión con Profesora guía | 0 days | 30-03-26, 07:00 | 30-03-26, 08:00 |
| 4 | Definir instrumentos de... | 21 days? | 02-03-26, 07:00 | 30-03-26, 17:00 |
| 5 | Reunión con Profesora guía | 0 days | 06-04-26, 08:00 | 06-04-26, 08:00 |
| 6 | Definición del problema | 26 days? | 06-04-26, 07:00 | 06-04-26, 17:00 |
| 7 | Reunión con Profesora guía | 0 days | 14-04-26, 08:00 | 14-04-26, 08:00 |
| 8 | Definición de la arquitectura | 15 days? | 23-03-26, 07:00 | 10-04-26, 17:00 |
| 9 | **HITO: ENTREGA AVANCE I** | 0 days | 17-04-26, 12:45 | 17-04-26, 13:00 |
| 10 | **HITO: PRESENTACIÓN AVANCE** | 0 days | 21-04-26, 08:00 | 21-04-26, 08:00 |
| 11 | **Desarrollo e Implementación** | 41 days? | 23-04-26, 08:00 | 18-06-26, 17:00 |
| 12 | Analizar feedback recibido | 6 days? | 23-04-26, 08:00 | 30-04-26, 17:00 |
| 13 | Implementar cambios | 6 days? | 23-04-26, 08:00 | 30-04-26, 17:00 |
| 14 | Desarrollo de pipeline | 11 days? | 01-05-26, 08:00 | 15-05-26, 17:00 |
| 15 | Evaluación de la experiencia | 11 days? | 15-05-26, 08:00 | 29-05-26, 17:00 |
| 16 | Desarrollar Informe Final | 14 days? | 30-05-26, 08:00 | 18-06-26, 17:00 |
| 17 | **HITO: ENTREGA INFORME** | 0 days | 19-06-26, 12:45 | 19-06-26, 13:00 |
| 18 | **HITO: EVALUACIÓN PRESENTACIÓN** | 0 days | 30-06-26, 08:00 | 30-06-26, 08:00 |

*(Nota: las figuras originales 5.1 a 5.4 corresponden a la representación gráfica de esta Carta Gantt).*

---

## 6. Marco Teórico y Estado del Arte

Este apartado establece las bases conceptuales que sustentan la investigación y revisa la literatura científica reciente para lograr identificar los avances y brechas actuales en la generación automatizada de material educativo.

### 6.1 Marco Conceptual (Conceptos Claves)

**Micro-aprendizaje (Microlearning):**
Según Luo y Li (2025), en los últimos años el microlearning ha surgido como un enfoque prometedor para el desarrollo de habilidades. A diferencia de la instrucción convencional basada en clases magistrales, que normalmente presenta información en sesiones extensas que pueden provocar sobrecarga cognitiva, el microlearning divide el aprendizaje en unidades pequeñas, más fáciles de procesar y retener. La literatura reciente define este concepto como "una serie de lecciones o módulos de aprendizaje electrónico en porciones pequeñas, elaborados meticulosamente para impartir conocimientos o habilidades enfocados en ráfagas cortas" (Liu and Mao, 2026). Este enfoque "se alinea bien con las necesidades de los estudiantes modernos, que a menudo se enfrentan a distracciones y tienen períodos de atención más cortos" (Saha et al., 2025).

Este método se conecta con teorías del aprendizaje cognitivo, como la repetición espaciada, la teoría de la carga cognitiva y el aprendizaje experiencial. En conjunto, estos principios respaldan la idea de que el microlearning facilita una mejor retención del conocimiento. Además, "el microaprendizaje puede salvar de manera efectiva la brecha entre el conocimiento teórico y la aplicación práctica al proporcionar contenido directamente aplicable a escenarios del mundo real" (Saha et al., 2025). No obstante, aunque el microlearning ha sido ampliamente adoptado en la educación técnica, su potencial para el desarrollo de competencias transversales en estudiantes universitarios aún requiere exploración profunda.

**Teoría de Carga Cognitiva y Estilos de Aprendizaje:**
Marco psicológico que estudia la capacidad limitada de la memoria humana. Para que el aprendizaje sea efectivo, la instrucción debe diseñarse reduciendo la carga innecesaria. Esto se complementa con los estilos de aprendizaje (como el modelo VARK), que sugieren que los estudiantes asimilan mejor la información cuando se presenta en formatos alineados a sus preferencias, ya sea visual, auditivo, lectura/escritura o kinestésico.

**Inteligencia Artificial Generativa y LLMs:**
Un modelo de lenguaje grande (LLM) es un modelo de lenguaje con una enorme cantidad de parámetros que pasa por tareas de preentrenamiento, como el modelado de lenguaje enmascarado y la predicción autorregresiva, para comprender y procesar el lenguaje humano, modelando la semántica contextualizada del texto y sus probabilidades a partir de grandes cantidades de datos textuales. Un LLM competente debe contar con cuatro características clave: primero, una comprensión profunda del contexto del lenguaje natural; segundo, capacidad para generar texto similar al humano; tercero, conciencia contextual, especialmente en dominios intensivos en conocimiento; y cuarto, una sólida capacidad para seguir instrucciones, lo que resulta útil para la resolución de problemas y la toma de decisiones. Existen varios LLM que fueron desarrollados y lanzados en 2023, alcanzando una popularidad significativa, entre ellos ChatGPT de OpenAI, LLaMA de Meta AI y Dolly 2.0 de Databricks. Actualmente, los LLM ofrecen una amplia variedad de aplicaciones versátiles en distintos dominios, incluyendo motores de búsqueda, atención al cliente, traducción, generación de código, atención sanitaria, finanzas y educación, demostrando su adaptabilidad y potencial para agilizar tareas relacionadas con el lenguaje en diversas industrias y contextos (Yao et al., 2024).

**Arquitectura RAG (Retrieval-Augmented Generation):**
La generación aumentada por recuperación (RAG) es el proceso de optimización de la salida de un modelo de lenguaje de gran tamaño, de modo que haga referencia a una base de conocimientos autorizada fuera de los orígenes de datos de entrenamiento antes de generar una respuesta. La RAG extiende las ya poderosas capacidades de los LLM a dominios específicos o a la base de conocimiento interna de una organización, todo ello sin la necesidad de volver a entrenar el modelo. Se trata de un método rentable para mejorar los resultados de los LLM de modo que sigan siendo relevantes, precisos y útiles en diversos contextos (Amazon Web Services, n.d.).

### 6.2 Estado del Arte

Una vez definidos los conceptos estructurales, se procedió a analizar la literatura científica actual para evaluar las implementaciones recientes en la intersección de estas tecnologías.

**Evolución del Micro-aprendizaje Adaptativo**
La investigación reciente demuestra que el micro-aprendizaje debe trascender la simple fragmentación. Sortwell et al. (2026) señalan que el diseño instruccional debe considerar la autorregulación y el "estado de preparación" (readiness) del estudiante para ser efectivo. Esta necesidad de adaptación es respaldada por Suazo-Galdames y Chaple-Gil (2025), quienes, en una revisión empírica, concluyeron que las plataformas adaptativas impulsadas por IA mejoran el rendimiento y reducen la carga docente, siempre que ofrezcan rutas estrictamente alineadas al currículo. Asimismo, Luo y Li (2025) demostraron experimentalmente que el micro-aprendizaje flexible es capaz de desarrollar competencias transversales sin sobrecargar asignaturas obligatorias.

**Generación de Contenidos mediante IA y Barreras de Adopción**
Para resolver la escalabilidad de estos sistemas, la IA generativa se ha posicionado como la herramienta principal. Saha et al. (2025) lograron automatizar la creación de microcontenidos procesando 150 minutos de clases en solo 45 minutos usando GPT-4o, logrando un 80% de compromiso estudiantil. Por su parte, Hang et al. (2024) desarrollaron MCQGen, un sistema que adapta la dificultad de preguntas de opción múltiple en tiempo real mediante prompting avanzado. A pesar de estos éxitos técnicos, la adopción enfrenta desafíos. Liu y Mao (2026) identificaron que la "amenaza a la identidad frente a la IA" reduce significativamente la intención de uso en estudiantes, evidenciando que el software educativo debe diseñarse desde una perspectiva empática que no amenace el estatus o la originalidad del usuario mismo.

**Implementación de RAG como Estándar Técnico Educativo**
Para implementar LLMs en educación de forma segura, la evidencia apunta unánimemente a la arquitectura RAG. Li et al. (2025) establecen que RAG es el estándar para mitigar alucinaciones y permitir la actualización dinámica de los planes de estudio. Tural et al. (2024) demostraron la superioridad de la recuperación semántica vectorial frente a métodos de búsqueda tradicionales. Además, el campo evoluciona rápidamente hacia el "RAG Modular" (Gao et al., 2024), que permite flujos de trabajo reconfigurables ideales para ecosistemas educativos complejos. Sin embargo, Hashiyada et al. (2025) advierten empíricamente sobre el punto crítico de esta tecnología: si los documentos inyectados en la base de conocimiento no son rigurosamente curados y estructurados, el sistema ignorará los datos institucionales, reduciendo su precisión drásticamente, lo que subraya la importancia del chunking y la curación de información.

Si bien la literatura reconoce el valor de la recuperación semántica vectorial en escenarios abiertos, el presente proyecto adopta un enfoque de RAG estructurado sobre base de datos relacional, debido a que el contexto educativo requiere mayor control curricular, trazabilidad explícita de las fuentes y recuperación determinista de fragmentos validados.

**Tabla 6.1 — Resumen del Estado del Arte**

| ID | Referencia (Autor, Año) | Eje temático / Palabras clave | Problema y Objetivo | Metodología y Muestra | Hallazgos Principales | Limitaciones del Estudio | Aporte y Citas Útiles |
|----|---|---|---|---|---|---|---|
| 1 | Saha, S. et al. (2025). *NextGen Education: Enhancing AI for Microlearning* | IA, microlearning y automatización. Microlearning, ChatGPT, Whisper | Los videos largos causan desinterés. Explorar la automatización de microlearning con IA | Encuestas; flujo Whisper + GPT-4o + quizzes; n=650 estudiantes | Percepción positiva generalizada; mayor engagement en cursos aplicados (80%); procesó 150 min de video en 45 min | Encuestas de autopercepción en vez de notas reales | Propuesta escalable para crear microlearning |
| 2 | Li, Z. et al. (2025). *Retrieval-augmented generation for educational application: A systematic survey* | IA en la educación, RAG, personalización | LLMs presentan alucinaciones y conocimiento estático. Revisión sistemática de RAG en educación | Revisión sistemática (WoS, Google Scholar); 51 artículos (2020-2025) | RAG mejora precisión factual y actualización dinámica; uso en chatbots, evaluación y admisiones | Depende de la calidad de la BD recuperada; costos computacionales elevados | Base teórica sólida para flujos RAG |
| 3 | Liu, X., & Mao, Z. (2026). *Micro-learning of generative AI on digital media...* | Adopción de IA, micro-aprendizaje en redes sociales; GenAI, AI identity threat | No se comprenden barreras psicosociales de adopción de IA. Examinar influencia de tutoriales y amenaza a la identidad | Estudio cuantitativo transversal (TAM, SEM); n=513 estudiantes de música en China | Micro-aprendizaje se asocia a percibir GenAI como útil; la "amenaza a la identidad frente a la IA" reduce intención de uso | Estudio transversal restringido a estudiantes de música en China | Freno sociológico clave en profesiones creativas |
| 4 | Suazo-Galdames, I. C., & Chaple-Gil, A. M. (2025). *AI-Powered Adaptive Learning...* | Impacto de IA adaptativa; sistemas adaptativos, personalización, analítica | Brechas y falta de marcos estandarizados en IA. Mapear evidencia de implementación e impacto empírico | Revisión exploratoria sistemática (PRISMA-ScR); 14 estudios empíricos | IA adaptativa genera mejoras significativas en rendimiento; reduce carga docente en casi un 40% | Escasa representación de América Latina; heterogeneidad en diseños | Valida empíricamente que IA adaptativa mejora resultados cognitivos |
| 5 | Hang, C. N. et al. (2024). *MCQGen: A Large Language Model-Driven MCQ Generator...* | Evaluación educativa, IA generativa, RAG; prompt engineering | Creación de MCQs consume mucho tiempo. Automatizar creación de MCQs mediante GPT-4 y RAG | Arquitectura GPT-4 + RAG; evaluación humana y por IA; base de 605 preguntas | Preguntas con excelente fluidez y relevancia; dificultad adaptativa exitosa; debilidades matemáticas | Muestra muy reducida; uso exclusivo de GPT-4 | Modelo arquitectónico sólido con RAG y prompting iterativo |
| 6 | Hashiyada, K. et al. (2025). *A Framework for Using LLMs and RAG...* | IA Generativa para materiales VARK; LLM, RAG, VARK Style | Diapositivas carecen de profundidad. Framework con RAG para generar materiales VARK | Framework de 5 pasos en plataforma Dify; diapositivas y material empresarial | RAG redujo alucinaciones; precisión depende críticamente de curación de documentos inyectados | Aún no verificado en un entorno real con estudiantes | Flujo claro de ingeniería y advertencia sobre curación RAG |
| 7 | Sortwell, A. et al. (2026). *Beyond Cognitive Load Theory...* | Psicopedagogía y Diseño Instruccional; Cognitive Load Theory, Self-regulation | CLT tradicional omite motivación y autorregulación. Proponer marco expandido holístico | Revisión sistemática en neurociencia; diversos estudios de caso | Aprendizaje requiere compromiso emocional; considerar estado de preparación (readiness) | Requiere validaciones empíricas más extensas | Base psicopedagógica para justificar adaptación |
| 8 | Luo, H., & Li, W. (2025). *Impact of microlearning on developing soft skills...* | Competencias transversales; Microlearning, Soft skills, Interdisciplinary | Difícil integración de habilidades blandas en carreras técnicas. Evaluar efectividad de micro-aprendizaje | Diseño experimental pre-test/post-test; estudiantes universitarios multi-facultad (China) | Mejoró significativamente autopercepción en habilidades blandas sin afectar materias troncales | Depende de datos auto-reportados | Valida versatilidad del micro-aprendizaje |
| 9 | Tural, B. et al. (2024). *Retrieval-Augmented Generation (RAG) and LLM Integration* | Sostenibilidad y RAG; RAG, LLMs, Information Retrieval | Costo ecológico y técnico de reentrenar LLMs. Analizar RAG como solución sostenible | Revisión analítica de literatura; revisión teórica | RAG evita reentrenamiento, es altamente sostenible; evolución hacia "Modular RAG" y "Corrective RAG" | No presenta pruebas de rendimiento cuantitativas propias | Argumento de viabilidad económica y ambiental |
| 10 | Gao, Y. et al. (2024). *Retrieval-Augmented Generation for Large Language Models: A Survey* | Marcos de evaluación RAG; RAG, LLMs, Hallucination | LLMs alucinan en tareas de conocimiento. Examen detallado de progresión de paradigmas RAG | Survey sistemático; +100 estudios y 50 datasets | Evolución: Naive RAG, Advanced RAG, Modular RAG; recuperación iterativa necesaria para complejidad | Faltan métricas estandarizadas maduras para RAG | Documento fundacional para estructurar marcos teóricos RAG |

---

## 7. Diseño de la Arquitectura Tecnológica Propuesta

Para cumplir con los objetivos trazados y materializar la generación automatizada de micro-aprendizaje adaptativo, en este capítulo se detalla el diseño de la arquitectura del sistema. La solución propuesta se estructura mediante una canalización (pipeline) modular que integra la caracterización del estudiante, la recuperación de información institucional y la generación de contenido mediante LLMs.

### 7.1 Visión General del Sistema

La arquitectura general del sistema opera bajo un enfoque centrado en el usuario y respaldado por datos estructurados. El flujo de interacción se divide en tres fases principales:

- **Fase de Inicialización y Perfilado:** El estudiante ingresa a la plataforma y su perfil cognitivo es evaluado.
- **Fase de Recuperación (Backend RAG):** El sistema identifica el tema a estudiar y extrae los fragmentos de conocimiento relevantes desde las fuentes oficiales del curso.
- **Fase de Generación y Entrega:** Un LLM procesa el contexto recuperado junto con el perfil del alumno mediante prompt engineering avanzado, devolviendo una cápsula de micro-aprendizaje estrictamente adaptada para el estudiante.

### 7.2 Módulo de Caracterización del Estudiante

Para superar el paradigma de "talla única", el sistema implementa un módulo de diagnóstico inicial basado en el modelo VARK (Visual, Auditivo, Lectura/Escritura, Kinestésico).

Mediante la aplicación de un cuestionario de diagnóstico breve integrado en la interfaz de usuario, el sistema captura las preferencias de aprendizaje. Estas preferencias se traducen algorítmicamente en variables de estado (state variables). Por ejemplo, si un estudiante es diagnosticado con una preferencia "Kinestésica", el sistema guarda este atributo para que, en la fase de generación, se priorice la creación de ejemplos prácticos, simulaciones paso a paso y preguntas de aplicación interactiva, mitigando así la sobrecarga cognitiva.

### 7.3 Arquitectura RAG: Recuperación de Información

Para garantizar la calidad y exactitud del material, mitigando las alucinaciones del modelo generativo, se implementa una arquitectura RAG. Este módulo se basa principalmente en dos subprocesos:

- **Etiquetado estructurado de documentos:** En lugar de depender exclusivamente de distancias semánticas, la base de conocimiento se organiza mediante documentos fuente, fragmentos recuperables, objetivos de aprendizaje y metadatos pedagógicos. Los materiales oficiales del curso son curados, fragmentados y etiquetados con información como asignatura, unidad temática, objetivo de aprendizaje, tipo de recurso, palabras clave y estado de validación.
- **Recuperación estructurada mediante consultas SQL:** Cuando el estudiante solicita una microcápsula, el backend ejecuta consultas SQL sobre la base de datos relacional para recuperar únicamente los fragmentos validados que coinciden con el tema solicitado y con el perfil VARK del estudiante.

### 7.4 Motor de Generación Adaptativa (LLM & Prompting)

El núcleo de personalización recae en este motor. Una vez que el sistema ha recuperado los documentos oficiales (contexto) y conoce el estilo de aprendizaje del usuario (perfil VARK), ensambla un Prompt Maestro.

Por ejemplo, este prompt inyecta instrucciones precisas al LLM:

> "Utilizando únicamente la información del contexto adjunto, genera una cápsula de estudio de 3 párrafos enfocada en un estudiante visual, priorizando metáforas espaciales y sugiriendo la estructura para un mapa conceptual".

El resultado es un micro-contenido único, con trazabilidad hacia la fuente original, asegurando rigor académico y pertinencia pedagógica.

### 7.5 Stack Tecnológico Preliminar

Para el desarrollo de un prototipo funcional, se contempla el uso de las siguientes herramientas estándar en la industria de la IA:

- **Orquestación de IA:** LlamaIndex será utilizado como framework principal para coordinar la recuperación estructurada de fragmentos desde la base de datos relacional, la construcción dinámica del prompt y la comunicación con el modelo generativo.
- **Almacenamiento relacional estructurado:** Bases de datos como PostgreSQL o MySQL para persistir los perfiles VARK, los documentos fuente, los fragmentos recuperables, los objetivos de aprendizaje y la trazabilidad de las microcápsulas generadas.
- **Recuperación estructurada de información:** Consultas SQL sobre metadatos, etiquetas temáticas, objetivos de aprendizaje, tipo de recurso y perfil VARK, evitando depender de búsqueda vectorial probabilística.
- **Modelos de Lenguaje:** APIs de LLMs de última generación, como GPT-4o, Claude o Llama, para la generación de texto adaptado al perfil del estudiante a partir de los fragmentos recuperados desde la base de conocimiento institucional.

---

## 8. Metodología de Evaluación y Validación

En el marco experimental diseñado para validar la efectividad del modelo de generación de micro-aprendizaje, la evaluación se divide en dos dimensiones fundamentales: la precisión técnica de la arquitectura RAG y la percepción de utilidad por parte de los usuarios finales (estudiantes y docentes).

### 8.1 Evaluación de la Calidad Técnica del Contenido (Métricas RAG)

Para mitigar el riesgo de alucinaciones y asegurar el rigor académico, se evaluará la respuesta del LLM utilizando métricas de fidelidad y relevancia:

- **Fidelidad:** Se verificará si la cápsula generada se deriva estrictamente de los documentos oficiales recuperados de la base de conocimiento.
- **Relevancia de la Respuesta:** Se medirá qué tan bien el micro-contenido generado responde a la consulta original del estudiante, evitando información tangencial que pueda generar sobrecarga cognitiva.
- **Exactitud Factual:** Siguiendo a Li et al. (2025), se verificará que las afirmaciones presentes en la microcápsula coincidan con los fragmentos oficiales recuperados desde la base de conocimiento relacional, considerando el documento fuente, la página o sección correspondiente y el objetivo de aprendizaje asociado.

### 8.2 Validación de la Adaptabilidad Pedagógica (Alineación VARK)

El éxito del proyecto depende de que el material realmente se ajuste a los estilos de aprendizaje. Para validar esto, se realizarán comparaciones directas de efectividad, donde un grupo de control recibirá material genérico ("talla única") y un grupo experimental recibirá cápsulas adaptadas a su perfil VARK.

Se evaluará si el sistema es capaz de reconfigurar exitosamente la estrategia instruccional (ej. pasar de un resumen textual a una lista de pasos prácticos para un perfil kinestésico), facilitando que los estudiantes absorban y retengan mejor los temas complejos.

### 8.3 Evaluación de la Experiencia de Usuario (Modelo TAM)

Para medir la intención de uso y la aceptación tecnológica, se aplicará un instrumento basado en el Modelo de Aceptación de la Tecnología (TAM). Se medirán tres variables clave:

- **Utilidad Percibida:** Grado en que el estudiante cree que el sistema mejora su rendimiento académico y reduce el tiempo de estudio.
- **Facilidad de Uso Percibida:** Evaluación de la interfaz y la simplicidad para obtener cápsulas de aprendizaje.
- **Compromiso (Engagement):** Siguiendo los hallazgos de Saha et al. (2025), se medirá el interés del alumno por consumir estos formatos breves frente a los tradicionales de larga duración.

### 8.4 Impacto en la Carga Docente

Finalmente, se realizará una validación con expertos (profesores) para determinar si la automatización del micro-contenido efectivamente reduce su carga de trabajo. La evidencia empírica sugiere que estos sistemas pueden disminuir las tareas operativas de los docentes en casi un 40%, permitiendo interacciones de mayor valor pedagógico.

Los docentes evaluarán la coherencia de las cápsulas generadas y la facilidad para integrar sus propios materiales oficiales en la base de conocimiento del sistema.

### 8.5 Plan de evaluación del prototipo funcional

Con el objetivo de validar de manera integral el prototipo funcional propuesto, se definirá un proceso de evaluación dividido en tres dimensiones principales: evaluación técnica del sistema, evaluación pedagógica del contenido generado y evaluación de la experiencia de usuario.

En primer lugar, la evaluación técnica se centrará en comprobar el correcto funcionamiento del flujo RAG estructurado, mediante un conjunto de consultas de prueba asociadas a distintos objetivos de aprendizaje. Se analizará si los fragmentos recuperados corresponden efectivamente al tema solicitado, si pertenecen a documentos validados y si la microcápsula generada mantiene coherencia con las fuentes institucionales (fidelidad, exactitud factual, relevancia y trazabilidad).

En segundo lugar, se evaluará la adaptabilidad pedagógica de las microcápsulas generadas utilizando perfiles VARK diferenciados (visual, auditivo, lectura/escritura, kinestésico y perfiles multimodales), verificando si cada versión adapta correctamente su estructura, tono, ejemplos, tipo de actividad y forma de explicación al perfil correspondiente.

En tercer lugar, se realizará una validación con usuarios (estudiantes y docentes). Los estudiantes responderán un instrumento basado en escala Likert orientado a medir utilidad percibida, facilidad de uso, claridad del contenido, adecuación al estilo de aprendizaje y disposición a utilizar la herramienta. Los docentes evaluarán la calidad académica de las microcápsulas, su coherencia con los contenidos oficiales, su utilidad como recurso complementario y el grado en que el sistema podría reducir la carga de creación manual.

Para complementar la evaluación subjetiva, se podrá aplicar una comparación simple entre una microcápsula genérica y una adaptada al perfil VARK del estudiante, indicando cuál se considera más clara, útil y adecuada para estudiar.

Los resultados serán analizados mediante estadística descriptiva (promedios, frecuencias y porcentajes de aprobación por criterio), complementada con revisión cualitativa de observaciones abiertas.

**Tabla 8.1 — Dimensiones de evaluación del prototipo funcional**

| Dimensión evaluada | Criterios principales | Instrumento o método |
|---|---|---|
| Calidad técnica del sistema | Fidelidad, exactitud, relevancia de la respuesta y trazabilidad de fuentes | Pruebas con consultas controladas y revisión de fragmentos recuperados |
| Adaptabilidad pedagógica | Alineación entre perfil VARK, formato de contenido, tono, ejemplos y actividad de cierre | Comparación de microcápsulas generadas para distintos perfiles VARK |
| Experiencia de usuario | Utilidad percibida, facilidad de uso, claridad, satisfacción y disposición de uso | Encuesta tipo Likert aplicada a estudiantes |
| Validación docente | Coherencia académica, pertinencia del contenido y reducción de carga operativa | Rúbrica de evaluación aplicada a docentes |

### 8.6 Limitaciones del estudio

El presente estudio presenta una serie de limitaciones que deben ser consideradas al momento de interpretar los resultados obtenidos y proyectar futuras etapas de desarrollo. En primer lugar, la investigación se enmarca en una fase de diseño y validación inicial de un prototipo funcional, por lo que sus resultados tendrán un carácter exploratorio y no necesariamente generalizable a todos los contextos educativos.

Una primera limitación corresponde al tamaño y composición de la muestra. Aunque se considera la participación de estudiantes universitarios, principalmente pertenecientes a Ingeniería en Informática, esta selección puede introducir sesgos asociados al perfil académico, familiaridad tecnológica y tipo de contenidos abordados.

Otra limitación relevante se relaciona con el uso del modelo VARK como mecanismo de caracterización del estudiante. VARK será utilizado como herramienta para identificar preferencias de presentación del contenido, sin asumir que dichas preferencias garantizan por sí solas una mejora directa en el aprendizaje.

La evaluación del prototipo estará limitada por el alcance de las métricas consideradas, las cuales no permiten comprobar completamente efectos de largo plazo, como la retención sostenida del conocimiento, la mejora del rendimiento académico o la transferencia de aprendizaje a nuevos contextos.

Desde el punto de vista técnico, el funcionamiento del sistema dependerá directamente de la calidad, estructura y actualización de la base de conocimiento utilizada. Si los documentos fuente no se encuentran correctamente curados, fragmentados, etiquetados y validados, la recuperación de información puede verse afectada.

Finalmente, el estudio también se encuentra condicionado por las características propias de los modelos de lenguaje utilizados (modelo seleccionado, calidad del prompt maestro, límites de contexto, costos de la API y estabilidad del servicio externo).

En consecuencia, estas limitaciones no invalidan la propuesta, sino que delimitan su alcance inicial como una primera aproximación al diseño e implementación de un sistema de generación de micro-aprendizaje adaptativo.

---

## 9. Caracterización de la Muestra y Datos Sociodemográficos

Para la validación del módulo de diagnóstico de estilos de aprendizaje se definirá una muestra objetiva compuesta por un mínimo de 40 estudiantes universitarios. El presente estudio se centra principalmente en alumnos pertenecientes a la carrera de Ingeniería en Informática, integrando una proporción controlada de estudiantes de otras disciplinas como grupo de control.

Con el objetivo de perfilar adecuadamente a los usuarios y descubrir posibles correlaciones entre su contexto y sus preferencias de estudio, el instrumento de recolección (implementado vía Google Forms) capturará los siguientes datos sociodemográficos básicos previo a la aplicación del cuestionario VARK:

- **Rango Etario y Género:** Para establecer una distribución demográfica de la muestra.
- **Carrera de Origen:** Variable fundamental para segmentar los resultados.
- **Año de Ingreso / Semestre Actual:** Esta métrica permitirá analizar el nivel de avance en la malla curricular.

---

## 10. Flujo de Diagnóstico y Procesamiento del Modelo VARK

Sobre la base de la investigación y el análisis expuesto en este documento, se establece la hoja de ruta técnica para una eventual fase de ejecución, asegurando que la implementación tecnológica se realice en estricta alineación con la teoría pedagógica estudiada.

Para dar respuesta a la necesidad de personalización pedagógica, el sistema integra un módulo de diagnóstico basado en el modelo de inventario de estilos de aprendizaje VARK (Visual, Aural/Auditivo, Read-Write/Lectura-Escritura, Kinesthetic/Kinestésico), desarrollado por Neil Fleming. El procesamiento de la información, desde el llenado del instrumento hasta la agregación estadística del perfil grupal, se define mediante un flujo estructurado de tres fases lógicas:

**Fase de Instrumentación y Recolección de Preferencias**
El diagnóstico se inicia con la aplicación de la versión estándar del cuestionario VARK, compuesto por preguntas de opción múltiple contextualizadas en situaciones cotidianas de resolución de problemas. El instrumento se distribuirá de forma digital utilizando Google Forms.

Siguiendo las directrices del modelo psicopedagógico original, se habilita la selección múltiple por pregunta, permitiendo al estudiante marcar más de una alternativa si considera que varias respuestas describen su comportamiento, o dejar preguntas en blanco si ninguna coincide. Esta flexibilidad es crítica para evitar sesgos analíticos y capturar de manera fidedigna la naturaleza multimodal del aprendizaje humano.

**Fase de Mapeo Algorítmico y Calificación Individual**
Una vez recolectadas las respuestas del formulario, los datos se someten a un proceso de tabulación automatizada basado en una matriz de puntuación fija:

- **Asignación Sensorial:** Cada alternativa seleccionada en las 16 preguntas se mapea directamente con su dimensión sensorial correspondiente (V, A, R o K).
- **Acumulación de Puntajes:** Se calcula la frecuencia absoluta de selección para cada una de las cuatro variables, obteniendo un vector de resultados individuales expresado como:

  P_usuario = {P_V, P_A, P_R, P_K}

  Donde cada componente representa la sumatoria de selecciones en dicha categoría.
- **Clasificación del Perfil:** El sistema define el perfil del alumno identificando el valor máximo del conjunto. Si un estudiante presenta una diferencia significativa en favor de un único componente, se le cataloga bajo un perfil unimodal. En caso de empates o diferencias mínimas, el sistema lo clasifica como un perfil multimodal (bimodal), permitiendo que la lógica del backend posteriormente orqueste cápsulas educativas híbridas.

**Fase de Agregación Grupal y Determinación del Perfil Predominante**
El flujo metodológico para determinar la tendencia de la muestra se compone de los siguientes pasos:

- **Segmentación por Carrera:** Se filtran los registros transaccionales aislando exclusivamente a los sujetos cuya variable sociodemográfica corresponda a "Ingeniería en Informática".
- **Cálculo de la Moda Estadística:** Se aplica la métrica de la moda sobre el universo de perfiles consolidados, cuantificando la frecuencia con la que cada estilo de aprendizaje (V, A, R, K o combinaciones multimodales) se presenta como la preferencia principal de los sujetos.
- **Extracción de Métricas de Tendencia:** Se generan distribuciones de frecuencia relativa (porcentajes) para caracterizar al grupo completo. La identificación de este "perfil más repetido" servirá como línea base de diseño para configurar los parámetros por defecto del prompt en el sistema RAG, optimizando la organización de los metadatos, las etiquetas pedagógicas y las relaciones internas de la base de conocimiento relacional para los formatos de micro-contenido con mayor probabilidad de demanda en la sede.

---

## 11. Definición de Estándares Estructurales de la Microcápsula y Reglas de Mapeo VARK

### 11.1 Estándares del micro-contenido

Para garantizar la coherencia pedagógica y técnica del sistema propuesto, resulta necesario establecer un conjunto de parámetros cuantitativos y cualitativos que definen la unidad mínima de micro-aprendizaje que el sistema deberá generar:

- **Duración:** La microcápsula generada debe poder consumirse en un rango de entre 3 y 7 minutos, con un límite de 10 minutos. Esta restricción se fundamenta en que "los estudiantes a menudo muestran desinterés en ver por ejemplo conferencias grabadas que duran de 50 a 70 minutos, y los videos de conferencias más largos provocan tasas de deserción más altas" (Saha et al., 2025), mientras que las cápsulas breves alcanzan tasas de completación superiores al 80%.
- **Extensión del texto generado:** El contenido principal de cada cápsula se acotará entre 150 y 300 palabras, permitiendo información suficientemente densa sin generar sobrecarga cognitiva (Sortwell et al., 2026).
- **Foco temático:** Cada microcápsula abordará exactamente un objetivo de aprendizaje, en línea con la definición del micro-aprendizaje como "una serie de módulos de aprendizaje electrónico en porciones pequeñas... enfocados en ráfagas cortas" (Liu & Mao, 2026).
- **Actividad de cierre:** Toda cápsula incluirá obligatoriamente una evaluación formativa al final, consistente en una pregunta de verificación o mini-quiz de opción múltiple, para activar el mecanismo de recuperación activa del conocimiento.
- **Trazabilidad de fuente:** El sistema registrará el fragmento o documento fuente de la base de conocimiento RAG del cual se extrajo el contenido, garantizando la auditabilidad y veracidad de la información generada.

**Anatomía estándar de una microcápsula:**

- **Título:** Enunciado descriptivo de no más de 10 palabras que identifica el concepto abordado.
- **Objetivo de aprendizaje:** Oración única que especifica qué deberá saber o poder hacer el estudiante al finalizar la cápsula.
- **Contenido principal:** Bloque de texto entre 150 y 300 palabras, generado por el LLM con parámetros de estilo adaptados al perfil VARK del estudiante.
- **Elemento de actividad:** Pregunta de verificación o ejercicio breve, cuyo formato también se adapta al perfil del estudiante.
- **Referencia de la fuente:** Identificador del fragmento recuperado desde la base de conocimiento relacional que permite la trazabilidad del contenido generado.

### 11.2 Reglas de mapeo del perfil VARK y tipos de micro-contenidos

Una vez determinado el perfil de aprendizaje del estudiante, el sistema debe traducir dicho perfil en parámetros concretos de generación de contenido. El sistema no utiliza únicamente una etiqueta rígida ("visual", "auditivo", etc.), sino que trabaja con los porcentajes exactos obtenidos por cada estudiante en las cuatro dimensiones del modelo VARK, de modo que la microcápsula generada sea proporcional al peso real de cada canal.

Sea el vector porcentual del estudiante definido como:

**P_usuario = {p_V, p_A, p_R, p_K}**

donde p_V, p_A, p_R y p_K corresponden a los porcentajes visual, auditivo, lector/escritor y kinestésico respectivamente. La suma de estos valores debe cumplir:

**p_V + p_A + p_R + p_K = 100**

A partir de este vector, el sistema calcula una configuración de generación de contenido que determina la ponderación interna de la microcápsula, mediante una combinación proporcional de los canales VARK:

- C_texto = 0.40·p_V + 0.55·p_A + 0.75·p_R + 0.50·p_K
- C_visual = 0.45·p_V + 0.10·p_A + 0.15·p_R + 0.15·p_K
- C_narrativo = 0.05·p_V + 0.30·p_A + 0.05·p_R + 0.10·p_K
- C_practico = 0.10·p_V + 0.05·p_A + 0.05·p_R + 0.25·p_K

Dado que los porcentajes VARK se expresan en escala de 0 a 100, los valores obtenidos representan la distribución relativa del énfasis instruccional de la cápsula. Un estudiante con mayor porcentaje visual recibirá una cápsula con mayor presencia de esquemas, tablas o mapas conceptuales; un estudiante con mayor porcentaje lector/escritor recibirá mayor densidad textual y definiciones formales; un estudiante auditivo recibirá una redacción más conversacional y basada en analogías; y un estudiante kinestésico recibirá mayor cantidad de ejemplos aplicados, pasos concretos y actividades prácticas.

**Tabla 11.1 — Reglas de decisión porcentual para adaptar la ponderación del contenido generado**

| Condición del perfil VARK | Decisión de generación de contenido |
|---|---|
| p_V ≥ 40% | La microcápsula debe incluir al menos dos recursos visuales (mapa conceptual, tabla comparativa, esquema textual o referencia a imagen recuperada). |
| 25% ≤ p_V < 40% | La microcápsula debe incluir al menos un recurso visual complementario. |
| p_R ≥ 40% | Se prioriza mayor densidad textual, definiciones formales, encabezados jerárquicos y glosario de conceptos clave. |
| p_A ≥ 40% | Se activa un tono conversacional, uso de analogías cotidianas, preguntas retóricas y frases mnemotécnicas. |
| p_K ≥ 40% | La microcápsula debe incluir obligatoriamente un ejemplo aplicado, una secuencia paso a paso y una actividad final del tipo "inténtalo tú". |
| Dos dimensiones con diferencia ≤ 10 puntos porcentuales | El sistema considera el perfil como bimodal y combina las reglas de ambos canales de forma proporcional. |
| Tres o más dimensiones sobre el 20% | El sistema considera el perfil como multimodal y genera una cápsula equilibrada, integrando texto, apoyo visual, explicación narrativa y actividad práctica. |

Estas reglas permiten que la adaptación no dependa únicamente del canal predominante, sino de la distribución completa del perfil del estudiante. Por ejemplo, un estudiante con perfil {45%V, 20%A, 15%R, 20%K} priorizará recursos visuales, manteniendo componentes prácticos y narrativos secundarios; mientras que un perfil {25%V, 20%A, 20%R, 35%K} se orientará principalmente a la aplicación práctica, conservando apoyo visual moderado.

Este enfoque se sustenta en el trabajo de Hashiyada et al. (2025), quienes demostraron la factibilidad técnica de adaptar materiales educativos generados por LLM a los estilos VARK, incluyendo la automatización de diagramas para perfiles visuales y explicaciones narrativas para perfiles auditivos.

**Perfil Visual (V)**
- *Elementos generados:* Mapas conceptuales descritos textualmente, tablas comparativas, listas jerarquizadas con múltiples sub-niveles e infografías estructuradas en texto.
- *Tono instruccional:* Espacial y ordenado, priorizando la organización visual mediante jerarquías y estructuras.
- *Parámetro de prompt:* `perfil = visual → incluir_mapa_conceptual + tabla_comparativa + estructura_jerarquica`

**Perfil Auditivo (A)**
- *Elementos generados:* Narración conversacional en estilo oral, analogías con situaciones cotidianas, preguntas retóricas intercaladas y frases o acrónimos mnemotécnicos.
- *Tono instruccional:* Conversacional y reflexivo, priorizando la oralidad y el ritmo narrativo.
- *Parámetro de prompt:* `perfil = auditivo → tono_oral + analogias_cotidianas + preguntas_reflexivas`

**Perfil Lector/Escritor (R)**
- *Elementos generados:* Resumen estructurado con encabezados jerárquicos, definiciones precisas de términos clave, glosario conceptual y ejercicio de escritura o completación de texto.
- *Tono instruccional:* Formal y académico, denso y bien organizado, con terminología técnica exacta.
- *Parámetro de prompt:* `perfil = lector_escritor → encabezados_jerarquicos + definiciones_exactas + ejercicio_escrito`

**Perfil Kinestésico (K)**
- *Elementos generados:* Ejemplos prácticos resueltos paso a paso con un problema del mundo real, caso de estudio aplicado y una actividad del tipo "inténtalo tú" al final.
- *Tono instruccional:* Práctico y orientado a la acción, conectando permanentemente la teoría con su aplicación.
- *Parámetro de prompt:* `perfil = kinestesico → ejemplo_resuelto + paso_a_paso + actividad_aplicada`

**Perfil multimodal (bimodal)**
Cuando el sistema identifica un perfil bimodal (por ejemplo, V+K), combinará los parámetros de prompt de ambas dimensiones activas, generando una cápsula híbrida. La ponderación de los elementos de cada estilo es proporcional a la diferencia de puntaje entre las dimensiones dominantes del vector P_usuario.

---

## 12. Definición de la Base de Conocimiento

Si bien en muchas implementaciones de RAG se utilizan bases de datos vectoriales y embeddings para recuperar información mediante similitud semántica, el presente proyecto adopta un enfoque de RAG estructurado sobre una base de datos relacional. Esta decisión responde a las características del contexto educativo, donde resulta necesario mantener un control explícito sobre los documentos fuente, los objetivos de aprendizaje, los metadatos pedagógicos y la trazabilidad del contenido generado.

- **Tipos de documento:** La base de conocimiento estará compuesta por material académico oficial del curso: presentaciones de clases, guías de estudio, actividades evaluadas, apuntes en PDF, esquemas, tablas, diagramas e infografías, incorporados únicamente cuando correspondan a contenidos vigentes y alineados con los objetivos de aprendizaje.
- **Multimodalidad de los documentos:** Para satisfacer los requerimientos del modelo VARK, especialmente en estudiantes con alta ponderación visual o kinestésica, cada recurso será clasificado según su tipo de fragmento (textual, imagen, tabla, esquema, diagrama o recurso mixto).
- **Origen del material:** Los documentos serán aportados directamente por el docente de la asignatura, ayudantes o repositorios académicos autorizados.
- **Revisión previa de documentos:** Antes de incorporarse al sistema, cada documento será sometido a un proceso de revisión y curación, reduciendo el riesgo de alucinaciones algorítmicas al recibir el modelo generativo únicamente fragmentos de fuentes validadas.
- **Fragmentación y etiquetado estructurado:** Los documentos curados serán divididos en fragmentos recuperables, almacenados junto con metadatos descriptivos (documento de origen, número de página, unidad temática, objetivo de aprendizaje asociado, tipo de recurso, palabras clave, estado de validación y descripción breve del contenido).
- **Recuperación estructurada de información:** La recuperación no dependerá de embeddings, sino de consultas SQL sobre los metadatos previamente definidos, permitiendo filtrar por asignatura, unidad, objetivo de aprendizaje, etiqueta temática y tipo de recurso.
- **Integración con el perfil VARK:** La selección de fragmentos considerará la configuración derivada del perfil VARK del estudiante (esquemas/tablas/diagramas para perfiles visuales; ejemplos aplicados y ejercicios para perfiles kinestésicos; textos con definiciones formales para perfiles lectores/escritores; contenidos narrativos/conversacionales para perfiles auditivos).
- **Trazabilidad y mitigación de alucinaciones:** Cada fragmento recuperado conservará la referencia exacta al documento fuente, permitiendo verificar si la respuesta generada se fundamenta efectivamente en material institucional validado.
- **Almacenamiento:** Se realizará en una base de datos relacional, con las entidades principales `documento_fuente`, `fragmento` y `objetivo_aprendizaje`.

---

## 13. Justificación del Modelo de Base de Datos

Para soportar la generación automatizada de micro-aprendizaje se debe definir un modelo de persistencia de datos que garantice tanto la escalabilidad como la exactitud pedagógica. Tras evaluar los requerimientos de RAG y del módulo de caracterización del estudiante, se ha determinado adoptar un modelo de **Base de Datos Relacional**, como MySQL o PostgreSQL. Esta decisión arquitectónica se fundamenta en la necesidad de asegurar recuperación determinista, trazabilidad explícita de fuentes, control curricular e integridad de los datos asociados al perfil del estudiante.

**Determinismo curricular contra probabilidad semántica**
Las bases de datos vectoriales operan mediante búsquedas de similitud espacial, lo cual introduce un factor probabilístico que puede comprometer la precisión del material educativo. Hashiyada et al. (2025) advierten empíricamente que la precisión del contenido generado depende críticamente de los documentos en la base de datos, ya que un mal manejo provoca que el modelo recurra a fuentes genéricas de internet y genere alucinaciones. Un modelo relacional soluciona esta vulnerabilidad al mapear los fragmentos de conocimiento directamente a identificadores únicos asociados a los objetivos curriculares, recuperando la información de manera completamente determinista (Li et al., 2025).

**Trazabilidad y Auditoría de Fuentes**
En una base de datos relacional, mantener la trazabilidad es un proceso nativo mediante el uso de llaves foráneas (foreign keys). Cada cápsula generada puede vincularse referencialmente al documento oficial exacto, al autor y a la versión del apunte.

**Gestión de la Complejidad del Perfil de Usuario (Modelo VARK)**
La tabulación automatizada del modelo VARK, la captura de variables sociodemográficas y el seguimiento transaccional del progreso del alumno son datos inherentemente estructurados. Una base de datos relacional es superior para manejar la integridad de estos registros interconectados, permitiendo analítica compleja como el cálculo de la moda estadística de los perfiles por carrera.

**Reducción de la Sobrecarga Arquitectónica Inicial**
Depender de bases vectoriales especializadas en la nube suele implicar elevados costos computacionales y problemas de latencia. Al utilizar una base de datos relacional robusta (con soporte de Full-Text Search), se simplifica el stack tecnológico del prototipo funcional, reduciendo puntos de fallo y optimizando los tiempos de desarrollo.

En síntesis, este sistema exige un entorno cerrado y con nula tolerancia a la desviación curricular. Al utilizar una base de datos relacional para orquestar el RAG Estructurado, el sistema recupera la información mediante consultas exactas, proporcionando el control transaccional, la precisión determinista y la integridad de los perfiles de usuario necesarios para lograr una adaptación pedagógica tecnológicamente confiable.

---

## 14. Herramientas y Librerías (Stack Tecnológico)

Para garantizar la viabilidad técnica y la correcta implementación del prototipo funcional, se ha seleccionado un conjunto de herramientas de software de código abierto ampliamente respaldadas por la comunidad de desarrollo de software y la industria de la Inteligencia Artificial:

- **Lenguaje de Programación (Python):** La totalidad del backend y el pipeline de procesamiento de datos se desarrollarán en Python, estándar de la industria para IA y LLMs, con extensa disponibilidad de bibliotecas especializadas.
- **Framework de Desarrollo API (FastAPI):** Para la exposición de los servicios del backend se utilizará FastAPI, framework moderno y de alto rendimiento con manejo asíncrono nativo, validación automática de datos y documentación interactiva bajo el estándar OpenAPI.
- **Orquestador RAG (LlamaIndex):** La gestión del flujo de datos, la estructuración del contexto y la comunicación con el modelo de lenguaje se delegarán en LlamaIndex, especializado en la conexión de fuentes de datos estructuradas y no estructuradas con modelos de lenguaje, con abstracciones avanzadas para motores de consulta personalizados integrados con bases de datos relacionales.

---

## 15. Flujo de LlamaIndex en el RAG Estructurado

La generación de la microcápsula educativa adaptativa sigue una secuencia lógica controlada rigurosamente por el orquestador LlamaIndex, en cuatro fases operativas consecutivas:

**Recuperación Determinista desde la Base de Datos Relacional**
Cuando un estudiante solicita una microcápsula sobre un tema específico, el sistema no realiza una búsqueda probabilística de similitud. El backend ejecuta una consulta SQL exacta en la base de datos relacional utilizando identificadores únicos vinculados al objetivo de aprendizaje y a la unidad del plan de estudios vigente. LlamaIndex recibe los fragmentos de texto oficiales (chunks) recuperados por la consulta y los encapsula en objetos de datos estructurados denominados nodos, asegurando que la única información disponible para el proceso de generación sea el material institucional validado.

**Construcción Dinámica del Prompt con Parámetros VARK**
LlamaIndex toma el vector de preferencias del perfil de aprendizaje del estudiante obtenido en el diagnóstico. El sistema selecciona automáticamente la plantilla de instrucciones correspondiente al estilo dominante (Visual, Auditivo, Lector o Kinestésico) e inyecta dinámicamente los parámetros de estilo pedagógico como variables dentro del prompt maestro.

**Inferencia de Modelos de Lenguaje Relacionados**
El paquete final que contiene el texto de la fuente oficial y las directrices de personalización psicopedagógica se envía al Modelo de Lenguaje Grande a través del conector de predicción de LlamaIndex. El LLM reescribe el contenido técnico estricto de la base de datos para adaptarlo a las estructuras visuales o narrativas requeridas por el alumno, respetando los límites de extensión de 150 a 300 palabras.

**Validación Estructural y Entrega del Recurso**
LlamaIndex recibe la respuesta del modelo de lenguaje y ejecuta un formateo final del contenido. El backend en FastAPI verifica la presencia de todos los componentes obligatorios de la anatomía de la microcápsula (título, objetivo, contenido adaptado, mini-quiz de cierre y referencia exacta de la fuente) y despacha el recurso educativo hacia la aplicación del estudiante en formato JSON, garantizando un flujo limpio y una experiencia de aprendizaje personalizada de alta velocidad.

*(Figura 15.1: Flujo de generación de microcápsulas adaptativas mediante RAG estructurado — muestra las etapas: Recuperación SQL Determinista → Inyección de Parámetros VARK → Inferencia y Reescritura del LLM → Validación Estructural en JSON → Entrega vía FastAPI).*

---

## 16. Análisis de Resultados del Diagnóstico VARK

### 16.1 Definición sociodemográfica de la muestra

La encuesta fue respondida por un total de **43 estudiantes universitarios**, superando el mínimo establecido de 40 participantes. Del total de la muestra, 23 estudiantes (53%) pertenecen a carreras del área de Ingeniería en Informática (incluyendo Ingeniería en Informática, Ingeniería Civil Informática e Ingeniería Civil en Ciencia de Datos) y 20 estudiantes (47%) corresponden al grupo de control, conformado por participantes de otras disciplinas universitarias.

En cuanto a la distribución por género, la muestra está compuesta por 27 estudiantes masculinos (63%), 14 femeninas (33%) y 2 participantes no binarios (5%). Respecto al nivel de avance académico, el grupo más representado corresponde a estudiantes de 4° año o superior (semestres 7+), con 20 participantes (47%), seguido por estudiantes de 3° año con 9 participantes (21%), y estudiantes de 1° y 2° año con 7 participantes cada uno (16% respectivamente).

*(Figura 16.1: Caracterización sociodemográfica — distribución por género, por año de carrera y por carrera).*

### 16.2 Distribución de perfiles VARK

Una vez aplicado el flujo de mapeo algorítmico y calificación individual, se obtuvieron los vectores de puntaje VARK para cada participante.

**Distribución de perfiles VARK — Muestra total (n=43):**

| Perfil | N° de estudiantes | Tipo |
|---|---|---|
| A+K | 10 | Multimodal |
| K+R | 8 | Multimodal |
| A | 6 | Unimodal |
| K | 6 | Unimodal |
| A+R | 5 | Multimodal |
| A+V | 3 | Multimodal |
| R | 3 | Unimodal |
| R+V | 1 | Multimodal |
| K+V | 1 | Multimodal |

**Distribución de perfiles VARK — Ingeniería en Informática (n=23):**

| Perfil | N° de estudiantes | % | Tipo |
|---|---|---|---|
| A+K | 8 | 35% | Multimodal |
| K | 5 | 22% | Unimodal |
| A | 4 | 17% | Unimodal |
| K+R | 3 | 13% | Multimodal |
| K+V | 1 | 4% | Multimodal |
| A+V | 1 | 4% | Multimodal |
| R+V | 1 | 4% | Multimodal |

Para la muestra total (n=43), la moda estadística de perfiles corresponde al perfil bimodal **A+K (Auditivo + Kinestésico)**. Este resultado se replica de manera consistente al segmentar la muestra por carrera: el perfil predominante en el grupo de Ingeniería en Informática (n=23) es también el perfil bimodal A+K, lo que otorga solidez y representatividad al hallazgo.

Con el propósito de caracterizar con mayor precisión el perfil multimodal predominante, se establece la jerarquía de canales según los puntajes promedio obtenidos por el grupo de Ingeniería en Informática. Dentro del perfil bimodal A+K, el canal Kinestésico (K) constituye la primera prioridad de aprendizaje con un promedio de 7,96 puntos, mientras que el canal Auditivo (A) representa la segunda prioridad con un promedio de 6,57 puntos. En consecuencia, el perfil predominante de este grupo se describe de forma completa como: **bimodal (K → A)** (Kinestésico como canal primario, Auditivo como canal secundario). Esta jerarquía es la que determina el orden de ponderación instruccional al momento de generar las cápsulas de micro-aprendizaje.

### 16.3 Análisis de puntajes promedio por dimensión

Con el objetivo de profundizar en la caracterización del grupo objetivo, se calcularon los puntajes promedio por dimensión VARK para ambos segmentos de la muestra:

| Dimensión VARK | Muestra total (n=43) | Ing. Informática (n=23) |
|---|---|---|
| Visual (V) | 3,1 | 3,65 |
| Auditivo (A) | 6,2 | 6,57 |
| Lector/Escritor (R) | 5,8 | 5,17 |
| Kinestésico (K) | 6,5 | 7,96 |

Los resultados para el grupo de Ingeniería en Informática son los siguientes:

- **Kinestésico (K):** 7,96 puntos, canal de primera prioridad.
- **Auditivo (A):** 6,57 puntos, canal de segunda prioridad.
- **Lector/Escritor (R):** 5,17 puntos, dimensión intermedia.
- **Visual (V):** 3,65 puntos, dimensión menos representada.

La brecha entre la dimensión Kinestésica (K = 7,96) y la Visual (V = 3,65) es de 4,31 puntos, lo que confirma una tendencia marcada hacia el aprendizaje práctico y experiencial con respecto de las representaciones puramente visuales dentro de este grupo. La proximidad entre K y A (diferencia de 1,39 puntos) respalda la clasificación del perfil predominante como bimodal A+K, en línea con el criterio de multimodalidad definido en la sección 11.

### 16.4 Implicaciones para el parámetro por defecto del sistema RAG

Tal como se estableció en la sección 11, el perfil más repetido de la muestra de Ingeniería en Informática constituye la línea base de diseño para configurar los parámetros por defecto del prompt en el sistema RAG. En consecuencia, dado que la moda estadística del grupo objetivo corresponde al perfil bimodal K→A (Kinestésico primario / Auditivo secundario), el sistema inicializará su generación de microcápsulas con el siguiente parámetro por defecto:

```
perfil = auditivo_kinestesico → tono_oral + analogias_cotidianas
       + ejemplo_resuelto + paso_a_paso + actividad_aplicada
```

Este parámetro combina los elementos instruccionales de ambas dimensiones activas según las reglas de mapeo definidas en la sección 12.2, generando cápsulas híbridas que integran una narración conversacional con ejemplos prácticos resueltos. Dicho valor por defecto será sobrescrito de forma dinámica cuando el sistema identifique un perfil individual distinto en el diagnóstico específico de cada estudiante.

El orden de los elementos instruccionales en el parámetro refleja la jerarquía de canales identificada: los componentes kinestésicos (ejemplo resuelto, secuencia paso a paso, actividad de aplicación) tienen prioridad de generación por sobre los auditivos (tono conversacional, analogías), de modo que el mayor peso del contenido responde al canal dominante.

---

## 17. Modelo Lógico de la Base de Datos Relacional

A partir de la justificación arquitectónica expuesta en la sección 14, que estableció la adopción de un modelo relacional con RAG Estructurado, se define a continuación el modelo lógico de datos que sustenta tanto el módulo de caracterización del estudiante como el proceso de generación de micro-contenido. El diseño se organiza en torno a un principio rector: el perfil de aprendizaje se almacena exclusivamente como un vector de porcentajes por canal sensorial, sin persistir etiquetas reductivas como la clasificación unimodal o multimodal. Esta decisión preserva la totalidad de la información diagnóstica y permite que las reglas de decisión definidas en la sección 12.3 operen sobre los valores exactos de cada preferencia.

*(Figura 17.1: Modelo de la base de datos relacional — entidades: `estudiante`, `diagnostico_vark`, `respuesta_vark`, `configuracion_contenido`, `objetivo_aprendizaje`, `documento_fuente`, `fragmento`, `microcapsula_generada`).*

### 17.1 Entidades de caracterización del estudiante

El núcleo del módulo de perfilamiento se compone de cuatro entidades interrelacionadas. La entidad `estudiante` almacena las variables sociodemográficas definidas en la sección 10 (rango etario, género, carrera y año de ingreso), constituyendo la unidad sobre la cual se ejecuta la analítica de segmentación, como el cálculo de la moda estadística de perfiles por carrera.

La entidad `diagnostico_vark` registra el resultado del proceso de calificación descrito en la sección 11, conservando tanto los puntajes crudos de frecuencia absoluta (`puntaje_v`, `puntaje_a`, `puntaje_r`, `puntaje_k`) como el vector porcentual normalizado (`porcentaje_v`, `porcentaje_a`, `porcentaje_r`, `porcentaje_k`), cuya suma equivale al cien por ciento. Este vector porcentual constituye el único registro del perfil de aprendizaje y representa el dato que el orquestador consume para la construcción dinámica del prompt.

De manera complementaria, la entidad `respuesta_vark` almacena las selecciones individuales del estudiante en cada uno de los dieciséis ítems del instrumento, garantizando la trazabilidad del diagnóstico y la posibilidad de recalcular los perfiles ante eventuales ajustes en la matriz de puntuación. Finalmente, la entidad `configuracion_contenido` materializa la salida de las reglas de decisión, traduciendo los porcentajes del perfil en parámetros concretos de generación (cantidad de recursos visuales, densidad textual, componentes prácticos, activación de audio y tono narrativo).

### 17.2 Representación Derivada de la Jerarquía de Canales

Dado que el sistema no persiste la clasificación del perfil, los atributos de orden superior (canal primario, canal secundario y condición de multimodalidad) se obtienen mediante una vista derivada que ordena los cuatro porcentajes en tiempo de consulta. De esta forma, la jerarquía de canales se calcula dinámicamente a partir de la fuente de verdad, sin introducir redundancia ni riesgo de inconsistencia entre el vector almacenado y su interpretación categórica.

### 17.3 Vinculación con la Generación de Contenido y Trazabilidad

La conexión entre el módulo de perfilamiento y el proceso de Recuperación Aumentada por Generación se materializa en la entidad `microcapsula_generada`, la cual referencia simultáneamente al estudiante, al objetivo de aprendizaje y al fragmento documental de origen. Esta última referencia, implementada mediante una llave foránea, satisface el requisito de auditabilidad establecido en la sección 13, al permitir vincular cada cápsula con el documento oficial exacto que fundamentó su contenido.

Las entidades correspondientes a la base de conocimiento (`documento_fuente`, `fragmento` y `objetivo_aprendizaje`) se modelan como estructuras de texto con metadatos, sin almacenar representaciones vectoriales de tipo embedding, en coherencia con la recuperación determinista por consultas SQL adoptada en el RAG Estructurado.

### 17.4 Diccionario de datos

**Tabla 17.1 — Entidad `estudiante`**

| Atributo | Tipo | Descripción |
|---|---|---|
| id_estudiante | INT (PK) | Identificador único del estudiante. |
| rango_etario | VARCHAR(20) | Rango de edad declarado. |
| genero | VARCHAR(20) | Género declarado. |
| carrera | VARCHAR(80) | Carrera de origen (variable de segmentación). |
| ano_ingreso | INT | Año de ingreso a la universidad. |
| fecha_registro | DATETIME | Fecha de incorporación al sistema. |

**Tabla 17.2 — Entidad `diagnostico_vark`**

| Atributo | Tipo | Descripción |
|---|---|---|
| id_diagnostico | INT (PK) | Identificador único del diagnóstico. |
| id_estudiante | INT (FK) | Referencia a la entidad estudiante. |
| puntaje_v | INT | Frecuencia absoluta de selecciones asociadas al canal visual. |
| puntaje_a | INT | Frecuencia absoluta de selecciones asociadas al canal auditivo. |
| puntaje_r | INT | Frecuencia absoluta de selecciones asociadas al canal lectura/escritura. |
| puntaje_k | INT | Frecuencia absoluta de selecciones asociadas al canal kinestésico. |
| porcentaje_v | DECIMAL(5,2) | Porcentaje normalizado correspondiente al canal visual. |
| porcentaje_a | DECIMAL(5,2) | Porcentaje normalizado correspondiente al canal auditivo. |
| porcentaje_r | DECIMAL(5,2) | Porcentaje normalizado correspondiente al canal lectura/escritura. |
| porcentaje_k | DECIMAL(5,2) | Porcentaje normalizado correspondiente al canal kinestésico. |
| fecha_diagnostico | DATETIME | Fecha de aplicación del instrumento VARK. |

**Tabla 17.3 — Entidad `respuesta_vark`**

| Atributo | Tipo | Descripción |
|---|---|---|
| id_respuesta | INT (PK) | Identificador único de la respuesta individual. |
| id_diagnostico | INT (FK) | Referencia al diagnóstico asociado. |
| num_pregunta | TINYINT | Número del ítem evaluado (rango de 1 a 16). |
| alternativa | CHAR(1) | Alternativa seleccionada por el alumno. |
| canal_mapeado | CHAR(1) | Canal sensorial asociado de forma directa (V, A, R, K). |

**Tabla 17.4 — Entidad `configuracion_contenido`**

| Atributo | Tipo | Descripción |
|---|---|---|
| id_config | INT (PK) | Identificador único de la configuración generada. |
| id_diagnostico | INT (FK) | Referencia al diagnóstico VARK asociado. |
| peso_texto | DECIMAL(5,2) | Ponderación asignada al componente textual de la cápsula. |
| peso_visual | DECIMAL(5,2) | Ponderación asignada a recursos visuales como esquemas, tablas o imágenes. |
| peso_narrativo | DECIMAL(5,2) | Ponderación asignada al componente conversacional o auditivo. |
| peso_practico | DECIMAL(5,2) | Ponderación asignada a ejemplos aplicados, pasos o actividades prácticas. |
| recursos_visuales | TINYINT | Cantidad de recursos visuales a incluir en la cápsula. |
| palabras_texto | SMALLINT | Extensión textual objetivo de la microcápsula generada. |
| componentes_practicos | TINYINT | Cantidad de componentes prácticos o de simulación kinestésica. |
| audio_activo | BOOLEAN | Indica si se debe generar una versión sonora o una redacción orientada al canal auditivo. |
| tono_narrativo | VARCHAR(20) | Tono instruccional definido para el modelo, por ejemplo: oral, formal, práctico o mixto. |
| canales_activos | VARCHAR(10) | Canales que superan el umbral mínimo de activación, por ejemplo: V, A, R, K o combinaciones. |

**Tabla 17.5 — Entidad `objetivo_aprendizaje`**

| Atributo | Tipo | Descripción |
|---|---|---|
| id_objetivo | INT (PK) | Identificador único del objetivo de aprendizaje. |
| codigo_objetivo | VARCHAR(30) | Código interno o institucional asociado al objetivo. |
| asignatura | VARCHAR(100) | Nombre de la asignatura a la que pertenece el objetivo. |
| unidad | VARCHAR(100) | Unidad, módulo o eje temático del curso. |
| tema | VARCHAR(150) | Tema específico asociado al objetivo de aprendizaje. |
| descripcion | TEXT | Descripción formal del aprendizaje esperado. |
| nivel_taxonomico | VARCHAR(50) | Nivel cognitivo esperado, por ejemplo: recordar, comprender, aplicar o analizar. |
| estado | VARCHAR(20) | Estado del objetivo dentro del sistema, por ejemplo: activo, inactivo o en revisión. |

**Tabla 17.6 — Entidad `documento_fuente`**

| Atributo | Tipo | Descripción |
|---|---|---|
| id_documento | INT (PK) | Identificador único del documento incorporado a la base de conocimiento. |
| titulo | VARCHAR(150) | Título del documento fuente. |
| tipo_documento | VARCHAR(40) | Clasificación del recurso, por ejemplo: guía, apunte, presentación, actividad o bibliografía. |
| formato | VARCHAR(20) | Formato del archivo original, por ejemplo: PDF, PPTX, DOCX, imagen o texto plano. |
| origen | VARCHAR(100) | Procedencia del material, por ejemplo: docente, ayudante, estudiante o repositorio institucional. |
| asignatura | VARCHAR(100) | Asignatura o curso al que pertenece el documento. |
| version | VARCHAR(20) | Versión del documento, útil para controlar actualizaciones del material. |
| ruta_archivo | VARCHAR(255) | Ubicación lógica o física del archivo dentro del sistema. |
| hash_archivo | VARCHAR(128) | Huella digital del archivo para controlar duplicados e integridad documental. |
| estado_curacion | VARCHAR(30) | Estado de revisión del documento, por ejemplo: pendiente, validado o rechazado. |
| fecha_carga | DATETIME | Fecha en que el documento fue incorporado al sistema. |

**Tabla 17.7 — Entidad `fragmento`**

| Atributo | Tipo | Descripción |
|---|---|---|
| id_fragmento | INT (PK) | Identificador único del fragmento recuperable por el sistema RAG. |
| id_documento | INT (FK) | Referencia al documento fuente desde el cual se extrajo el fragmento. |
| id_objetivo | INT (FK) | Referencia al objetivo de aprendizaje asociado al fragmento. |
| numero_fragmento | INT | Posición secuencial del fragmento dentro del documento original. |
| tipo_fragmento | VARCHAR(30) | Tipo de recurso indexado, por ejemplo: texto, imagen, tabla, esquema o diagrama. |
| contenido_texto | TEXT | Contenido textual del fragmento, cuando corresponda. |
| ruta_recurso | VARCHAR(255) | Ruta del recurso visual o multimodal asociado, cuando el fragmento no sea solo texto. |
| pagina_inicio | INT | Página inicial del documento donde se ubica el fragmento. |
| pagina_fin | INT | Página final del documento donde se ubica el fragmento. |
| etiqueta_tematica | VARCHAR(100) | Etiqueta que resume el tema principal del fragmento. |
| metadatos_json | JSON | Metadatos adicionales del fragmento, como palabras clave, descripción visual o relación con VARK. |
| estado_validacion | VARCHAR(30) | Estado de validación del fragmento, por ejemplo: pendiente, validado o descartado. |

**Tabla 17.8 — Entidad `microcapsula_generada`**

| Atributo | Tipo | Descripción |
|---|---|---|
| id_capsula | INT (PK) | Identificador único de la cápsula de micro-aprendizaje. |
| id_estudiante | INT (FK) | Referencia al estudiante destinatario del recurso. |
| id_objetivo | INT (FK) | Referencia al objetivo pedagógico institucional. |
| id_config | INT (FK) | Referencia a la configuración de contenido derivada del perfil VARK. |
| id_fragmento_fuente | INT (FK) | Referencia al fragmento principal de origen para trazabilidad y auditoría. |
| titulo | VARCHAR(150) | Título asignado a la cápsula. |
| contenido_json | JSON | Estructura del contenido dinámico adaptado al perfil del alumno. |
| mini_quiz_json | JSON | Actividad interactiva de evaluación de cierre en formato JSON. |
| estado_validacion | VARCHAR(30) | Estado de revisión de la cápsula generada, por ejemplo: generada, validada o rechazada. |
| fecha_generacion | DATETIME | Marca de tiempo exacta del proceso de generación del recurso. |

---

## 18. Arquitectura de la Solución y Modelo de Procesos

Para comprender la articulación operativa del sistema propuesto, es fundamental modelar el ciclo de vida completo de los datos y las interacciones entre los componentes tecnológicos. A diferencia de las plataformas tradicionales de e-learning que operan de forma estática, la arquitectura diseñada requiere una sincronización fluida entre la captura psicopedagógica del usuario y los procesos asíncronos de inferencia y recuperación del motor generativo.

Este flujo de datos se divide en cuatro macro-fases secuenciales:

1. **Etapa de caracterización:** el estudiante responde el instrumento de diagnóstico en la interfaz y el backend computa un vector numérico representativo de sus preferencias de aprendizaje.
2. **Fase de persistencia determinista** dentro del motor relacional.
3. **Proceso de orquestación RAG** llevado a cabo por FastAPI y LlamaIndex, donde se intersectan los fragmentos de conocimiento institucional indexados con las reglas condicionales derivadas del perfil del alumno.
4. **Capa de validación estructural** sintáctica del archivo JSON que antecede al despliegue adaptativo del micro-contenido.

**Figura 18.1 — Diagrama de bloques del ciclo completo de datos e interacción del sistema adaptativo:**

**FASE 1: Captura y Perfilamiento (Frontend a Base de Datos)**
1. Estudiante completa Diagnóstico VARK (interacción inicial en el frontend).
2. Tabulación y Cálculo de Porcentajes Exactos — el algoritmo procesa las respuestas y calcula el vector exacto (V: %, A: %, R: %, K: %).
3. Almacenamiento del Perfil en DB Relacional — se guardan los porcentajes en la tabla `diagnostico_vark` vinculados al ID del estudiante.

**FASE 2: Solicitud y Recuperación RAG (Backend)**
1. Estudiante solicita Microcápsula de un Tema — petición HTTP enviada al orquestador (FastAPI).
2. Consulta SQL a la Base de Conocimientos (RAG Estructurado) — el backend busca en la DB el material oficial exacto usando determinismo curricular (unidad, tema).
3. Extracción de Fragmentos Multimodales — se devuelven textos y metadatos gráficos a LlamaIndex.

**FASE 3: Adaptación y Generación LLM (Motor IA)**
1. Aplicación de Reglas de Decisión VARK — se cruza el perfil del estudiante con las reglas de mapeo.
2. Construcción del Prompt Maestro Integrado — se unen los fragmentos oficiales (RAG) + las instrucciones de formato (VARK) + límite de 150-300 palabras.
3. Generación de Microcápsula (LLM) — llamada a la API del LLM para generar título, contenido y quiz en formato JSON.

**FASE 4: Validación y Entrega (FastAPI a Frontend)**
1. ¿JSON Estructuralmente Válido? — FastAPI revisa si la salida del LLM cumple el esquema (si no, hay reintento hacia la Fase 3).
2. Presentación Adaptativa en Interfaz — el frontend renderiza la cápsula de 3-7 minutos con sus proporciones de texto/imagen según el perfil.
3. Estudiante consume contenido y responde Quiz.

---

## 19. Conclusiones

A partir del desarrollo realizado en este informe, se concluye que la generación de micro-aprendizaje educativo mediante Inteligencia Artificial Generativa constituye una alternativa pertinente y técnicamente viable para enfrentar las limitaciones de los modelos tradicionales de enseñanza en línea. La problemática inicial evidencia que los enfoques homogéneos de tipo "talla única" no responden adecuadamente a la diversidad de ritmos, preferencias y formas de aprendizaje de los estudiantes, mientras que la creación manual de materiales personalizados representa una carga operativa difícil de sostener para los equipos docentes. En este contexto, la propuesta desarrollada permite avanzar hacia un modelo más dinámico, escalable y centrado en el estudiante.

El análisis teórico permitió establecer que la combinación entre micro-aprendizaje, estilos de aprendizaje VARK y arquitectura RAG ofrece una base sólida para diseñar cápsulas educativas breves, focalizadas y adaptadas al perfil del usuario. La incorporación de RAG resulta especialmente relevante, ya que permite reducir el riesgo de alucinaciones propias de los modelos generativos, anclando la generación de contenido en fuentes oficiales, revisadas y trazables. De esta forma, el sistema no depende únicamente del conocimiento preentrenado del modelo, sino que utiliza una base de conocimiento institucional como fuente principal para garantizar mayor exactitud, actualización y confiabilidad del material generado.

Asimismo, los resultados del diagnóstico VARK entregan una orientación concreta para la configuración inicial del sistema. La muestra estuvo compuesta por 43 estudiantes, de los cuales 23 pertenecen al área de Ingeniería en Informática y 20 corresponden a un grupo de control. En el grupo objetivo se identificó una tendencia predominante hacia el perfil bimodal Kinestésico–Auditivo, con mayor prioridad para el canal Kinestésico. Esto justifica que las microcápsulas generadas por defecto prioricen ejemplos prácticos, resolución paso a paso, actividades aplicadas, tono conversacional y analogías cotidianas, sin impedir que el sistema ajuste dinámicamente el contenido cuando un estudiante presente un perfil diferente.

Desde el punto de vista tecnológico, el diseño de la solución demuestra coherencia entre los objetivos pedagógicos y la implementación propuesta. El uso de un modelo relacional para almacenar los porcentajes exactos de cada dimensión VARK, en lugar de guardar únicamente etiquetas rígidas como "visual" o "kinestésico", permite conservar mayor granularidad en el perfil del estudiante y facilita una personalización más precisa. Además, la integración de una base de conocimiento curada, un flujo RAG estructurado y un motor de generación basado en prompts adaptativos proporciona una arquitectura capaz de producir micro-contenidos personalizados, verificables y alineados con los objetivos de aprendizaje.

En síntesis, el proyecto logra establecer una propuesta integral que articula fundamentos pedagógicos, evidencia empírica y diseño tecnológico para transformar la entrega de contenidos educativos. Si bien aún es necesario implementar y validar el prototipo funcional mediante métricas de calidad, pruebas con usuarios y evaluación docente, el avance desarrollado permite afirmar que la solución propuesta posee un alto potencial para mejorar la experiencia de aprendizaje, fomentar la autonomía del estudiante y disminuir la carga asociada a la producción manual de recursos educativos. Por tanto, este modelo representa una base prometedora para el desarrollo de sistemas educativos adaptativos, escalables y confiables apoyados por Inteligencia Artificial Generativa.

---

## Bibliography

- Amazon Web Services. (n.d.). *¿Qué es la generación aumentada por recuperación (RAG)?* Retrieved April 15, 2026, from https://aws.amazon.com/es/what-is/retrieval-augmented-generation/
- Gao, Y., Xiong, Y., Gao, X., Jia, K., Pan, J., Bi, Y., Dai, Y., Sun, J., Wang, M., & Wang, H. (2024). Retrieval-augmented generation for large language models: A survey. *arXiv preprint arXiv:2312.10997v5*.
- Hang, C. N., Tan, C. W., & Yu, P. D. (2024). MCQGen: A large language model-driven MCQ generator for personalized learning. *IEEE Access*.
- Hashiyada, K., Shi, W., & Yin, C. (2025). A framework for using LLMs and RAG to realize the automatic generation of learning materials from lecture slides. *Proceedings of the 1st International Conference on Learning Evidence and Analytics*.
- Li, Z., Wang, Z., Wang, W., Hung, K., Xie, H., & Wang, F. L. (2025). Retrieval-augmented generation for educational application: A systematic survey. *Computers and Education: Artificial Intelligence*.
- Liu, X., & Mao, Z. (2026). Micro-learning of generative AI on digital media and its adoption among college music majors: Applying the technology acceptance model with AI identity threat as a moderator. *Education and Information Technologies*.
- Luo, H., & Li, W. (2025). Impact of microlearning on developing soft skills of university students across disciplines. *Frontiers in Psychology*.
- Saha, S., et al. (2025). Next-gen education: Enhancing AI for microlearning. *2025 ASEE Annual Conference*.
- Sortwell, A., et al. (2026). Beyond cognitive load theory: Why learning needs more than memory management. *Brain Sciences*.
- Suazo-Galdames, I. C., & Chaple-Gil, A. M. (2025). AI-powered adaptive learning systems in higher education: A scoping review of implementation and impact on academic performance. *Data & Metadata*.
- Tural, B., Örpek, Z., & Destan, Z. (2024). Retrieval-augmented generation (RAG) and LLM integration. *2024 8th International Symposium on Innovative Approaches in Smart Technologies (ISAS)*.
- Yao, Y., Duan, J., Xu, K., Cai, Y., Sun, Z., & Zhang, Y. (2024). A survey on large language model (LLM) security and privacy: The good, the bad, and the ugly. *High-Confidence Computing*.
