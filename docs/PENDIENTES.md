# Pendientes

> **La única lista de lo que falta.** Junta lo abierto de la revisión de código
> del 16-oct-2026, de `AVANCE.md` §6 y §7, de los hallazgos H# de
> `PRUEBAS_VARK.md`, de la Fase 5 de `PLAN_DESARROLLO.md` y de los riesgos
> legales. Cada ítem dice de dónde viene (**Origen**), para buscar ahí su
> historia y su evidencia.
>
> **Cómo se mantiene:** al cerrar algo se borra de acá y se registra en
> `AVANCE.md` con su commit. Las listas de origen quedan como registro de su
> fecha y no se vuelven a actualizar.
>
> Última revisión: 17-oct-2026. Las ubicaciones de código van por función; los
> números de línea son aproximados.

---

## Cómo se trabaja (acordado con el autor)

- **Un punto por commit.** El autor hace los commits en GitHub Desktop: al
  terminar cada punto, detenerse y entregar título y descripción en estilo
  Conventional Commits, en español (`fix(área): …`). Nunca correr `git commit`.
- **Primero el test que falla** y reproduce el bug; después el arreglo.
- **Correr la suite de dos formas** al cerrar cada punto:

  ```powershell
  # Sin base: DATABASE_URL a un puerto cerrado
  $env:DATABASE_URL="postgresql+psycopg://nadie:nada@127.0.0.1:1/nada?connect_timeout=2"; $env:LLM_API_KEY=""
  .\.venv\Scripts\python -m pytest -q --ignore=tests/test_visual.py --ignore=tests/test_voz.py

  # Con el Docker del autor levantado (sin DATABASE_URL en el entorno)
  $env:LLM_API_KEY=""
  .\.venv\Scripts\python -m pytest -q --ignore=tests/test_visual.py --ignore=tests/test_voz.py
  ```

  `LLM_API_KEY` vacía para no gastar en el proveedor. `test_visual.py` y
  `test_voz.py` cargan SDXL y XTTS al importarse (H8): siempre se ignoran.
- **No tocar nada fuera del punto en curso.** Si aparece algo más, anotarlo acá
  o avisar; meterlo en el mismo commit solo si sin eso el punto no queda
  correcto, y decirlo.

**Estado de la suite al 17-oct-2026** (los fallos son todos previos):

| Forma | Resultado | Fallos |
|---|---|---|
| Puerto cerrado | 384 pasan, 196 omitidos, 4 fallan | 4 de `test_web_auth.py` sin `@necesita_bd` (R10) |
| Con Postgres | 580 pasan, 2 omitidos, 2 fallan | 2 de `test_interaccion_quiz.py` que exigen la tabla vacía (R10) |

---

## Antes del piloto con estudiantes

Lo que conviene cerrar antes de que la app la usen personas reales. El detalle
de cada uno está más abajo.

1. **R2** — dos estudiantes en el mismo computador (siguiente punto de la revisión).
2. **Credenciales de fábrica** (`admin`/`admin123`) y `SESSION_SECRET` de la máquina 2 (O1).
3. **Repetir la batería VARK con `deepseek-flash`**, incluido el perfil V (G1).
4. **Desplegar ya los cambios del 17-oct**: el cambio de la huella del caché
   (`ce30e6d`) regenera cada cápsula una vez, y no conviene que eso pase a mitad
   del piloto. Y cada máquina tiene que quedar al día (O2).
5. **Instrumentos y consentimiento de la Fase 5** (E1–E4).
6. **Riesgos legales** L1, L3 y L5.

---

## R. Revisión de código del 16-oct-2026

Corregidos el 17-oct: puntos 5 (`b7f769d`), 1 (`a3883ef`), 4 (`6e081fe`),
6 (`ce30e6d`) y 3 (`a922240`). El detalle de qué cambió está en la descripción de
cada commit.

### R2. Dos estudiantes en el mismo computador — **siguiente**

Prioridad alta: contamina los datos del A/B en un laboratorio.

- **Qué pasa hoy:**
  - El estudiante no tiene «cerrar sesión» ni «no soy yo».
  - La cookie `id_estudiante` dura 30 días (`web/sesion.py`, `DURACION_SEGUNDOS`).
  - `student.py::_armar_payload`: con sesión válida, el cuestionario se **agrega
    al estudiante de la cookie**. Una segunda persona en el mismo navegador
    pisa el perfil vigente del primero, sus datos sociodemográficos se
    descartan y su aceptación legal queda a nombre del otro.
  - Lo único que hoy borra la cookie es «Eliminar mis datos» o un id inexistente.
