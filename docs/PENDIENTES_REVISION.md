# Pendientes de la revisión del 16-oct-2026

> Documento de traspaso entre sesiones. Resume la revisión completa del código
> del 16-oct-2026 y lo que se corrigió el 17-oct, para retomar **sin volver a
> analizar todo el repositorio**. Leerlo antes de tocar código; para el
> contexto general del proyecto siguen valiendo `AVANCE.md` y `PLAN_DESARROLLO.md`.
>
> Las ubicaciones son del 17-oct-2026 (después de los commits de abajo). Se
> dan por función; los números de línea son aproximados.

---

## Cómo se trabaja (acordado con el autor)

- **Un punto por commit.** El autor hace los commits en GitHub Desktop: al
  terminar cada punto, detenerse y entregar título y descripción en estilo
  Conventional Commits, en español (`fix(área): …`). Nunca correr `git commit`.
- **Primero el test que falla** y reproduce el bug; después el arreglo.
- **Correr la suite de dos formas** al cerrar cada punto:

  ```powershell
  # Sin base (lo que pidió el autor): DATABASE_URL a un puerto cerrado
  $env:DATABASE_URL="postgresql+psycopg://nadie:nada@127.0.0.1:1/nada?connect_timeout=2"; $env:LLM_API_KEY=""
  .\.venv\Scripts\python -m pytest -q --ignore=tests/test_visual.py --ignore=tests/test_voz.py

  # Con el Docker del autor levantado (sin DATABASE_URL en el entorno)
  $env:LLM_API_KEY=""
  .\.venv\Scripts\python -m pytest -q --ignore=tests/test_visual.py --ignore=tests/test_voz.py
  ```

  `LLM_API_KEY` vacía para no gastar en el proveedor. `test_visual.py` y
  `test_voz.py` cargan SDXL y XTTS al importarse (H8): siempre se ignoran.
- **No tocar nada fuera del punto en curso.** Si aparece algo más, anotarlo
  acá o avisar; meterlo en el mismo commit solo si sin eso el punto no queda
  correcto (y decirlo).

### Estado de la suite al cierre (17-oct-2026)

| Forma | Resultado | Fallos (todos **previos**, no de esta revisión) |
|---|---|---|
| Puerto cerrado | 384 pasan, 196 omitidos, 4 fallan | 4 de `test_web_auth.py` sin `@necesita_bd` (punto 10) |
| Con Postgres | 580 pasan, 2 omitidos, 2 fallan | 2 de `test_interaccion_quiz.py` que exigen la tabla `interaccion_quiz` vacía y la base de desarrollo tiene 2 intentos reales (punto 10) |

`ruff check .` tiene ~40 avisos previos (sobre todo E501 en `scripts/`); los
archivos tocados en esta revisión quedaron limpios.

---

## Ya corregido (17-oct-2026)

Orden pedido por el autor: 5, 1, 4, 6, 3 (de menor a mayor riesgo).

| Punto | Commit | Qué quedó |
|---|---|---|
| 5 | `b7f769d` fix(auth): aceptar tildes y ñ en las credenciales del docente | `sesion.verificar_credenciales_docente` compara bytes UTF-8 (antes 500 con «ñ»). |
| 1 | `a3883ef` fix(llm): informar la caída del proveedor en vez de responder 500 | `ErrorProveedorLLM` (subclase de `ErrorGeneracion`) en `generation/generator.py`; API responde **504**; visor explica y ofrece reintentar; tagger detiene el lote; `LLM_MAX_RETRIES=1`. Helper de tests `cliente_con_proveedor_caido` en `tests/conftest.py`. |
| 4 | `6e081fe` fix(legal): que «Eliminar mis datos» funcione con cápsulas y borre sus audios | **Bug extra encontrado:** la supresión daba 500 a todo estudiante con cápsulas (faltaba `cascade` en `Estudiante.capsulas`). Módulo nuevo `web/narracion.py` (guion, directorio absoluto de audios, nombres posibles) y `audio.voces_posibles()`. |
| 6 | `ce30e6d` fix(cache): invalidar la cápsula cacheada al cambiar el material o el prompt | `orchestrator.huella` incluye texto/procedencia de fragmentos, objetivo y un hash de las plantillas. Los C_* siguen fuera **a propósito** (test que lo fija). Las cápsulas viejas no vuelven a coincidir: se regeneran una vez. |
| 3 | `a922240` fix(analytics): corregir en el servidor y separar la métrica por tipo de actividad | `corregir_actividad` y `registrar_intento` en `api/routers/capsules.py`; flashcards sin corrección; cuestionarios por pregunta (`aciertos`, `total_preguntas`, `detalle_json`); panel separa «Selección única» y «Cuestionario» (opción elegida por el autor). Migración `d7e2b9c41a58`, **ya aplicada en la base de la máquina 1**. |

**Para la máquina 2 (Vicente):** correr `alembic upgrade head` (migración
`d7e2b9c41a58`).

