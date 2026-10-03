# Studify — Estado de avance

> Documento vivo. Se actualiza al cierre de cada fase para que cualquier sesión de trabajo
> (o cualquier persona) pueda retomar el proyecto sin releer todo el hilo de conversación.
> Última actualización: **02-oct-2026** — **marco legal** (sección 5 tervicies): Términos y
> Política de Privacidad (Ley 19.628/21.719) en borrador con `[PLACEHOLDER]`, footer legal,
> consentimiento con trazabilidad (`aceptacion_legal`), `/mis-datos` para ejercer derechos,
> cierre de los endpoints de la API que exponían perfiles ajenos y fuentes/HTMX sin terceros.
> Antes, el mismo día: **rediseño completo del frontend** (sección 5
> duovicies): design system propio (tokens, modo oscuro, íconos, componentes), landing en `/`,
> cuestionario de una pregunta a la vez, perfil con radar SVG, catálogo con buscador, pantalla
> "Generando tu cápsula…", visor con referencias que muestran el fragmento citado y panel
> docente responsive con el gráfico VARK de la cohorte. Solo capa de presentación: ningún
> endpoint ni flujo HTMX cambió. Convenciones en [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md).
> **341 tests en verde** (4 fallos previos, documentados en la sección).
> Antes: **26-ago-2026** — **separación de las vistas del estudiante y del
> docente** (secciones 5 duodevicies y 5 undevicies). Hasta ahora `/teacher/*` estaba abierto:
> la cabecera ofrecía las tres pestañas del docente a cualquiera y ninguna comprobaba nada, de
> modo que la bandeja de curación —que decide qué material llega a las cápsulas, cap. 12/13— la
> podía usar quien escribiera la URL. Ahora hay un botón «Soy docente» que lleva a
> `/teacher/login`, una credencial única (usuario + clave) y un guardián declarado en el
> `APIRouter`, de forma que toda vista nueva del panel queda cerrada por construcción y no por
> disciplina; un test lo comprueba recorriendo las rutas ya montadas. La cookie del docente
> lleva el vencimiento y la huella de la credencial dentro de la firma (rotar usuario o clave
> expulsa las sesiones abiertas), las peticiones HTMX sin sesión reciben `HX-Redirect` en vez
> de un 303 que HTMX incrustaría dentro de un `<div>`, y con `TEACHER_PASSWORD=` puesta vacía a
> propósito el panel se cierra para todos en vez de quedar abierto en silencio. **A pedido del
> equipo, el valor de fábrica —sin tocar el `.env`— es usuario `admin` y clave `admin123`**
> (sección 5 undevicies): es un retroceso de seguridad deliberado a cambio de que el panel
> funcione nada más clonar el repo, documentado como tal y a cambiar antes de exponer el
> sistema a estudiantes reales. **330 tests en verde** (327 + 3). El mismo día, además,
> **higiene operativa** (sección 5 vicies): al ir a cerrar los tres pendientes «operativos»,
> dos describían un estado que ya no era cierto —las dependencias de ingesta ya estaban
> instaladas, y la base no estaba vacía sino **contaminada**: 157 diagnósticos donde los reales
> son 43—. La causa era `tests/test_api_diagnosticos.py`, el único archivo de la suite sin
> fixture de limpieza, que sumaba una decena de estudiantes en cada corrida de `pytest`; el
> mismo problema que la sección 3 ter ya había documentado el 10-ago y que volvió porque
> entonces se limpió el resultado y no la causa. Se arregló primero la causa (fixture autouse,
> verificada con dos corridas seguidas sin que se muevan los conteos) y después el resultado
> (`--reset` + recarga: 43 estudiantes y 1.202 respuestas, el número exacto de la sección
> 5 ter). El material curado no se tocó y `SESSION_SECRET` quedó fijada. Y por último, también
> el mismo día, **el cierre de `/api/*`** (sección 5 unvicies, pendiente n.º 17): el login había
> separado las *vistas* pero no los *endpoints*, así que `POST /api/objetivos`, los `PATCH` de
> curación y `DELETE /api/documentos/{id}` seguían aceptando escrituras anónimas. Los 13 de
> curación y analítica pasaron a un `router_docente` que responde 401 con `WWW-Authenticate`
> —no el 303 de la web, que un cliente HTTP seguiría hasta creer que la llamada funcionó— y
> acepta cookie o HTTP Basic; quedan abiertos los seis del estudiante. **De paso apareció un
> problema peor:** el test de cobertura de rutas escrito esa mañana **pasaba en vacío**, porque
> FastAPI 0.141 no aplana `include_router` y el filtro veía 2 de 41 rutas — corregido, con un
> test que ahora vigila al vigilante. **339 tests en verde.**
> Antes: **24-ago-2026** — repaso de coherencia entre `PLAN_DESARROLLO.md` y el
> estado real: quedaron marcadas ✅/reabiertas las cinco decisiones de la sección 6 del plan
> (el mapeo de C_* se cerró con una fórmula **distinta** a la propuesta original — sobre
> porcentajes VARK, no sobre C_* —, fragmentos no textuales quedó parcialmente cerrado, tema y
> regeneración cerrados, audio reabierto), se corrigió una frase de la Fase 5 que ya no era
> cierta (el simulador "todavía no" comparaba V/A/R/K — sí lo hace desde hoy mismo), se anotó
> el estado real del criterio de término de la Fase 3 (comparación hecha, ≥95% todavía no) y se
> marcó como superado el esquema de cápsula de la sección 3, reemplazado el 19-ago por la
> estructura de siete pasos. Nada de esto es código nuevo — es que el plan había quedado un
> paso atrás del propio `AVANCE.md`. Antes, el mismo día: se agregó la **Fase 6** a
> `PLAN_DESARROLLO.md` §4 a pedido del equipo — generación local de imagen/audio/video con
> modelos gratuitos (candidatos: SDXL-Turbo, Piper TTS, video compuesto con `ffmpeg`/`moviepy`)
> para complementar los canales V/A/K, fuera del horizonte de 10 semanas y sin bloquear el
> criterio de término de las fases 1–5. Reabre el punto 2 de la sección 7 (`audio_activo`);
> queda como pendiente n.º 16 de la sección 6, no iniciado — falta confirmar qué GPU/VRAM tiene
> disponible cada máquina del equipo antes de empezar a implementar. Antes, el mismo día (esta
> vez sí con código): implementado `knowledge/tagger.py`: el LLM propone objetivo y etiqueta
> temática por fragmento contra el catálogo curricular activo, y la bandeja
> de revisión del docente preselecciona esa propuesta en el `<select>` que ya existía. La
> propuesta nunca escribe `Fragmento.id_objetivo` ni `estado_validacion` — "propone, no decide"
> se hizo cumplir en el código, no solo en la intención —, y un `id_objetivo` fuera del catálogo
> entregado (u otra asignatura) se descarta igual que una cita alucinada. Verificado contra
> DeepSeek real: acertó los dos objetivos que sí correspondían a sus fragmentos y devolvió
> `null`, con motivo, en el que no calzaba con ninguno. Cierra el pendiente n.º 3 (sección 5
> septendecies). Suite completa: 308 tests en verde. Antes, el mismo día: investigado por qué el
> perfil lector-escritor (R) fallaba la validación más que los otros tres (pendiente n.º 15),
> hasta encontrar y corregir
> **dos causas reales**: su objetivo de palabras interpolaba exactamente en el máximo duro del
> validador, sin margen para la variación normal del modelo (corregido en
> `rag/orchestrator.py`); y, capturando el texto crudo de cada intento, se confirmó que el
> modelo **reenviaba la respuesta anterior byte a byte idéntica** cuando el mensaje de
> reparación no le daba un blanco concreto (corregido en `generation/validator.py`). Verificado
> contra DeepSeek real en tres rondas: **6 de 11 generaciones de R exitosas en total (55%)**,
> con dos de los tres temas de prueba pasando ya de forma consistente — mejora real medida, no
> resuelto del todo: ver sección 5 sedecies. Antes, el mismo día: el simulador docente pasó a
> comparar los cuatro perfiles VARK lado a lado
> (`POST /teacher/simulator/compare`), cerrando el criterio de término de la Fase 3 y siendo la
> corrida que encontró el problema de R (sección 5 quindecies). Antes de eso: los 16 enunciados
> del cuestionario VARK se verificaron carácter a carácter contra el CSV original y resultaron
> idénticos, cerrando el pendiente n.º 6 (sección 5 quaterdecies). Antes de eso: la microcápsula
> pasó a tener la estructura pedagógica de siete pasos que definió la profesora guía (19-ago,
> sección 5 terdecies), alta de objetivos desde el panel del docente (14-ago,
> sección 5 duodecies), rebranding a "RepasAi" y fondo de marca (13-ago, sección 5 undecies) y
> panel de analíticas con tres bugs de fondo corregidos (12-ago, sección 5 decies).

---

## 0. Qué es este proyecto (resumen para contexto rápido)

Studify es el prototipo funcional del Seminario de Título *"Generación de micro-aprendizaje
educativo mediante IA generativa, basado en estilos de aprendizaje del estudiante"* (Patricio
Hernández Vergara, Vicente Cisternas León — PUCV, profesora guía Sandra Cano Mazuera).

Genera **microcápsulas educativas** (150–300 palabras, 3–7 min de consumo, con quiz de cierre)
adaptadas al perfil VARK del estudiante (Visual / Auditivo / Lector-escritor / Kinestésico),
ancladas mediante **RAG estructurado sobre base de datos relacional** — es decir, sin
embeddings ni búsqueda vectorial: la recuperación de fragmentos de conocimiento se hace con
SQL determinista sobre metadatos curados, para garantizar trazabilidad y control curricular.

El documento fuente de todo el diseño es [`seminario_titulo.md`](seminario_titulo.md)
(el informe de avance ya entregado). El plan de implementación derivado de ese informe está en
[`PLAN_DESARROLLO.md`](PLAN_DESARROLLO.md) — **léase antes de tocar código**, ahí están las
decisiones de arquitectura, el roadmap de 10 semanas y las decisiones pendientes.

Este archivo (`AVANCE.md`) es el complemento: qué se hizo realmente, qué se verificó, qué
quedó pendiente y qué decisiones se tomaron sobre la marcha.

---

## 1. Estado actual en una frase