- **Condición del autor:** antes de implementar, **mostrarle cómo quedaría el
  flujo de «No soy yo»** (pantallas y qué pasa con la sesión y los datos) y
  esperar su visto bueno.
- **Ideas para la propuesta (no decididas):**
  - Enlace «No soy yo / cerrar sesión» en la cabecera (`templates/base.html`):
    un `POST` que llame a `sesion.cerrar` y vuelva a la portada. No borra
    datos, solo olvida la cookie.
  - En `GET /student/vark` con sesión abierta: aviso «Estás respondiendo como
    el estudiante n.º X», con «Soy yo, actualizar mi perfil» o «Soy otra
    persona» (cierra la sesión y empieza de cero).
  - En `post_vark`: exigir esa elección en el formulario cuando hay sesión, en
    vez de reutilizarla en silencio.
  - Tests: con la cookie de A, responder como «otra persona» crea un
    estudiante nuevo, deja intacto el diagnóstico vigente de A y registra la
    aceptación a nombre del nuevo.
- **Relacionado, preguntar si entra:** tras `scripts/reset_db.py` las ids
  vuelven a 1 y una cookie vieja firmada con el mismo `SESSION_SECRET` apunta
  a otro estudiante. Se resuelve metiendo algo propio del estudiante en la
  firma (p. ej. `fecha_registro`).

### Prioridad media

- **R7. No hay cómo retirar material ya usado.** El 409 de
  `api/routers/knowledge.py::eliminar_documento` pide marcar
  `estado_curacion='rechazado'`, pero no existe endpoint ni pantalla para
  hacerlo (`EstadoCuracion` en `schemas_knowledge.py` no se usa). Tampoco se
  puede editar ni desactivar un objetivo, y `crear_capsula` no comprueba
  `objetivo.estado`.
- **R8. `teacher.py::_fila`** busca el fragmento entre los primeros 600
  (`listar_fragmentos(limite=LIMITE_BANDEJA * 10)`). Con más material, aprobar
  o descartar hace desaparecer la fila y oculta el error. Arreglo:
  `db.get(Fragmento, id)` con sus relaciones.
- **R9. La regla de idioma no revisa `tarjetas` ni `preguntas`**:
  `generation/schemas.py::Microcapsula.texto_plano`. Reproducido: una cápsula
  K con todo el quiz en inglés pasa.
- **R10. Los tests usan la base de desarrollo.**
  - `tests/test_api_diagnosticos.py::limpiar_lo_que_cree_el_test` borra todo
    estudiante con `id > max(antes)`: un registro real hecho mientras corre
    `pytest` se perdería.
  - 4 tests de `test_web_auth.py` sin `@necesita_bd`; 2 de
    `test_interaccion_quiz.py` exigen la tabla entera vacía.
  - `hay_base_de_datos()` sin `connect_timeout` (es H11).
  - Propuesta: base de pruebas separada (`studify_test`) o transacción con
    rollback por test.
- **R11. `scripts/import_vark_csv.py --reset`** hace `db.query(Estudiante).delete()`:
  borra también a los estudiantes del piloto, sin confirmación.
- **R12. Rutas relativas al directorio de trabajo**: `config.py` lee `.env`
  con `env_file=".env"`; `documentos_dir`, `media_dir` y `tts_modelos_dir` son
  `data/...`; XTTS busca `tests/referencia.wav`. Arrancada desde otra carpeta,
  la app queda sin `.env`: clave de docente `admin123`, sin LLM, sesiones
  efímeras. Los audios ya se resolvieron (`narracion.DIRECTORIO_AUDIO`).
- **R13. Promedio VARK de la cohorte** (`teacher.py::get_analytics`): promedia
  todos los diagnósticos, con reintentos y los 43 del CSV mezclados con el
  piloto. Debería tomar el último por estudiante; convendría una columna
  `origen` (importado / app).
- **R14. La fila 7 de la tabla 11.1 como regla de contenido no existe** →
  decisión del equipo (ver D4).

### Prioridad baja

- **Chunker:** un residuo corto al final de una sección no se une al anterior
  (`knowledge/chunker.py::_fusionar_residuos`). Reproducido: queda un
  fragmento de 21 palabras con mínimo 40.