**Para el A/B:** el cambio de la huella (punto 6) hace que la primera visita a
cada tema después del despliegue genere una cápsula nueva. Desplegar antes del
piloto, no a mitad.

---

## Siguiente: punto 2 — dos estudiantes en el mismo computador

**Prioridad alta** (contamina los datos del A/B en un laboratorio).

**Qué pasa hoy**

- El estudiante no tiene «cerrar sesión» ni «no soy yo». La cookie
  `id_estudiante` dura 30 días (`web/sesion.py`, `DURACION_SEGUNDOS`).
- `student.py::_armar_payload`: si hay sesión válida, el cuestionario se
  **agrega al estudiante de la cookie**. Una segunda persona en el mismo
  navegador pisa el perfil vigente del primero, sus datos sociodemográficos se
  descartan y su aceptación legal queda a nombre del otro
  (`consentimiento.registrar` con el id viejo).
- Lo único que hoy borra la cookie es «Eliminar mis datos» o un id inexistente.

**Condición del autor:** antes de implementar, **mostrarle cómo quedaría el
flujo de «No soy yo»** (pantallas y qué pasa con la sesión y los datos) y
esperar su visto bueno.

**Ideas para la propuesta (no decididas)**

- Un enlace «No soy yo / cerrar sesión» en la cabecera para el estudiante
  conectado (`templates/base.html`), `POST` que llame a `sesion.cerrar` y
  vuelva a la portada. No borra datos: solo olvida la cookie.
- En `GET /student/vark` con sesión abierta: aviso «Estás respondiendo como el
  estudiante n.º X» con dos opciones: «Soy yo, actualizar mi perfil» o «Soy
  otra persona» (cierra sesión y empieza de cero).
- En `post_vark`: exigir que esa elección venga explícita en el formulario
  cuando hay sesión, en vez de reutilizarla en silencio.
- Tests: con cookie de A, responder como «otra persona» crea un estudiante
  nuevo, deja intacto el diagnóstico vigente de A y registra la aceptación a
  nombre del nuevo.
- Relacionado y **fuera de este punto**: tras `scripts/reset_db.py` las ids
  vuelven a 1 y una cookie vieja firmada con el mismo `SESSION_SECRET` apunta
  a otro estudiante. Se resolvería metiendo algo propio del estudiante en la
  firma (p. ej. `fecha_registro`). Preguntar si entra en el punto 2.

---

## Pendientes del informe (prioridad media)

7. **No hay cómo retirar material ya usado.** El 409 de
   `api/routers/knowledge.py::eliminar_documento` pide marcar
   `estado_curacion='rechazado'`, pero no existe endpoint ni pantalla para
   hacerlo (`EstadoCuracion` en `schemas_knowledge.py` no se usa). Tampoco se
   puede editar ni desactivar un objetivo (`estado` siempre «activo»). Además
   `crear_capsula` no comprueba `objetivo.estado`.
8. **`teacher.py::_fila`** busca el fragmento entre los primeros 600
   (`listar_fragmentos(limite=LIMITE_BANDEJA * 10)`). Con más material,
   aprobar o descartar hace desaparecer la fila y oculta el error. Arreglo:
   `db.get(Fragmento, id)` con sus relaciones.
9. **La regla de idioma no revisa `tarjetas` ni `preguntas`:**
   `generation/schemas.py::Microcapsula.texto_plano` solo incluye
   `pregunta`, `alternativas` y `retroalimentacion` de la actividad.
   Reproducido: una cápsula K con todo el quiz en inglés pasa.
10. **Los tests usan la base de desarrollo.**
    - `tests/test_api_diagnosticos.py::limpiar_lo_que_cree_el_test` borra todo
      estudiante con `id > max(antes)`: un registro real hecho mientras corre
      `pytest` se perdería.
    - 4 tests de `test_web_auth.py` (`test_la_api_de_curacion_acepta_http_basic`,
      `…_acepta_la_cookie_del_panel`, `test_los_endpoints_del_estudiante_siguen_abiertos`,
      `test_una_peticion_anonima_no_gasta_intentos`) no llevan `@necesita_bd`.
    - 2 de `test_interaccion_quiz.py` exigen la tabla entera vacía.
    - `hay_base_de_datos()` sin `connect_timeout` (H11).
    - Propuesta: base de pruebas separada (`studify_test`) o transacción con
      rollback por test.
11. **`scripts/import_vark_csv.py --reset`** hace `db.query(Estudiante).delete()`:
    borra también a los estudiantes del piloto, sin confirmación.
12. **Rutas relativas al directorio de trabajo.** `config.py` lee `.env` con
    `env_file=".env"`; `documentos_dir`, `media_dir`, `tts_modelos_dir` son
    `data/...`; XTTS busca `tests/referencia.wav` (`media/audio.py::_sintetizar_xtts`).
    Arrancado desde otra carpeta, la app queda sin `.env`: clave de docente
    `admin123`, sin LLM, sesiones efímeras. **Los audios ya se resolvieron en
    el punto 4** (`narracion.DIRECTORIO_AUDIO` es absoluto).
