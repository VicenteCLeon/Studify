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
> Última revisión: 08-nov-2026. Las ubicaciones de código van por función; los
> números de línea son aproximados.

---

## Cómo se trabaja (acordado con el autor)

- **Un punto por commit.** El autor hace los commits en GitHub Desktop: al
  terminar cada punto, detenerse y entregar título y descripción en estilo
  Conventional Commits, en español (`fix(área): …`). Nunca correr `git commit`.
- **Primero el test que falla** y reproduce el bug; después el arreglo.
- **Correr la suite de dos formas** al cerrar cada punto:

  ```powershell
  # Sin base: DATABASE_URL a un puerto cerrado (el nombre igual termina en _test)
  $env:DATABASE_URL="postgresql+psycopg://nadie:nada@127.0.0.1:1/nada_test?connect_timeout=2"; $env:LLM_API_KEY=""
  .\.venv\Scripts\python -m pytest -q --ignore=tests/test_visual.py --ignore=tests/test_voz.py

  # Con el Docker del autor levantado, contra la base de pruebas (nunca `studify`)
  $env:DATABASE_URL="postgresql+psycopg://studify:studify@localhost:5432/studify_test"; $env:LLM_API_KEY=""
  .\.venv\Scripts\python -m pytest -q --ignore=tests/test_visual.py --ignore=tests/test_voz.py
  ```

  `LLM_API_KEY` vacía para no gastar en el proveedor. `test_visual.py` y
  `test_voz.py` cargan SDXL y XTTS al importarse (H8): siempre se ignoran.
  Desde el 08-nov (R10) `tests/conftest.py` no arranca si el nombre de la base
  no termina en `_test`. Crear y migrar `studify_test`: README, «Testing y
  calidad».
- **No tocar nada fuera del punto en curso.** Si aparece algo más, anotarlo acá
  o avisar; meterlo en el mismo commit solo si sin eso el punto no queda
  correcto, y decirlo.

**Estado de la suite al 08-nov-2026**, en `main` después de unir el chunker
(`3929c0f`), la base de pruebas y el retriever (`eb1d75a`, `396616d`) y los
logs a archivo (`2f33ca7`). El cierre de la Etapa 2 (`c28df6a`: 769/2/0 y
452/315/4) está en AVANCE §5 undequadragies, y los estados anteriores en las
secciones de su fecha.

| Forma | Pasan | Omitidos | Fallan |
|---|---|---|---|
| Puerto cerrado | 482 | 326 | 4: los de `test_web_auth.py` sin `@necesita_bd` |
| Con Postgres (`studify_test`) | 810 | 2 | 0 |
| `node tests/*.cjs` | 7 + 5 comprobaciones | — | 0 (no se volvió a correr el 08-nov) |

Antes de lanzar la forma «con Postgres», comprobar que el contenedor
`studify-db` esté *healthy*: sin base la corrida no falla, se cuelga (H11).

---

## Antes del piloto con estudiantes

Lo que conviene cerrar antes de que la app la usen personas reales. El detalle
de cada uno está más abajo. Los seis primeros quedaron abiertos al cerrar las
Etapas 1 y 2 del estudio A/B (08-nov, AVANCE §5 undequadragies); el 7 (R10)
se sumó ese mismo día.

1. **Recorrido manual con Google real, con una cuenta de cada grupo** (O6):
   elegir grupo, entrar, salir y volver, cápsula, actividad y «Mis datos».
   Incluye las **4 comprobaciones de la animación de carga** del punto 2b.
2. **Rotar el `client_secret` de Google** cuando termine esa prueba (O6).
3. **Prueba pre/post común a los dos grupos** (E1): el instrumento que mide
   el aprendizaje en el A/B, igual para Control y Experimental.
4. **R15:** arreglar `scripts/eval_runner.py`, que puede mandar la clave de
   DeepSeek a otros proveedores. No usarlo antes.
5. **D7:** decidir si se restringe el acceso a cuentas `@mail.pucv.cl`.
6. **Punto 1d** (G8): métricas de adherencia sin rechazo y auditoría de las
   cápsulas guardadas, como evidencia para E3.
7. ✅ **R10: que la suite no use la base de desarrollo** (resuelto el 08-nov,
   `eb1d75a`). La suite corre contra `studify_test` y `tests/conftest.py` se
   niega a arrancar contra una base cuyo nombre no termine en `_test`. En la
   máquina del piloto falta crear y migrar su `studify_test` (README); queda
   lo menor anotado en R10.
