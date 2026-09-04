# Sesión de Testeo y Mejoras — 03 de Septiembre de 2026

**Proyecto:** Studify — Micro-aprendizaje adaptativo con RAG curricular y perfilamiento VARK  
**Rol:** Desarrollador Senior / Arquitecto de Software  
**Fecha:** 03 de Septiembre de 2026  
**Estado:** Completado y Validado en Entorno Local  

---

## 1. Resumen Ejecutivo

Durante esta sesión de trabajo y testeo intensivo se resolvieron bloqueos críticos del entorno, se optimizó el pipeline de generación adaptativa con LLMs, se extendió la arquitectura de actividades pedagógicas con componentes interactivos ricos (Flashcards 3D y Multi-Quiz) para perfiles kinestésicos, y se transformó la experiencia de usuario (UI/UX) integrando una pantalla de carga moderna con animación en video.

Todas las modificaciones fueron validadas mediante pruebas de integración, análisis de contratos de datos y suites completas de pruebas automatizadas (**163 tests superados con 0 fallos**).

---

## 2. Decisiones Arquitectónicas y Técnicas

| Área | Decisión Tomada | Justificación Técnica |
| :--- | :--- | :--- |
| **Entorno Python** | Recreación del virtualenv con **Python 3.12.10** en lugar de 3.14 alpha. | Python 3.14 carece de wheels precompilados en PyPI para paquetes de análisis de datos y ML (`numpy`, `pydantic-core`, `psycopg2`), provocando fallos de compilación con MSVC. |
| **Generación de Imágenes (IA Local)** | Dejar en stand-by la inferencia local de FLUX.2 Klein y desacoplar de la UI. | Priorizar el rendimiento del flujo principal de generación de texto y actividades de estudio. La auditoría empírica demostró que los modelos de difusión destilados aún no garantizan legibilidad tipográfica en diagramas educativos complejos. |
| **Base de Datos y Semilla** | Mantener la operación directa sobre PostgreSQL sin requerir el CSV de 43 estudiantes en runtime. | La base de datos ya cuenta con las 45 filas de estudiantes, diagnósticos VARK y 1.240 respuestas históricas cargadas; el CSV solo operó como semilla histórica inicial. |
| **Control de Extensión en LLM** | Ajustar el prompt de reparación y validación de palabras (`_error_exceso_de_palabras`). | Cuando un estudiante bimodal (ej. R+K) acumula 6 directivas, el modelo tendía a exceder las 300 palabras. Exigir un recorte explícito de `exceso + 15` palabras distribuido entre secciones erradicó los bucles de rechazo. |
| **Actividades Kinestésicas** | Extender el contrato `Actividad` para incluir `flashcards` y `quiz_multi`. | Los estudiantes con $p_K \ge 40\%$ requieren manipulación activa (*learning by doing*). El campo de texto abierto (`intentalo_tu`) era insuficiente para ejercitar el recuerdo activo (*Active Recall*). |
| **Recursos Estáticos Públicos** | Montar la carpeta `src/studify/public` en la ruta `/public`. | Permite servir assets de medios interactivos (como el video `animacionCarga.mp4`) de forma directa y optimizada por streaming sin pasar por lógica de controladores. |

---

## 3. Detalle de Implementaciones Realizadas