- **Configuración sin efecto:** `CAPSULA_MAX_PALABRAS_TITULO` no se usa (el
  esquema tiene 10 fijo). `CAPSULA_MIN/MAX_PALABRAS` pueden desalinearse del
  CHECK 150–300 y de `vark/rules.py`.
- **Narración:** `narracion.guion` lee solo activación + concepto central; no
  incluye la analogía, que es el bloque propio del perfil A.
- **Glosario:** llega como lista de strings y se dibuja como `<ul>`; el
  `<dl class="glosario">` de `_capsula.html` solo aparece con lista de listas.
- **Guion de audio** (`media/guion.py`): «→» se lee «determina» (Bases de
  Datos) en todas las asignaturas.
- **Registro:** con `APP_ENV=dev`, `db/session.py` usa `echo=True` y la consola
  muestra SQL con parámetros (género, contenido). `/health` expone el texto
  del error de la base.
- **Ingesta:** PPTX ignora formas agrupadas, SmartArt y notas; PDF no filtra
  encabezados ni pies repetidos.
- **Peticiones largas:** el tagger hace hasta 60 llamadas seguidas en un
  request; `/simulator/compare`, 4 generaciones en serie.
- **Retriever:** con más de 8 fragmentos validados por objetivo, los que
  quedan después de los primeros 8 nunca llegan al prompt.
- **Coste sin tope:** un estudiante puede llamar `POST /api/capsulas?regenerar=true`
  sobre sí mismo sin límite.

### Calidad y reproducibilidad

- Sin archivo de versiones fijas (todo `>=` en `pyproject.toml`) ni CI.
- Alembic: con `include_object` en `alembic/env.py` se evita quitar a mano el
  `drop_index` de `ix_fragmento_contenido_fts` en cada autogenerate. El `Index`
  de ese nombre en `db/models.py` no queda asociado a ninguna tabla.
- Código muerto o desfasado: `media/generator.py` (`GeneradorMultimedia`),
  docstring de `media/image.py` (dice Z-Image/FLUX, carga SDXL),
  `scripts/check_taesd3.py` (UTF-16, no se ejecuta), `scripts/scratch.py`.
- `ruff check .` tiene unos 40 avisos previos, sobre todo E501 en `scripts/`.

---

## G. Generación y adaptación VARK

- **G1. Repetir la batería VARK con el modelo de producción.** `deepseek-flash`
  se validó con 4 cápsulas, todas de perfil V; la batería de 30 perfiles A/R/K
  se corrió con `deepseek-chat` (29/30 válidas, 26 a la primera = 96,7 %).
  Repetirla con `scripts/probar_perfiles_vark.py`, incluido el perfil V, que
  quedó fuera. K es la salida más larga y va con `max_tokens=2000`. Absorbe el
  pendiente n.º 15 de AVANCE (R fallaba más), que la batería ya mostró
  superado en validez y que hoy vive como H1/H3.
  Origen: `PRUEBAS_VARK.md` «Resumen de fallos»; `analisis-modulo-visual.md` §10.8.
- **G2. H3 — K se pasa de largo y R se queda corto** (+48 / −57 palabras
  respecto del objetivo). Abierto. Origen: `PRUEBAS_VARK.md`, H3.
- **G3. H4 — con 25 ≤ p_K < 40 % el prompt pide «2 componentes prácticos» sin
  nombrar un bloque**, y el modelo entrega 1. Inconsistencia entre
  `_cantidad_componentes_practicos` y `_directivas` de `vark/rules.py`; toca
  la lectura de la tabla 11.1, así que la decide el equipo. Origen: H4.
- **G4. H1 — el perfil R no recibe glosario** (cerrado como limitación
  conocida tras 4 rondas). Si se retoma, los parches A y E están en
  `scripts/h1h3/parches/` y quedan dos alternativas sin probar: degradación
  elegante y validar el número de entradas. Origen: H1 y «Etapa 1».
- **G5. H6 — el modelo inventa datos de ejemplo** (RUT ficticios, 2/29). Origen: H6.
- **G6. H7 — «preguntas reflexivas» casi nunca se cumple** (2/13). Origen: H7.
- **G7. H12 — el texto por defecto de `flashcards_y_quiz` nombra el perfil**
  («Sesión práctica kinestésica…», `generation/schemas.py::Actividad`). Origen: H12.