8. **Sesión en computadores compartidos:** fijar `SESION_ESTUDIANTE_HORAS` según
   dónde se use (1–4 en un laboratorio) y dejar cada máquina en la última
   migración (`a7c3d9e51f64`, O2). R2 ya está corregido (`75c14fa`, AVANCE §5
   sextricies).
9. **Credenciales en la máquina 2** (O1): la parte de código está hecha el
   27-oct (sin `admin123` de fábrica; fuera de `APP_ENV=dev` no arranca sin un
   `SESSION_SECRET` fuerte). Falta fijar los valores a mano.
10. **Repetir la batería VARK con `deepseek-flash`**, incluido el perfil V (G1).
11. **Desplegar los cambios antes del piloto, no durante:** el cambio de huella
    del 17-oct (`ce30e6d`) y el del punto 1c (`666f587`, perfiles con
    `actividad_aplicada`) regeneran las cápsulas afectadas una vez, y el control
    estrena la variante `control-neutro-v1`. El 08-nov cambió además la huella
    del control (esquema básico con «entre 3 y 5 alternativas»), así que sus
    cápsulas guardadas también se regeneran una vez. Conviene que esas generaciones
    ocurran antes del piloto y no a mitad de él. Cada máquina tiene que quedar
    al día (O2).
12. **Instrumentos y consentimiento de la Fase 5** (E1–E4).
13. **Riesgos legales** L1, L3 y L5.

---

## R. Revisión de código del 16-oct-2026

Corregidos el 17-oct: puntos 5 (`b7f769d`), 1 (`a3883ef`), 4 (`6e081fe`),
6 (`ce30e6d`) y 3 (`a922240`). El 24-oct, el punto 2 (`75c14fa`: R2, dos estudiantes en
el mismo computador; AVANCE §5 sextricies). El 08-nov, R16: un test del
grupo control fallaba al azar porque buscaba «43» en el HTML entero, que trae
tokens aleatorios; ahora los textos cortos se buscan con
`tests/conftest.py::texto_visible`. El detalle de qué cambió está en la
descripción de cada commit.

### Prioridad alta

- ✅ **R10. Los tests usaban la base de desarrollo** (resuelto el 08-nov,
  `eb1d75a`; antes del piloto, punto 7). `tests/conftest.py` importa el
  `engine` de `db/session.py`, que se conecta al `DATABASE_URL` efectivo. Con
  el `.env` eso era la misma base que la app: `test_api_diagnosticos.py`
  borraba todo estudiante con `id > max(antes)` (un registro real hecho
  mientras corría `pytest` se perdía con sus diagnósticos, cápsulas e
  intentos), y los 2 tests de `test_interaccion_quiz.py` que exigen la tabla
  `interaccion_quiz` vacía fallaban con los intentos del uso local de la app.

  **Cómo se resolvió: una base `studify_test` fija y una protección**, en vez
  del esquema temporal por corrida que se había propuesto ese mismo día.

  - **Base de pruebas:** `studify_test`, creada una vez con
    `docker exec studify-db createdb -U studify studify_test` y migrada con
    `alembic upgrade head` (con `DATABASE_URL` apuntando a ella). Para correr la
    suite se fija `DATABASE_URL` a esa base en la terminal: la variable de
    entorno manda sobre el `.env`, así que la app sigue usando `studify`.
    Instrucciones en el README («Testing y calidad»).
  - **Protección en `tests/conftest.py`:** `pytest_configure` detiene la suite
    (código 2, antes de importar cualquier test) si el nombre de la base no
    termina en `_test`, con un mensaje que dice cómo apuntar a `studify_test`.
    Se comprobó con `pytest` solo y con una ruta explícita.
  - **Verificación (08-nov):** filas de `documento_fuente`, `fragmento`,
    `objetivo_aprendizaje`, `estudiante`, `interaccion_quiz` y
    `microcapsula_generada` de `studify` iguales antes y después de cada
    corrida (2/107/11/1/6/5). Los 2 tests de la tabla vacía pasan en
    `studify_test`. `main`: 810 pasan, 2 omitidos, 0 fallan.
  - **Por qué base y no esquema:** es más simple de inspeccionar y no cambia
    `db/session.py` ni la forma de conectarse. El costo es que hay que crearla
    (pide `CREATEDB` o superusuario; el rol `studify` del Docker lo es) y que
    no se vacía sola entre corridas.

  **Queda abierto (prioridad baja salvo donde se indica):**

  - **Máquina del piloto:** crear y migrar su `studify_test`, y repetir
    `alembic upgrade head` sobre ella después de cada migración nueva.
  - **`studify_test` acumula lo que un test interrumpido no limpie.** Los dos
    `== []` de `test_interaccion_quiz.py` volverían a fallar si quedaran
    intentos sueltos. Conviene filtrarlos por las cápsulas del escenario,
    para que no dependan de que la base esté vacía ni del orden de los tests.
    Si la base se ensucia: `dropdb` y `createdb` de `studify_test` y migrar
    de nuevo (nunca sobre `studify`).
  - **Los 2 tests que hacen `CREATE DATABASE`**
    (`test_interaccion_quiz.py::test_la_migracion_recalcula_los_intentos_ya_guardados`
    y `test_preferencia_voz.py::test_la_migracion_sube_baja_y_vuelve_a_subir`)
    siguen fallando con un rol sin `CREATEDB`. Propuesta sin cambios: que
    usen su propio esquema `test_mig_<uuid>`, como
    `test_grupo_control.py::test_migracion_rol_es_reversible_y_preserva_estudiantes`.
  - `test_api_diagnosticos.py` conserva el borrado por `id > max(antes)`; ya
    solo alcanza a `studify_test`.
  - Aparte, sin relación con el aislamiento: 4 tests de `test_web_auth.py`
    sin `@necesita_bd` **solo fallan sin base** (forma «puerto cerrado»).
  - `hay_base_de_datos()` sin `connect_timeout` es H11 (abajo).