13. **Promedio VARK de la cohorte** (`teacher.py::get_analytics`,
    `func.avg(DiagnosticoVark.porcentaje_*)`): promedia todos los
    diagnósticos, con reintentos y los 43 del CSV mezclados con el piloto.
    Debería usar el último diagnóstico por estudiante; convendría una columna
    `origen` (importado / app).
14. **La fila 7 de la tabla 11.1 como regla de contenido no existe.**
    `vark/hierarchy.py` dice que `UMBRAL_MULTIMODAL` se usa «para contenido»,
    pero nadie lo usa: `vark/rules.py::_directivas` aplica el criterio de
    ≤ 10 puntos (`jerarquia.es_multimodal`). `{0V, 21A, 21R, 58K}` no recibe
    las directivas de equilibrio. **Decisión del equipo**, no arreglo directo.

## Prioridad baja

- **Chunker:** un residuo corto al final de una sección no se une al anterior
  (`knowledge/chunker.py::_fusionar_residuos`, solo mira `previo.palabras`).
  Reproducido: queda un fragmento de 21 palabras con mínimo 40.
- **Configuración sin efecto:** `CAPSULA_MAX_PALABRAS_TITULO` no se usa
  (`generation/schemas.py` tiene `MAX_PALABRAS_TITULO = 10` fijo).
  `CAPSULA_MIN/MAX_PALABRAS` pueden desalinearse del CHECK 150–300 y de
  `vark/rules.py` (`PALABRAS_MIN/MAX`).
- **Narración:** `narracion.guion` lee solo activación + concepto central; no
  incluye la analogía, que es el bloque propio del perfil A.
- **Glosario:** el prompt lo pide como lista de strings y el visor lo dibuja
  como `<ul>`; el `<dl class="glosario">` de `_capsula.html` solo aparece si
  llega como lista de listas.
- **Guion de audio** (`media/guion.py`): «→» se lee «determina» (vocabulario de
  Bases de Datos) en todas las asignaturas.
- **Registro:** con `APP_ENV=dev`, `db/session.py` usa `echo=True` y la
  consola muestra SQL con parámetros (género, contenido). `/health` expone el
  texto del error de la base.
- **Ingesta:** PPTX ignora formas agrupadas, SmartArt y notas; PDF no filtra
  encabezados ni pies repetidos.
- **Peticiones largas:** el tagger hace hasta 60 llamadas seguidas en un
  request; `/simulator/compare` hace 4 generaciones en serie.
- **Retriever:** con más de 8 fragmentos validados por objetivo, los que
  quedan después de los primeros 8 (por documento y número) nunca llegan al
  prompt.
- **Coste sin tope:** un estudiante puede llamar `POST /api/capsulas?regenerar=true`
  sobre sí mismo sin límite.

## Calidad, reproducibilidad y documentación

- Sin archivo de versiones fijas (todo `>=` en `pyproject.toml`) ni CI.
- Alembic: con `include_object` en `alembic/env.py` se evita quitar a mano el
  `drop_index` de `ix_fragmento_contenido_fts` en cada autogenerate. El
  `Index` de ese nombre en `db/models.py` no queda asociado a ninguna tabla.
- **Validación del cambio de modelo:** `deepseek-flash` se validó con 4
  cápsulas, todas de perfil V; la batería VARK (A/R/K, 30 perfiles) se corrió
  con `deepseek-chat`. Repetirla antes del piloto (`scripts/probar_perfiles_vark.py`):
  K es la salida más larga y va con `max_tokens=2000`.
- `estado_validacion` de las cápsulas nunca cambia: no hay revisión docente de
  cápsulas (Fase 5) y el caché compartido no filtraría las rechazadas.
- Código muerto o desfasado: `media/generator.py` (`GeneradorMultimedia`),
  docstring de `media/image.py` (dice Z-Image/FLUX, carga SDXL),
  `docs/IMPLEMENTACION_IA_LOCAL.md` (describe un `video.py` inexistente),
  `scripts/check_taesd3.py` (UTF-16, no se ejecuta), `scripts/scratch.py`.
- `AVANCE.md` no se actualiza desde el 05-oct-2026: faltan la migración a
  `deepseek-flash`, el borrado de documentos y los cinco commits del 17-oct.

## Ya registrados en otros documentos (siguen abiertos)

- `PRUEBAS_VARK.md`: H1 (glosario de R, limitación conocida), H3, H4, H6, H7,
  H8, H11, H12; H13 es decisión de diseño.
- `AVANCE.md` §6: pendientes n.º 5, 7 (cambiar `admin`/`admin123` antes de
  exponer el sistema), 10, 11, 12 (`reset_db.py` sin confirmación), 13, 14,
  16 y 18.
- Fase 5 (encuesta TAM, rúbrica docente, registro de notas del A/B) sin
  empezar.

**Orden sugerido para seguir:** punto 2 → cambiar la clave de fábrica →
punto 10 (base de pruebas) → repetir la batería VARK con `deepseek-flash` →
puntos 7, 8, 9 → el resto.