**Semana 0 completa** (`fbf4b3f`, pusheada a `origin/main` —
https://github.com/VicenteCLeon/Studify.git) y **Fase 1 cerrada**: las 8 entidades del cap. 17
migradas sobre Postgres, el motor VARK completo (scoring → pesos → jerarquía → reglas) y los 43
diagnósticos reales cargados.
Además, se construyó el **andamiaje inicial de la UI (Fase 4)** utilizando Jinja2, HTMX y Vanilla CSS, con 5 vistas principales (flujo estudiante y docente) — que en su momento usaban datos *mock* y hoy están conectadas al motor real (sección 5 nonies).

**Núcleo de la Fase 2 cerrado** (sección 5 septies): ingesta de PDF/PPTX con trazabilidad de
página, curación humana con estados reales y **retriever determinista sin embeddings**.

**Motor de generación de la Fase 3 cerrado** (sección 5 octies): contrato Pydantic de la
microcápsula, validador con las seis reglas de rechazo, prompt maestro en cuatro bloques,
bucle de reparación y `POST /api/capsulas` con caché y versionado. *(El contrato de la
microcápsula se reemplazó el 19-ago por la estructura de siete pasos — sección 5 terdecies;
el resto de esta sección sigue vigente.)*

**Fase 4 cerrada** (sección 5 nonies): la UI dejó de usar datos *mock*. El cuestionario
muestra los 16 ítems reales del instrumento, el diagnóstico se guarda de verdad, hay sesión
por cookie firmada, el perfil lee el vector y la configuración persistidos, el catálogo
consulta `objetivo_aprendizaje` ocultando lo que no tiene material curado, el visor invoca el
motor de generación y renderiza los siete tipos de bloque del contrato, el quiz se corrige
contra `mini_quiz_json`, y el panel del docente ingiere y cura material real.
**229 tests en verde y `ruff` limpio en todo el repositorio** (desaparecieron los 21 avisos
que arrastraban los routers mock).

**Fase 3 finalizada al 100% (incluyendo validación LLM):** Se agregó la credencial real de DeepSeek (`LLM_API_KEY`) al entorno y se cargó material curricular genuino (objetivo 369). El **bake-off de modelos** fue ejecutado exitosamente, obteniendo cápsulas 100% válidas en el primer intento con `deepseek-chat` (latencia ~5.5s) y quedando seleccionada definitivamente tras fallos de autorización de los otros candidatos (Qwen y GLM). ⚠️ Matiz sobre "bake-off": solo se pudo **medir** un modelo — Qwen y GLM fallaron por autorización, no por calidad — así que es más preciso decir que se seleccionó DeepSeek por ser el único candidato evaluable, no que ganó una comparación de tres.

**Panel de analíticas del docente (12-ago-2026, sección 5 decies):** se agregaron cinco vistas nuevas para el docente y se auditaron a fondo. Tres tenían fallos de fondo, no solo visuales: el simulador VARK generaba cápsulas rotas e indistinguibles de un perfil inválido, la métrica de aciertos del quiz podía inflarse por reintentos, y la cobertura curricular podía marcar en verde temas cuyo material el retriever ya no recupera. Las tres quedaron corregidas con 32 tests nuevos (261 en total) y una migración (`interaccion_quiz` con intentos numerados).

**Rebranding y fondo de marca (13-ago-2026, sección 5 undecies):** la UI pasó a llamarse "RepasAi" y toda la web tiene ahora una textura de fondo con íconos educativos. Es un cambio visual, sin código de dominio.

**Estructura pedagógica de siete pasos (19-ago-2026, sección 5 terdecies):** la profesora guía observó que el informe no define la estructura de una microcápsula y propuso una (OA → activación → concepto central → representación adaptativa VARK → ejemplo → pregunta de comprobación → retroalimentación). Está implementada: cada paso es ahora un campo obligatorio del contrato en vez de un bloque suelto dentro de una lista, y el prompt le muestra al modelo los cuatro pesos C_* en crudo además de las instrucciones estructurales. Verificado contra DeepSeek con material real: cápsula válida al primer intento, 247 palabras, los siete pasos en orden. **277 tests en verde.** Tres puntos de su lista quedaron fuera a propósito (embeddings, OA secundarios y el campo "contenido" del OA) — el detalle está en la sección 5 terdecies y en [`AUDITORIA_LISTA_PROFESORA_14AGO2026.md`](AUDITORIA_LISTA_PROFESORA_14AGO2026.md).

**Alta de objetivos desde el panel del docente (14-ago-2026, sección 5 duodecies):** `POST /api/objetivos` existía desde la Fase 2 pero no estaba conectado a ninguna pantalla — el catálogo solo se podía cargar por consola. Ahora hay un formulario en `/teacher/curation` que reutiliza el mismo handler; el script de carga masiva se conserva para sembrar un plan de estudios completo. **265 tests en verde** (261 + 4), `ruff` limpio. De paso se cargó el primer material curricular real del proyecto —5 objetivos de "Diseño de UX" y un PPTX con 40 fragmentos— aunque todavía sin curar, y se encontró que esta máquina tenía dos migraciones de Patricio sin aplicar (`/teacher/analytics` daba 500 hasta correr `alembic upgrade head`).

**Enunciados VARK verificados (24-ago-2026, sección 5 quaterdecies):** los 16 enunciados del cuestionario en `web/textos.py`, marcados como "provisionales" desde la Fase 4, resultaron ser idénticos carácter a carácter al CSV original al compararlos programáticamente — no hubo nada que reemplazar. Test de regresión nuevo (`tests/test_textos_vark.py`) para que no vuelva a divergir en silencio.

**Simulador: comparación V/A/R/K lado a lado (24-ago-2026, sección 5 quindecies):** `POST /teacher/simulator/compare` genera las cuatro cápsulas puras del mismo objetivo y las muestra una junto a otra, cerrando el criterio de término de la Fase 3. Verificado contra DeepSeek real (no solo tests): V, A y K salieron válidos y visiblemente distintos entre sí; **R falló la validación las tres veces por exceder las 300 palabras**, un hallazgo no buscado.

**Investigación y doble corrección del fallo de R (24-ago-2026, sección 5 sedecies):** investigando por qué el perfil lector-escritor fallaba más que los otros tres, se encontraron y corrigieron **dos causas reales**, cada una verificada contra DeepSeek real por separado. La primera: el objetivo de palabras de R interpola exactamente en el máximo duro del validador (300), sin margen para la variación normal del modelo — corregido en `rag/orchestrator.py` (el modelo ahora apunta a 270, sin tocar el `palabras_texto` de `vark/rules.py` que persiste la tabla 17.4); la tasa de éxito subió de 1/3 a 2/3 sobre los mismos tres temas. La segunda, más sorprendente: capturando el texto crudo de cada intento se vio que el modelo **reenviaba la respuesta anterior byte a byte idéntica** cuando el mensaje de reparación no le daba un blanco concreto — corregido en `generation/validator.py`, y verificado que ahora el modelo sí recorta en vueltas sucesivas (3257→3202→3104 caracteres, cada una distinta) en vez de repetirse. **Panorama agregado de las tres rondas de verificación: 6 de 11 generaciones de R exitosas (55%)**, todavía lejos del ≥95% del criterio de término, pero dos de los tres temas de prueba ya pasan de forma consistente. Detalle completo y lo que queda pendiente en el pendiente n.º 15.

**Etiquetado asistido por LLM (24-ago-2026, sección 5 septendecies):** `knowledge/tagger.py` le muestra al modelo el catálogo de objetivos activos de la asignatura y el texto de un fragmento, y le pide que proponga objetivo y etiqueta temática. La propuesta **no escribe** `Fragmento.id_objetivo` ni `estado_validacion` — vive en `metadatos_json` y solo preselecciona el `<select>` que el curador ya tenía que confirmar con «Validar» —, y un objetivo fuera del catálogo entregado se descarta igual que una cita alucinada. Verificado contra DeepSeek real: acertó los dos objetivos que sí correspondían a sus fragmentos y devolvió `null` en el que no calzaba con ninguno. Cierra el pendiente n.º 3. **308 tests en verde** (289 + 19).

**Separación de vistas estudiante/docente (26-ago-2026, sección 5 duodevicies):** `/teacher/*`
dejó de estar abierto. La cabecera muestra un botón «Soy docente» a quien no tiene sesión y las
tres pestañas del panel más «Salir» a quien sí; el acceso lo da `/teacher/login` con una
credencial única, y el guardián está declarado en el `APIRouter` para que cualquier vista que
se agregue después quede cerrada por construcción — hay un test que lo verifica sobre las
rutas ya montadas, no sobre una lista escrita a mano.

**Credencial de fábrica `admin`/`admin123` (mismo día, sección 5 undevicies):** a pedido del
equipo, el default sin tocar el `.env` pasó de "panel cerrado" a "panel abierto con
`admin`/`admin123`" — retroceso de seguridad deliberado a cambio de que el sistema funcione
nada más clonar el repo, documentado como tal (`config.py`, `.env.example`) y a cambiar antes
de exponer el sistema a estudiantes reales. **330 tests en verde** (308 + 19 + 3).

**Rediseño completo del frontend (02-oct-2026, sección 5 duovicies):** la UI pasó de un estilo mínimo a un design system propio, sin build y sin migrar de Jinja2 + HTMX: modo claro/oscuro, navegación móvil, landing, cuestionario paginado, radar VARK, catálogo con buscador, visor con referencias que muestran el fragmento citado y panel docente responsive. Contraste AA, foco visible y `prefers-reduced-motion` en todas las vistas. Convenciones en [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md). **341 tests en verde.**

Queda una discrepancia abierta: las tablas 16.2/16.3 del informe no se reproducen desde el CSV (sección 5 ter) — es un problema del informe, no del código.

---

## 2. Decisiones tomadas y por qué

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **PostgreSQL 16** | MySQL (que el informe cap. 14 menciona como opción) | `JSONB` nativo para `contenido_json`/`mini_quiz_json`/`metadatos_json` (tablas 17.4, 17.7, 17.8) y full-text search en español sin extensiones. **Verificado**: `to_tsvector('spanish', …)` aplica stemming correcto ("generación"→`gener`, "validadas"→`valid`) y `plainto_tsquery` matchea. |
| **Postgres nativo (winget)**, no Docker | Docker Desktop | Windows 11 Home requiere WSL2 + reinicio para Docker Desktop. Postgres nativo fue más rápido de poner en marcha. El `docker-compose.yml` se dejó igual creado y con las mismas credenciales (`studify`/`studify`/db `studify`), por si en algún momento se prefiere esa vía o se necesita reproducir el entorno en la otra máquina del equipo. |
| **Endpoints FastAPI síncronos** (`def`, no `async def`) + SQLAlchemy síncrono | Async con `asyncpg`/`AsyncSession` | FastAPI corre los `def` en su threadpool, así que el I/O bloqueante (BD, llamadas al LLM) no bloquea el event loop. Evita el error más común en prototipos: mezclar código sync dentro de handlers async y bloquear el server. |
| **LlamaIndex acotado** a `BaseRetriever` custom + `PromptTemplate` + conector LLM | `VectorStoreIndex` (el uso "por defecto" de LlamaIndex) | Usar el índice vectorial estándar contradiría la tesis central del proyecto (RAG estructurado, no semántico). LlamaIndex se usa solo como capa de orquestación de prompt, no de recuperación. |
| **Cliente LLM único vía interfaz OpenAI-compatible** (`llama-index-llms-openai-like`) | SDKs nativos de cada proveedor | DeepSeek, Qwen y GLM (los "LLMs chinos" que el equipo decidió usar) exponen todos una API compatible con OpenAI. Un solo cliente, modelo intercambiable por variable de entorno (`LLM_BASE_URL`, `LLM_MODEL`), sin tocar código. La elección final entre los tres se hace con datos en un bake-off programado para la Fase 3. |
| **`/health` reporta la BD caída en vez de fallar (500)** | Que el endpoint dependa de la BD para responder | Permite distinguir "la app no levanta" de "falta Postgres" al diagnosticar. Los tests (`tests/test_health.py`) corren sin necesidad de una base de datos activa. |
| **UI mínima con Jinja2 + HTMX** servida por el mismo FastAPI | Streamlit / SPA React desde el inicio | Cero build step, todo pasa por `/api/*`, así que una UI más completa después no obliga a rediseñar el backend. Streamlit habría sido un callejón sin salida para la UI final. React queda para una fase posterior si el tiempo lo permite. |
| **`data/*` en `.gitignore`, no `data/`** | `.gitignore` con solo `data/` | Git no permite re-incluir un archivo (`!data/.gitkeep`) cuyo directorio padre está excluido por completo. Con `data/*` + `!data/.gitkeep` el directorio sí se versiona vacío. |

---

## 2 bis. Decisiones tomadas en la Fase 1 (06-ago-2026)

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **Cortes de la tabla 11.1 sobre los porcentajes VARK crudos**, no sobre los C_* | La propuesta original del plan (`recursos_visuales = 0 si C_visual<15, 1 si <25, 2 si ≥25`) | La tabla 11.1 del informe está escrita sobre `p_V`/`p_K` ("p_V ≥ 40% → dos recursos visuales"), no sobre los C_*. Cortar sobre C_visual contradiría al informe: un perfil con `p_V = 40%` exacto da `C_visual = 24,5`, que con el corte propuesto entregaría 1 recurso visual en vez de los 2 que exige la tabla. Cierra la decisión pendiente n.º 1 de `PLAN_DESARROLLO.md` §6. |
| **`palabras_texto` interpolado sobre el rango alcanzable de C_texto** | Interpolar sobre 0–100 | Los C_* **no** recorren 0–100: cada uno tiene un rango acotado (`C_texto ∈ [40,75]`, `C_visual ∈ [10,45]`, `C_narrativo ∈ [5,30]`, `C_practico ∈ [5,25]`), porque los coeficientes de cada columna suman 1,00. Tratar un C_* como porcentaje daría umbrales mal calibrados. Único parámetro del motor no determinado por el informe; **aprobado por el equipo el 06-ago-2026**. |
| **Regla 7 leída como `> 20%` estricto** | `≥ 20%` | "Tres o más dimensiones **sobre** el 20%". Con el criterio inclusivo, un perfil `{0V, 20A, 20R, 60K}` —claramente dominado por K— quedaría multimodal solo porque dos canales tocan el borde exacto. |
| **El tono lo fija el canal dominante; "mixto" solo para perfiles planos** | Que `es_multimodal` fuerce siempre tono mixto | Las reglas 1–5 y la 7 de la tabla 11.1 **se solapan**: `{0V, 21A, 21R, 58K}` cumple ambas a la vez (tres canales sobre 20% y uno sobre 40%), porque el dominante puede ser uno de los tres. Verificado por fuerza bruta sobre la grilla del símplex: 15.960 casos de solapamiento. Se aplican en capas —las reglas 1–5 deciden elementos de contenido, la 6–7 solo la etiqueta de modalidad. |
| **Reparto del residuo por resto mayor** en la normalización a porcentajes | Redondeo simple por canal | El cap. 11.2 exige `p_V+p_A+p_R+p_K = 100` como igualdad estricta y hay un CHECK en la tabla que lo replica. Redondear cada canal por separado no lo garantiza: `{1,1,1,0}` da tres veces 33,33 y suma 99,99. |
| **`TIMESTAMP WITH TIME ZONE`** para todas las fechas | `DATETIME` literal del informe | El informe usa notación MySQL. Un `TIMESTAMP` sin zona en Postgres deja la interpretación a merced del huso de la sesión, y los dos computadores del equipo no tienen por qué compartirlo. |
| **CHECK constraints en vez de `ENUM` nativo** para los vocabularios controlados | `ENUM` de Postgres | Agregar un valor a un `ENUM` exige `ALTER TYPE`; un CHECK se cambia en una migración normal. En un prototipo que todavía está afinando estados, eso importa. |
| **`alembic/versions/` excluido de ruff** | Reformatear las migraciones a mano | Las escribe `--autogenerate` con su propio formato; cualquier arreglo manual se perdería en la siguiente regeneración. |

---

## 3. Qué se instaló y verificó en esta máquina (05-ago-2026)

Entorno de partida: **sin Python, sin Docker, sin Node**, solo Git y winget disponibles.

| Herramienta | Versión instalada | Método |
|---|---|---|
| Python | 3.12.10 | `winget install --id Python.Python.3.12 -e` |
| PostgreSQL | 16.14 | `winget install --id PostgreSQL.PostgreSQL.16 -e` — quedó como servicio Windows `postgresql-x64-16`, `Status: Running`, `StartType: Automatic` |

Base de datos creada manualmente (superusuario `postgres`, password por defecto de winget:
`postgres` — **es solo local, cambiar si se expone algo**):

```sql
CREATE ROLE studify LOGIN PASSWORD 'studify';
CREATE DATABASE studify OWNER studify;
```

Coincide exactamente con las credenciales de `docker-compose.yml` y con `DATABASE_URL` en
`.env.example`, así que ambas vías (nativa o Docker) son intercambiables sin editar `.env`.

**Verificaciones realizadas (no solo "se instaló", sino "se probó que funciona"):**

1. `python -m venv .venv` + `pip install -e ".[dev]"` → instala sin errores. Versiones clave
   resueltas: `fastapi==0.141.1`, `sqlalchemy==2.0.51`, `alembic==1.19.0`, `psycopg==3.3.4`,
   `pydantic==2.13.4`, `llama-index-core==0.14.23`, `llama-index-llms-openai-like==0.7.2`.
2. `pytest` → **2 passed** (`tests/test_health.py`, corre sin BD activa).
3. `ruff check .` → **All checks passed** (se corrigió un orden de imports en `alembic/env.py`
   con `ruff check . --fix`).
4. `GET /health` contra la base **real** (no mockeada) → `{"status": "ok", "database":
   {"reachable": true, "error": null}, "llm": {"model": "deepseek-chat", "api_key_configured":
   false}}`.
5. `alembic current` → conecta correctamente a la BD (todavía sin revisiones, es lo esperado
   en esta fase).
6. Full-text search en español, probado directo contra Postgres vía SQLAlchemy:
   `to_tsvector('spanish', 'La generación aumentada por recuperación ancla el contenido en
   fuentes institucionales validadas')` → stemming correcto, y
   `@@ plainto_tsquery('spanish', 'fuentes validadas')` → `True`.

### 3 bis. Segundo computador del equipo (06-ago-2026)

El proyecto ya corre en una segunda máquina, en la ruta
`C:\Users\vleon\Documents\proyectos\SpotCheck\Studify` (la de la sección anterior era
`e:\code\Studify\Studify`). Diferencias que conviene tener presentes:

| | Máquina 1 | Máquina 2 |
|---|---|---|
| Python | 3.12.10 | **3.14.5** |
| PostgreSQL | 16.14 nativo | 16.x nativo (servicio `postgresql-x64-16`) |
| Clave del superusuario `postgres` | `postgres` (default de winget) | **distinta** — la fijó el instalador, no es la default |

**Python 3.14 no dio problemas**: todas las dependencias resolvieron con wheels `cp314`
(incluidos `numpy`, `psycopg-binary` y `pydantic-core`, que son los que compilan). Las versiones
de librerías quedaron idénticas a las de la máquina 1: `fastapi==0.141.1`, `sqlalchemy==2.0.51`,
`alembic==1.19.0`, `psycopg==3.3.4`, `pydantic==2.13.4`, `llama-index-core==0.14.23`. Aun así,
`pyproject.toml` declara `requires-python = ">=3.11"` y no fija una versión exacta, así que
ambas máquinas son válidas.

El rol y la base se crearon igual que en la máquina 1 (mismas credenciales `studify`/`studify`),
por lo que `DATABASE_URL` del `.env` es la misma en ambas y no hay que editar nada al cambiar de
computador.

**Ojo con `seminario_titulo.md`:** el informe **no estaba versionado** (quedó solo en la máquina
1) y sin él no se puede escribir ni el modelo de datos ni el motor VARK. Se subió a
`docs/seminario_titulo.md` el 06-ago-2026 y el enlace de la sección 0 se corrigió en
consecuencia. No volver a sacarlo del repo.

### 3 ter. Los 43 diagnósticos reales cargados en la Máquina 1 (10-ago-2026)

`data/data_cuestionarios_43.csv` (no versionado — está en `.gitignore`) llegó a esta máquina y se
cargó con `python scripts/import_vark_csv.py data/data_cuestionarios_43.csv --reset`. El
`--dry-run` previo reprodujo exactamente los promedios ya documentados en la sección 5 ter
(V=5,44 A=7,37 R=7,23 K=7,91), confirmando que es el mismo dataset que en la máquina de Patricio.
`--reset` solo toca `estudiante` (con CASCADE a diagnóstico/respuestas/configuración) — no afecta
`objetivo_aprendizaje`, `documento_fuente` ni `fragmento`. Reemplazó 28 diagnósticos que eran
ruido de `test_api_diagnosticos.py` (crea diagnósticos y no los limpia) por los 43 reales.
Verificado: `estudiante`, `diagnostico_vark` y `configuracion_contenido` quedaron en 43 cada una.

> ⚠️ **Volvió a pasar.** Esta limpieza barrió el resultado pero no la causa: `pytest` siguió
> sumando estudiantes en cada corrida y al 26-ago-2026 había otra vez **157 diagnósticos** para
> 43 reales. La fixture que lo cierra de raíz se agregó ese día — ver sección 5 vicies.

**Distinción importante para no confundir en sesiones futuras:** este CSV son las **respuestas
del cuestionario VARK** (dato de estudiantes). No es el **catálogo de objetivos de aprendizaje**
que la Fase 3 necesita (`codigo_objetivo, asignatura, unidad, tema, descripcion,
nivel_taxonomico`, cargado con `scripts/cargar_objetivos.py`) — son dos CSV distintos con
propósitos distintos. Ese sigue sin existir en ninguna máquina.

De paso se eliminó un documento huérfano (`documento_fuente` id 46, `'otro_nombre'`) que había
quedado de una corrida end-to-end fallida durante la verificación de la Fase 2.

---

## 4. Estructura del repositorio (estado real, no aspiracional)

```
Studify/
├─ .env.example          # plantilla — LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, DATABASE_URL, etc.
├─ .env                  # copia local, NO versionada (ya creada en esta máquina)
├─ .gitignore
├─ .gitattributes
├─ README.md             # instrucciones de instalación y arranque
├─ docker-compose.yml    # Postgres 16 alternativo a la instalación nativa
├─ pyproject.toml        # dependencias + config de ruff/pytest
├─ alembic.ini
├─ alembic/
│  ├─ env.py             # lee DATABASE_URL desde studify.config; importa models para autogenerate
│  ├─ script.py.mako
│  └─ versions/
│     ├─ ec6446cc3c52_*.py  # Fase 1: las 8 entidades. Aplicada y verificada reversible.
│     ├─ 8eb6f0399fee_*.py  # Fase 1: estudiante.genero a VARCHAR(50)
│     ├─ 8010505ef66e_*.py  # Fase 3: huella_generacion + modelo_llm. ⚠️ corregida a mano:
│     │                     #   autogenerate quería borrar el índice GIN de FTS
│     ├─ 5e11a9cf4a0b_*.py  # Fase 5: tabla interaccion_quiz
│     └─ 2fbc7391c0a3_*.py  # Fase 5: numero_intento + nulables. ⚠️ corregida a mano: mismo
│                           #   defecto del índice GIN, otra vez
├─ src/studify/
│  ├─ main.py            # app FastAPI + endpoint /health
│  ├─ config.py          # Settings (pydantic-settings, lee .env)
│  ├─ db/
│  │  ├─ base.py         # DeclarativeBase compartida
│  │  ├─ session.py      # engine + SessionLocal + get_db() síncronos
│  │  └─ models.py       # ✅ las 8 entidades del cap. 17
│  ├─ vark/              # ✅ motor completo
│  │  ├─ scoring.py      #    16 ítems → puntajes crudos → vector porcentual
│  │  ├─ weighting.py    #    fórmulas C_* del cap. 11.2 + rangos alcanzables
│  │  ├─ hierarchy.py    #    canal primario/secundario/multimodalidad (derivado)
│  │  └─ rules.py        #    tabla 11.1 → configuracion_contenido + directivas de prompt
│  │  └─ instrumento.py  #    matriz de puntuación: las 64 alternativas → canal
│  ├─ api/
│  │  ├─ schemas.py      # ✅ contratos Pydantic del perfilamiento
│  │  ├─ schemas_knowledge.py  # ✅ contratos de la base de conocimiento (Fase 2)
│  │  ├─ schemas_capsulas.py   # ✅ contratos de la generación (Fase 3)
│  │  └─ routers/
│  │     ├─ diagnostics.py  # ✅ POST /api/diagnosticos, GET /api/diagnosticos/{id}
│  │     ├─ knowledge.py    # ✅ documentos, fragmentos, curación, catálogo, recuperar
│  │     └─ capsules.py     # ✅ POST /api/capsulas (+ caché, ?regenerar, historial)
│  ├─ knowledge/         # ✅ ingesta, curación y etiquetado (Fase 2)
│  │  ├─ extract.py      #    PDF/PPTX → bloques con página y detección de encabezados
│  │  ├─ chunker.py      #    bloques → fragmentos recuperables (fronteras duras)
│  │  ├─ ingest.py       #    persistencia + dedup por SHA-256 + almacén de archivos
│  │  ├─ curation.py     #    validar / descartar / asignar objetivo / editar texto
│  │  └─ tagger.py       #    ✅ sugerencia de objetivo/etiqueta por LLM — propone, no decide
│  │                     #       (sección 5 septendecies, 24-ago-2026)
│  ├─ rag/               # ✅ recuperación determinista (Fase 2) + prompt (Fase 3)
│  │  ├─ retriever.py    #    SQL por id_objetivo + FTS español + orden por canal VARK
│  │  ├─ orchestrator.py #    ✅ ensamblado del prompt maestro + huella de caché
│  │  └─ prompts/
│  │     └─ maestro.py   #    ✅ plantillas + directiva VARK → instrucción estructural
│  ├─ generation/        # ✅ motor de generación (Fase 3)
│  │  ├─ schemas.py      #    contrato de la microcápsula: 7 pasos pedagógicos
│  │  ├─ idioma.py       #    detección de deriva de idioma (regla 6)
│  │  ├─ validator.py    #    parser tolerante + reglas 2, 5 y 6 + realimentación
│  │  └─ generator.py    #    cliente LLM (inyectable) + bucle de reparación
│  └─ web/               # ✅ UI mínima con HTMX + Jinja2 (Fase 4, conectada al motor)
│     ├─ deps.py         #    entorno Jinja2 + procesador de contexto (`es_docente`)
│     ├─ sesion.py       #    ✅ cookies firmadas: `id_estudiante` (quién) y `docente` (permiso)
│     ├─ textos.py       #    ✅ copy de la UI + enunciados de los 16 ítems (verificados 24-ago)
│     ├─ routers/
│     │  ├─ auth.py      #    ✅ login/logout del docente + guardián de /teacher/* (26-ago)
│     │  ├─ student.py   #    ✅ cuestionario, perfil, catálogo, visor, quiz e intentos (Fase 5)
│     │  └─ teacher.py   #    ✅ curación + analíticas + simulador VARK (Fase 5, sección 5 decies)
│     ├─ templates/
│     │  ├─ student/     #    _capsula.html (partial compartido con el simulador), _feedback, …
│     │  └─ teacher/     #    login.html, _bandeja, _fila, analytics, simulator, _comparacion
│     └─ static/css/
├─ tests/
│  ├─ conftest.py        # ✅ fixtures compartidas (necesita_bd, db, almacen_temporal)
│  ├─ test_health.py     # smoke test de Semana 0
│  ├─ test_vark.py       # ✅ 44 tests del motor VARK, contrastados contra el informe
│  ├─ test_api_diagnosticos.py   # ✅ 15 tests del endpoint (+ limpieza autouse, 26-ago)
│  ├─ test_knowledge_ingesta.py  # ✅ 22 tests de extracción y chunking (sin BD)
│  ├─ test_knowledge_persistencia.py  # ✅ 6 tests de ingesta contra Postgres
│  ├─ test_curacion_retriever.py      # ✅ 17 tests de curación y determinismo
│  ├─ test_tagger.py                  # ✅ 12 tests del etiquetado por LLM (propone, no decide)
│  ├─ material.py                # ✅ material de prueba compartido de la Fase 3 (no es un test)
│  ├─ test_generacion_contrato.py     # ✅ 56 tests del contrato y las 6 reglas (sin BD ni LLM)
│  ├─ test_prompt_maestro.py          # ✅ 25 tests del prompt y la huella (sin BD ni LLM)
│  ├─ test_generador.py               # ✅ 15 tests del bucle de reparación (LLM falso)
│  ├─ test_api_capsulas.py            # ✅ 14 tests del endpoint (Postgres, LLM falso)
│  ├─ test_web_estudiante.py          # ✅ 24 tests del flujo web del estudiante (Fase 4)
│  ├─ test_web_auth.py                # ✅ 19 tests del login del docente y el guardián (26-ago)
│  ├─ test_web_docente.py             # ✅ 18 tests del panel de curación, incl. etiquetado (Fase 4)
│  ├─ test_web_simulador.py           # ✅ 13 tests del simulador VARK, incl. comparación (Fase 5)
│  ├─ test_interaccion_quiz.py        # ✅ 12 tests de intentos numerados y ownership (Fase 5)
│  ├─ test_cobertura_curricular.py    # ✅ 12 tests de cobertura por canal (Fase 5)
│  └─ test_textos_vark.py             # ✅ 2 tests: enunciados vs. CSV original (se saltan sin el CSV)
├─ scripts/
│  ├─ import_vark_csv.py   # ✅ carga los 43 diagnósticos reales (--dry-run, --reset)
│  ├─ cargar_objetivos.py  # ✅ carga el catálogo curricular desde CSV (--dry-run)
│  ├─ eval_runner.py       # ✅ batería de evaluación técnica / bake-off (Fase 3)
│  └─ reset_db.py          # ⚠️ drop_all sin confirmación — ver sección 6, punto 12
├─ data/                  # vacío (.gitkeep), ignorado por git salvo el .gitkeep
└─ docs/
   ├─ seminario_titulo.md # el informe fuente (subido el 06-ago-2026, antes no estaba en el repo)
   ├─ PLAN_DESARROLLO.md  # plan completo de 10 semanas, decisiones pendientes, riesgos
   └─ AVANCE.md           # este archivo
```

**Nota importante:** ya no queda ningún paquete vacío. `db/`, `vark/`, `knowledge/`, `rag/`,
`generation/` y `api/` tienen lógica real y tests. Adicionalmente, el material curricular real y la credencial han sido incorporados al entorno (el Bake-off concluyó exitosamente con DeepSeek).

---

## 5. Qué se hizo y se verificó en la Fase 1 (06-ago-2026)

**Modelo de datos — las 8 entidades del cap. 17, migradas y aplicadas.**

- `src/studify/db/models.py` transcribe las tablas 17.1–17.8 a SQLAlchemy 2.0, adaptando los
  tipos MySQL del informe a Postgres (`DATETIME`→`TIMESTAMPTZ`, `TINYINT`→`SMALLINT`,
  `JSON`→`JSONB`, `DECIMAL`→`NUMERIC`).
- Migración `ec6446cc3c52`, generada con `--autogenerate` y **verificada reversible**:
  `upgrade head` → 9 tablas → `downgrade base` → solo queda `alembic_version` → `upgrade head`
  → 9 tablas otra vez.
- Índice GIN de full-text search en español añadido **a mano** a la migración: autogenerate
  **no emite los índices definidos por expresión**. Verificado en la BD como
  `gin (to_tsvector('spanish'::regconfig, contenido_texto))`. ⚠️ Si alguien regenera esta
  migración desde cero, hay que volver a agregarlo.

**Motor VARK — completo, 41 tests.**

`scoring.py` (cap. 10) → `weighting.py` (cap. 11.2) → `hierarchy.py` (cap. 17.2) →
`rules.py` (tabla 11.1). Los tests no comprueban valores sacados del propio código: cada uno
contrasta contra una afirmación concreta del informe.

Verificaciones que encontraron algo (no solo "pasa el test"):

1. **Los C_* suman exactamente 100** para cualquier vector de entrada, porque los coeficientes
   de cada canal suman 1,00 (V: 0,40+0,45+0,05+0,10; A, R y K análogos). Confirmado
   numéricamente. Esto hace que los pesos sean interpretables como reparto del énfasis
   instruccional — y hay un test que lo protege si alguien edita la matriz.
2. **Los C_* no recorren 0–100**, cada uno tiene un rango acotado (ver tabla de decisiones).
   Es el motivo por el que se descartó la propuesta de cortes del plan.
3. **Las reglas 1–5 y la 7 de la tabla 11.1 se solapan**, y no se arregla cambiando `≥` por `>`:
   el canal dominante puede ser uno de los tres que superan el 20% (`{0V, 21A, 21R, 58K}`).
   Comprobado por fuerza bruta sobre la grilla del símplex → 15.960 casos. Se resolvió
   aplicándolas en capas, no como alternativas excluyentes.
4. **Bug encontrado por la prueba end-to-end, no por los tests unitarios:** un perfil multimodal
   `{33,34V / 33,33A / 0R / 33,33K}` recibía una sola directiva de prompt
   (`recurso_visual_complementario`), porque la rama multimodal solo se aplicaba si ninguna otra
   regla había disparado. Contradecía la regla 7 ("cápsula equilibrada integrando los cuatro
   registros"). Corregido y con test de regresión.
5. **End-to-end contra Postgres real:** calificar → reglas → persistir en `estudiante` +
   `diagnostico_vark` + `respuesta_vark` + `configuracion_contenido`, con el caso de redondeo
   más incómodo (`{1,1,0,1}` → 33,34/33,33/0/33,33). El CHECK de suma=100 lo acepta, y el
   `ON DELETE CASCADE` limpia las cuatro tablas.

Estado de las verificaciones: **41 tests VARK + 2 de salud = 43 passed**, `ruff check .` limpio,
`/health` con `database.reachable: true`.

---

## 5 ter. Carga de los 43 diagnósticos reales (06-ago-2026)

Los 43 registros del Google Forms (`data/data_cuestionarios_43.csv`, no versionado) están
cargados en Postgres: 43 estudiantes, 43 diagnósticos, **1.202 respuestas individuales**, 43
configuraciones. Los porcentajes suman 100 exacto en las 43 filas.

El importador es `scripts/import_vark_csv.py` (con `--dry-run` y `--reset`). La matriz de
puntuación vive en `src/studify/vark/instrumento.py`, no en el script, porque es la definición
del instrumento y no un detalle de la carga.

### El mapeo alternativa→canal está verificado por dos vías independientes

1. **Semántica:** cada alternativa describe un canal sin ambigüedad.
2. **Posicional:** Google Forms exporta las selecciones múltiples en el orden en que las
   opciones aparecen en el formulario. Reconstruido ese orden desde las respuestas reales, los
   **16 ítems presentan sus alternativas en el orden V, A, R, K sin excepción**.

Las dos vías coinciden en los 64 textos. No es el mapeo lo que falla.

### ⚠️ Las tablas 16.2 y 16.3 del informe NO se reproducen desde el CSV

**El dataset es el correcto**: todos los sociodemográficos del cap. 16.1 calzan al número —
n=43, Ing. Informática n=23, género 27/14/2, año de carrera 20/9/7/7.

| | Informe | Calculado desde el CSV |
|---|---|---|
| Promedios, muestra total | V=3,1 A=6,2 R=5,8 K=6,5 | **V=5,44 A=7,37 R=7,23 K=7,91** |
| Promedios, Ing. Informática | V=3,65 A=6,57 R=5,17 K=7,96 | **V=6,30 A=7,87 R=6,22 K=9,61** |
| Ranking, muestra total | K > A > R > V | **K > A > R > V** ✅ coincide |
| Ranking, Ing. Informática | K > A > R > V | K > A > **V > R** (R y V casi empatados: 6,22 vs 6,30) |
| Moda de perfil | A+K | K (unimodal) |

**Lo que sí se sostiene, y es lo que importa para el código:** el cap. 16.4 fija
`perfil = K→A` como parámetro por defecto del prompt, y **eso se reproduce exactamente** —
K primario, A secundario, en ambos segmentos. La conclusión de diseño del informe es correcta
aunque sus números intermedios no cuadren.

**Por qué no cuadran.** Los promedios del informe implican ~21,6 selecciones por persona; el
CSV tiene **28,0** (mín. 16, máx. 58). Se probaron cuatro reglas de conteo —todas las marcas,
solo la primera, tope de 2 por ítem, solo ítems de respuesta única— y ninguna se acerca: la
mejor deja un error acumulado de 4,6 puntos. **Los números publicados no salen de este CSV con
ninguna regla de conteo razonable.** Queda como discrepancia abierta a resolver con el equipo y
la profesora guía; lo más probable es que la tabulación original se haya hecho a mano o sobre
un export parcial.

### Criterio de clasificación de perfiles (decidido el 06-ago-2026)

Un canal está **activo** si empata con el máximo o queda a ≤10 puntos porcentuales de él. Con
dos activos el perfil es bimodal; con tres o más, multimodal.

Esto **reemplaza** la implementación anterior, que usaba la fila 7 de la tabla 11.1 («tres o más
dimensiones sobre el 20%») para etiquetar. Ese umbral es absoluto y no relativo al máximo, así
que marcaba como multimodal a perfiles claramente dominados: `{0V, 21A, 21R, 58K}` quedaba
multimodal pese a que A y R están a 37 puntos de K. La fila 7 se conserva, pero como regla de
**contenido** (qué bloques incluir), que es donde el informe la usa.

---

## 5 quinquies. `POST /api/diagnosticos` — el flujo completo por HTTP

Con esto la Fase 1 queda cerrada según su criterio de término. Archivos nuevos:

- `src/studify/api/schemas.py` — contratos Pydantic de entrada/salida.
- `src/studify/api/routers/diagnostics.py` — `POST /api/diagnosticos` y
  `GET /api/diagnosticos/{id}`, conectados en `main.py` con `include_router`.

**El cliente no conoce la matriz de puntuación.** El cuestionario se responde por posición
(«ítem 3, alternativa b») y es el servidor quien traduce eso a un canal, vía
`instrumento.canal_por_posicion()`. Si la matriz cambiara, se recalculan los perfiles desde
`respuesta_vark` sin tocar el frontend ni volver a aplicar el cuestionario — que es exactamente
para lo que el cap. 17.1 justifica esa tabla.

**La jerarquía se recalcula al leer, no se guarda.** `GET /api/diagnosticos/{id}` deriva canal
primario/secundario y modalidad desde los porcentajes almacenados, cumpliendo el cap. 17.2: la
interpretación categórica no puede quedar desincronizada del vector porque no existe como dato.

Verificado contra el servidor real (no solo con `TestClient`): un perfil `{A=40, K=60}` devuelve
201 con la configuración completa. Caso interesante que confirma el diseño en capas — queda
**unimodal K** (diferencia de 20 > 10) pero sus directivas incluyen igual las auditivas, porque
`p_A = 40` dispara la fila 4 de la tabla 11.1 con independencia de la etiqueta de modalidad.

Los tests que tocan la base **se saltan solos si Postgres no está levantado**, mismo criterio que
`test_health.py`, para que `pytest` siga verde en una máquina recién clonada.

---

## 5 sexies. UI Mínima Funcional (07-ago-2026)

Se adelantó el desarrollo de un andamiaje visual para la Fase 4 creando una maqueta UI funcional para interactuar con el motor.
- **Tecnologías:** FastAPI (servidor), Jinja2 (plantillas renderizadas en servidor), HTMX (interactividad, reemplazo de fragmentos sin SPA) y Vanilla CSS (diseño limpio, premium, sin frameworks pesados).
- **Flujo Estudiante:** Vistas creadas y enrutadas (con datos *mock*) para el Cuestionario VARK (`vark.html`), Resultados del Perfil (`profile.html`), Catálogo de Temas en cascada (`catalog.html`) y el Visor de Microcápsulas (`viewer.html` con quiz interactivo).
- **Flujo Docente:** Panel de Curación (`curation.html`) preparado para subir documentos (PDF/PPTX) y una bandeja interactiva para revisar/aprobar/rechazar fragmentos extraídos de la base de conocimiento.
- **Infraestructura Web:** Configurado el montaje estático (`/static`), directrices en `deps.py`, endpoints en `student.py` y `teacher.py`, resolviendo problemas de firmas con `TemplateResponse` de las versiones recientes de FastAPI/Starlette.

---

## 5 septies. Fase 2 — Ingesta, curación y retriever determinista (10-ago-2026)

Cierra el núcleo de la base de conocimiento: entra un PDF/PPTX oficial, sale material curado
que el retriever puede recuperar de forma determinista y trazable.

### Arquitectura en tres capas

Se separó en tres módulos en vez del `ingest.py` único que proponía el plan, porque la
fragmentación es la decisión que más impacta la calidad del RAG y conviene poder ajustarla y
testearla sin volver a parsear archivos:

| Módulo | Responsabilidad | Depende de Postgres |
|---|---|---|
| `knowledge/extract.py` | Archivo → bloques con página y marca de encabezado | No |
| `knowledge/chunker.py` | Bloques → fragmentos recuperables | No |
| `knowledge/ingest.py` | Persistencia, dedup, almacén de archivos | Sí |

### Decisiones tomadas en la Fase 2

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **Fragmento objetivo de ~180 palabras** (máx. 350, mín. 40) | Fragmentar por página o por párrafo | La cápsula mide 150–300 palabras y se genera *a partir* del fragmento. Uno más corto no alcanza a sostenerlas y el LLM rellena inventando —alucinación por falta de contexto, no por exceso—; uno más largo rompe la correspondencia «un fragmento ↔ un objetivo» del cap. 12. |
| **El encabezado es frontera dura**: siempre abre fragmento nuevo | Cerrar solo al llegar al tamaño objetivo | Unir dos secciones distintas en un fragmento destruye la correspondencia temática, que es lo único que hace recuperable el material. Se aplica aunque el fragmento anterior quede corto. |
| **Detección de encabezados por tamaño de fuente relativo** (moda del documento × 1,15, y ≤ 15 palabras) | Umbral absoluto de tamaño | Cada apunte usa su propia tipografía: un umbral fijo marca todo como título en un documento de letra grande y nada en uno de letra chica. La moda se pondera por caracteres para que muchos títulos cortos no desplacen al cuerpo real. |
| **La tabla va siempre en su propio fragmento** | Mezclarla con la prosa circundante | Para un perfil visual la tabla comparativa es el recurso que pide la tabla 11.1; fundida en un párrafo se vuelve irrecuperable. |
| **No se puede validar un fragmento sin objetivo asignado** | Permitirlo y asignar después | El retriever recupera por `id_objetivo`. Un fragmento validado con `id_objetivo = NULL` queda inalcanzable para siempre: aprobado, sin error visible y sin llegar nunca a una cápsula. Es el fallo silencioso más fácil de cometer revisando decenas de fragmentos seguidos. |
| **El retriever filtra `documento.estado_curacion != 'rechazado'`**, no `== 'validado'` | Exigir el estado positivo | Con el criterio positivo, una curación fragmento a fragmento sin marcar el documento completo devolvería cero resultados en silencio. En negativo, rechazar un documento sí retira su material aunque los fragmentos estuvieran validados. |
| **Validar un fragmento promueve el documento a `validado`** | Dejar el estado del documento a cargo del curador | Si no, el documento queda "pendiente" para siempre y el panel muestra trabajo terminado como si estuviera por hacer. |
| **Descartar no borra** | `DELETE` del fragmento | El cap. 12 exige trazabilidad del proceso de curación: saber qué se descartó (y que se revisó) es parte de eso. |
| **`DELETE /api/documentos/{id}` se rechaza si el documento fundamentó cápsulas** | Permitir el borrado siempre | La FK es `ON DELETE SET NULL`: borrar no daría error, dejaría cápsulas con la fuente en blanco y rompería en silencio la auditabilidad del cap. 13. Para retirar material ya usado está `estado_curacion = 'rechazado'`. |
| **El catálogo oculta los objetivos sin material validado** | Mostrar todos los temas | Un tema sin fragmentos validados no puede producir una cápsula fundamentada: llevaría al estudiante a un error o a contenido inventado. |
| **El canal VARK reordena, no filtra** | Devolver solo los tipos preferidos del canal | Si un perfil visual recibiera solo tablas, un apunte sin tablas no daría nada. La preferencia sube los tipos afines y conserva el resto. |
| **Los archivos se copian a `data/documentos/<sha256>.<ext>`** | Guardar la ruta original del docente | `ruta_archivo` debe seguir siendo válida aunque el docente mueva o borre su copia. Nombrar por hash evita además colisiones entre archivos llamados igual. |

### Bug encontrado inspeccionando la salida, no por los tests

Los 21 tests iniciales pasaban en verde y aun así **el texto extraído de todo PDF venía
corrupto**: PyMuPDF entrega una `line` por renglón y se estaban uniendo con `""`, de modo que la
última palabra de un renglón quedaba pegada a la primera del siguiente (`parareducir`,
`nocontienen`, `ningunatributo`). Los tests de estructura —encabezados, páginas, numeración— no
lo veían porque la estructura era correcta; solo apareció al imprimir el texto de un documento
realista. Corregido uniendo las líneas con `"\n"` (que `normalizar` convierte después en espacio
y aprovecha para deshacer los guiones de corte) y con test de regresión que verifica que todo
token del texto extraído exista en el original.

Habría degradado el full-text search en español y le habría entregado texto corrupto al LLM en
la Fase 3, sin ningún síntoma visible salvo cápsulas de mala calidad.

### Verificación end-to-end contra el servidor real

Los 45 tests nuevos (22 sin BD + 6 de ingesta + 17 de curación/retriever) se complementaron con
una corrida completa por HTTP sobre `uvicorn`, que confirmó las invariantes que importan:

1. El catálogo **no muestra** un objetivo sin material validado.
2. Reingerir el mismo archivo con otro nombre → **409** (dedup por contenido).
3. `GET /api/recuperar` devuelve **vacío antes de curar** — la barrera del cap. 12/13.
4. Validar sin objetivo → **422** con el motivo explicado.
5. Tras curar, la recuperación entrega los fragmentos **con su cita** (`documento, p. N`).
6. **Determinismo:** tres llamadas idénticas devuelven `[161, 162]` en el mismo orden.
7. El full-text search en español acota de 2 a 1 fragmento con `"dependencia parcial claves"`.

### Limitación conocida

La deduplicación es por SHA-256 de los **bytes**, así que detecta el mismo archivo subido dos
veces pero **no una reexportación** del mismo documento: un PDF regenerado lleva otro
`/CreationDate` embebido y por lo tanto otro hash. Si el docente vuelve a exportar el apunte
desde PowerPoint, entra como documento nuevo y sus fragmentos conviven con los anteriores en el
retriever. Mitigarlo pide comparar el texto extraído y no los bytes.

---

## 5 octies. Fase 3 — Motor de generación (11-ago-2026)

Cierra el motor completo: entra un `(id_estudiante, id_objetivo)` y sale una microcápsula
validada, en español, con quiz y con fuentes verificables contra el material curado.

> ⚠️ **Leer junto con la sección 5 terdecies (19-ago-2026).** La *forma* de la microcápsula que
> describe esta sección —`contenido[]`, una lista de bloques sueltos— fue reemplazada por la
> estructura pedagógica de siete pasos que definió la profesora guía. Todo lo demás de esta
> sección (las seis reglas del validador, el bucle de reparación, la huella de caché, el
> detector de idioma) sigue vigente tal cual.

### Módulos nuevos

| Módulo | Responsabilidad | Necesita LLM |
|---|---|---|
| `generation/schemas.py` | Contrato Pydantic de la microcápsula (reglas 1, 3 y 4 del plan §3) | No |
| `generation/idioma.py` | Detección de deriva de idioma (regla 6) | No |
| `generation/validator.py` | Parser tolerante + reglas 2, 5 y 6 + realimentación | No |
| `rag/prompts/maestro.py` | Plantillas y traducción de directivas VARK a instrucciones | No |
| `rag/orchestrator.py` | Ensamblado del prompt y huella de caché | No |
| `generation/generator.py` | Llamada al modelo y bucle de reparación | Solo el cliente real |
| `api/routers/capsules.py` | `POST /api/capsulas`, historial y consulta por id | Solo al generar |

**Solo una línea del motor habla con el modelo.** Todo lo demás —contrato, validación, prompt,
bucle de reparación, caché— se ejerce con un cliente falso, sin red y sin costo. Por eso los
94 tests nuevos corren en una máquina sin `LLM_API_KEY`.

### Decisiones tomadas en la Fase 3

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **Detección de idioma por conteo de palabras funcionales**, escrita a mano | `langdetect` u otra librería | `langdetect` es probabilístico y, sin fijarle la semilla, **devuelve resultados distintos entre corridas sobre el mismo texto**. Meter no-determinismo dentro del validador contradice el argumento del cap. 13 y haría que un mismo JSON se acepte o rechace según la corrida. El problema real es acotado —distinguir español de inglés y de chino— y con listas de marcadores es exacto y explicable. |
| **Las palabras clave de SQL quedan fuera de la lista de marcadores del inglés** (`from`, `where`, `select`, `in`, `on`, `as`, `not`, `all`, `and`, `or`, `by`, `if`) | Usar una lista de stopwords estándar | Una cápsula legítima en español sobre bases de datos contiene todas esas palabras. Con la lista estándar, el validador rechazaría por «deriva al inglés» justo el contenido de la asignatura que se está usando de piloto. Hay un test que cubre ese caso. |
| **Escape por ortografía española** (tildes, ñ, ¿, ¡) cuando el ratio de palabras funcionales es bajo | Solo el umbral de ratio | Un perfil visual puede recibir una cápsula casi toda de tabla y glosario, donde apenas hay palabras funcionales. Sin el escape sería un falso rechazo sistemático contra los perfiles V. |
| **`documento` y `pagina` de las fuentes se reescriben con los valores de la base** | Confiar en lo que redactó el modelo | Si la cápsula cita el fragmento 161, la procedencia la afirma el sistema consultando `fragmento`/`documento_fuente`. Así la trazabilidad del cap. 13 es verdadera por construcción y no depende de que el modelo copie bien un número de página. Cuántas veces la corrigió queda como métrica. |
| **`PromptMaestro` acarrea los fragmentos que embebió** | Que el llamador se los pase por separado al validador | Si fueran dos listas distintas, la regla 5 podría rechazar una cita legítima o —peor— dejar pasar una inventada. Toda la tesis se apoya en que esa comprobación sea exacta. |
| **El bloque de perfil pide bloques concretos, no adjetivos de tono** | «Redacta de forma visual / práctica» | Es la mitigación que el propio plan §5 fija para el riesgo de que las cuatro cápsulas salgan indistinguibles. Cada directiva de `vark/rules.py` se traduce a una instrucción que nombra un `tipo` del contrato y una cantidad, de modo que la diferencia es comprobable en la cápsula resultante. |
| **El prompt nunca nombra el canal ni la etiqueta del perfil** | Decirle «este estudiante es kinestésico» | El cap. 17.2 prohíbe persistir la etiqueta, y además nombrarla invita al modelo a comentar el estilo de aprendizaje en vez de aplicarlo. Hay un test que lo verifica. |
| **`palabras_texto` se redondea a tramos de 10 antes de entrar al prompt** | Usar el valor exacto | La huella de caché se calcula sobre lo que entra al prompt. Sin redondear, casi cada estudiante tendría su propio tramo y el caché no serviría: en una cohorte de 43 se pagarían 43 generaciones del mismo tema. Pedir «aproximadamente 247» y «aproximadamente 250» da cápsulas indistinguibles. |
| **La huella incluye los fragmentos y el modelo**, no solo objetivo y configuración | La definición literal del plan §4 | Ambos cambian la salida: si el docente valida material nuevo, la cápsula cacheada dejó de reflejar el material disponible; y el bake-off corre la misma configuración contra tres modelos, que sin esto se pisarían en el caché. |
| **Caché compartido entre estudiantes del mismo tramo, copiando la fila** | Compartir la misma fila, o cachear solo por estudiante | Se ahorra la llamada al modelo, que es lo caro, pero cada estudiante conserva su propia fila: la tabla 17.8 vincula cada cápsula a un estudiante y el A/B de la Fase 5 necesita saber qué vio cada uno. |
| **`get_cliente_llm` devuelve `None` si falta la credencial**, en vez de abortar con 503 | Levantar 503 dentro de la dependencia | Las dependencias de FastAPI se resuelven **antes** del handler: abortar ahí dejaría sin servir también las cápsulas que ya estaban en caché y no necesitan al modelo. El 503 se levanta recién cuando se comprueba que hay que generar. Con el `.env` actual (sin key) la demo puede seguir mostrando lo ya generado. |
| **La actividad se guarda en `mini_quiz_json`, aparte de `contenido_json`** | Meter la cápsula entera en `contenido_json` | La tabla 17.8 declara las dos columnas por separado; dejar una en NULL apartaría el modelo físico del diccionario de datos del informe sin ninguna ganancia. |
| **Dos columnas nuevas en `microcapsula_generada`** (`huella_generacion`, `modelo_llm`) | Guardar la huella dentro de `contenido_json` | La huella se consulta en cada petición y un `->>` sobre JSONB no aprovecha índice. `modelo_llm` hace legible una cápsula guardada: el bake-off deja en la misma tabla las cápsulas de los tres modelos y sin la columna no hay forma de saber cuál produjo cada una. **Son un añadido a la tabla 17.8 del informe** y hay que declararlo en el capítulo 17. |

### Decisión de regeneración: se versiona, no se sobrescribe

Cierra la decisión 5 de la sección 7, que estaba marcada como «se decide en la Fase 3».

`POST /api/capsulas` devuelve por defecto la cápsula ya generada para la misma huella;
`?regenerar=true` produce una versión nueva y **conserva la anterior**. Se descartó sobrescribir
porque el bake-off de la Fase 3 (mismo prompt × 3 modelos × 4 perfiles) y la validación docente
de la Fase 5 comparan varias cápsulas del mismo objetivo, y sobrescribir las haría desaparecer.

### Dos cosas que encontró la inspección, no los tests

1. **El autogenerate de Alembic volvió a proponer borrar el índice GIN de full-text search.**
   La migración `8010505ef66e` salió con un `drop_index('ix_fragmento_contenido_fts')` en el
   `upgrade` y su `create_index` en el `downgrade` — o sea, destruir el índice del retriever al
   migrar hacia adelante. Es el mismo defecto ya advertido en la sección 5 (autogenerate no ve
   los índices definidos por expresión), y esta vez se cumplió. Ambas líneas se quitaron a mano
   y la migración quedó verificada reversible: `head → downgrade -1 → upgrade head` deja las dos
   columnas nuevas y el índice FTS intacto en los tres estados. **Si alguien regenera esta
   migración, hay que volver a quitarlas.**

2. **El prompt le pedía al modelo un bloque que no existe.** Imprimiendo el prompt ensamblado
   para un perfil K se vio la línea «Componentes prácticos (bloques `ejemplo_resuelto` o
   `lista_pasos`): 3» junto a solo **dos** instrucciones de bloque. La causa: con `p_K ≥ 40%` la
   tabla 11.1 cuenta tres componentes —ejemplo aplicado, secuencia paso a paso y actividad
   «inténtalo tú»— pero el tercero es la **actividad de cierre**, que no es un bloque de
   `contenido`. Tal como estaba, el modelo tenía que inventarse un tercer bloque para cuadrar la
   cuenta. Corregido en la redacción del bloque de perfil, con test de regresión. Los tests no
   lo veían porque cada pieza era correcta por separado.

### Qué cubren los 94 tests nuevos

- `test_generacion_contrato.py` (42): las seis reglas de rechazo, el parser tolerante
  (cercas Markdown, preámbulo del modelo, coma colgante, llave dentro de una cadena, respuesta
  truncada) y los casos límite del detector de idioma.
- `test_prompt_maestro.py` (23): sincronía entre módulos —toda directiva de `vark/rules.py`
  tiene instrucción, todo campo del contrato aparece en el prompt—, diferenciación entre los
  cuatro perfiles y las propiedades de la huella de caché.
- `test_generador.py` (15): el bucle de reparación completo con cliente falso, incluidos los
  cuatro modos de fallo que tiene que poder reparar.
- `test_api_capsulas.py` (14, requieren Postgres): lo que el endpoint rechaza, el caché en sus
  dos niveles, el versionado y el comportamiento sin credencial.

Dos de ellos existen para detectar **desincronización entre módulos**, que es el fallo que no
produce ningún error y sí cápsulas peores: si alguien agrega una regla a `vark/rules.py` sin
traducirla en `rag/prompts/maestro.py`, ese elemento del perfil desaparecería de la cápsula sin
dejar rastro; y si el contrato cambia sin que cambie el prompt, se gastarían los dos reintentos
en cada llamada. Ambos casos fallan la suite ahora.

### Lo que falta para cerrar la Fase 3 según su criterio de término

El criterio del plan es «`POST /api/capsulas` devuelve una cápsula válida ≥95% de las veces» más
la prueba de diferenciación entre las cuatro cápsulas VARK. Nada de eso se puede **medir**
todavía: falta `LLM_API_KEY` y falta material real. El motor está completo y el prompt está
construido para que la diferenciación ocurra —hay tests que prueban que los cuatro perfiles
producen prompts distintos y estructuralmente distintos—, pero que las **cápsulas** resulten
distinguibles es una observación empírica pendiente.

---

## 5 nonies. Fase 4 — UI mínima funcional conectada al motor (11-ago-2026)

Cierra el pendiente n.º 2 de la sección 6: `web/routers/student.py` y `teacher.py` ya no
tienen `MOCK_FRAGMENTS` ni cápsulas escritas a mano. Cada vista llama al **mismo handler**
que expone `/api/*` en vez de reimplementarlo, de modo que la demo y la API no pueden
contradecirse: si cambia el cálculo del perfil, cambian las dos a la vez.

| Vista | Con qué se conectó |
|---|---|
| `GET /student/vark` | `vark/instrumento.py` — los 16 ítems y sus 64 alternativas reales |
| `POST /student/vark` | `crear_diagnostico`, el handler de `POST /api/diagnosticos` |
| `GET /student/profile` | `diagnostico_vigente` + `vark/rules.aplicar_reglas` + la fila de `configuracion_contenido` |
| `GET /student/catalog` | `catalogo`, el handler de `GET /api/catalogo` |
| `GET /student/viewer/{id_objetivo}` | `crear_capsula`, el handler de `POST /api/capsulas` |
| `POST /student/viewer/{id_capsula}/submit` | `mini_quiz_json.indice_correcta` de la fila persistida |
| `POST /teacher/curation/upload` | `subir_documento` → `knowledge/ingest.ingerir` |
| `POST /teacher/curation/{id}/approve` \| `/reject` | `knowledge/curation.validar` \| `descartar` |

### Decisiones tomadas en la Fase 4

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **Casillas de verificación en el cuestionario**, no botones de radio | Un radio por ítem, como tenía la maqueta | El cap. 10 permite marcar **varias** alternativas por ítem y dejar ítems en blanco. Con radios ninguna de las dos cosas es expresable, y el instrumento aplicado por la web dejaría de ser el mismo que se aplicó por Google Forms a los 43 estudiantes ya cargados: los perfiles no serían comparables. |
| **Cookie `id_estudiante` firmada con HMAC** (stdlib) | Cookie con el id en claro; o `itsdangerous`; o sesión en servidor | Un entero en una cookie lo edita cualquiera: escribir `id_estudiante=7` bastaba para ver el perfil y las cápsulas de otra persona. La firma lo cierra sin agregar dependencia ni tabla de sesiones. No es autenticación —el sistema no tiene usuarios, el cap. 9 identifica por diagnóstico— pero sí impide la manipulación trivial. |
| **`SESSION_SECRET` opcional, con secreto efímero por proceso si falta** | Un secreto fijo escrito en el código | Firmar con un secreto público es lo mismo que no firmar. Si falta, la app funciona y las sesiones simplemente no sobreviven a un reinicio; queda documentado en `.env.example`. |
| **Repetir el cuestionario agrega un diagnóstico al mismo estudiante** | Crear un estudiante nuevo en cada intento | La tabla 17.2 admite varios diagnósticos por estudiante y la generación ya usa el más reciente. Si cada intento creara una persona, el A/B de la Fase 5 quedaría con la cohorte inflada de duplicados y las cápsulas de un mismo estudiante repartidas entre varios identificadores. |
| **El bloque `contenido` se recorre por `tipo` y se arma la etiqueta HTML que corresponde** | Que el modelo devuelva HTML | El contrato de `generation/schemas.py` es estructurado justamente para que la UI decida la presentación. Además, HTML del LLM inyectado con `\|safe` sería XSS con firma del proveedor. Jinja escapa todo lo que viene del modelo. |
| **`indice_correcta` y `retroalimentacion` no viajan al navegador** | Mandar la actividad completa y comparar en el cliente | Estarían en el código fuente de la página y el quiz dejaría de medir nada. La corrección se hace en el servidor contra `mini_quiz_json`. |
| **`submit` comprueba que la cápsula sea del estudiante de la sesión** | Corregir por id sin más | Sin la comprobación, iterar ids ajenos devolvería la alternativa correcta de cualquier cápsula. |
| **Los errores de formulario viajan como HTML con estado 200** | Devolver 4xx | HTMX solo intercambia contenido en respuestas exitosas: un 422 deja al estudiante mirando un formulario que no reacciona. |
| **El visor distingue tres fallos en pantalla** (sin credencial / sin material curado / el modelo no logró una cápsula válida) | Un único "no se pudo generar" | Cada uno lo arregla una persona distinta: el equipo con la `LLM_API_KEY`, el docente curando, o revisando el prompt. Con un mensaje genérico, la demo no dice qué hacer. |
| **El botón de validar va junto al selector de objetivo, en la misma fila** | Validar primero y asignar después | Es la regla de la Fase 2 llevada a la interfaz: un fragmento validado sin objetivo queda inalcanzable para siempre. `curation.validar` ya lo bloquea; ahora además no se puede ni intentar por descuido. |
| **`GET /api/catalogo` con `solo_con_material=True` también en la web** | Mostrar todos los temas y avisar al entrar | Ofrecer un tema sin material curado lleva a un error de generación o a contenido inventado (cap. 12/13). Con el catálogo vacío se explica qué falta y se enlaza al panel de curación. |

### Lo que encontró la inspección, no los tests

1. **XSS reflejado en el aviso de error del cuestionario.** El mensaje cita la alternativa
   recibida (`el ítem 1 trae una alternativa desconocida: 'z'`) y se estaba interpolando en
   HTML sin escapar, así que un POST con `q1=<script>…` devolvía ese script dentro de la
   página y el navegador lo ejecutaba — con la cookie de sesión ahí para robar. Corregido con
   `html.escape` y con test de regresión. Los tests no lo veían porque el mensaje era correcto.

2. **Faltan los enunciados de los 16 ítems.** `instrumento.py` guarda las 64 alternativas
   (que son las que se puntúan) pero no el texto de las preguntas, porque para calificar no
   hace falta, y el informe tampoco los transcribe. Están en el encabezado de
   `data/data_cuestionarios_43.csv`, que no está versionado. Para que la Fase 4 se pudiera
   mostrar se escribieron enunciados equivalentes, aislados en `web/textos.py` y marcados como
   **provisionales**. ⚠️ **Hay que reemplazarlos por los originales del CSV antes de aplicar
   el instrumento a estudiantes nuevos**, o los 43 diagnósticos ya cargados y los que entren
   por la web no habrán respondido exactamente la misma pregunta.

### Verificación

Además de los 31 tests nuevos (`test_web_estudiante.py` y `test_web_docente.py`), se hizo el
recorrido completo **contra uvicorn**, no con `TestClient`, para ejercitar de verdad las
cabeceras de HTMX, la cookie y la subida multipart:

1. Catálogo vacío al principio → explica que falta material curado.
2. Alta del objetivo curricular (es carga manual por diseño: cap. 12).
3. Subida de un PDF real desde el panel → 2 fragmentos, 2 páginas, 472 palabras, **todos
   pendientes**, y la bandeja se recarga sola vía `HX-Trigger`.
4. Validar sin objetivo → rechazado con el motivo, el fragmento **sigue pendiente**.
5. Validar con objetivo → `validado`, y el documento promovido a `validado`.
6. El mismo tema **ya aparece** en el catálogo del estudiante, con su conteo de fragmentos.
7. El visor renderiza la cápsula con los cuatro tipos de bloque en su etiqueta correcta
   (`<p>`, `<ol>`, `<table>`, `<dl>`), sus fuentes con documento y página, y el quiz corrige
   bien acierto y error. La segunda visita al mismo tema sale del caché.
8. Sin `LLM_API_KEY` el visor explica exactamente eso, que es el estado real de la máquina.

El paso 7 se verificó con un doble del cliente LLM aplicado sobre la app real
(`dependency_overrides`), sin tocar el repositorio: el motor está completo, lo que falta es
la credencial.

---

## 5 decies. Panel de analíticas del docente — auditoría y correcciones (12-ago-2026)

Antes de esta sesión ya existían cinco vistas nuevas para el docente, construidas sobre el
motor real: **Historial de cápsulas**, **Cobertura curricular**, **Rendimiento en quizzes**,
**Simulador VARK** y **Estilos de aprendizaje de la cohorte** (`web/routers/teacher.py`,
`web/templates/teacher/analytics.html` y `simulator.html`). No es una fase nueva del roadmap
de `PLAN_DESARROLLO.md` — se documenta bajo el rótulo "Fase 5" porque así lo llaman ya los
docstrings del código (`InteraccionQuiz`, `get_analytics`); ver la nota al final de esta
sección sobre el choque de nombres con la Fase 5 del plan.

Se pidió analizar el apartado completo y mejorar solo el gráfico VARK de la cohorte (el resto
de la UI quedaba fuera de alcance). El análisis encontró que tres de las cinco secciones no
eran solo mejorables: tenían **bugs que invalidaban lo que decían mostrar**. Se trabajaron en
tres tandas, cada una cerrada con tests antes de pasar a la siguiente.

### Corrección de UI (la única solicitada): gráfico VARK de la cohorte

Las barras usaban variables CSS que no existen en `style.css`
(`--color-visual`/`--color-auditivo`/`--color-read`/`--color-kinesthetic`): salían transparentes,
con las etiquetas fuera del contenedor (`top: -25px`) y texto blanco sobre fondo blanco.
Reemplazado por el mismo patrón de barras horizontales que ya usa `student/profile.html`, con
los colores y nombres de canal tomados de `web/textos.py` (`_barras_cohorte` en `teacher.py`)
para que docente y estudiante vean el mismo azul para "Visual".

### 1. Simulador VARK — cuatro bugs, no un problema de UI

El simulador pasaba `resultado.capsula` (un `Microcapsula`, sin `id_capsula` ni `origen`) al
mismo `viewer.html` que usa el estudiante:

| Bug | Efecto | Corrección |
|---|---|---|
| `hx-post="/student/viewer//submit"` (id vacío) | El botón "Revisar Respuesta" del simulador daba 404 | Se extrajo `student/_capsula.html`, un partial que ambas vistas incluyen; el simulador ya no ofrece formulario porque la cápsula simulada no está persistida |
| `capsula.origen` no existe en `Microcapsula` → siempre falso | El badge decía "Recuperada de caché" sobre una cápsula recién generada | Badge propio de simulación: `Simulación · perfil {canal} 100%` |
| `viewer.html` extiende `base.html` completo | HTMX inyectaba un `<head>` y una barra de navegación duplicados dentro de `#simulator-result` | El simulador renderiza el partial directo, no la página |
| Canal inválido → `PerfilVark(0,0,0,0)` | Rompe el invariante `v+a+r+k=100`; `derivar()` lo clasifica como multimodal con primario V y genera igual, pagando la llamada al LLM | Se valida contra `CANALES` antes de construir el perfil; error explícito sin llamar al modelo |

Ganancia adicional: como el docente sí necesita ver la clave de la actividad (a diferencia del
estudiante, para quien es una fuga de datos), `es_simulacion` ahora controla exactamente esa
diferencia en el mismo partial — antes era un flag del contexto que ninguna plantilla leía.

Tests: `tests/test_web_simulador.py` (8).

### 2. Métricas de quiz — la cifra podía inflarse por reintentos

El visor deja el formulario en pantalla después de la retroalimentación, así que un estudiante
puede cambiar la alternativa y reenviar. `interaccion_quiz` guardaba **cada intento con el
mismo peso**: quien insistía hasta acertar subía el "% de acierto" del curso igual que quien
acertó a la primera. Además `es_correcta`/`alternativa_seleccionada` eran `NOT NULL`, así que
las actividades `intentalo_tu` (perfiles K) no podían registrarse y esos objetivos
desaparecían del panel como si nadie los hubiera trabajado.

Corregido con la migración `2fbc7391c0a3`:

- `numero_intento` (calculado **en el servidor**, nunca por el cliente) + `UNIQUE(id_capsula,
  numero_intento)` para que un doble clic no duplique el intento.
- `es_correcta` y `alternativa_seleccionada` pasan a `NULL`-ables, para registrar las
  actividades abiertas sin acierto.
- El panel (`_rendimiento_actividades`) reporta el **acierto al primer intento** como métrica
  principal, con los reintentos como columna aparte (una señal de material que no se entiende
  a la primera, no ruido a descartar).
- `POST /api/capsulas/{id}/quiz` ahora exige `id_estudiante` y devuelve **403** si la cápsula
  no es de quien responde — antes cualquiera podía inflar las métricas del curso con `curl`.

Ojo con la auto-corrección respecto de lo que se dijo en el chat al proponer este punto: no se
agregó `id_estudiante` a `interaccion_quiz` como columna propia. Es derivable con un JOIN a
`microcapsula_generada` (una cápsula tiene un solo dueño) y duplicarlo solo habría abierto la
puerta a que las dos copias se desincronizaran.

Al regenerar la migración, Alembic volvió a proponer borrar el índice GIN de FTS
(`ix_fragmento_contenido_fts`) — el mismo defecto ya documentado en `8010505ef66e` y
`8eb6f0399fee` (autogenerate no ve índices por expresión). Se quitó a mano otra vez.

Tests: `tests/test_interaccion_quiz.py` (12).

### 3. Cobertura curricular — el falso verde

La consulta original contaba `estado_validacion == 'validado'` y nada más. El retriever exige
además `documento.estado_curacion != 'rechazado'`: un apunte retirado **después** de haber
curado sus fragmentos dejaba el tema en verde en el panel mientras el motor ya lo ignoraba. Se
resolvió compartiendo los filtros entre los dos (`retriever._filtros_recuperables()`, usado
tanto por `recuperar` como por el nuevo `inventario_por_objetivo`), así que no pueden volver a
divergir — hay un test que compara la cifra del panel contra `retriever.contar_disponibles`.

Dos mejoras más sobre la misma sección:

- **Desglose por canal.** `PREFERENCIA_POR_CANAL` (tabla 11.1) **reordena, no filtra**: un
  objetivo con solo fragmentos de tipo texto está perfecto para A y R, y deja al perfil V
  leyendo lo mismo que ellos — la cápsula sale igual, pero la adaptación no se nota. El panel
  ahora marca en ámbar el canal sin recursos de su tipo preferido, sin decir que ese perfil se
  queda sin cápsula (no es así).
- **Umbral en vez de binario**, atado a la constante real del retriever:
  `MINIMO_RECOMENDADO = LIMITE_POR_DEFECTO // 2` → 0 fragmentos = falta material, 1–3 = escaso,
  ≥4 = cubierto.

Auto-corrección respecto de lo propuesto en el chat: no se agregó una columna de "pendientes
por tema". El objetivo se asigna **al validar** (`curation.validar`), así que un fragmento
pendiente casi siempre tiene `id_objetivo = NULL` y todavía no pertenece a ningún tema — una
columna por objetivo habría dado cero en todas las filas. Quedó como aviso global
("`N` fragmentos ingeridos sin revisar", con enlace a la bandeja de curación).

Tests: `tests/test_cobertura_curricular.py` (12).

### Verificación

**261 tests en verde** (229 + 32 nuevos) y `ruff` limpio salvo un aviso de línea larga en
`web/textos.py:35` que ya arrastraba `main`. Los tres endpoints del docente responden 200 con
la base vacía (que es el estado real de esta máquina ahora mismo — ver sección 6, punto 1).

### Nota sobre el rótulo "Fase 5"

Esta sección usa "Fase 5" porque así etiquetó ya el código que se auditó (comentarios y
docstrings de `models.py`, `schemas_capsulas.py`, `teacher.py`). No es la Fase 5 de
`PLAN_DESARROLLO.md` §4 ("Evaluación y resultados": A/B pedagógico con estudiantes, encuesta
TAM, rúbrica docente) — ese trabajo sigue sin empezar. Lo construido acá (analíticas + panel
docente) es alcance adicional que no estaba en el plan de 10 semanas original. Ver
`PLAN_DESARROLLO.md` §4 para la nota equivalente.

### Pendiente de esta sección (no se llegó a implementar)

1. **Simulador con perfiles reales de la cohorte.** Hoy solo simula 100/0/0/0 puro, un perfil
   que no existe en ninguno de los 43 diagnósticos reales — el caso multimodal, el más
   frecuente en la cohorte, no se puede simular. Y falta la **comparación V/A/R/K lado a lado
   del mismo objetivo**, que es literalmente el criterio de término de la Fase 3 en
   `PLAN_DESARROLLO.md` §4 ("comparar visualmente cuatro cápsulas… si no se distinguen, la
   adaptación no está funcionando"). Hoy esa comparación se arma de a una cápsula por vez.
2. **Historial de cápsulas** no muestra `estado_validacion` (la tasa de validez real del LLM,
   el otro criterio de término de la Fase 3) ni persiste `intentos`/`segundos` de la
   generación — con esas dos columnas el panel reemplazaría al CSV del bake-off como evidencia
   viva.
3. **Higiene de repo:** `scripts/reset_db.py` sigue sin confirmación antes de `drop_all`; la
   base de datos está vacía en esta máquina (0 objetivos, 0 diagnósticos, 0 fragmentos, 0
   cápsulas) pese a lo que las secciones 3 ter/5 quinquies de arriba describen como cargado —
   hay que volver a correr `import_vark_csv.py` y `cargar_objetivos.py` antes de usar el panel
   con datos reales.

---

## 5 undecies. Rebranding a "RepasAi" y fondo de marca (13-ago-2026)

Cambios de UI hechos directamente por Vicente (commit `7b34ba3`, fuera de una sesión de
trabajo asistida) — se documentan acá para que este archivo siga reflejando el estado real de
la interfaz.

- **Renombrado en toda la web:** "Studify" → "RepasAi" (`base.html`: `<title>` y el enlace del
  logo en el header). Es solo el nombre visible en la UI — el paquete Python (`studify`), el
  repositorio, `PLAN_DESARROLLO.md` y el resto de la documentación siguen diciendo "Studify".
  Si el cambio de nombre se vuelve definitivo, falta decidir hasta dónde propagarlo.
> ⚠️ **Superado en parte el 02-oct-2026** (sección 5 duovicies): la textura ya no es el fondo de
> toda la web. Quedó como decoración de la landing, monocroma y teñida según el tema claro/oscuro.

- **Fondo de marca en toda la web:** textura repetible de íconos educativos (libro, lápiz,
  regla, compás, globo, letras sueltas "A"/"3") en verde y azul muy tenues, sobre un degradado
  casi blanco. Viene de `docs/School Background.dc.html` y quedó aplicado a `body` en
  `style.css` con `background-attachment: fixed`, para que se vea igual y quieta en toda la
  app y no se repita "por página". El header conserva su fondo blanco sólido (`--bg-surface`),
  así que la textura solo se nota detrás del contenido — no compite con la navegación.
- **Tarjeta del cuestionario VARK** (`student/vark.html`): `background-color: #fafffc` (blanco
  verdoso muy sutil), fijado a mano en hexadecimal y no con el token `--success-bg` —ese token
  lo usan también las alertas de éxito en curación, así que tocarlo habría cambiado otra
  pantalla sin querer.

Verificado por captura contra el servidor real en `/student/vark`, `/teacher/curation` y
`/teacher/analytics`: el fondo se ve consistente entre vistas y las tarjetas siguen legibles
encima.

---

## 5 duodecies. Alta de objetivos de aprendizaje desde el panel del docente (14-ago-2026)

Cierra una brecha entre lo que el backend ya podía hacer y lo que la UI ofrecía:
`POST /api/objetivos` existe desde la Fase 2, pero nunca se conectó a ninguna pantalla — la
única vía para agregar un objetivo era `scripts/cargar_objetivos.py`, pensado para sembrar un
catálogo completo, no para la tarea de treinta segundos de agregar un tema suelto.

- **`POST /teacher/curation/objetivos`** (`web/routers/teacher.py`): reutiliza `crear_objetivo`,
  el handler de la API, en vez de reimplementar la lógica — mismo patrón que ya usaba la subida
  de documentos con `subir_documento`. El control de código duplicado (`codigo_objetivo` es
  clave natural) viene incluido sin escribirlo dos veces.
- **Formulario nuevo en `teacher/curation.html`**, arriba de "Cargar nuevo documento" — es el
  paso 0 real del flujo de curación. Muestra cuántos objetivos hay en el catálogo y una lista
  desplegable con los existentes, para no tener que adivinar códigos ya usados.
- **Mensajes de validación traducidos** (`_explicar_campos`): Pydantic devuelve errores en
  inglés ("String should have at most 30 characters") y esta es una pantalla en español para un
  docente, no un cliente de API.
- **`scripts/cargar_objetivos.py` no se retira.** Sigue siendo la vía correcta para cargar un
  plan de estudios completo de una vez —nadie escribe 60 objetivos en un formulario, uno por
  uno—; el `--dry-run` y la actualización masiva por `codigo_objetivo` no tienen equivalente en
  la UI y no lo necesitan. Ambas vías escriben por el mismo camino (`crear_objetivo`), así que
  no pueden divergir ni duplicar un código entre sí.

Tests nuevos en `tests/test_web_docente.py` (4): creación desde el panel, disponibilidad
inmediata del objetivo para validar fragmentos, rechazo de código duplicado con el motivo
explicado, y mensaje de error en español (no el texto de Pydantic). **265 tests en verde**
(261 + 4), `ruff` limpio en todo lo tocado.

### Bug encontrado al levantar el servidor, no por los tests

Esta máquina tenía aplicada la migración de la Fase 3 (`8010505ef66e`) pero no las dos que
agregó Patricio después (`5e11a9cf4a0b` interaccion_quiz, `2fbc7391c0a3` intentos numerados):
`/teacher/analytics` daba **500** — `UndefinedTable: no existe la relación "interaccion_quiz"`.
`pytest` no lo detecta porque la suite corre contra el estado real de la BD, y una migración
faltante no es un caso que los tests simulen. Corregido con `alembic upgrade head`. Es
exactamente el escenario que ya describe la sección 9 ("dos computadores del equipo"): cuando
alguien más pushea migraciones nuevas, hay que acordarse de aplicarlas en la máquina local
antes de levantar el servidor — no pasa solo.

### Primer material curricular real cargado (parcial)

De paso quedó armado `data/objetivos.csv`: 5 objetivos de "Diseño de UX", Unidad 1, derivados
del contenido real de un PPTX ya subido (`01 - Introducción al diseño UX`, 40 fragmentos
extraídos). Avanza en parte el pendiente n.º 1 de la sección 6: el catálogo ya no está vacío y
hay material real esperando curación.

**Sigue sin curar.** Los 40 fragmentos están todos en `pendiente`, 0 en `validado` — cargar el
catálogo no es lo mismo que curar el material. Varios fragmentos del PPTX son solo el pie de
página con el correo de la profesora (`Dra. Daniela Quiñones Otey — daniela.quinones@pucv.cl`,
repetido en más de diez fragmentos distintos): conviene **rechazarlos** al revisar, no
validarlos, porque no aportan contenido y ensuciarían las cápsulas generadas sobre ese objetivo.

> **Actualización 19-ago-2026:** ya se curó. Los cinco objetivos tienen material validado —13
> fragmentos en "Diferencia entre diseño UX y UI", 10 en "Etapas del Design Thinking", 10 en
> "Diseño centrado en el usuario", 4 y 3 en los dos restantes—, de modo que el pendiente n.º 1
> de la sección 6 queda cerrado para esta asignatura.

---

## 5 terdecies. Estructura pedagógica de siete pasos (19-ago-2026)

La profesora guía revisó el avance y observó que **el informe no define qué estructura tiene
una microcápsula**. Propuso una, y esta sección la implementa. Es el cambio más profundo desde
la Fase 3: toca el contrato, el validador, el prompt, el visor y cinco archivos de tests.

La auditoría completa de su lista de revisión —punto por punto, con veredicto y ruta de archivo—
está en [`AUDITORIA_LISTA_PROFESORA_14AGO2026.md`](AUDITORIA_LISTA_PROFESORA_14AGO2026.md).
Esta sección documenta solo lo que se implementó de ahí.

### Qué cambió en el contrato

Antes la cápsula era `contenido[]`, una lista de bloques tipados que el modelo ordenaba a su
criterio. Ahora cada paso tiene su propio campo obligatorio:

| Paso | Campo | Antes |
|---|---|---|
| 1. OA | `objetivo_aprendizaje` | ya existía |
| 2. Activación | `activacion` | **no existía** |
| 3. Concepto central | `concepto_central` | un bloque más de `contenido[]`, sin etiqueta |
| 4. Representación adaptativa | `representacion_adaptativa[]` | ídem, mezclado con el resto |
| 5. Ejemplo / aplicación | `ejemplo` | tipo de bloque opcional |
| 6. Pregunta de comprobación | `actividad.pregunta` | ya existía |
| 7. Retroalimentación | `actividad.retroalimentacion` | ya existía |

**Por qué un campo por paso y no una lista con etiquetas.** Con la forma anterior, "falta la
activación" era algo que había que descubrir leyendo la cápsula; ahora es un error de
validación que el bucle de reparación corrige solo. Que el orden sea el correcto tampoco
depende ya de que el modelo se acuerde: lo fija el contrato.

### Decisiones tomadas en esta entrega

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **La adaptación VARK no se encierra en el paso 4** | Concentrarla toda ahí, que es lo que sugiere el diagrama de la profesora | `ejemplo` también es un bloque tipado, así que un perfil kinestésico recibe `lista_pasos` donde otro recibe un párrafo, y la actividad sigue cambiando a `intentalo_tu` con `p_K ≥ 40%`. Concentrar todo en el paso 4 habría dejado sin destino a varias directivas de `vark/rules.py` que la tabla 11.1 del informe sí exige — el «inténtalo tú» del perfil K y el glosario del lector-escritor se habrían perdido. |
| **El prompt muestra los cuatro pesos C_* en crudo *además* de las instrucciones estructurales** | Solo los porcentajes (literal a su plantilla), o seguir ocultándolos como hasta ahora | Su plantilla los pide explícitamente y son informativos —sobre todo dentro del paso 4, donde se mezclan los cuatro canales—, pero un modelo ignora con facilidad un «22,75 % de texto». Las instrucciones concretas («incluye una `tabla` de 3×2») siguen siendo las únicas que se pueden comprobar después en el JSON. Se dan las dos cosas: es estrictamente más información. |
| **Los C_* se muestran redondeados a un decimal** | Pasarlos con la precisión completa | El modelo no hace nada distinto con 22,75 que con 22,8, y la cifra larga invita a que la copie tal cual dentro del texto de la cápsula. |
| **La activación se valida como pregunta** (exige `?`) y se acota a 45 palabras | Aceptar cualquier texto en ese campo | Una «activación» sin interrogación es exposición, no activación; y si se alarga, invade el paso 3. Se comprueba el signo de cierre y no el de apertura porque los modelos omiten el «¿» inicial con frecuencia, y eso es un problema ortográfico, no pedagógico — gastar un reintento en ello sería desperdiciarlo. |
| **`concepto_central` es texto plano, no un bloque tipado** | Hacerlo un `BloqueContenido` como los otros | Lo que cambia entre perfiles es *cómo se refuerza* el concepto (paso 4), no la definición misma. El paso 3 es deliberadamente el mismo para los cuatro canales. |
| **Se borraron las 2 cápsulas existentes en vez de migrarlas** | Escribir una migración de datos o versionar el contrato | Eran dos filas de pruebas del bake-off. Una migración de `contenido_json` habría costado más que regenerarlas, y versionar el contrato para dos filas obsoletas habría dejado dos caminos de renderizado vivos para siempre. |
| **`bloques_legibles()` duplicado en `Microcapsula` y en `CapsulaOut`** | Un único helper compartido | El visor recibe indistintamente una `CapsulaOut` (flujo del estudiante, que lee de la base) o una `Microcapsula` (simulador del docente, que no persiste nada). Ambas tienen que responder lo mismo o la plantilla dejaría de servir para las dos. |

### Verificación contra el modelo real

No solo tests: se generó una cápsula real contra DeepSeek sobre el material de UX ya curado
(objetivo 190, «Diferencia entre diseño UX y diseño UI», perfil `{V:35, A:15, R:20, K:30}`):

- **Válida al primer intento**, 8,4 s, **247 palabras** (dentro del rango 150–300 del cap. 11.1).
- Los siete pasos presentes y en orden.
- La representación adaptativa trajo **un esquema jerárquico y una tabla comparativa** — que es
  lo que corresponde a un perfil con V como canal dominante.
- Las cuatro fuentes citadas (`725, 728, 730, 731`) verificadas contra los fragmentos
  realmente inyectados.
- Renderizada en el visor por HTTP: la activación sale destacada arriba, el concepto central
  rotulado, y después los bloques adaptativos y el ejemplo.

**277 tests en verde** (265 + 12 nuevos), `ruff` limpio salvo el aviso preexistente de
`web/textos.py:35`.

Los 12 tests nuevos cubren: que cada uno de los siete pasos sea obligatorio (parametrizado, uno
por paso), que la activación sea una pregunta y no la explicación completa, que `ejemplo` se
adapte al perfil, que los cuatro pasos del cuerpo sumen para el rango de palabras, y que el
bucle de reparación arregle una cápsula a la que le falte la pregunta de activación.

### Lo que de la lista de la profesora **no** se implementó

Tres puntos quedaron fuera a propósito y conviene tenerlos claros para la próxima reunión:

1. **Embeddings / vectores** (punto 5 de su pipeline). No es un pendiente: contradice
   directamente el cap. 13 del informe que ella ya aceptó, donde se argumenta que la
   recuperación por similitud vectorial introduce un factor probabilístico incompatible con la
   trazabilidad curricular. Se resuelve conversándolo, no programándolo.
2. **OA secundarios por chunk.** `Fragmento.id_objetivo` es una FK singular; admitir varios
   exige una tabla de asociación nueva. Además **hay tensión con otra regla de su propia
   lista**: pide OA secundarios y a la vez «evitar que un chunk pertenezca a varios contenidos».
   Antes de tocar el modelo hay que decidir si «contenido» (tema) y «OA» (objetivo evaluable)
   son la misma jerarquía o dos cosas distintas — hoy el sistema los trata como una sola.
3. **Campo «contenido» asociado al OA** (su ejemplo `OA01 → Contenido: Probabilidad
   condicionada`). Existe `ObjetivoAprendizaje.descripcion`, que es texto libre, pero no es
   exactamente lo mismo.

---

## 5 quaterdecies. Verificación de los 16 enunciados VARK (24-ago-2026)

Cierra el pendiente n.º 6 de la sección 6, abierto desde la Fase 4 (sección 5 nonies,
11-ago-2026): `web/textos.py` mostraba los 16 enunciados del cuestionario con un aviso de que
eran una "redacción equivalente, reconstruida desde las alternativas", y que había que
reemplazarlos por los originales del CSV antes de aplicarle el instrumento a más estudiantes.

**El aviso estaba desactualizado.** Esta máquina sí tiene `data/data_cuestionarios_43.csv`
(no versionado, pero presente acá), así que se pudo comparar programáticamente:

```python
# tests/test_textos_vark.py::test_enunciados_identicos_al_csv_original
for mostrado, real in zip(ENUNCIADOS, enunciados_del_csv, strict=True):
    assert mostrado == real
```

Los 16 enunciados de `web/textos.py` resultaron **idénticos, carácter a carácter** (tildes,
signos de interrogación y puntuación incluidos) a las columnas 5:21 del encabezado del CSV. No
hubo que corregir ni un enunciado. La hipótesis más probable es que quien los escribió durante
la Fase 4 sí tenía el CSV a la vista en ese momento y copió el texto literal, pero redactó el
aviso de forma conservadora ("por si acaso hay que reconstruirlos") y nadie volvió a
verificarlo contra el archivo — que es exactamente el tipo de advertencia que envejece mal si
no se revisita.

**Lo que sí se encontró:** un salto de línea sobrante en el encabezado del ítem 2 (artefacto
propio del export de Google Forms, columna `...lo primero que haces es:\n`), que no afecta la
comparación porque el test hace `.strip()` de cada columna antes de comparar — es whitespace de
exportación, no una diferencia de contenido.

### Qué se hizo

- **`web/textos.py`**: se reemplazó el docstring de advertencia por uno que documenta la
  verificación (con fecha y con el archivo de test que la sostiene), sin tocar ni una palabra
  de la tupla `ENUNCIADOS` — no había nada que corregir.
- **`tests/test_textos_vark.py`** (nuevo, 2 tests): compara `ENUNCIADOS` contra
  `vark/instrumento.ITEMS` (mismo largo, sin requerir el CSV) y contra el CSV real
  (carácter a carácter, con `strict=True` en el `zip` para que un desfase de largo falle en vez
  de comparar en silencio hasta el ítem más corto). Sigue el mismo criterio que `necesita_bd` en
  `conftest.py`: se **salta**, no falla, en una máquina sin el CSV — así queda como guardia de
  regresión permanente sin convertirse en un test frágil para el resto del equipo.

---

## 5 quindecies. Simulador: comparación V/A/R/K lado a lado (24-ago-2026)

Cierra la mitad del pendiente n.º 10 de la sección 6 (queda abierta la otra mitad, "perfiles
reales de la cohorte") y con ella el criterio de término de la Fase 3 en
`PLAN_DESARROLLO.md` §4: «comparar visualmente cuatro cápsulas del mismo objetivo generadas
para V, A, R y K: si no se distinguen entre sí, la adaptación no está funcionando». Hasta
ahora el simulador solo generaba una cápsula a la vez; comparar los cuatro perfiles exigía
abrir cuatro pestañas y acordarse de lo que decía cada una.

### Qué se agregó

- **`POST /teacher/simulator/compare`** (`web/routers/teacher.py`): recibe un `id_objetivo` y
  genera las cuatro cápsulas puras (V, A, R, K al 100%) sobre el mismo material, en el orden
  fijo de `vark.scoring.CANALES`.
- **`teacher/_comparacion.html`** (nuevo partial): cuatro columnas en una grilla, cada una con
  el título, la activación, el concepto central, los tipos de bloque de la representación
  adaptativa (como badges, para ver la huella estructural de un vistazo), los bloques mismos,
  el tipo de actividad de cierre y el conteo de palabras/fuentes. **No reutiliza
  `student/_capsula.html`**: cuatro cápsulas completas una junto a la otra habrían sido
  ilegibles, y lo que hay que juzgar acá es la diferencia estructural entre columnas, no leer
  cada cápsula entera — para eso sigue estando el generador de un solo canal.
- **`teacher/simulator.html`**: segundo formulario, "Los cuatro perfiles, lado a lado", con su
  propio `<select>` de objetivo (no comparte el del generador de un canal) para que el
  `required` del `<select>` de canal del primer formulario no bloquee el botón de comparar.

### Decisiones tomadas

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **Cada columna se genera y falla de forma independiente** (`_generar_capsula_pura` atrapa su propio error y devuelve un dict con `error`, nunca deja escapar una excepción) | Abortar toda la comparación si una de las cuatro llamadas al LLM falla | Cuatro llamadas son cuatro oportunidades de que una falle (timeout, cápsula que no pasa el validador en los reintentos). Abortar por una desperdiciaría las otras tres, que ya se pagaron. Verificado con un cliente falso que falla desde la tercera llamada (`tests/test_web_simulador.py::test_compare_una_columna_que_falla_no_tumba_a_las_otras`) y, sin buscarlo, con el modelo real — ver más abajo. |
| **`_generar_capsula_pura` se factorizó desde `post_simulator_generate`** | Duplicar la construcción del perfil puro y la llamada al motor en la ruta nueva | El generador de un solo canal y el comparador tienen que producir exactamente la misma cápsula ante el mismo canal; si divergieran, la comparación de a cuatro podría mostrar algo distinto de lo que el docente ya vio al probar un canal suelto. |
| **La comparación no muestra `indice_correcta` ni `retroalimentacion`**, solo el tipo de actividad y la pregunta | Mostrar la actividad completa, como hace el generador de un solo canal | La comparación es sobre *estructura* (¿la actividad cambia de `quiz_mc` a `intentalo_tu` con el perfil K?, ¿la pregunta cambia de tono?), no sobre la clave de corrección. Para revisar la actividad completa está el generador de un canal, que sí la muestra entera. |
| **Grilla `auto-fit, minmax(280px, 1fr)`** en vez de una fila con scroll horizontal | `overflow-x: auto` con las cuatro columnas en una sola fila | Cuatro cápsulas comparándose son exactamente el caso en que uno quiere verlas todas sin desplazarse; en una pantalla angosta se apilan en vez de obligar a hacer scroll para llegar a la cuarta. |

### Verificación contra el modelo real, no solo tests

Con los 13 tests nuevos en verde (`tests/test_web_simulador.py`, 8→13) se hizo además una
corrida real contra DeepSeek —igual que en la Fase 3 y en la sección 5 terdecies—, sembrando
un objetivo y un fragmento de prueba y llamando al endpoint sin sustituir el cliente LLM.

**Resultado: 3 de 4 columnas salieron válidas y visiblemente distintas entre sí**, que es
justamente lo que el criterio de término pide poder ver:

- **V** trajo un esquema jerárquico, una tabla comparativa y un párrafo — material para
  «ver» la estructura.
- **A** trajo una analogía cotidiana («imagina que tienes una lista de pedidos…») en tono
  conversacional.
- **K** trajo una secuencia paso a paso, un ejemplo resuelto, y su actividad de cierre cambió
  sola a `intentalo_tu` (respuesta abierta) en vez de `quiz_mc` — exactamente la directiva
  `actividad_aplicada` de `vark/rules.py` en acción.
- **R falló las tres veces**: «el contenido tiene 360 palabras y el máximo es 300: hay que
  recortarlo». El bucle de reparación reinyectó el error dos veces y el modelo no logró bajar
  lo suficiente. La comparación **no se cayó por esto** — mostró las otras tres columnas y el
  motivo del fallo en la cuarta, que es exactamente el diseño de resiliencia de esta entrega.

Este hallazgo no estaba buscado — apareció al verificar la funcionalidad, no al perseguir un
bug— y queda registrado como pendiente n.º 15 de la sección 6: con una sola corrida no alcanza
para afirmar que el canal R falla sistemáticamente, pero es la clase de dato que el criterio
de término de la Fase 3 (`≥95% cápsula válida`) tiene que medir con más repeticiones antes de
darse por cumplido, y el comparador es ahora la herramienta que permite observarlo de un
vistazo en vez de tropezar con él por casualidad.

Los datos de prueba (objetivo, documento y fragmento sembrados a mano para esta verificación)
se borraron después: la base quedó exactamente como estaba antes de la corrida.

---

## 5 sedecies. Por qué falla el perfil R: dos causas encontradas y corregidas (24-ago-2026)

Cierra —parcialmente— el pendiente n.º 15 que dejó la sección anterior. No es una corrección
de un test: es una investigación sobre el motivo de un fallo real contra el modelo, con dos
correcciones encontradas una después de la otra, cada una aplicada y vuelta a medir contra el
modelo real antes de seguir.

### La causa está en el código, no en el modelo

`vark/rules._palabras_objetivo` interpola linealmente el objetivo de palabras de la cápsula
sobre el rango 150–300 (cap. 11.1), según dónde cae `C_texto` dentro de su rango alcanzable
[40, 75] (cap. 11.2). El perfil lector-escritor puro tiene el coeficiente más alto de la matriz
para ese componente (0.75, el máximo de toda la fila), así que su `C_texto` cae exactamente en
75 — el techo del rango— y su objetivo de palabras interpola exactamente en **300**: el mismo
número que `capsula_max_palabras`, el máximo duro que aplica el validador (regla 2 del plan §3).

El prompt le dice al modelo, literalmente: «Extensión del contenido: aproximadamente 300
palabras (mínimo 150, máximo 300)». Apuntar al mismo número que el techo no deja ningún margen
para la variación normal de redacción de un LLM — cualquier verbosidad de más cae directo en
rechazo. Ningún otro perfil tiene este problema: el segundo coeficiente más alto de la fila
`texto` es K (0.50 → objetivo ≈ 193) y después A (0.55 → objetivo ≈ 214), ambos con más de 80
palabras de margen antes de tocar el techo. Es un caso límite de una fórmula que en general
está bien —interpolación lineal sobre un rango acotado—, no un error de esa fórmula: el problema
es que nunca se había puesto ese caso límite frente al modelo real hasta la sección anterior.

### Confirmación empírica antes de tocar nada

Se repitió la generación del perfil R puro sobre tres temas nuevos y distintos entre sí (para
que no fuera un problema de un tema en particular), sembrando material de prueba y usando el
cliente real de DeepSeek:

| Tema | Resultado | Detalle |
|---|---|---|
| Segunda forma normal | ❌ Falló | 345 palabras las tres veces —**exactamente el mismo número en los tres intentos**, la reinyección del error no le hizo cambiar nada perceptible al modelo |
| Recursividad en algoritmos | ❌ Falló | 359 → 303 → 303 palabras: bajó una vez y se estancó |
| Notación O grande | ✅ Pasó | 299 palabras al segundo intento — pasó raspando, a 1 palabra del límite |

**1 de 3 (33%)**, coherente con el fallo ya visto en la sección anterior con un cuarto tema
distinto. Con este dato ya no es una sola corrida: son cuatro intentos de R en tres sesiones
distintas, con **tres fallos por el mismo motivo exacto**.

### La corrección

En `rag/orchestrator.py::construir`, el número que se le pide al modelo (`palabras_objetivo`,
el mismo que entra en la huella de caché) queda acotado a `capsula_max_palabras -
MARGEN_PALABRAS_OBJETIVO` (30 palabras, así que 270 con la configuración actual), sin bajar
nunca de `capsula_min_palabras`. **No se tocó `vark/rules.py`**: `configuracion_contenido.
palabras_texto` —el campo persistido de la tabla 17.4, aprobado por el equipo el 06-ago-2026—
sigue siendo exactamente 300 para el perfil R puro; lo único que cambia es el número que se
escribe dentro del texto del prompt. `test_perfil_lector_puro_pide_mas_palabras_que_visual_
puro` (`test_vark.py`) sigue pasando sin tocarlo.

Se descartó bajar el propio `palabras_texto` de `rules.py`: habría cambiado un valor que la
tabla 17.4 persiste y que el equipo ya aprobó, por una razón que es enteramente de *cómo se le
comunica el número al modelo*, no de cuántas palabras le corresponden al perfil según el
informe.

### Verificación después de la corrección

Se repitió la misma corrida —los mismos tres temas, mismo perfil R puro, mismo modelo real—:

| Tema | Antes | Después |
|---|---|---|
| Segunda forma normal | ❌ 345 palabras (máx. 300) | ✅ 277 palabras, 1 intento |
| Recursividad en algoritmos | ❌ 359→303 palabras | ✅ 292 palabras, 1 intento |
| Notación O grande | ✅ 299 palabras (raspando) | ❌ 310 palabras las tres veces |

**La tasa de éxito subió de 1/3 a 2/3** sobre exactamente los mismos temas. También bajó la
latencia de los que sí pasaron (6–7 s con 1 intento, contra 12–17 s cuando había que reintentar)
y, sobre las dos corridas que sí pasaron, quedaron más lejos del límite (277 y 292, contra 299
antes). **No queda resuelto del todo**: "Notación O grande" pasó antes y falla ahora —la
temperatura del modelo (0.4, no cero) introduce variación entre corridas incluso con el mismo
prompt, así que parte del efecto es ruido y no se puede afirmar que el margen de 30 sea el
número óptimo con esta sola comparación—, y el patrón más preocupante persiste: **el modelo
devolvió el mismo conteo de palabras en los tres intentos**, tanto antes como después de la
corrección. La reinyección del error ("recórtalo") no parece estar logrando que el modelo haga
un recorte real; podría estar haciendo cambios cosméticos que no bajan el total, o simplemente
no está claro *qué* recortar. Ese es un motivo de fallo distinto del que se corrigió acá y queda
como parte no resuelta del pendiente n.º 15.

### Verificación de que no rompió nada

`tests/test_prompt_maestro.py` gana dos tests: uno que fija que el objetivo que ve el modelo
para R puro queda por debajo del máximo real, y otro que confirma que el margen no le cambia el
número a ningún perfil que no se acerque al techo (V, A, K y el multimodal equilibrado). **286
tests en verde** (284 + 2), `ruff` limpio. Los datos de prueba de las dos corridas contra el
modelo real se borraron al terminar cada una.

### Segunda causa: el modelo repetía la respuesta byte a byte

El patrón que quedó pendiente arriba —mismo conteo de palabras en los tres intentos— se
investigó capturando el texto crudo de **cada** intento, no solo el conteo final, envolviendo el
cliente real con un espía que guarda lo que se envía y lo que se recibe. Se repitió R sobre
«Notación O grande» —el tema que venía fallando— y se comparó intento 1 contra intento 2 contra
intento 3 con `==` de Python, no por longitud:

```
intento 1: 3268 caracteres
intento 2: 3268 caracteres  →  ¿idéntico al intento 1?  True
intento 3: 3268 caracteres  →  ¿idéntico al intento 2?  True
```

**Los tres intentos eran byte a byte idénticos.** No es que el modelo intentara acortar y no
lograra bajar lo suficiente: **no cambiaba una sola coma**. El JSON capturado confirma que el
mensaje de reparación sí le llegaba completo y correcto en cada reintento (`num_mensajes_
enviados` crecía 2 → 4 → 6, y el último mensaje de usuario traía el motivo de rechazo tal cual lo
arma `mensaje_para_reparacion`) — así que no era un bug en cómo se arma o se envía la
conversación. El problema es que el mensaje —«tiene 337 palabras, el máximo es 300: hay que
recortarlo»— no le daba al modelo ningún lugar concreto por dónde empezar, y ante eso DeepSeek
optaba por reenviar lo que ya consideraba una buena respuesta antes que arriesgarse a estropearla
recortando a ciegas.

### La segunda corrección

Dos cambios en `generation/validator.py`, ambos en el mensaje que se reinyecta:

1. **`_error_exceso_de_palabras`** (nueva función): el mensaje de la regla 2 cuando sobran
   palabras ahora dice **cuánto** sobra (`sobran {exceso}`, no solo el total y el máximo) y
   **cuál es la parte más extensa** —comparando `activación`, `concepto_central` y cada bloque de
   `bloques_legibles()` por su cuenta de palabras—, nombrándola por su tipo y su encabezado si
   tiene uno. Le da al modelo un blanco concreto en vez de una resta que tiene que hacer él
   mismo y que, evidentemente, no estaba usando para decidir qué tocar.
2. **`mensaje_para_reparacion`**: se agregó una frase explícita — «La respuesta nueva tiene que
   ser distinta de la anterior: si envías el mismo contenido otra vez, el motivo de rechazo se
   repite» —, dirigida exactamente al comportamiento que se observó (reenviar lo mismo).

Tests nuevos en `tests/test_generacion_contrato.py` (3): que el mensaje incluya el exceso exacto
y la parte más larga cuando esta es un bloque, que no reviente cuando la parte más larga es
`concepto_central` en vez de un bloque (cubre la rama sin caso especial de empate), y que
`mensaje_para_reparacion` incluya el pedido explícito de una respuesta distinta.

### Verificación de la segunda corrección

Se repitió la captura byte a byte sobre el mismo tema que fallaba, con el mensaje ya corregido:

```
intento 1: 3257 caracteres
intento 2: 3202 caracteres  →  ¿idéntico al intento 1?  False
intento 3: 3104 caracteres  →  ¿idéntico al intento 2?  False
```

**Esta vez el modelo sí recortó en cada vuelta** —3257 → 3202 → 3104 caracteres, cada uno
distinto del anterior— y la cápsula quedó válida al tercer intento con 291 palabras. Es la
primera vez en toda esta investigación que se observa al modelo *corrigiendo de verdad* en vez
de reenviar o estancarse.

Repetida además la corrida completa de los tres temas (con las dos correcciones ya aplicadas):

| Tema | Sin corregir | Solo el margen | Margen + mensaje específico |
|---|---|---|---|
| Segunda forma normal | ❌ 345×3 (idéntico) | ✅ 277, 1 intento | ✅ 250, 1 intento |
| Recursividad en algoritmos | ❌ 359→303→303 | ✅ 292, 1 intento | ✅ 266, 2 intentos |
| Notación O grande | ✅ 299 (raspando) | ❌ 310×3 | ❌ 308×3 (mismo motivo, sin bytes capturados esta vez) |

Dos de los tres temas (normalización y recursividad) **pasan de forma consistente** en las dos
corridas posteriores a la primera corrección, y con la segunda corrección normalización quedó
además más lejos del límite (250 contra 277 palabras) en el mismo primer intento; recursividad
necesitó un intento más (2 en vez de 1), pero ese intento adicional es justamente el mecanismo
de reparación funcionando —recortando de verdad— y no un síntoma nuevo. «Notación O grande»
sigue siendo el caso difícil: su
`concepto_central` sobre complejidad algorítmica necesita más palabras para explicarse con rigor
(147 de las 308) que el de los otros dos temas, y comprimir una explicación técnica sin perder
precisión parece costarle más al modelo que comprimir una explicación de bases de datos —es una
hipótesis razonable a partir de los números, no algo confirmado con más de estos datos.

**Panorama agregado de toda la investigación (11 generaciones de R en total, tres sesiones el
mismo día): 6 de 11 exitosas (55%).** Sigue lejos del ≥95% del criterio de término de la Fase 3,
pero ya no es un fallo sin explicación: se identificaron y corrigieron **dos causas reales y
distintas** —el objetivo de palabras pegado al techo, y un mensaje de reparación que no le daba
al modelo un blanco concreto—, ambas con mejora medida contra el modelo real, y lo que queda es
un caso de contenido genuinamente más difícil de comprimir, no un defecto del sistema.

### Verificación de que la segunda corrección no rompió nada

**289 tests en verde** (286 + 3), `ruff` limpio. Los tres tests existentes que comprobaban el
texto del mensaje de rechazo (`"máximo es 300" in e`, `"español" in mensaje`) siguen pasando sin
tocarlos: ambas frases se conservaron tal cual, el mensaje solo se extendió. Los datos de prueba
de las tres corridas nuevas contra el modelo real se borraron al terminar cada una.

### Lo que queda pendiente

1. **«Notación O grande» sigue fallando más que los otros dos temas.** Con una sola comparación
   de tres temas no alcanza para separar «es un tema con contenido genuinamente más largo» de
   «sigue habiendo margen para mejorar el mensaje de reparación». Antes de tocar nada más hace
   falta un muestreo más grande —varios temas más, varias corridas por tema— para saber si el
   55% agregado sube con más datos o si «Notación O grande» es un caso atípico que arrastra el
   promedio hacia abajo.
2. **El margen de 30 palabras sigue siendo una primera estimación.** Con la segunda corrección
   puesta, dos de tres temas ya no necesitan el margen para pasar (pasan incluso sin reintentos);
   subirlo más allá de 30 tiene sentido revisarlo recién si el problema persiste con una muestra
   más grande, no ahora sobre esta evidencia.
3. **No se implementó telemetría persistente de intentos/fallos por perfil.** Cada corrida de
   esta sección se armó a mano con un script de investigación (no versionado) que siembra datos
   de prueba y los borra al terminar. El pendiente n.º 11 de esta sección (historial de cápsulas
   con `estado_validacion` e `intentos`) resolvería esto de forma permanente: con eso, el panel
   de analíticas del docente mostraría la tasa de éxito real por perfil sin tener que armar un
   script cada vez que se quiera revisar.

---

## 5 septendecies. Etiquetado asistido por LLM — `knowledge/tagger.py` (24-ago-2026)

Cierra el pendiente n.º 3 de la sección 6. Quedó fuera de la Fase 2 porque entonces no había
credencial de LLM; desde el 13-ago-2026 sí la hay, así que el único motivo real para no
implementarlo ya no aplicaba. El dolor que motiva esto está registrado en el propio plan: «se
vio al curar los 40 fragmentos de UX» que asignar objetivo a mano, fragmento por fragmento, es
lo más lento de la curación.

### Qué se agregó

- **`knowledge/tagger.py`** (nuevo módulo): `etiquetar_fragmento(db, id_fragmento, cliente=…)`
  le muestra al modelo el catálogo de objetivos activos (acotado a la asignatura del documento,
  cuando se conoce) y el texto del fragmento, y le pide un JSON con `id_objetivo`,
  `etiqueta_tematica` y `motivo`. `etiquetar_pendientes(db, cliente=…, id_documento=…, limite=…)`
  hace lo mismo en lote sobre los fragmentos `pendiente` sin objetivo, sin que un fragmento que
  falla tumbe al resto.
- **`POST /teacher/curation/tag`** (`web/routers/teacher.py`): dispara el lote sobre el
  documento que esté filtrado en la bandeja (o sobre todos si no hay filtro), y devuelve un
  resumen de cuántos fragmentos quedaron con propuesta.
- **`teacher/curation.html`**: botón «Sugerir objetivos con IA» junto a la bandeja de revisión.
- **`teacher/_fila.html`**: si un fragmento sin objetivo tiene una sugerencia guardada, el
  `<select>` la trae **preseleccionada** y debajo aparece un badge «IA» con la etiqueta temática
  y el motivo.

### La decisión de diseño que sostiene todo lo demás: propone, no decide — literal

`PLAN_DESARROLLO.md` lo dice en palabras («el LLM propone, no decide») y acá se hizo cumplir en
el código, no solo en la intención: `tagger.py` **no escribe `Fragmento.id_objetivo` ni
`estado_validacion`**. Guarda la propuesta en `metadatos_json['sugerencia_llm']`, y es la UI la
que la usa para prellenar el `<select>` de la bandeja — el mismo `<select>` que ya existía, con
el mismo botón «Validar» que ya existía. Si el modelo se equivoca, no hay nada que deshacer: es
un valor por defecto en un formulario, no una escritura en la base. Un curador que no confía en
la sugerencia simplemente elige otra opción antes de validar, exactamente igual que si el select
hubiera estado vacío.

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **La sugerencia vive en `metadatos_json`, nunca en `id_objetivo`** | Escribir `id_objetivo` directo y dejar el fragmento "pre-asignado" | Es la diferencia entre proponer y decidir. Escribir la FK real —aunque `estado_validacion` siguiera en `pendiente`— habilitaría un camino donde alguien confirma sin mirar, y el fallo silencioso que `curation.py` bloquea con tanto cuidado (fragmento inalcanzable por FK nula) tendría un gemelo nuevo: fragmento mal clasificado por FK puesta por una máquina sin supervisión real. |
| **El catálogo del prompt se acota a la asignatura del documento** | Listar todos los objetivos activos de todas las asignaturas | Menos opciones irrelevantes es menos superficie para que el modelo elija algo que no corresponde, y de paso abarata cada llamada. `DocumentoFuente.asignatura` es opcional; si falta, se listan todos — peor que nada, pero sigue siendo mejor que negarse a sugerir. |
| **Un `id_objetivo` fuera del catálogo entregado se descarta, no se usa** | Confiar en cualquier entero que el modelo devuelva | Es el mismo riesgo de "cita alucinada" que la regla 5 de `generation/validator.py`, aplicado acá al catálogo curricular en vez de a los fragmentos citados. Se descarta solo la propuesta de objetivo — la etiqueta temática puede seguir siendo útil aunque el modelo no haya sabido a qué objetivo del catálogo asociarla. |
| **`tipo_fragmento` no se re-propone** | Pedirle al modelo también el tipo de fragmento, como sugiere la lista textual del plan | Ya lo resuelve `knowledge/chunker.py` a partir de la estructura del documento (PDF/PPTX), con más certeza que la que puede tener un LLM leyendo solo el texto plano. Re-proponerlo sería redundante y una fuente nueva de error sobre algo que ya está bien resuelto. |
| **Un fragmento ya sugerido se vuelve a etiquetar si se pide de nuevo** | Saltarlo si ya tiene `sugerencia_llm` guardada | El curador puede haber corregido el texto (`curation.editar_texto`) entre una corrida y la siguiente; volver a etiquetar entrega una propuesta consistente con el texto actual, a costa de una llamada de más si simplemente se repite el clic sin haber cambiado nada. |

### Verificación

`tests/test_tagger.py` (12 tests, capa de servicio) cubre la invariante central —la sugerencia
nunca toca `id_objetivo` ni `estado_validacion`, pase lo que pase en la respuesta del modelo—,
el descarte de un id inventado o de otra asignatura, el caso sin candidatos (no llama al modelo:
ahorra el costo), el JSON inservible, y que el lote sigue adelante cuando un fragmento falla.
`tests/test_web_docente.py` agrega 7 tests por HTTP: sin `LLM_API_KEY` avisa y no toca nada, el
`<select>` queda preseleccionado con la propuesta, el resumen cuenta bien los fragmentos, y
ningún caso de fallo tumba la respuesta.

**Contra el modelo real**, no solo con el cliente falso: se sembró un catálogo de tres objetivos
claramente distintos (segunda forma normal, recursividad, arquitectura cliente-servidor) y tres
fragmentos — dos que calzan sin ambigüedad con uno de los tres, y uno "trampa" sobre fotosíntesis
que no calza con ninguno. DeepSeek acertó los tres: propuso el objetivo correcto en los dos
primeros y devolvió `id_objetivo: null` en el tercero en vez de forzar una respuesta, con un
motivo en español explicando por qué ninguno correspondía. Se confirmó además, contra el modelo
real y no solo con el falso, que `id_objetivo` siguió en `NULL` en la base los tres casos — la
invariante "propone, no decide" se sostiene también fuera de los tests. Los datos de prueba se
borraron al terminar.

Suite completa: 308 tests en verde (289 + 19 nuevos). `ruff check .` limpio sobre los archivos
tocados por este cambio (las dos excepciones preexistentes y ajenas a este cambio —
`web/textos.py:33` y `scripts/eval_runner.py`, `scratch.py`— no se tocaron ni se atribuyen a
esta entrega).

---

## 5 duodevicies. Separación de vistas: login del docente (26-ago-2026)

Hasta hoy la aplicación tenía **una sola cara**. La cabecera compartida
(`base.html`) mostraba las tres pestañas del docente junto a las del estudiante,
y `/teacher/*` no comprobaba nada: cualquiera que escribiera la URL —o que
simplemente leyera el menú— entraba a la bandeja de curación. Eso no es un
detalle de presentación: **lo que se valida en esa bandeja es lo único que el
retriever recupera** (cap. 12/13), así que la pantalla que decide qué material
llega a las cápsulas estaba abierta, igual que las analíticas de la cohorte y el
simulador, que gasta créditos del LLM en cada clic.

No estaba anotado como pendiente en ninguna de las dos listas de este documento.
Apareció al revisar qué existía como "panel de administración" y encontrar que
`web/sesion.py` decía, en su propio docstring, «no hay usuarios, contraseñas ni
roles, porque el sistema no los tiene».

### La decisión de fondo: una clave compartida, no un sistema de usuarios

El informe no modela docentes. El cap. 9 identifica al **estudiante** por su
diagnóstico VARK y no por una credencial, y el docente aparece únicamente como
el rol que cura, valida y revisa. Con una o dos personas en el piloto, una tabla
de usuarios con hash de contraseñas, alta, baja y recuperación sería
infraestructura que nadie va a usar y que además hay que justificar en el
capítulo de modelo de datos, donde no existe.

Se implementó entonces una credencial única (`TEACHER_USERNAME`/`TEACHER_PASSWORD`,
con **`admin`/`admin123` como valor de fábrica** — ver sección 5 undevicies) que
abre las tres vistas del panel. Si el proyecto llegara a tener varios docentes
con material propio, el punto de cambio es una sola función
(`sesion.verificar_credenciales_docente`) y el resto del andamiaje —guardián,
cookie firmada, redirecciones— sirve igual.

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **El guardián se declara en el `APIRouter`**, no en cada handler | `Depends(requiere_docente)` endpoint por endpoint | Cualquier vista que se agregue después al panel queda cerrada por el solo hecho de colgar de ese router. Handler por handler, olvidar un decorador abre un agujero silencioso —que es exactamente el modo de fallo que este cambio viene a cerrar—. Hay un test (`test_todas_las_rutas_del_panel_exigen_sesion`) que recorre `app.routes` ya montadas y falla si alguna ruta de `/teacher/*` queda sin guardián. |
| **Sin `TEACHER_PASSWORD` el panel se cierra para todos** | Dejarlo abierto cuando no hay clave configurada | Fallar abierto en silencio ante un `.env` incompleto es peor que no tener puerta: nadie se entera de que no está cerrada. La pantalla de login lo explica con el nombre exacto de la variable en vez de decir "clave incorrecta", que mandaría a buscar el problema donde no está. |
| **Una petición HTMX sin sesión recibe 401 + `HX-Redirect`**, no un 303 | El mismo 303 que recibe una navegación normal | HTMX sigue los 303 **dentro del propio XHR**. Con la sesión vencida, el docente vería la página de login entera incrustada dentro del `<div>` de estado de la bandeja: una pantalla rota, sin forma de escribir la clave ahí y sin explicación. `HX-Redirect` pide una navegación completa del navegador. Casi todo el panel se mueve por HTMX, así que este no es un caso de borde. |
| **La huella de la clave va dentro de la firma de la cookie** | Firmar solo el vencimiento | Hace que **cambiar `TEACHER_PASSWORD` invalide las sesiones ya abiertas**. Sin esto, rotar la clave —el único remedio disponible si se filtra— no expulsaría a quien ya tuviera la cookie, que es justo el escenario en que uno la rota. |
| **El vencimiento viaja firmado, no solo en el `max_age`** | Confiar en el `max_age` de la cookie | El `max_age` lo respeta el navegador, y el navegador es precisamente lo que no se puede dar por bueno. Con el vencimiento dentro del mensaje firmado, estirar la sesión desde el cliente rompe la firma. |
| **12 horas de sesión para el docente, contra 30 días del estudiante** | La misma duración para ambos | Las dos cookies no arriesgan lo mismo: la del estudiante recuerda un perfil de aprendizaje, la del docente concede permiso sobre la curación. Un computador de laboratorio con la sesión olvidada deja de ser una puerta abierta al día siguiente. |
| **`next` acotado a rutas que empiezan en `/teacher/`** | Redirigir a donde diga el parámetro | Sin la comprobación, `/teacher/login?next=https://sitio-falso` convierte el login en un redirector abierto: el patrón clásico para hacer pasar un enlace de phishing por un enlace legítimo del sistema. Se descarta también `//otro-sitio`, que el navegador lee como URL absoluta pese a empezar con `/`. |
| **Freno de fuerza bruta en memoria (5 intentos / 60 s por IP)** | Sin freno, o un limitador con almacenamiento compartido | Una clave compartida se elige corta y no se rota seguido: sin freno, un script la encuentra en minutos. El freno es deliberadamente modesto —cuenta en el proceso, se reinicia con el servidor, agrupa por IP y por tanto no sirve contra un atacante distribuido— pero convierte un ataque de minutos en uno de días. Un limitador serio pediría Redis o una tabla, y esto corre en un solo proceso. |
| **`es_docente` se inyecta con un procesador de contexto de Jinja** | Pasarlo en el `context` de cada `TemplateResponse` | La cabecera es compartida por las dos caras de la app. Vista por vista, cualquier pantalla nueva que lo olvidara le mostraría la cabecera de estudiante a un docente conectado: un fallo silencioso y puramente visual que nadie nota hasta estar en una demo. |
| **El logout queda fuera del guardián** | Protegerlo como el resto del panel | Cerrar sesión tiene que ser idempotente: hacerlo dos veces —o con la cookie ya vencida— debe borrar la cookie igual, no rebotar a un login que el docente justamente está tratando de dejar atrás. |
| **El login es un `<form>` normal, no HTMX** | Un `hx-post` como el resto del panel | El login tiene que provocar una navegación completa para que el navegador guarde la cookie **y la cabecera se redibuje** con las pestañas del docente. Un swap de HTMX dejaría media pantalla con la sesión nueva y la cabecera con la anterior. |

### Qué se agregó

- **`web/routers/auth.py`** (nuevo): la dependencia `requiere_docente`,
  `GET/POST /teacher/login`, `POST /teacher/logout` y el freno de intentos.
- **`web/sesion.py`**: cookie `docente` firmada con HMAC, con vencimiento y
  huella de la clave dentro del mensaje firmado. Su docstring, que afirmaba que
  el sistema no tiene credenciales, quedó corregido: ahora describe las dos
  cookies y para qué sirve cada una.
- **`web/deps.py`**: procesador de contexto que expone `es_docente` a todas las
  plantillas.
- **`teacher/login.html`** (nueva) y **`base.html`**: la cabecera muestra el
  botón «Soy docente» a quien no tiene sesión, y las tres pestañas más «Salir» a
  quien sí. Ningún enlace del panel se le ofrece a un estudiante.
- **`config.py` / `.env.example`**: `TEACHER_PASSWORD`, documentada con el aviso
  de que vacía cierra el panel.

### Verificación

`tests/test_web_auth.py` (19 tests, casi todos **sin Postgres** — el guardián
rechaza antes de que el handler pida la base, y eso mismo es una propiedad que
vale la pena tener): el redirect con `next`, el 401 con `HX-Redirect` de una
petición HTMX, la cobertura del guardián sobre `app.routes` ya montadas, el
rechazo del `next` externo y del protocolo-relativo, la cookie inventada, la
cookie **legítimamente firmada pero vencida**, la expulsión al rotar la clave,
el logout, el freno de intentos y las dos formas de la cabecera.

Los 31 tests que ya existían del panel (`test_web_docente.py`,
`test_web_simulador.py`) pasan ahora por el **login real** —no por una cookie
inyectada a mano— vía la fixture `http_docente` de `conftest.py`. Es
deliberado: si el guardián se rompiera o el login dejara de emitir una cookie
válida, esa suite se cae entera en vez de seguir verde sobre una puerta que ya
no cierra.

**327 tests en verde** (308 + 19) al cierre de esta entrega — ver sección 5
undevicies para los 3 que se agregaron después el mismo día. `ruff check`
limpio sobre todo lo tocado; la única excepción del repositorio sigue siendo
`web/textos.py:33`, que es un enunciado literal del instrumento y es anterior y
ajena a este cambio.

### Lo que este cambio **no** es

No es autenticación de grado producción y no conviene presentarlo como tal en el
informe. Es una credencial compartida sobre HTTP local: sin TLS, quien pueda leer
el tráfico la ve. `secure=True` en la cookie ya se activa solo cuando `APP_ENV`
deja de ser `dev`, así que el día que esto se sirva por HTTPS la cookie viaja
protegida — pero mientras la demo corra en `http://127.0.0.1` la garantía real es
«separa las dos vistas y frena la entrada casual», no «resiste a un atacante en
la red».

---

## 5 undevicies. La credencial del docente pasa a tener valor de fábrica: `admin` / `admin123` (26-ago-2026)

Mismo día, después de la entrega anterior. La sección 5 duodevicies dejó el
panel **cerrado por defecto**: sin `TEACHER_PASSWORD` en el `.env`, nadie entra,
ni siquiera el docente. A pedido del equipo se invirtió ese default: ahora el
panel **abre nada más clonar el repo**, con usuario `admin` y clave `admin123`,
sin tocar ningún archivo — la app deja de depender de que alguien complete el
`.env` antes de poder demostrarla, que es justo la fricción que esta sección
elimina.

### Qué cambió

- **`config.py`:** `teacher_password` deja de tener default `""` y pasa a
  `"admin123"`; se agrega `teacher_username: str = "admin"` (antes no existía
  — el login solo pedía la clave). El comentario del campo pasa de "vacía
  cierra el panel" a advertir explícitamente que **`admin`/`admin123` son
  credenciales de demo, no un secreto**, y que hay que cambiarlas antes de
  exponer el sistema a la cohorte.
- **`sesion.py`:** `verificar_clave_docente(clave)` se reemplaza por
  `verificar_credenciales_docente(usuario, clave)`, que compara **ambos**
  campos con `hmac.compare_digest` sin cortocircuitar en el usuario (para no
  dejar un canal por tiempo que confirme el usuario antes de tocar la clave).
  `_huella_clave()` pasa a `_huella_credenciales()` y ahora entra a la firma de
  la cookie el hash de `usuario:clave` junto, no solo de la clave — cambiar
  cualquiera de los dos expulsa las sesiones abiertas, no solo cambiar la clave.
  `clave_docente_configurada()` se renombra a `credenciales_docente_configuradas()`
  por consistencia, pero sigue mirando únicamente `teacher_password`: es la
  única señal confiable de "esto se desactivó a propósito" (`teacher_username`
  vacío en el `.env` seguiría siendo, técnicamente, un usuario).
- **`teacher/login.html`:** gana un campo `usuario` antes de la clave.
- **`.env.example`** y **`.env`** (esta máquina): documentan `TEACHER_USERNAME`
  y `TEACHER_PASSWORD`, con el valor de fábrica explícito y la advertencia de
  que hay que cambiarlo antes de un despliegue real.

### Lo que sigue igual

**El panel sigue cerrándose por completo si `TEACHER_PASSWORD` se deja vacía a
propósito** (`TEACHER_PASSWORD=` sin valor en el `.env`, distinto de no tocar la
variable): eso no se revirtió, porque sigue siendo la única forma de apagar el
panel del todo si alguna vez hace falta. Lo que cambió es únicamente el
**default quieto** —qué pasa cuando nadie toca la variable en absoluto—, de
"cerrado" a "abierto con `admin`/`admin123`".

### La decisión de fondo, dicha sin adornos

Esto es un **retroceso de seguridad deliberado a cambio de conveniencia**, y
conviene que quede así de explícito y no envuelto en el lenguaje de la sección
anterior: la sección 5 duodevicies argumentó "fallar cerrado es mejor que fallar
abierto en silencio", y esta sección hace exactamente lo segundo, a pedido
explícito del equipo, porque en esta etapa (prototipo, sin estudiantes reales
todavía, iterando rápido en dos máquinas) la fricción de un panel bloqueado por
un `.env` sin completar pesaba más que el riesgo de una credencial pública y
conocida. Es aceptable **mientras el sistema no se exponga fuera del equipo**;
el propio código lo dice en el comentario de `config.py` y esta sección lo deja
para el informe: `admin`/`admin123` es un secreto tan público como no tener
contraseña, y hay que cambiarlo —fijando `TEACHER_USERNAME`/`TEACHER_PASSWORD`
distintos en el `.env`— antes de la primera sesión con estudiantes reales.

### Verificación

Tres tests nuevos en `tests/test_web_auth.py`: que el usuario incorrecto por sí
solo (con la clave correcta) no abre sesión, que cambiar `teacher_username`
expulsa una sesión abierta igual que cambiar la clave, y que las credenciales
de fábrica (`admin`/`admin123`, forzadas por una fixture que no depende del
`.env` de la máquina) sí abren el panel. Los tests existentes se actualizaron
para mandar también el campo `usuario` en el login. Verificado además contra el
servidor real con el `.env` de esta máquina tal cual queda tras este cambio
(sin ningún monkeypatch): `POST /teacher/login` con `admin`/`admin123` responde
303 a `/teacher/curation`, y la vista se sirve completa.

**330 tests en verde** (327 + 3). `ruff check` limpio sobre todo lo tocado.

---

## 5 vicies. Higiene operativa: la base se estaba ensuciando sola (26-ago-2026)

Al ir a cerrar los tres pendientes «operativos» de la sección 6 (puntos 7, 8 y 9), **dos de los
tres describían un estado que ya no era cierto**, y el tercero resultó ser el síntoma de un
problema distinto y peor del que decía el texto.

| Pendiente | Lo que decía el documento | Lo que se encontró al medir |
|---|---|---|
| 8 — dependencias de ingesta | «faltan `pymupdf`/`python-pptx`» | Ya estaban instaladas y funcionando |
| 9 — repoblar la base | «está vacía: 0 objetivos, 0 diagnósticos, 0 fragmentos» | 5 objetivos, 3 documentos, 89 fragmentos (40 validados) y **157 diagnósticos donde los reales son 43** |
| 7 — `SESSION_SECRET` | «no está fijada» | Correcto. Era el único de los tres que seguía vigente |

La moraleja para las próximas sesiones no es sobre estos tres puntos en particular: es que una
lista de pendientes escrita a mano envejece en silencio, y que **conviene medir el estado antes
de actuar sobre lo que dice el documento**. Los puntos 8 y 9 llevaban semanas pidiendo trabajo
ya hecho, o —peor— apuntando en la dirección contraria al problema real.

### El problema real: los tests dejaban basura permanente

La base no estaba vacía sino **contaminada**: 141 estudiantes y 157 diagnósticos, contra los 43
reales del CSV. El origen es `tests/test_api_diagnosticos.py`, el único archivo de la suite que
crea estudiantes por HTTP **sin ninguna fixture de limpieza** (`test_web_estudiante.py`, que
hace lo mismo, sí tiene una desde la Fase 4). Cada corrida de `pytest` sumaba una decena de
estudiantes con sus diagnósticos, respuestas y configuraciones, y no restaba ninguno.

**No era la primera vez.** La sección 3 ter documenta que el 10-ago se barrieron «28
diagnósticos que eran ruido de `test_api_diagnosticos.py` (crea diagnósticos y no los limpia)».
Es decir: el problema estaba **identificado y escrito por su nombre**, y aun así volvió a
ocurrir, porque entonces se limpió el resultado y no la causa. En dieciséis días volvió a
acumular 114.

**Por qué importa, más allá del desorden:** `/teacher/analytics` promedia el vector VARK sobre
*toda* la tabla `diagnostico_vark` para mostrar «Estilos de Aprendizaje del Curso». Con 114
diagnósticos sintéticos —muchos de ellos kinestésicos puros, porque es el perfil que usan los
tests— contra 43 reales, ese panel no describía a la cohorte: describía a los tests. Y es
justamente uno de los números que el informe usa.

### La corrección, en ese orden: primero la causa

1. **Fixture de limpieza** (`limpiar_lo_que_cree_el_test`, autouse) en
   `tests/test_api_diagnosticos.py`: anota el `max(id_estudiante)` antes del test y borra al
   terminar todo lo que quedó por encima. El resto de las tablas cae sola por `ON DELETE
   CASCADE`.
   - Se descartó filtrar por un marcador en `carrera`: estos tests usan valores que también
     existen de verdad en el CSV («Ingeniería en Informática»), así que borrar por contenido
     habría destruido datos reales. El `id` autoincremental no tiene esa ambigüedad.
   - Se descartó igualmente envolver cada test en una transacción con `rollback`: los tests
     llaman al endpoint por HTTP y el handler hace su propio `commit`, así que no hay una
     transacción del test que revertir.
2. **Recién después**, `python scripts/import_vark_csv.py data/data_cuestionarios_43.csv
   --reset`. `--reset` borra `estudiante` completo y recarga desde el CSV; **no toca**
   `objetivo_aprendizaje`, `documento_fuente` ni `fragmento`, así que el material curado de
   "Diseño de UX" quedó intacto. Se confirmó antes con `--dry-run` que el CSV reproduce los
   promedios ya documentados en la sección 5 ter (Informática: V=6,30 A=7,87 R=6,22 K=9,61).

### Verificación

- **La fuga está sellada:** dos corridas completas de `pytest` seguidas, 330 tests en verde cada
  una, y los conteos no se movieron ni una fila (141/157/2622 antes del reset, 43/43/1202
  después). Antes de la fixture, cada corrida sumaba ~10 estudiantes.
- **El estado quedó como lo describe el informe:** 43 estudiantes, 43 diagnósticos, **1.202
  respuestas** — exactamente el número que la sección 5 ter registró el 06-ago-2026.
- **El material curado sobrevivió:** 5 objetivos, 3 documentos, 89 fragmentos (40 validados, 48
  pendientes, 1 descartado), sin cambios antes y después.
- `SESSION_SECRET` fijada en el `.env` de la máquina 1.
- 330 tests en verde, `ruff` limpio sobre lo tocado (sigue la única excepción preexistente,
  `web/textos.py:33`).

---

## 5 unvicies. Cierre de `/api/*` y un test que mentía (26-ago-2026)

Cierra el pendiente n.º 17, abierto ese mismo día al comprobar que el login de la sección 5
duodevicies separaba las **vistas** pero no los **endpoints** que esas vistas usan por dentro:
`GET /api/documentos` y `GET /api/objetivos` respondían 200 a un cliente anónimo, y
`POST /api/objetivos`, los `PATCH` de curación y `DELETE /api/documentos/{id}` aceptaban
escrituras sin credencial. Quien conociera la ruta podía curar material por HTTP sin pasar por
el panel.

### El dato que hizo el cambio seguro: la UI no llama a `/api` por HTTP

Antes de mover nada se comprobó que **ninguna plantilla referencia `/api/`**: `web/routers/*.py`
importa los handlers (`catalogo`, `crear_objetivo`, `subir_documento`, …) como funciones de
Python y los llama directo. Una dependencia declarada en el router solo corre en el camino HTTP,
así que cerrar los endpoints no podía romper la interfaz. Sin esa comprobación previa, este
cambio habría sido a ciegas.

### La separación, por rol

| Abiertos — los necesita un front del estudiante | Cerrados — curación y analítica |
|---|---|
| `POST /api/diagnosticos`, `GET /api/diagnosticos/{id}` | `POST` y `GET /api/objetivos` |
| `GET /api/catalogo` | `POST`, `GET` y `DELETE /api/documentos*`, `GET …/resumen` |
| `POST /api/capsulas`, `GET /api/capsulas/{id}` | `GET /api/fragmentos` + `validar` / `descartar` / `objetivo` / `texto` |
| `POST /api/capsulas/{id}/quiz` | `GET /api/recuperar`, `GET /api/capsulas` (historial) |

`GET /api/capsulas` quedó del lado del docente porque `?id_estudiante=` es un **filtro
opcional, no una restricción**: sin él devuelve las cápsulas de toda la cohorte. Es la vista de
analítica del panel, no algo que el estudiante necesite.

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **Un `router_docente` por módulo**, con la dependencia en el `APIRouter` | `Depends(...)` endpoint por endpoint | Mismo motivo que en `web/routers/teacher.py`: un endpoint nuevo queda cerrado por colgar del router, no por acordarse de anotarlo. |
| **401 con `WWW-Authenticate`**, no el 303 del guardián web | Reusar `requiere_docente` tal cual | Los clientes HTTP siguen los redirects solos: un script que llamara a `/api/fragmentos` habría recibido un **200 con la página de login en HTML** y habría creído que la llamada funcionó. Un 401 es lo que un cliente de API puede entender y reintentar. |
| **Se aceptan cookie *y* HTTP Basic** | Solo la cookie del panel | La cookie mantiene usable Swagger (`/docs`) para quien ya entró por la UI; Basic es lo que necesitan `curl -u` y los scripts de `scripts/`, que no tienen dónde guardar una cookie. `HTTPBasic(auto_error=False)` es lo que permite considerar las dos: con el valor por defecto, FastAPI corta con su propio 401 antes de mirar la cookie. |
| **El freno de fuerza bruta del login web se aplica también a `/api`** | Dejar Basic sin límite de intentos | Si no, `/api/*` sería un canal de adivinación de contraseñas sin tope justo al lado de un formulario que sí lo tiene, y documentar «el panel está protegido» sería falso. |
| **Una petición anónima no gasta intentos**; solo cuenta la que presenta credencial | Contar todo 401 como intento fallido | Pedir una ruta protegida sin credencial es el caso **normal** de «esto requiere login». Contarlo dejaría al docente bloqueado por cualquier rastreador que pasara por `/api`. |

### El hallazgo colateral, más grave que el pendiente: un test que pasaba en vacío

Al listar las rutas de `/api` para comprobar el resultado, la lista salió **vacía** — con la app
funcionando. La causa: **FastAPI 0.141 no aplana lo que entra por `include_router`**. Deja un
envoltorio `_IncludedRouter` que no es `APIRoute` y que no expone `.routes`, sino el `APIRouter`
original en `.original_router`. Un `isinstance(r, APIRoute)` sobre `app.routes` ve **2 de las 41
rutas reales**.

Eso significa que `test_todas_las_rutas_del_panel_exigen_sesion` —escrito el mismo día en la
sección 5 duodevicies, y presentado ahí como *la* garantía de que ninguna vista del panel se
quedaría sin guardián— **nunca comprobó nada**: iteraba una lista de dos elementos que no
incluían ninguna ruta de `/teacher/`, no encontraba desprotegidas y pasaba. Un endpoint nuevo sin
guardián habría entrado sin que la suite dijera una palabra.

Corregido con un helper `rutas_montadas()` que baja al `original_router`, y —más importante— con
un **test que vigila al vigilante** (`test_el_recorrido_de_rutas_ve_la_app_completa`): afirma que
el recorrido devuelve más de 30 rutas e incluye caminos conocidos de los tres prefijos. Sin él,
los dos tests de cobertura podrían volver a mentir en silencio si una versión futura de FastAPI
cambia otra vez la estructura interna.

La lista blanca del test de `/api` se escribe **explícita** por la misma razón: afirmar solo «las
de curación están cerradas» dejaría pasar un endpoint nuevo y abierto. Así, agregar algo al router
abierto obliga a justificarlo tocando el test.

### Verificación

`tests/test_web_auth.py` pasa de 24 a 31 tests: el 401 con `WWW-Authenticate` y sin HTML, Basic
aceptado y rechazado, la cookie del panel sirviendo para `/api`, `/api/catalogo` todavía abierto,
el freno por fuerza bruta con `Retry-After`, y que una ráfaga de peticiones anónimas no bloquee
al docente. Más los dos de cobertura de rutas y el que los vigila.

**Contra el servidor real** (`uvicorn` en un puerto aparte, con `curl`), no solo con `TestClient`:
anónimo recibe 401 en `/api/objetivos`, `/api/documentos`, `/api/fragmentos`, `/api/recuperar` y
`/api/capsulas`, y también en `DELETE /api/documentos/1` y `POST /api/fragmentos/1/validar`;
`POST /api/objetivos` con cuerpo válido devuelve **401 y no 422**, o sea que la autenticación
corre **antes** de validar el cuerpo y no se filtra el esquema; con `-u admin:admin123` las cinco
lecturas dan 200 y el alta devuelve 201. El objetivo de prueba creado en esa comprobación se
borró al terminar y la base quedó en 43/43/5/3/89, igual que antes.

**339 tests en verde** (332 + 7). `ruff` limpio sobre lo tocado.

### Lo que sigue sin cubrir

`POST /api/diagnosticos`, `GET /api/diagnosticos/{id}`, `GET /api/capsulas/{id}` y
`POST /api/capsulas/{id}/quiz` quedan **abiertos y sin noción de identidad**: cualquiera puede
leer el diagnóstico o la cápsula de otro estudiante conociendo el `id`. No es un descuido de este
cambio —el sistema no tiene autenticación de estudiantes, y el cap. 9 lo identifica por su
diagnóstico y no por una credencial (`web/sesion.py` lo dice desde la Fase 4)—, pero conviene
tenerlo escrito antes de una sesión con estudiantes reales: la cookie firmada evita que alguien
se haga pasar por otro **en la UI**, no que llame a la API con un `id` ajeno.

---

## 5 duovicies. Rediseño completo del frontend (02-oct-2026)

La UI de la Fase 4 era funcional pero mínima: un `style.css` de 1.228 líneas con estilos inline
en los templates, sin modo oscuro, sin íconos (emojis en su lugar), con formularios sin
`<label>` y tablas que desbordaban en el celular. Se rediseñó **toda la capa de presentación**
—las 9 pantallas y sus parciales HTMX— sin tocar backend, modelos, RAG, VARK, validación ni
migraciones, y sin cambiar ningún endpoint, campo ni flujo HTMX. Se hizo por etapas, un commit
por etapa: design system → layout base → landing → cuestionario → perfil → catálogo y carga →
visor → panel docente → esta documentación.

Las convenciones resultantes (tokens, componentes, colores VARK, módulos JS, contratos con los
tests y checklist de accesibilidad) están en [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md).

### Qué cambió, por pantalla

| Pantalla | Antes | Ahora |
|---|---|---|
| `/` | Redirigía al cuestionario | **Landing** con propuesta de valor, las 4 dimensiones VARK, "cómo funciona" y trazabilidad. El CTA cambia según haya sesión. |
| Cuestionario | Los 16 ítems en una sola tarjeta larga | **Una pregunta a la vez** sobre el mismo `<form>`: barra de progreso, "Saltar"/"Siguiente", atajos 1–4, mapa de revisión y borrador en `sessionStorage`. Sin JS se ve como antes. |
| Perfil | Barras con colores fijos (K en rojo de error) | **Radar SVG** armado en el servidor + barras por canal con ícono, "¿qué significa?" teñido con el canal principal, configuración como estadísticas. |
| Catálogo | Acordeones anidados con `▼` | Temas como tarjetas, **buscador** en el cliente (sin distinguir tildes), estado vacío sin enlace al panel para estudiantes. |
| Carga del visor | Video `animacionCarga.mp4` | **"Generando tu cápsula…"** en CSS: pasos que se marcan, `role="dialog"`, versión sin movimiento. El video se conserva en `public/`. |
| Visor | Bloques con poco contraste entre tipos, JS inline duplicado | Índice de pasos, **estilo propio por tipo de bloque** en el color de su canal, flashcards 3D accesibles, cuestionario con detalle por pregunta, **referencias con el extracto del fragmento citado**. |
| Panel docente | Formularios solo con placeholder, colores hex concatenados | Labels reales, bandeja apilable en móvil, **gráfico VARK de la cohorte** (se calculaba y no se mostraba), comparación V/A/R/K teñida por canal. |

En todas: header con navegación e íconos, **barra inferior en móvil**, **modo claro/oscuro**
(sistema + botón), foco visible, `prefers-reduced-motion`, sin scroll horizontal a 390 px.

### Decisiones tomadas

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **CSS propio con design tokens** en un solo archivo por capas | Tailwind vía CDN | El CDN de Tailwind compila en el navegador en tiempo de ejecución (no es para producción y produce un destello sin estilos) y llenaría los templates de clases. Los tests y los routers ya dependían de clases semánticas (`alerta-error`, `badge-success`…). |
| **Sprite SVG local** con un subconjunto de Lucide | Lucide/Phosphor por CDN con JS | Sin JS que reinicializar tras cada swap de HTMX y sin depender de la red. |
| **El cuestionario se pagina en el cliente, sobre el mismo `<form>`** | Un endpoint por pregunta | No cambia el contrato de `POST /student/vark` ni la calificación; el instrumento sigue siendo el mismo de los 43 diagnósticos. Las alternativas **no** se tiñen por canal: eso filtraría la matriz al navegador (cap. 17.1). |
| **La textura escolar de la sección 5 undecies queda solo en la landing y el CTA**, como máscara CSS teñida por tema | Mantenerla de fondo en toda la web | Sobre el contenido bajaba la legibilidad y con colores fijos no funcionaba en modo oscuro. Se conserva el motivo de marca, ahora monocromo (`static/img/textura-escolar.svg`). |
| **Referencias con el texto del fragmento** | Solo documento y página | Es la trazabilidad del cap. 13 a la vista del estudiante. Cuesta una lectura por clave primaria de fragmentos que `validator.py` ya verificó. |
| **Sin `autoplay` en el audio del perfil auditivo** | Mantenerlo | Un audio que arranca solo interrumpe al lector de pantalla y a quien estudia en un lugar público (WCAG 1.4.2). |
| **"Intentar de nuevo" solo si falló el modelo (502)** | Ofrecerlo siempre | Sin material o sin credencial, reintentar devuelve el mismo error. |

### Lo que se tocó fuera de templates y estáticos

Solo lo necesario para pasar datos a las vistas; ninguna lógica de dominio:

- `main.py`: `GET /` renderiza la landing (antes, redirect). Lee la cookie solo para el CTA.
- `web/routers/student.py`: `_referencias()` (texto de los fragmentos citados, solo lectura); el
  audio se renderiza con `student/_audio.html` en vez de un f-string; flag `reintentable`.
- `web/routers/teacher.py`: pasa `referencias` al simulador; `_barras_cohorte` incluye la letra
  del canal.
- `web/deps.py`: `NOMBRE_CANAL` como global de Jinja para los macros.

### Verificación

- **Tests:** 341 en verde (338 + 3 nuevos: la portada con y sin sesión, y que el visor muestra
  el fragmento citado; además se amplió un test para que sin material no se ofrezca reintentar).
  Los 4 que fallan **ya fallaban antes de empezar** (ver abajo). `ruff`: 41 errores, todos
  previos; bajó de 45 al sacar el HTML largo del router de audio.
- **En navegador real** (Playwright sobre Chrome, a 390 y 1280 px, claro y oscuro), en cada
  etapa: capturas de cada pantalla, verificación de que no hay scroll horizontal ni errores de
  consola, y los flujos HTMX: envío del cuestionario (`HX-Redirect`), error de envío vacío,
  filtro del catálogo, pantalla de carga, actividades y retroalimentación del visor, aviso de
  objetivo duplicado en curación.
- Para el visor y la comparación V/A/R/K se usó un **servidor de previsualización** fuera del
  repo, con los templates reales y una cápsula de ejemplo: así no se gastaron créditos del LLM
  ni se guardó en la base una cápsula falsa que el caché podría servir a un estudiante real.

### Lo que queda pendiente o se encontró de paso

1. **No se generó ninguna cápsula real con DeepSeek** durante el rediseño. Falta abrir un tema
   desde el catálogo con la credencial configurada para ver la pantalla de carga y el visor con
   contenido real, incluido el audio del perfil auditivo.
2. **4 tests ya fallaban antes del rediseño**: dos de `test_interaccion_quiz.py` encuentran
   intentos de quiz que otras corridas dejaron en la base, y dos de `test_prompt_maestro.py`
   no calzan con el prompt actual: las actividades kinestésicas de `614238e` y `1dc5286`
   cambiaron el texto del prompt y el test no se actualizó desde `07fc15d`. Uno espera
   `intentalo_tu` y el otro que el prompt no nombre la etiqueta "kinestésico".
3. **`pytest` a secas no recolecta en la máquina 1**: alguna dependencia de `media` (probablemente
   TTS) instala un paquete `tests` en `site-packages` que tapa el `tests/` del repo, y
   `from tests.conftest import …` falla. `test_visual.py` y `test_voz.py` además no cargan sin
   las dependencias de medios. No se tocó porque no es de la UI.
4. **`uvicorn --reload` se quedó colgado en Windows** al recargar `main.py` (siguió sirviendo el
   código viejo). Si un cambio en Python no aparece, reiniciar el servidor.
5. `textos.COLOR_CANAL` ya no lo usa ningún template (los colores salen de los tokens
   `--vark-*`); los routers todavía lo pasan. Se puede retirar cuando convenga.

---

## 5 tervicies. Marco legal: Términos, Privacidad, consentimiento y derechos (02-oct-2026)

Antes de exponer RepasAi a la cohorte hacía falta informar con transparencia qué pasa con
los datos y reducir la exposición legal del equipo. Se hizo en seis etapas, cada una con
su commit. **No se tocó la lógica de RAG, VARK ni generación.**

### 1. Auditoría de datos (lo que los textos describen)

| Pregunta | Hallazgo |
|---|---|
| Qué se persiste | `estudiante` (rango etario, género y carrera opcionales), diagnósticos VARK con **cada alternativa marcada**, configuración, cápsulas, intentos de quiz, audios `capsula_{id}.wav`. Sin nombre, correo ni RUT: son datos **seudónimos**, pero siguen siendo datos personales. |
| Qué viaja al LLM (DeepSeek) | Objetivo curricular, fragmentos curados y los 4 pesos de formato derivados del perfil. **Ningún identificador ni dato sociodemográfico**; la llamada sale del servidor, así que el proveedor no ve la IP del estudiante. |
| Cookies y almacenamiento | `id_estudiante` (30 días) y `docente` (12 h), firmadas con HMAC, `httponly` y `samesite=lax`; `repasai-theme` en localStorage y el borrador del cuestionario en sessionStorage. **Nada de analítica ni terceros → no corresponde banner de cookies.** |
| Terceros que recibían la IP | Google Fonts y unpkg (corregido en la etapa 2). |
| Autenticación y menores | No hay cuentas: la cookie es la identidad. El docente usa una clave compartida. Nada impedía el uso por menores de 18. |

**Lo más grave no era el LLM, sino la API:** `GET /api/diagnosticos/{id}`, `GET`/`POST
/api/capsulas` y `generate-audio` eran anónimos y el dueño lo declaraba el cliente.
Recorriendo ids correlativos se leía el perfil VARK de toda la cohorte.

### 2. Qué se implementó

| Etapa | Cambio |
|---|---|
| 1. `fix(api)` | Guardián `estudiante_o_docente_api`: los endpoints con `id_estudiante` exigen ser el dueño (cookie) o el docente. Al ajeno se le responde 404 y no 403, para no confirmar que el recurso existe. `POST /api/diagnosticos` pasa a ser solo del docente. El audio narra siempre el texto guardado (ignora `texto_override`) y el del simulador es solo del docente. |
| 2. `feat(web)` | Fuentes (Figtree y Fraunces variables, OFL) y HTMX 1.9.10 servidos desde `/static`. El SRI calza byte a byte. Un test impide volver a enlazar un CDN. |
| 3. `feat(legal)` | `/terminos` y `/privacidad` en plantillas editables (`templates/legal/`), con tabla de contenidos, versión y fecha (`web/legal.py`), `ui.placeholder()` para lo pendiente y el comentario `BORRADOR`. Footer legal en todas las páginas; compacto en el cuestionario y el visor. |
| 4. `feat(legal)` | Tabla `aceptacion_legal` (migración `aaf2d3de8b4e`): estudiante, documento, versión y `aceptado_en` en UTC, con historial y cascada. Casilla **no premarcada** (18+ y aceptación) en el paso 0 del cuestionario, con los botones deshabilitados hasta marcarla. Consentimiento **separado** para el género, que es dato sensible. Guardián `exigir_vigente` en `/student/*`, que lleva a `/aceptar` si la versión cambió. |
| 5. `feat(legal)` | `/mis-datos`: ver y descargar JSON (acceso y portabilidad), corregir los datos opcionales y retirar el consentimiento del género (rectificación), y eliminar todo en cascada con los `.wav` y el cierre de sesión (supresión). Oposición y bloqueo van por correo. |

**Decisiones:**
- `/mis-datos` va fuera del guardián de aceptación: ejercer derechos no puede depender de
  aceptar primero.
- Sin cuentas, la cookie es la única forma de verificar la identidad. Por eso los derechos
  se ejercen en la página y no por correo.
- Todo queda asociado a `id_estudiante` para que sobreviva al cambio a **Google Identity**
  previsto para una fase posterior. Cuando llegue, habrá que declarar el correo, el nombre y
  el identificador de Google en la Política y subir su versión.

### 3. Datos del proyecto completados (03-oct-2026)

Ya no queda ningún `[PLACEHOLDER]`; `test_no_quedan_placeholders_sin_completar` lo vigila.

- **Datos entregados por el equipo:**
  - autores, carrera y profesora guía;
  - el correo de contacto `patricio.hernandez.v@mail.pucv.cl`, personal porque no hay uno del proyecto;
  - el uso en asignaturas de Ingeniería Informática con estudiantes de la PUCV u otras universidades;
  - el acceso al panel: desarrolladores y profesores que se sumen;
  - el cierre del proyecto entre noviembre y diciembre de 2026;
  - el alojamiento solo local, sin acceso desde internet;
  - la voz de referencia: Linda Johnson, LibriVox, dominio público;
  - el origen del material: aulas virtuales y material propio, y más adelante material de docentes PUCV;
  - que las actividades no califican;
  - que los resultados se presentan solo ante la profesora guía;
  - que el código es público en GitHub.
- **Lo que se asumió**, porque el sistema no se publicará ni seguirá en marcha tras la evaluación:
  - conservación hasta el cierre del proyecto, **a más tardar el 31-dic-2026**;
  - respuesta a solicitudes en **15 días hábiles**;
  - tribunales de **Valparaíso**;
  - la PUCV no participa en el tratamiento;
  - el código no tiene licencia de código abierto, porque el repo no tiene `LICENSE`;
  - se quitaron las notas de revisión legal.
- El piloto de **mayo de 2026** (los 43 diagnósticos importados) se describe sin afirmar qué
  consentimiento se informó en el formulario. Se ofrece eliminarlo a pedido, identificándolo
  por carrera, edad y fecha. Los pre y post test futuros informarán su propio tratamiento.

### 4. Riesgos legales que siguen abiertos

1. **Los textos no tienen revisión legal profesional.** Bastan para un prototipo local y
   temporal, pero no para un servicio abierto. Por eso cada página conserva el comentario
   `BORRADOR`.
2. **Credenciales de demostración** (`admin`/`admin123`, `studify`/`studify`). Hoy el riesgo es
   bajo porque todo corre en local, pero habría que cambiarlas si alguna vez se expone a una red.
3. **El material del curso viaja a un proveedor en China** con términos propios sobre uso
   de las entradas. No hay datos personales, pero sí puede haber obras de terceros o
   material institucional confidencial.
4. **Voz clonada:** la referencia es una grabación de dominio público de LibriVox (Linda Johnson).
   Imitar la voz de una persona real sigue siendo sensible, aunque la grabación sea libre.
   XTTS-v2 solo permite uso no comercial (CPML).
5. **Los 43 diagnósticos del piloto** (mayo de 2026) se tomaron en Google Forms con un
   consentimiento que no está documentado. Además, el **material de las aulas virtuales** es
   obra de sus docentes y viaja al LLM: conviene pedirles autorización.
6. **Menores:** solo hay una declaración de edad en la casilla, sin verificación.
7. **Los audios `public/audio/capsula_{id}.wav` se sirven sin control de acceso** y sus nombres
   son predecibles. El contenido es curricular, no personal, pero conviene darles nombres no
   adivinables.
8. **La aceptación solo se exige en la web:** los endpoints `/api/*` del dueño no la piden.
9. **La Ley 21.719 rige desde el 01-dic-2026.** La Agencia y sus procedimientos todavía no
   tienen canales verificados para citar.

### Verificación

- pytest: **381 en verde**, 40 tests nuevos entre acceso a la API, recursos de terceros,
  documentos, footer, consentimiento y `/mis-datos`. Fallan los **mismos 4** previos de la
  sección 5 duovicies. `ruff`: 41 errores, los mismos previos.
- Migración aplicada, revertida y vuelta a aplicar; el índice FTS sigue intacto.
- En Chrome, a 390 y 1280 px y en claro y oscuro:
  - 0 peticiones a terceros y 0 errores de consola;
  - el flujo de aceptación completo, el rechazo de un género sin consentimiento, `/aceptar`
    y `/mis-datos`;
  - en la base, la aceptación quedó en UTC y la eliminación cayó en cascada.

## 6. Pendiente inmediato

Los dos primeros son ahora los que bloquean todo lo demás: el motor está escrito y probado,
pero **no se ha ejecutado nunca contra un modelo real ni sobre material real**.

0. ~~**Conseguir la credencial del LLM y ponerla en `LLM_API_KEY`.**~~ ✅ **Cerrado.** La key de
   DeepSeek está cargada (verificado el 13-ago-2026: `llm.api_key_configured: true` en
   `/health`) y el bake-off ya corrió — ver sección 1. Queda igual el resto de este punto como
   referencia, porque la mitigación que describe sigue siendo la que aplica si al ampliar el
   material real las cuatro cápsulas VARK del mismo objetivo salieran parecidas. El plan §5 ya
   fija la mitigación —
   instrucciones estructurales, no adjetivos de tono— y el prompt ya está construido así, de
   modo que lo que habría que ajustar son las instrucciones de
   `rag/prompts/maestro.py::INSTRUCCION_POR_DIRECTIVA`, no el motor.
1. ~~**Cargar material real de la base de conocimiento.**~~ ✅ **Cerrado el 19-ago-2026 para la
   primera asignatura.** Los cinco objetivos de "Diseño de UX" tienen material curado (13 + 10 +
   10 + 4 + 3 fragmentos validados) y ya se generaron cápsulas reales sobre ellos. Queda como
   deseable —no bloqueante— una **segunda asignatura**, para que la prueba de diferenciación
   entre perfiles VARK del punto 0 no dependa de un solo dominio.
2. ~~**Conectar la UI de Patricio a los endpoints reales.**~~ ✅ **Cerrado el 11-ago-2026**
   (sección 5 nonies). Las cinco vistas del estudiante y el panel del docente llaman a los
   handlers reales; el visor recorre los bloques del contrato por `tipo` y muestra las dos
   formas de actividad. Desde el 19-ago los recorre vía `bloques_legibles()`, que devuelve la
   representación adaptativa seguida del ejemplo.
3. ~~**`tagger.py` (etiquetado asistido por LLM)**~~ ✅ **Cerrado el 24-ago-2026** — ver
   sección 5 septendecies. `knowledge/tagger.py` propone objetivo y etiqueta temática por
   fragmento contra el catálogo activo; la propuesta queda en `metadatos_json`, nunca en
   `Fragmento.id_objetivo`, y la bandeja de revisión la usa solo para preseleccionar el
   `<select>` que el curador confirma con «Validar». Verificado contra DeepSeek real: acertó
   los dos objetivos que sí correspondían y devolvió `null` en el fragmento que no calzaba con
   ninguno, en vez de forzar una respuesta.
4. ~~Los **21 avisos de `ruff`** en `web/deps.py`, `web/routers/student.py` y
   `web/routers/teacher.py`.~~ ✅ **Cerrado el 11-ago-2026:** desaparecieron al conectar esos
   routers a la API real, tal como se había previsto. `ruff check .` está limpio en todo el
   repositorio.
5. **Resolver la discrepancia de las tablas 16.2/16.3** con la profesora guía: o se corrige el
   informe con los valores recalculados, o aparece la planilla original que explique la
   diferencia. El código ya entrega los números reales; el informe es lo que habría que ajustar.
6. ~~**Reemplazar los enunciados provisionales de los 16 ítems.**~~ ✅ **Cerrado el
   24-ago-2026** — ver sección 5 quaterdecies. No hizo falta reemplazar nada: comparados
   carácter a carácter contra el encabezado real de `data/data_cuestionarios_43.csv`, los 16
   enunciados de `web/textos.py` ya eran idénticos al instrumento original. El aviso de
   "provisional" describía un riesgo que en los hechos nunca se concretó, y se mantuvo ahí sin
   volver a verificarse. Test de regresión en `tests/test_textos_vark.py`.
7. 🔶 **Credenciales del `.env`.** Parcialmente cerrado el 26-ago-2026 (sección 5 vicies).
   - ~~Fijar `SESSION_SECRET`~~ ✅ **Cerrado en la máquina 1** el 26-ago-2026. Sin ella cada
     reinicio de `uvicorn --reload` cerraba las sesiones y obligaba a responder el
     cuestionario de nuevo a mitad de una demo. **Sigue pendiente en la máquina 2.** Se genera
     con `python -c "import secrets; print(secrets.token_hex(32))"`.
   - **Sigue abierto: cambiar `TEACHER_USERNAME`/`TEACHER_PASSWORD` del valor de fábrica.** El
     panel del docente abre sin tocar nada desde la sección 5 undevicies: usuario `admin`,
     clave `admin123`, valores por defecto en `config.py`. Es deliberado —conveniencia de
     prototipo— pero es una credencial pública y conocida por cualquiera que lea este documento
     o el código. **Antes de exponer el sistema fuera del equipo hay que fijarlas a algo propio
     en el `.env`.** Con `TEACHER_PASSWORD=` puesta vacía a propósito el panel se cierra para
     todos, que sigue siendo la forma de apagarlo del todo si hiciera falta.
8. ~~**Instalar las dependencias opcionales de ingesta** (`pip install -e ".[ingest]"`).~~
   ✅ **Cerrado — ya estaban instaladas.** Verificado el 26-ago-2026 en la máquina 1:
   `pymupdf`, `fitz` y `pptx` importan sin problema, así que el panel del docente puede
   procesar PDF/PPTX. Este punto llevaba abierto describiendo un estado que ya no era cierto.
   Sigue valiendo para una **máquina nueva**: es una dependencia opcional del `pyproject.toml`
   y `pip install -e ".[dev]"` a secas no la trae.
9. ~~**Repoblar la base de datos** (estaba vacía).~~ ✅ **Cerrado el 26-ago-2026, pero el
   problema real era el opuesto** — ver sección 5 vicies. La base no estaba vacía: tenía
   **141 estudiantes y 157 diagnósticos donde los reales son 43**, porque
   `tests/test_api_diagnosticos.py` creaba estudiantes por HTTP y no los borraba, sumando una
   decena en cada corrida de `pytest`. Se arregló **la causa** (fixture de limpieza en ese
   archivo, verificada con dos corridas seguidas sin que se muevan los conteos) y después el
   resultado (`import_vark_csv.py --reset`, que dejó los 43 reales con sus 1.202 respuestas).
   El material curado no se tocó.
10. ~~**Simulador VARK: comparación V/A/R/K lado a lado.**~~ ✅ **Cerrado el 24-ago-2026** —
    ver sección 5 quindecies. `POST /teacher/simulator/compare` genera las cuatro cápsulas
    puras del mismo objetivo y las muestra una junto a otra. **Sigue abierta la otra mitad de
    este punto: perfiles reales de la cohorte.** El simulador solo ofrece perfiles puros
    (100% en un canal); ninguno de los 43 diagnósticos reales tiene ese vector, y el caso
    multimodal —el más frecuente en la cohorte— no se puede simular todavía.
11. **Historial de cápsulas: mostrar `estado_validacion` y persistir `intentos`/`segundos`
    de la generación.** Convertiría el panel en evidencia viva del bake-off en vez de depender
    solo de `data/resultados_evaluacion.csv`. Detalle en sección 5 decies.
12. **`scripts/reset_db.py` sin confirmación** antes de `drop_all` + borrar `alembic_version`.
    Es destructivo y de un solo comando; conviene una confirmación explícita antes de que borre
    algo que cueste recuperar en una máquina compartida por el equipo.
13. **Definir con la profesora si "contenido" y "OA" son la misma jerarquía.** De su lista salen
    dos requisitos que hoy se contradicen: pide **OA secundarios** por chunk y a la vez «evitar
    que un chunk pertenezca a varios contenidos». Con el modelo actual —`Fragmento.id_objetivo`
    como FK singular— el segundo se cumple por construcción y el primero es imposible. Implementar
    OA secundarios exige una tabla de asociación nueva, y antes hay que cerrar esa ambigüedad
    conceptual. Detalle en `AUDITORIA_LISTA_PROFESORA_14AGO2026.md`, punto 3.
14. **Zanjar el punto de los embeddings con la profesora.** Su pipeline propuesto los incluye
    (paso 5); el cap. 13 del informe que ella aceptó argumenta explícitamente en contra. No es
    trabajo de programación: es una conversación pendiente sobre si la arquitectura sigue siendo
    la aprobada. Mientras no se cierre, el sistema sigue con recuperación SQL determinista.
15. 🔶 **El perfil lector-escritor (R) falla la validación con más frecuencia que los otros
    tres — significativamente mejorado, no cerrado del todo.** Investigado a fondo el
    24-ago-2026 (sección 5 sedecies) hasta encontrar y corregir **dos causas reales, verificadas
    por separado contra DeepSeek real**: (1) el objetivo de palabras de R interpola exactamente
    en el máximo duro del validador, sin margen para la variación normal del modelo — corregido
    en `rag/orchestrator.py`; (2) capturando el texto crudo de cada intento se confirmó que el
    modelo **reenviaba la respuesta anterior byte a byte idéntica** cuando el mensaje de
    reparación no le daba un blanco concreto — corregido en `generation/validator.py` (el
    mensaje ahora dice cuánto sobra y cuál es la parte más larga, y pide explícitamente una
    respuesta distinta). Verificado que la segunda corrección sí logra que el modelo recorte de
    verdad en vueltas sucesivas (3257→3202→3104 caracteres, cada uno distinto del anterior, en
    vez de tres copias idénticas). **Panorama agregado de las tres sesiones de investigación:
    6 de 11 generaciones de R exitosas (55%)**, todavía lejos del ≥95% del criterio de término
    de la Fase 3, pero dos de los tres temas de prueba ya pasan de forma consistente. Queda un
    tema («Notación O grande») que sigue fallando más que los otros —hipótesis: su explicación
    técnica necesita más palabras y comprimirla sin perder rigor le cuesta más al modelo—, sin
    confirmar todavía con más datos. Detalle completo, con las tres tablas de evidencia
    antes/después/después-de-lo-otro, en la sección 5 sedecies.
16. **Generación multimedia local (imagen/audio/video) — planificada, no iniciada.** Agregada
    el 24-ago-2026 a pedido del equipo: `PLAN_DESARROLLO.md` §4 tiene la Fase 6 completa
    (candidatos de modelo por modalidad, riesgos, integración propuesta). Es una **extensión**
    fuera del horizonte de 10 semanas — no bloquea el criterio de término de las fases 1–5, que
    sigue siendo solo texto — y reabre el punto 2 de la sección 7 (`audio_activo`), que hasta
    ahora estaba cerrado como "fuera de alcance para el prototipo". Antes de empezar a
    implementar hace falta confirmar qué GPU/VRAM tiene disponible cada máquina del equipo: los
    modelos candidatos (SDXL-Turbo, Piper TTS) se eligieron pensando en hardware modesto, pero
    sin ese dato confirmado no se puede afirmar que corran razonablemente.
17. ~~🔶 **`/api/*` sigue abierto, aunque `/teacher/*` ya no.**~~ ✅ **Cerrado el 26-ago-2026** —
    ver sección 5 unvicies. Los 13 endpoints de curación y analítica pasaron a un
    `router_docente` con `dependencies=[Depends(auth.requiere_docente_api)]`, que responde
    **401 con `WWW-Authenticate`** (no el 303 del guardián web, que un cliente HTTP seguiría
    hasta entregarle al script un 200 con HTML de login) y acepta tanto la cookie del panel
    como HTTP Basic. Quedan abiertos solo los seis del estudiante. Verificado contra el
    servidor real con `curl`, no solo con `TestClient`. **De paso apareció algo peor:** el test
    de cobertura escrito el mismo día para `/teacher/*` **pasaba en vacío** —FastAPI 0.141 no
    aplana `include_router` y el filtro veía 2 de 41 rutas—; corregido, y con un test nuevo que
    vigila que el recorrido no vuelva a quedarse ciego.
18. **Los endpoints abiertos del estudiante no tienen noción de identidad.**
    `GET /api/diagnosticos/{id}`, `GET /api/capsulas/{id}` y `POST /api/capsulas/{id}/quiz`
    quedan accesibles a cualquiera que conozca el `id`: se puede leer el diagnóstico o la
    cápsula de otro estudiante, o responder su quiz. **No es un efecto del cierre de `/api`**
    (sección 5 unvicies) sino algo que ese trabajo dejó a la vista: el sistema no tiene
    autenticación de estudiantes por diseño —el cap. 9 lo identifica por su diagnóstico, no
    por una credencial, y `web/sesion.py` lo dice desde la Fase 4—, así que la cookie firmada
    impide suplantar a alguien **en la UI**, no llamar a la API con un `id` ajeno. Para la
    demo local no importa; antes de una sesión con estudiantes reales hay que decidir si se
    acepta (los datos son de bajo riesgo y el A/B es anónimo) o si el estudiante necesita
    alguna credencial mínima. Es una decisión de alcance, no un bug.

~~Ratificar `palabras_texto`~~ ✅ **Aprobado por el equipo el 06-ago-2026** — queda la
interpolación lineal sobre C_texto tal como está implementada.

---

## 7. Decisiones de diseño aún abiertas (no bloquean la Semana 0, sí bloquean partes de la Fase 1/3)

Copiadas y mantenidas en sincronía con `PLAN_DESARROLLO.md` sección 6 — resumen aquí para no
tener que saltar de archivo:

1. ~~**Cortes numéricos de C_\* a enteros.**~~ ✅ **Cerrada en la Fase 1.** Se cortó sobre los
   porcentajes VARK crudos y no sobre los C_*, descartando la propuesta del plan (ver tabla de
   decisiones de la Fase 1 y el docstring de `vark/rules.py`). El único parámetro sin base
   directa en el informe (`palabras_texto`, interpolado sobre C_texto) también quedó aprobado
   por el equipo el 06-ago-2026.
2. ~~**`audio_activo`**~~ ✅ **Cerrada en la Fase 1 para el prototipo (fases 1–5):** queda fuera
   de alcance. El campo existe en el modelo por fidelidad a la tabla 17.4 pero se persiste
   siempre en `False`, y el canal auditivo se atiende con redacción conversacional
   (`tono_narrativo = 'oral'`). **Reabierta el 24-ago-2026, no como reversión sino como
   extensión**: a pedido del equipo se agregó la Fase 6 en `PLAN_DESARROLLO.md` §4 —
   generación local de imagen/audio/video (modelos gratuitos, sin API de pago) para
   complementar los canales V/A/K, fuera del horizonte de 10 semanas y sin bloquear el
   criterio de término de las fases 1–5. Planificada, **no iniciada**: ver pendiente n.º 16 de
   la sección 6.
3. **Fragmentos no textuales** (tablas, diagramas): ✅ **parcialmente cerrada en la Fase 2.** Las
   tablas de PPTX se serializan a texto (`tipo_fragmento = 'tabla'`, filas separadas por `|`) y
   van en su propio fragmento, de modo que el retriever y el FTS las ven. Sigue abierto el caso
   de **imágenes y diagramas**: necesitan una descripción textual escrita durante la curación en
   `metadatos_json`, y hoy la ingesta simplemente los omite.
4. ~~**Selección de tema por el estudiante**~~ ✅ **Cerrada en la Fase 2:** `GET /api/catalogo`
   devuelve el árbol asignatura → unidad → tema, ocultando por defecto los objetivos sin
   material validado (parámetro `solo_con_material`).
5. ~~**Regeneración de cápsulas**~~ ✅ **Cerrada en la Fase 3 (11-ago-2026): se versiona.**
   `POST /api/capsulas` devuelve por defecto la cápsula cacheada para la misma huella; con
   `?regenerar=true` genera una versión nueva y conserva la anterior. El motivo está en la
   sección 5 octies: el bake-off de la Fase 3 y la validación docente de la Fase 5 comparan
   varias cápsulas del mismo objetivo, y sobrescribir las haría desaparecer.

---

## 8. Correcciones detectadas en el informe (`seminario_titulo.md`), no aplicadas aún

Estas no bloquean código, pero quedaron identificadas para el informe final (ver
`PLAN_DESARROLLO.md` sección 7 para el detalle completo):

- Referencias cruzadas desfasadas (cap. 16.4 remite a "sección 12.2" debiendo ser 11.2; cap. 17
  remite a "sección 14" y "sección 12.3" inexistentes; cap. 17.1 remite a secciones 10/11
  cuando corresponden a 9/10).
- Resumen (condicional: "se espera que contribuya") vs. Abstract (indicativo: "effectively
  improves") inconsistentes en el tiempo verbal / grado de certeza.
- Cita de Saha et al. sobre duración de clases: "50 a 70 minutos" (cap. 11.1) vs. "50 a 75
  minutos" (cap. 2) — verificar contra la fuente original.
- Tabla 16.2 (muestra total) sin columna de porcentaje, a diferencia de la tabla de Ing.
  Informática — homologar formato.
- Distribución por año (cap. 16.1): 20+9+7+7=43 pero 47+21+16+16=100 solo por redondeo —
  aclarar con nota al pie.
- **(Nueva, detectada al implementar el motor VARK)** El criterio de multimodalidad está
  definido dos veces y de forma no equivalente: cap. 10 («empates o diferencias mínimas», sin
  cuantificar, sobre puntajes crudos) contra cap. 11.1 («diferencia ≤ 10 puntos porcentuales»,
  cuantificado, sobre el vector porcentual). No son intercambiables: 10 puntos porcentuales
  sobre ~16 selecciones equivalen a ~1,6 selecciones de diferencia, mientras que "empate" exige
  diferencia 0. Unificar en el informe final dejando el criterio del cap. 11.1, que es el
  implementado.
- **(Nueva)** Las reglas de la tabla 11.1 no son mutuamente excluyentes: las filas 1–5
  (umbrales por canal) y la fila 7 (tres o más dimensiones sobre 20%) pueden cumplirse a la vez,
  porque el canal dominante puede ser uno de los tres que superan el umbral —p. ej.
  `{0V, 21A, 21R, 58K}`. Conviene que el informe diga explícitamente que se aplican en capas
  (las 1–5 fijan los elementos de contenido, la 6–7 solo la etiqueta de modalidad) y no como
  alternativas.
- **(Nueva, la más importante)** **Las tablas 16.2 y 16.3 no se reproducen desde el CSV de
  respuestas**, pese a que el dataset es verificablemente el mismo (todos los sociodemográficos
  del cap. 16.1 calzan). Detalle completo en la sección 5 ter. Hay que decidir con la profesora
  guía si se corrigen los valores publicados.
- **(Nueva)** La tabla 17.1 declara `genero VARCHAR(20)`, pero el propio instrumento ofrece la
  alternativa **"No Binario / otra identidad"**, de 27 caracteres, que no cabe. Corregido en el
  modelo con `VARCHAR(50)` (migración `8eb6f0399fee`); falta corregir el diccionario de datos
  del informe.
- **(Nueva, Fase 3)** La tabla 17.8 se amplió con dos columnas que el informe no declara:
  `huella_generacion VARCHAR(64)` (clave de caché, indexada) y `modelo_llm VARCHAR(60)`. La
  primera es lo que permite no volver a pagarle al LLM por una cápsula ya generada; la segunda
  es lo que hace legible una cápsula guardada cuando el bake-off deja en la misma tabla las de
  los tres modelos candidatos. Hay que agregarlas al diccionario de datos del capítulo 17.
- **(Nueva, Fase 3)** El cap. 11.1 no distingue entre los componentes prácticos que son
  **bloques de contenido** y el que es la **actividad de cierre**. Con `p_K ≥ 40%` la tabla 11.1
  cuenta tres —ejemplo aplicado, secuencia paso a paso y actividad «inténtalo tú»— pero el
  tercero no es un bloque del cuerpo de la cápsula. Conviene que el informe lo diga
  explícitamente, porque leído al pie de la letra pide tres bloques donde solo corresponden dos.
- **(Nueva)** La tabla 17.1 define `ano_ingreso INT` ("año de ingreso a la universidad"), pero
  el formulario preguntó el **año de carrera** ("4° año o superior (semestres 7+)"). No son el
  mismo dato y uno no se deriva del otro, así que la columna se carga en `NULL`. Hay que decidir
  si se cambia el atributo del modelo a "año de carrera" (que es lo que efectivamente se
  recolectó y lo que usa el cap. 16.1) o si se agrega la pregunta al instrumento.

---

## 9. Cómo retomar el trabajo (para una sesión nueva)

```powershell
# Máquina 1: e:\code\Studify\Studify
# Máquina 2: C:\Users\vleon\Documents\proyectos\SpotCheck\Studify
cd <la ruta que corresponda>
.\.venv\Scripts\Activate.ps1

alembic upgrade head          # deja el esquema al día antes de tocar nada
uvicorn studify.main:app --reload --app-dir src
# → http://127.0.0.1:8000/health  y  http://127.0.0.1:8000/docs
# → el panel del docente: botón «Soy docente» → /teacher/login → admin / admin123
#   (valor de fábrica en config.py si el .env no fija TEACHER_USERNAME/TEACHER_PASSWORD;
#   cambiarlas antes de exponer el sistema fuera del equipo — ver pendiente n.º 7).

pytest
ruff check .
```

✅ **Verificado end-to-end contra el servidor real** (no solo `TestClient`) el 26-ago-2026, en
la máquina 1, con el `.env` tal como queda tras las secciones 5 vicies/undevicies: `uvicorn`
arriba, `GET /health` con `database.reachable: true` y `llm.api_key_configured: true`,
`GET /` redirige a `/student/vark`, `GET /teacher/curation` sin sesión responde 303 al login,
`POST /teacher/login` con `admin`/`admin123` abre sesión y `GET /teacher/curation` y
`/teacher/analytics` responden 200, y `GET /api/catalogo` devuelve los 5 objetivos reales de
"Diseño de UX". Nada de esto quedó pendiente de "debería funcionar": se probó con curl contra
el puerto real.

**Estado del `.env` por máquina** (lo que antes había que completar a mano, hoy):

| | Máquina 1 | Máquina 2 |
|---|---|---|
| `DATABASE_URL`, `LLM_API_KEY` | ✅ fijadas | ✅ fijadas |
| `SESSION_SECRET` | ✅ fijada (26-ago-2026) | ⚠️ pendiente — sin ella cada `--reload` cierra las sesiones de estudiante |
| `TEACHER_USERNAME` / `TEACHER_PASSWORD` | de fábrica (`admin`/`admin123`) | de fábrica (`admin`/`admin123`) |
| Datos VARK (`estudiante`, `diagnostico_vark`) | ✅ 43 reales, sin ruido de tests (sección 5 vicies) | sin auditar — puede tener el mismo ruido que se encontró en la máquina 1 |

Si `.venv` no existe (máquina nueva): seguir `README.md` sección "Puesta en marcha" completa,
incluyendo la creación del rol/base de Postgres (comando en README sección "Crear el rol y la
base"). Ojo con dos cosas que costaron tiempo en la máquina 2:

- La clave del superusuario `postgres` **no siempre es `postgres`**: depende de lo que se haya
  puesto al instalar. Si `psql -U postgres` rechaza la conexión, esa es la causa.
- El rol y la base se crean con estos dos comandos, y las credenciales deben ser exactamente
  estas para que el `.env` funcione sin editarlo en ninguna de las dos máquinas:

  ```sql
  CREATE ROLE studify LOGIN PASSWORD 'studify';
  CREATE DATABASE studify OWNER studify;
  ```

**Orden de lectura recomendado para contexto:** este archivo → `docs/PLAN_DESARROLLO.md` →
`seminario_titulo.md` (el informe fuente) → código en `src/studify/`.