- **H11. La suite se cuelga si Postgres no responde.** `tests/conftest.py::hay_base_de_datos()`
  se conecta sin `connect_timeout`, así que cuando no hay base los tests no se
  saltan: la corrida se queda esperando. **Causó un cuelgue real el 27-oct-2026**:
  la suite «con Postgres» (sin `DATABASE_URL`, a `localhost:5432`) se lanzó con
  Docker apagado y pasó más de 10 minutos sin salida ni avance (unos 6 s de
  CPU) hasta que hubo que matar el proceso. La forma «puerto cerrado» no se
  cuelga porque su `DATABASE_URL` ya trae `connect_timeout=2`. Arreglo:
  pasar `connect_args={"connect_timeout": …}` al conectar en
  `hay_base_de_datos()` (o en `db/session.py`). Mientras tanto, comprobar que
  Postgres responde antes de correr la suite con base.
  Origen: AVANCE §5 duodetricies («H11: `test_api_diagnosticos` se cuelga sin
  Postgres») y R10.
- **R15. `scripts/eval_runner.py` puede enviar la clave de DeepSeek a otros
  proveedores.** En la línea 104, `api_key = os.environ.get(env_key) or
  os.environ.get("LLM_API_KEY")`: si faltan `QWEN_API_KEY` o `GLM_API_KEY`, usa
  `LLM_API_KEY` (la de DeepSeek) y la manda a `dashscope-intl.aliyuncs.com` y a
  `open.bigmodel.cn`. El respaldo solo debería valer para el modelo cuyo
  proveedor es el de `LLM_API_KEY`; para los demás, sin su clave propia, saltar.
  Además, por defecto sobrescribe `data/resultados_evaluacion.csv`. **No usar
  `eval_runner.py` hasta arreglarlo**; para verificar perfiles K está
  `scripts/verificar_1c_k.py`. Va en su propio punto. Origen: revisión del
  punto 1c, 05-nov-2026.

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
- **R11. `scripts/import_vark_csv.py --reset`** hace `db.query(Estudiante).delete()`:
  borra también a los estudiantes del piloto, sin confirmación.
- **R12. Rutas relativas al directorio de trabajo**: `config.py` lee `.env`
  con `env_file=".env"`; `documentos_dir`, `media_dir` y `tts_modelos_dir` son
  `data/...`; XTTS busca `tests/referencia.wav`. Arrancada desde otra carpeta,
  la app queda sin `.env`: desde O1 no arranca (sin `SESSION_SECRET` y sin
  `APP_ENV=dev`), y con las variables en el entorno arrancaría sin LLM. Los
  audios ya se resolvieron (`narracion.DIRECTORIO_AUDIO`).