- **G8. El validador no comprueba las directivas del perfil** (tabla para
  V ≥ 40 %, glosario para R, tipo de actividad para K). La adaptación VARK no
  se verifica, solo se pide. Origen: revisión del 16-oct.
- **G9. Simulador con perfiles reales de la cohorte.** Solo ofrece perfiles
  puros (100 % en un canal), que no tiene ninguno de los 43 diagnósticos; el
  caso multimodal, el más frecuente, no se puede simular.
  Origen: AVANCE §6 n.º 10 y §5 decies.
- **G10. Historial de cápsulas sin `estado_validacion`, `intentos` ni
  `segundos`.** Con esas columnas el panel sería la evidencia viva del
  criterio de término de la Fase 3, sin depender de scripts.
  Origen: AVANCE §6 n.º 11 y §5 sedecies.
- **G11. Revisión docente de cápsulas.** `estado_validacion` nunca cambia de
  «generada» y el caché compartido no filtraría las rechazadas. La Fase 5 lo
  necesita (E3). Origen: revisión del 16-oct.

## E. Evaluación (Fase 5) — sin empezar

El horizonte del plan terminaba el 09-oct-2026. Origen: `PLAN_DESARROLLO.md` §4, Fase 5.

- **E1. A/B pedagógico:** definir cómo se registran las calificaciones de los
  dos grupos (es dato externo, la base no lo captura) y qué material exacto
  estudia el grupo de control para que sea comparable en cobertura y tiempo.
- **E2. Batería técnica:** 20 a 30 consultas controladas con rúbrica 1–5 y
  doble evaluador (fidelidad, exactitud factual, relevancia, trazabilidad).
  `scripts/eval_runner.py` hoy cubre un objetivo y perfiles puros.
- **E3. Validación docente de la adaptación:** el profesor compara las
  cápsulas de un mismo objetivo para los distintos perfiles. Ajustar la
  rúbrica del cap. 8.5 para incluir ese criterio. Depende de G11.
- **E4. Encuesta TAM a estudiantes, rúbrica a docentes y reclutamiento con
  consentimiento informado.** El plan pedía tenerlos listos en la semana 6.
- **E5. Estadística descriptiva y capítulo de resultados.**

## L. Legal y licencias

Origen: `AVANCE.md` §5 tervicies «Riesgos legales que siguen abiertos» y
`PRUEBAS_VARK.md` «Material de origen no documentado».

- **L1. Los textos legales no tienen revisión profesional**; cada página
  conserva el comentario `BORRADOR`. Bastan para un prototipo local, no para
  un servicio abierto.
- **L2. El material del curso viaja a un proveedor en China** con términos
  propios sobre el uso de las entradas.
- **L3. Autorizaciones pendientes:** el consentimiento de los 43 diagnósticos
  de Google Forms (mayo de 2026) no está documentado, y el material de las
  aulas virtuales es obra de sus docentes: conviene pedirles autorización.
- **L4. Menores de edad:** solo hay una declaración en la casilla, sin verificación.
- **L5. La aceptación de Términos y Política solo se exige en la web**: los
  endpoints de `/api/*` del estudiante no la piden.
- **L6. La Ley 21.719 rige desde el 01-dic-2026**; la Agencia todavía no tiene
  canales verificados para citar.
- **L7. Origen y licencia del material sin documentar:** `animacionCarga.mp4`,
  `docs/historico/2026-08-13_fondo_de_marca.dc.html`, las imágenes de prueba de
  `docs/images/` (qué variante de SD3 se usó), `tests/referencia.wav` y
  `tests/prueba_entorno.wav`. La tabla con lo que hay que confirmar de cada uno
  y una redacción propuesta para los Términos están en `PRUEBAS_VARK.md`.
- **L8. Licencias que restringen:** XTTS-v2 (CPML, solo uso no comercial; es
  opción administrativa) y la voz `sharvard`, que parte de una voz entrenada
  con datos solo para investigación. `pymupdf` es AGPL-3.0, compatible con la
  licencia del repo; si se quisiera evitar, las alternativas son pdfminer.six,
  pdfplumber o pypdf, sin probar.

## O. Operación y entorno

- **O1. Credenciales.** Cambiar `TEACHER_USERNAME`/`TEACHER_PASSWORD` del valor
  de fábrica antes de exponer el sistema; fijar `SESSION_SECRET` en la máquina
  2. Origen: AVANCE §6 n.º 7 y §9.