### 3.1. Corrección del Límite de Palabras y Generación de Cápsulas
* **Diagnóstico del problema:** Al solicitar la cápsula `UX-U1-05 — Diferencia entre diseño UX y diseño UI` para el estudiante `2012` ($R=45.45\%$, $K=40.91\%$), el modelo DeepSeek entregó 361 palabras (límite: 300 palabras). El mensaje de error solo señalaba `concepto_central`, haciendo que el modelo recortara solo ahí y volviera a fallar con 335 palabras.
* **Archivos modificados:**
  * [src/studify/generation/validator.py](file:///e:/code/Studify/Studify/src/studify/generation/validator.py): Se recalculó el feedback para instruir un recorte obligatorio de `exceso + 15` palabras repartido entre `concepto_central`, `representacion_adaptativa` y `ejemplo`.
  * [src/studify/rag/prompts/maestro.py](file:///e:/code/Studify/Studify/src/studify/rag/prompts/maestro.py): Se añadieron directivas estrictas de concisión en `PERFIL` y `FORMATO`.
* **Resultado:** La cápsula #1317 se generó, validó y persistió con éxito en PostgreSQL al primer intento.

---

### 3.2. Actividades Interactivas para Perfiles Kinestésicos ($p_K \ge 40\%$)

Se desarrollaron dos nuevas modalidades pedagógicas enriquecidas:

#### A. Flashcards Interactivas 3D (Active Recall)
* **Contrato Pydantic:** Se crearon los modelos `TarjetaFlashcard(anverso, reverso)` y se extendió `Actividad(tipo="flashcards", tarjetas=[...])` exigiendo entre 3 y 5 tarjetas por cápsula.
* **Visualización Web:**
  * Implementación de tarjeta 3D con efecto flip (`perspective: 1000px`, `transform-style: preserve-3d`, `rotateY(180deg)`).
  * Anverso con el desafío o concepto y reverso con la respuesta y justificación formativa.
  * Controles táctiles y botones «Anterior», «Girar» y «Siguiente», con indicador dinámico de progreso (`Tarjeta 2 / 4`) y barra de llenado proporcional.
  * Formulario HTMX para registrar la finalización del repaso activo en la sesión del estudiante.

#### B. Cuestionarios Mixtos Ampliados (Multi-Quiz)
* **Contrato Pydantic:** Se crearon los modelos `PreguntaQuiz(enunciado, alternativas, indice_correcta, explicacion)` con validación de 3 a 5 preguntas y descarte de alternativas duplicadas.
* **Visualización Web y Evaluación:**
  * Batería secuencial de preguntas con selección de alternativas.
  * El endpoint `POST /student/viewer/{id_capsula}/submit` evalúa en servidor las respuestas seleccionadas, previene trampas desde el código fuente y genera un desglose visual detallado con tarjetas individuales (correcto/incorrecto, respuesta correcta y explicación pedagógica).

#### C. Modo Simulador Docente
* En `/teacher/simulator`, el profesor puede simular perfiles kinestésicos y auditar de inmediato la baraja completa de flashcards desplegada o las preguntas del cuestionario con sus respectivas claves y justificaciones.

**Archivos afectados:**
* [src/studify/generation/schemas.py](file:///e:/code/Studify/Studify/src/studify/generation/schemas.py)
* [src/studify/rag/prompts/maestro.py](file:///e:/code/Studify/Studify/src/studify/rag/prompts/maestro.py)
* [src/studify/web/templates/student/_capsula.html](file:///e:/code/Studify/Studify/src/studify/web/templates/student/_capsula.html)
* [src/studify/web/templates/student/_feedback.html](file:///e:/code/Studify/Studify/src/studify/web/templates/student/_feedback.html)
* [src/studify/web/routers/student.py](file:///e:/code/Studify/Studify/src/studify/web/routers/student.py)
* [tests/test_generacion_contrato.py](file:///e:/code/Studify/Studify/tests/test_generacion_contrato.py)

---

### 3.3. Pantalla de Carga Adaptativa con Reproductor de Video

Para evitar la incertidumbre del estudiante mientras el LLM y el RAG estructuran la cápsula (proceso que toma entre 4 y 15 segundos), se diseñó una pantalla de carga inmersiva:

1. **Montaje de Assets Públicos:**
   * En [src/studify/main.py](file:///e:/code/Studify/Studify/src/studify/main.py), se montó la carpeta `src/studify/public` en la ruta `/public`.
2. **Video de Carga (`animacionCarga.mp4`):**
   * Se incorporó el elemento `<video>` en [catalog.html](file:///e:/code/Studify/Studify/src/studify/web/templates/student/catalog.html) con reproducción continua silenciada (`autoplay`, `loop`, `muted`, `playsinline`).
   * Contenedor estilizado en [style.css](file:///e:/code/Studify/Studify/src/studify/web/static/css/style.css) con bordes redondeados (`border-radius: 1rem`), iluminación sutil y sombra de elevación.
3. **Control del Ciclo de Vida (JavaScript):**
   * Al hacer clic en «Estudiar», el video reinicia en `0s` y arranca la reproducción.
   * La interfaz muestra el código y tema seleccionado dinámicamente (`UX-U1-01`, etc.).
   * Se rotan etiquetas pedagógicas cada 2.3 segundos (*«Consultando tu perfil VARK...»* $\rightarrow$ *«Recuperando material curricular...»* $\rightarrow$ *«Estructurando contenido...»*).
   * Al volver atrás con el navegador (`pageshow`), el overlay se oculta y el video se pausa de forma defensiva.

---

## 4. Auditoría y Pruebas Automatizadas

Se verificó la estabilidad de todo el sistema ejecutando la suite completa de pruebas:

| Suite de Tests | Archivo | Estado | Métricas |
| :--- | :--- | :--- | :--- |
| **Contrato y Validación Pydantic** | `tests/test_generacion_contrato.py` | **PASS** | 59 tests exitosos en 0.22s |
| **Sincronización de Prompts** | `tests/test_prompt_maestro.py` | **PASS** | 25 tests exitosos en 1.38s |
| **Generador y Bucle de Reparación**| `tests/test_generador.py` | **PASS** | 16 tests exitosos |
| **Flujo Web del Estudiante** | `tests/test_web_estudiante.py` | **PASS** | 24 tests exitosos en 2.47s |
| **Flujo Web del Docente y Simulador** | `tests/test_web_docente.py` / `simulador.py` | **PASS** | 25 tests exitosos |
| **Endpoints REST de Cápsulas** | `tests/test_api_capsulas.py` | **PASS** | 14 tests exitosos |
| **Asset de Video Streaming** | Endpoint `/public/animacionCarga.mp4` | **PASS** | HTTP 200 OK (Content-Type: video/mp4, 3.8 MB) |

**Total de pruebas ejecutadas:** 163 pruebas unitarias y de integración superadas con 0 errores.

---

## 5. Instrucciones para Ejecución Local

Para levantar el entorno y verificar los cambios:

```powershell
# 1. Asegurarse de tener activo el entorno virtual
.\.venv\Scripts\Activate.ps1

# 2. Iniciar el servidor Uvicorn en modo recarga
uvicorn studify.main:app --reload --app-dir src
```

* **Acceso Estudiante:** [http://127.0.0.1:8000/student/catalog](http://127.0.0.1:8000/student/catalog) (Selecciona «Estudiar» en cualquier tema nuevo para ver la pantalla de carga con video y la generación de flashcards 3D).
* **Acceso Docente:** [http://127.0.0.1:8000/teacher/simulator](http://127.0.0.1:8000/teacher/simulator) (Credenciales: `admin` / `admin123`).