- **R13. Promedio VARK de la cohorte** (`teacher.py::get_analytics`): promedia
  todos los diagnósticos, con reintentos y los 43 del CSV mezclados con el
  piloto. Debería tomar el último por estudiante. Desde R2 existe
  `estudiante.origen_registro` (NULL para los del CSV, la API y los anteriores):
  agregarle `importado` permitiría separar el CSV del piloto y, de paso,
  excluir los posibles duplicados.
  - **Diagnósticos de estudiantes del grupo control (08-nov, revisión del
    2d):** el promedio tampoco filtra por rol. Hoy no cambia nada, porque el
    control no responde VARK (2a/2c). Pero si un estudiante con rol `control`
    tuviera un diagnóstico (guardado antes de quedar en ese grupo, o agregado
    por un proceso externo, caso que `perfil_de_contenido` ya ignora), entraría
    al promedio de la cohorte. Al arreglar R13, tomar solo diagnósticos de
    estudiantes con rol `estudiante`. No se tocó en el 2d.
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
- **Secretos en la salida de `pytest`:** cuando falla un test que toca
  `get_settings()`, el `repr` de `Settings` imprime `session_secret`,
  `teacher_password` y `llm_api_key` en claro (visto el 24-oct). Pasarlos a
  `SecretStr` de Pydantic.
- **Registro:** con `APP_ENV=dev`, `db/session.py` usa `echo=True` y la consola
  muestra SQL con parámetros (género, contenido). `/health` expone el texto
  del error de la base.
- **Ingesta:** PPTX ignora formas agrupadas, SmartArt y notas; PDF no filtra
  encabezados ni pies repetidos.
- **Peticiones largas:** el tagger hace hasta 60 llamadas seguidas en un
  request; `/simulator/compare`, 4 generaciones en serie.
- **Retriever:** con más de 8 fragmentos validados por objetivo, los que
  quedan después de los primeros 8 nunca llegan al prompt. En el grupo control
  (cápsula básica, `canal_primario=None`, 04-nov-2026) entran los 8 primeros
  por documento y número de fragmento; en el experimental, los 8 primeros
  según el canal primario. Con más de 8, los dos grupos pueden recibir
  material distinto del mismo objetivo.
- **Alternativas de los cuestionarios:** `generation/schemas.py::Pregunta`
  acepta de 2 a 5 alternativas por pregunta (`min_length=2`), mientras `quiz_mc`
  exige de 3 a 5 (`MIN_ALTERNATIVAS`), y el código explica que con 2 se acierta
  la mitad de las veces por azar. El prompt del experimental no se contradice:
  pide 4 alternativas en `quiz_mc` y muestra 4 en cada pregunta del esquema
  (`ESQUEMA_JSON`), y el validador tolera de 3 a 5 a propósito. Lo distinto es
  solo el mínimo del validador en los cuestionarios. Visto el 08-nov al
  unificar el esquema del control; no se tocó.
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
  - **Actividad de K cerrada (punto 1c, 05-nov):** con la directiva
    `actividad_aplicada` el validador exige `flashcards_y_quiz` y la huella de
    esos perfiles la incluye, así que sus cápsulas guardadas que no cumplían
    se regeneran. Ojo: la directiva no sale solo con p_K ≥ 40; la regla de
    respaldo de `rules._directivas` también la da a perfiles sin canal sobre
    40 y con K primario (6 de los 43; p. ej. A23-R38-K39).
  - **Punto 1d (sigue ahora que la Etapa 2 cerró el 08-nov; evidencia para
    E3, en «Antes del piloto»):** métricas de
    adherencia **sin rechazo** en `metricas` del validador para las
    directivas verificables en el JSON (bloque `tabla` ≥ 2×3, `esquema`,
    `glosario`, `lista_pasos`, `ejemplo_resuelto`, `analogia`, cantidad de
    recursos visuales, encabezados no vacíos) y una auditoría de solo lectura
    de las cápsulas guardadas. Con esos números se decide qué directivas pasan
    a ser obligatorias; exigirlas sin medir antes choca con el tope de 300
    palabras (como el glosario de R, G4). No verificables: definiciones
    exactas, tono oral, preguntas reflexivas (G6), orden general→particular.
  - **Primer dato de adherencia (05-nov, `scripts/verificar_1c_k.py --live`,
    `deepseek-flash`, BD-U3-02, `data/pruebas_vark/20261105-013904_1c_K/`):**
    6/6 válidas, 6 a la primera, las 6 con `flashcards_y_quiz`. Veredicto de la
    batería 4/6; los dos fallos pasan el contrato y fallan en adherencia:
    - **A10-R40-K50**, criterio *texto*: falta el `glosario` pedido con
      p_R ≥ 40 (entregó `lista_pasos` + `ejemplo_resuelto`). Es **H1/G4**, ahora
      en un perfil R+K codominante con 6 directivas y 272 palabras.
    - **V30-A10-R10-K50**, criterio *ejercicios*: 2/3 componentes prácticos,
      falta `lista_pasos` pese a la directiva `paso_a_paso` (p_K ≥ 40). La
      representación trae un solo bloque, la `tabla` de
      `recurso_visual_complementario`. **No corresponde a un hallazgo
      conocido:** G3/H4 es para 25 ≤ p_K < 40, y la batería del 03-oct (12/12
      con `lista_pasos`) no tenía perfiles con V. Es la primera combinación
      V ≥ 25 + K ≥ 40 medida; con n = 1 es una señal, no una conclusión.
    - Extensión (sin fallo de criterio): desviaciones de −54 a +53 palabras
      respecto del objetivo, en línea con **G2/H3**.
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