- **O2. Dejar cada máquina al día.** Correr `alembic upgrade head` (migración
  `d7e2b9c41a58`, 17-oct-2026; ya aplicada en la de la revisión, `D:\PUCV\…`)
  y fijar `LLM_MODEL=deepseek-flash` en el `.env` (desde el 11-oct). Los datos
  VARK de la máquina 2 siguen sin auditar: puede tener el mismo ruido de tests
  que tuvo la máquina 1. Origen: AVANCE §9 y §5 quatertricies.
- **O3. `scripts/reset_db.py` no pide confirmación** antes de `drop_all`.
  Origen: AVANCE §6 n.º 12.
- **O4. Los `codigo_objetivo` siguen el patrón `PREFIJO-Ux-NN`, pero la API no
  lo exige**, y falta un archivo común de respaldo con los objetivos de cada
  materia. Origen: AVANCE §5 undetricies.
- **O5. Kokoro tiene episodios de ~0,6 × la duración del audio** que no se
  explicaron (la mediana es ~0,19). Origen: AVANCE §5 duotricies.

## D. Decisiones con la profesora guía

- **D1. Tablas 16.2/16.3 del informe:** no se reproducen desde el CSV de los 43
  diagnósticos. O se corrige el informe con los valores recalculados, o
  aparece la planilla que explique la diferencia. Origen: AVANCE §6 n.º 5 y §5 ter;
  `CORRECCIONES_INFORME.md` C1.
- **D2. ¿«Contenido» y «OA» son la misma jerarquía?** Pidió OA secundarios por
  fragmento y a la vez evitar que un fragmento pertenezca a varios contenidos;
  con `Fragmento.id_objetivo` singular lo segundo se cumple y lo primero es
  imposible. Origen: AVANCE §6 n.º 13.
- **D3. Embeddings:** su pipeline los incluye y el cap. 13 del informe
  argumenta en contra. Mientras no se cierre, la recuperación sigue siendo SQL
  determinista. Origen: AVANCE §6 n.º 14.
- **D4. Fila 7 de la tabla 11.1** («tres o más dimensiones sobre el 20 %»):
  `vark/hierarchy.py` dice que `UMBRAL_MULTIMODAL` se usa para contenido, pero
  nadie lo usa; `vark/rules.py::_directivas` aplica el criterio de ≤ 10
  puntos. `{0V, 21A, 21R, 58K}` no recibe las directivas de equilibrio.
  Origen: revisión del 16-oct (R14).
- **D5. H13 — los pesos C_* llegan al prompt con el nombre de su canal.** Se
  mantuvo como decisión de diseño; si el cap. 17.2 se lee de forma estricta,
  hay que decidirlo aparte. Origen: H13.
- **D6. Identidad del estudiante:** hoy es solo la cookie firmada; una fase
  posterior agregaría Google Identity, con el consentimiento y los derechos
  colgando de `id_estudiante`. Origen: AVANCE §6 n.º 18.

## X. Extensiones planificadas

- **X1. Módulo Visual:** propuesta del 11-oct-2026 con prototipo
  determinístico (el LLM entrega una especificación y la plataforma dibuja el
  SVG). El prompt existe (`rag/prompts/visual.py`) pero la app no lo usa.
  Estimación de esfuerzo y cambios previos a implementar en
  `docs/modulo-visual/analisis-modulo-visual.md` §10.6 y §11.
- **X2. Fragmentos no textuales:** la ingesta omite imágenes y diagramas; la
  propuesta es guardar una descripción textual en `metadatos_json` al curar.
  Origen: AVANCE §7 n.º 3.
- **X3. Imagen generada (Fase 6):** en pausa por decisión del equipo (texto
  ilegible con difusión, `docs/historico/2026-09-03_experimento_flux2_klein.md`
  §10); X1 la reemplaza para los diagramas. El audio de esta fase ya está
  hecho (Kokoro y Piper). Origen: AVANCE §6 n.º 16.

## Correcciones al informe

Qué corregir, actualizar o agregar en el informe final respecto del de avance
está en [`CORRECCIONES_INFORME.md`](CORRECCIONES_INFORME.md).

---

**Orden sugerido:** R2 → O1 → R10 → G1 → R7, R8, R9 → E1–E4 → el resto.