## E. Evaluación (Fase 5)

El horizonte del plan terminaba el 09-oct-2026. Origen: `PLAN_DESARROLLO.md` §4, Fase 5.

- **E1. A/B pedagógico.**
  - ✅ **En la app (Etapas 1 y 2, 04–08-nov, AVANCE §5 undequadragies):** el
    experimental recibe la cápsula adaptada a su perfil y el control una
    cápsula básica sin VARK (resumen y `quiz_mc`), sin narración. Los dos
    entran con Google y eligen su grupo en `/student/login`. El panel separa
    las métricas por grupo y `/teacher/exportar/intentos.csv` entrega los
    intentos con su rol, sin datos personales.
  - **Falta la prueba pre/post común a los dos grupos:** qué instrumento mide
    el aprendizaje, igual para Control y Experimental, cuándo se aplica y cómo
    se registra (la base no lo captura; se cruzaría por `id_estudiante` con el
    CSV de intentos). También definir las calificaciones y comprobar que el
    material de los dos grupos sea comparable en cobertura y tiempo (ver la
    limitación del retriever con más de 8 fragmentos, en «Prioridad baja»).
  - **Asignación:** cada estudiante elige su grupo en el login; la app no
    sortea. El equipo decide cómo asigna y comunica qué grupo elige cada
    participante. Esto no reemplaza el diseño experimental.
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

- **O1. Credenciales.** Origen: AVANCE §6 n.º 7 y §9.
  - ✅ **Código (27-oct-2026):** `TEACHER_PASSWORD` ya no tiene valor por
    defecto (sin ella el panel queda cerrado). `APP_ENV` vale `prod` si no se
    fija, y fuera de `dev` `config.verificar_configuracion` no deja arrancar sin
    un `SESSION_SECRET` de 32+ caracteres que no sea de ejemplo, ni con una
    clave de docente débil (menos de 12 caracteres o conocida, como `admin123`).
    En `dev` solo avisa. Tests en `tests/test_config_seguridad.py`.
  - **Falta, a mano en la máquina 2:** fijar en su `.env` un `SESSION_SECRET`
    propio (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) y
    una `TEACHER_PASSWORD` nueva de 12+ caracteres, y reiniciar la app.
    Decidir su `APP_ENV`: fuera de `dev` la cookie lleva `Secure`, así que con
    `prod` la app hay que servirla por HTTPS o desde `localhost`; por HTTP a la
    IP de la red el navegador descarta la cookie y nadie puede iniciar sesión.
  - En la máquina 1 conviene revisar que su `TEACHER_PASSWORD` no siga siendo
    `admin123` (en `dev` arranca igual, con un aviso).
- **O2. Dejar cada máquina al día.** Correr `alembic upgrade head` (migración
  `d7e2b9c41a58`, 17-oct-2026; ya aplicada en la de la revisión, `D:\PUCV\…`)
  y fijar `LLM_MODEL=deepseek-flash` en el `.env` (desde el 11-oct). Los datos
  VARK de la máquina 2 siguen sin auditar: puede tener el mismo ruido de tests
  que tuvo la máquina 1. Origen: AVANCE §9 y §5 quatertricies.
  - **Máquina 2, 01-nov:** esquema actualizado a `f6b2c8d40e53` (grupo control),
    previo respaldo. Conserva los 49 estudiantes anteriores; sus datos VARK
    siguen sin auditar. Falta comprobar modelo y credenciales locales (O1).
- **O3. `scripts/reset_db.py` no pide confirmación** antes de `drop_all`.
  Origen: AVANCE §6 n.º 12.
- **O4. Los `codigo_objetivo` siguen el patrón `PREFIJO-Ux-NN`, pero la API no
  lo exige**, y falta un archivo común de respaldo con los objetivos de cada
  materia. Origen: AVANCE §5 undetricies.
- **O5. Kokoro tiene episodios de ~0,6 × la duración del audio** que no se
  explicaron (la mediana es ~0,19). Origen: AVANCE §5 duotricies.
- **O6. Activar y probar Google Identity.** El código de D6 está implementado
  (01-nov, AVANCE §5 octtricies) y la migración `a7c3d9e51f64` está aplicada en
  la máquina 2 y, desde el 02-nov, en la máquina 1.
  - ✅ **02-nov-2026, máquina 1:** `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y
    `GOOGLE_REDIRECT_URI` (`http://127.0.0.1:8000/student/google/callback`)
    quedaron en su `.env`; la app arranca y `/student/login` responde. El venv
    no tenía `google-auth`: hizo falta `pip install -e .` (README, paso de
    Google). Las 47 pruebas de `tests/test_google_login.py` pasan.
  - **Falta:** probar con una cuenta real **de cada grupo** (Control y
    Experimental), a mano en el navegador: elegir el grupo en
    `/student/login` (2a), entrar con cuenta nueva, salir y volver, vincular
    un perfil local, el borrador VARK antes de iniciar sesión (y que se
    descarte al elegir Control), cápsula, actividad, «Mis datos» y la descarga
    del CSV desde el panel (2d). Las pruebas automáticas simulan el intercambio y la
    verificación del token; el camino contra Google no está cubierto. Confirmar
    en Google Cloud que la URI exacta está registrada y que las cuentas de
    prueba están como usuarios de prueba.
  - **Animación de carga del visor (punto 2b), en el mismo recorrido manual:**
    no se verificó en un navegador real (05-nov; la extensión de Chrome no
    estaba conectada). Las pruebas cubren el cálculo
    (`tests/test_carga_visor.cjs`) y el HTML, no la apertura y el cierre de la
    capa. Comprobar, con una cuenta control y una experimental:
    1. **Cápsula desde el caché:** al hacer clic en un tema la capa aparece y
       se cierra cerca de los 4 s (`VISOR_CARGA_MINIMA_MS`) en los dos grupos.
    2. **Generación real** (cápsula no cacheada): la capa se ve durante la
       generación y se cierra al llegar la cápsula, sin quedarse pegada ni
       cerrarse antes.
    3. **Recarga, botón «atrás» y enlace directo al visor:** la cápsula se ve
       de inmediato, sin capa.
    4. **bfcache (atrás y adelante):** la capa no queda abierta.
  - **Rotar el `client_secret`:** se pegó en una conversación con el asistente
    el 02-nov. Crear uno nuevo en Google Cloud cuando termine la prueba y
    actualizar el `.env`.
  - **Prueba por túnel (Cloudflare):** con la URI en `127.0.0.1` el retorno de
    Google no vuelve al host del túnel y falla con «El acceso no corresponde a
    este navegador». Para probar desde otro dispositivo hay que poner la URL
    del túnel en `GOOGLE_REDIRECT_URI` y registrarla en Google Cloud; un túnel
    rápido cambia de URL en cada arranque (conviene uno con nombre fijo). Fuera
    de `APP_ENV=dev` la cookie lleva `Secure` y exige un `SESSION_SECRET` fuerte
    (O1).
  - **Abierto, decisión del equipo (D7):** ver más abajo.

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
- **D6. Perfiles históricos sin vinculación y sin sesión válida.** El acceso
  y la recuperación mediante Google ya están implementados (AVANCE §5
  octtricies; activación pendiente O6). Los registros del CSV y los perfiles
  locales cuya cookie se perdió no contienen una identidad verificable para
  vincularlos a una cuenta. Acordar cómo tratar esos históricos en el piloto;
  no se emparejan por correo, nombre o sociodemográficos ni se fusionan solos.

- **D7. ¿Restringir el acceso a cuentas `@mail.pucv.cl`?** Hoy entra cualquier
  cuenta Google con correo verificado (`google_login.py::verificar_token`).
  Si el piloto es solo para la PUCV, falta validar el dominio del correo (o el
  claim `hd`) en el servidor. Si es abierto, queda como está. Origen: análisis
  del flujo, 02-nov-2026.

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

**Orden sugerido:** «Antes del piloto» (arriba) → H11 → R7, R8, R9 → E2–E5 → el resto.
