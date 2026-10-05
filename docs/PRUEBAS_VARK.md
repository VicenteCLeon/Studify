# Pruebas de punta a punta del motor adaptativo VARK

Batería que ejecuta el pipeline real —retriever → reglas VARK → prompt maestro →
DeepSeek con bucle de reparación → XTTS local— sobre **un objetivo fijo** y un
conjunto de perfiles {V, A, R, K}, para comprobar que el motor adapta la
microcápsula al perfil. Script: [`scripts/probar_perfiles_vark.py`](../scripts/probar_perfiles_vark.py).
Tests sin red: [`tests/test_perfiles_vark.py`](../tests/test_perfiles_vark.py).

## Alcance

| Canal | Qué se prueba | Dónde vive |
|---|---|---|
| **R** (lector/escritor) | El texto de la cápsula: extensión, idioma, fidelidad a los fragmentos, y con p_R ≥ 40 % glosario y encabezados en todos los bloques | `vark/rules.py` → `rag/prompts/maestro.py` |
| **A** (auditivo) | El WAV que genera XTTS-v2 en local con el guion del visor (`activacion` + `concepto_central`) cuando p_A ≥ 25 %, y con p_A ≥ 40 % analogía, segunda persona y preguntas | `media/audio.py`, `web/routers/student.py` |
| **K** (kinestésico) | Los ejercicios: con p_K ≥ 40 % la actividad `flashcards_y_quiz` (3–5 tarjetas y 3–5 preguntas) más los bloques `ejemplo_resuelto` y `lista_pasos`; con 0 < p_K < 40 % la cantidad de componentes prácticos | `vark/rules.py`, `generation/schemas.py` |
| **V** (visual) | **Excluido por decisión del equipo (03-oct-2026).** V vale 0 % en todos los perfiles y el script no importa `media/image.py` | ver «Limitaciones conocidas» |

**Objetivo fijo:** `BD-U3-02` — Dependencias Funcionales (6 fragmentos validados, todos
de tipo texto, 513 palabras, con página). Se eligió por ser el que más material tiene
y porque trae contenido para los tres canales: definición formal (R), la analogía del
RUT (A) y un ejercicio guiado con el algoritmo de cierre (K).

## Cómo reproducir

```powershell
# Capa 1 — sin red, sin BD, sin GPU (~2 s)
.venv\Scripts\python.exe -m pytest tests/test_perfiles_vark.py -q

# Capa 2 — plan, llamadas y costo estimado (consulta la BD, no llama al LLM)
.venv\Scripts\python.exe scripts/probar_perfiles_vark.py

# Capa 2 — ejecución real (acotada o completa)
.venv\Scripts\python.exe scripts/probar_perfiles_vark.py --live --max-runs 3
.venv\Scripts\python.exe scripts/probar_perfiles_vark.py --live --semilla 42

# Regenerar la sección de resultados desde una corrida guardada
.venv\Scripts\python.exe scripts/probar_perfiles_vark.py --informe data/pruebas_vark/<corrida>/resumen.json
```

Los artefactos (cápsula JSON, prompt, respuestas crudas del LLM, WAV y
`resultado.json` por perfil, y `resumen.json` por corrida) quedan en
`data/pruebas_vark/<fecha>_semilla<N>/`, que git ignora. No se escribe nada en la
base de datos: el script llama a las funciones del motor directamente, sin
estudiantes, diagnósticos ni caché por huella.

## Batería

- **Fase A — puros:** 100 % A, 100 % R, 100 % K.
- **Fase B — mezclas controladas:** parejas 50/50 (A+R, A+K, R+K); 70/20/10 y 60/30/10 en
  las seis permutaciones de A, R, K; equilibrado 34/33/33; extremos 90/5/5 con cada
  canal dominante. 19 perfiles.
- **Fase C — aleatorias:** N mezclas (8 por defecto) Dirichlet(1, 1, 1) sobre A, R, K,
  redondeadas por resto mayor a enteros que suman 100. La semilla queda en el informe;
  `--semilla` la reproduce.
- **Fase D — Visual:** no se ejecuta (ver «Limitaciones conocidas»).

## Criterios y heurísticas

Una ejecución **pasa** si ningún criterio falla. Las advertencias (⚠️) no hacen fallar.

| Criterio | Falla si… | Límite conocido |
|---|---|---|
| **Contrato** | El JSON no valida contra `Microcapsula` (Pydantic) más las reglas de `validator.py` en 3 intentos. Se informa el intento en que validó. | — |
| **Trazabilidad** | No hay fuentes, alguna cita un `id_fragmento` que no se inyectó en el prompt, o alguna queda sin página. Se recalcula contra los fragmentos inyectados, no solo con la métrica del validador. | El validador ya reescribe documento y página desde la BD, así que la página falla solo si el fragmento no la tiene. |
| **Texto** | Contenido fuera de 150–300 palabras, idioma no español, o cifras de 2+ dígitos que no están en los fragmentos. Con p_R ≥ 40 %: falta `glosario` o algún bloque no tiene encabezado. | La **cobertura léxica** (raíces de 6 letras de la cápsula presentes en los fragmentos) solo advierte bajo 50 %: una analogía cotidiana legítima usa palabras ajenas al material. La fidelidad semántica no se puede automatizar del todo, así que se revisa a mano una muestra. |
| **Audio** (p_A ≥ 25 %) | Falla el TTS, el archivo está vacío o no se decodifica completo (`ffmpeg -f null`), la duración queda fuera de 1,5–4 palabras/s del guion, o el guion es JSON o está vacío. Con p_A < 25 % no se genera audio y el criterio queda «—». | La duración detecta truncamientos y silencios, no si la pronunciación es buena: eso exige escuchar los WAV. |
| **Ejercicios** (p_K > 0) | Componentes prácticos contados (`ejemplo_resuelto` + `lista_pasos` + actividad práctica) menores que los de `configuracion_contenido`. Con p_K ≥ 40 % además: la actividad no es `flashcards_y_quiz` con 3–5 tarjetas y 3–5 preguntas explicadas, falta `ejemplo_resuelto` o `lista_pasos`, o menos del 80 % de las respuestas correctas están respaldadas léxicamente por los fragmentos. | La «resolubilidad» es léxica: comprueba que la respuesta correcta use el vocabulario del material, no que sea la única correcta. |
| **Proporcionalidad** | Algún canal ≥ 40 % no puntúa estrictamente más que cada canal bajo 40 %. Todos los canales sobre el umbral son codominantes (50/50 o 41/46), porque todos reciben sus directivas completas. | Ver abajo. |
| **Operativo** | Error de red, credencial o timeout (💥). Se informan la latencia del LLM y del TTS, las llamadas y los tokens leídos del `usage` de la API. | — |

### Heurística de proporcionalidad

Cada canal tiene **marcadores observables** en la cápsula, cada uno ligado a una
directiva de `vark/rules.py` que solo pide ese canal. El puntaje del canal es la
fracción de sus marcadores presentes (0–1):

| Canal | Marcadores |
|---|---|
| R | bloque `glosario` · todos los bloques con encabezado · contenido ≥ 240 palabras |
| A | bloque `analogia` · ≥ 3 marcas de segunda persona · pregunta dentro de la prosa · audio generado |
| K | bloque `ejemplo_resuelto` · bloque `lista_pasos` · actividad práctica (`flashcards`, `flashcards_y_quiz` o `intentalo_tu`) |
| V | bloque `tabla` · bloque `esquema` (solo para detectar que no aparezca, porque V = 0 %) |

**Límites:**

1. **El motor decide por umbrales, no de forma continua.** Solo un canal ≥ 40 % recibe
   directivas propias, así que un secundario al 20 % o al 30 % casi no deja marcas.
   La proporción solo se exige al dominante; con un perfil sin canal ≥ 40 % queda «n/a».
2. **Un canal al 0 % puede tener marcadores** sin que sea un error: toda cápsula
   tiene `ejemplo` y actividad (los siete pasos son obligatorios), y el modelo puede
   elegir por su cuenta una `lista_pasos` o una analogía. Por eso se informa como
   advertencia y no como falla.
3. El marcador «audio» de A lo decide el código (p_A ≥ 25 %), no el LLM: mide que el
   pipeline completo responde al perfil, no la redacción.

## Resultados

<!-- inicio:resultados-generados -->

### Corrida `20261003-235748_semilla42`

- **Fecha:** 2026-10-03 23:57
- **Objetivo fijo:** BD-U3-02 — Dependencias Funcionales (id 1452, 6 fragmentos validados)
- **Modelo:** `deepseek-chat` · **semilla Fase C:** `42` (8 mezclas) · **fases:** ABC
- **Comando:** `python scripts/probar_perfiles_vark.py --live --semilla 42`
- **Artefactos:** `data/pruebas_vark/20261003-235748_semilla42/` (ignorado por git; los enlaces solo funcionan en la máquina que corrió la batería)

| Métrica | Valor |
|---|---|
| Perfiles que pasan todos los criterios | 15/30 |
| Cápsulas válidas | 29/30 (26 al primer intento) |
| Reparaciones totales | 3 |
| Citas inventadas (cápsulas válidas) | 0 |
| Latencia LLM (media / p95 / máx) | 4.9 / 10.1 / 11.1 s |
| Tokens entrada / salida (total) | 121,542 / 38,151 (≈ US$ 0.050) |
| Audios válidos | 16/16 |
| Latencia XTTS (media / máx) | 142 / 229 s |

#### Fase A — perfiles puros

| Perfil (A/R/K) | Contrato | Traz. | Texto | Audio | K | Proporción (A · R · K) | Veredicto | LLM s | Tokens in/out | Audio s | Artefactos |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A100-R0-K0 (100/0/0) | ✅ 1 | ✅ | ✅ | ✅ | — | ✅ A 0.75 · R 0.67 · K 0.33 | ✅ | 4.2 | 3101/826 | 226.0 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/A_A100-R0-K0/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/A_A100-R0-K0/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/A_A100-R0-K0/audio.wav) |
| A0-R100-K0 (0/100/0) | ✅ 1 | ✅ | ❌ | — | — | ✅ A 0.00 · R 0.33 · K 0.00 | ❌ | 3.88 | 3099/836 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/A_A0-R100-K0/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/A_A0-R100-K0/capsula.json) |
| A0-R0-K100 (0/0/100) | ✅ 1 | ✅ | ✅ | — | ✅ | ✅ A 0.25 · R 0.67 · K 1.00 | ✅ | 5.28 | 3234/1258 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/A_A0-R0-K100/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/A_A0-R0-K100/capsula.json) |

#### Fase B — mezclas controladas

| Perfil (A/R/K) | Contrato | Traz. | Texto | Audio | K | Proporción (A · R · K) | Veredicto | LLM s | Tokens in/out | Audio s | Artefactos |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A50-R50-K0 (50/50/0) | ✅ 1 | ✅ | ❌ | ✅ | — | ✅ A 0.50 · R 0.67 · K 0.33 | ❌ | 3.94 | 3180/896 | 177.63 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A50-R50-K0/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A50-R50-K0/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/B_A50-R50-K0/audio.wav) |
| A50-R0-K50 (50/0/50) | ✅ 2 | ✅ | ✅ | ✅ | ✅ | ❌ A 0.50 · R 0.67 · K 1.00 | ❌ | 10.11 | 8219/2732 | 121.73 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A50-R0-K50/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A50-R0-K50/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/B_A50-R0-K50/audio.wav) |
| A0-R50-K50 (0/50/50) | ✅ 1 | ✅ | ❌ | — | ✅ | ✅ A 0.00 · R 0.67 · K 1.00 | ❌ | 5.19 | 3311/1297 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A0-R50-K50/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A0-R50-K50/capsula.json) |
| A70-R20-K10 (70/20/10) | ✅ 1 | ✅ | ✅ | ✅ | ✅ | ❌ A 0.50 · R 0.67 · K 0.33 | ❌ | 3.89 | 3101/821 | 172.41 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A70-R20-K10/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A70-R20-K10/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/B_A70-R20-K10/audio.wav) |
| A70-R10-K20 (70/10/20) | ✅ 1 | ✅ | ✅ | ✅ | ✅ | ✅ A 0.50 · R 0.33 · K 0.33 | ✅ | 3.82 | 3101/797 | 151.77 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A70-R10-K20/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A70-R10-K20/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/B_A70-R10-K20/audio.wav) |
| A20-R70-K10 (20/70/10) | ✅ 1 | ✅ | ❌ | — | ✅ | ❌ A 0.25 · R 0.33 · K 0.33 | ❌ | 3.39 | 3099/709 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A20-R70-K10/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A20-R70-K10/capsula.json) |
| A10-R70-K20 (10/70/20) | ✅ 1 | ✅ | ❌ | — | ✅ | ❌ A 0.25 · R 0.33 · K 0.33 | ❌ | 3.43 | 3099/828 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A10-R70-K20/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A10-R70-K20/capsula.json) |
| A20-R10-K70 (20/10/70) | ✅ 1 | ✅ | ✅ | — | ✅ | ✅ A 0.00 · R 0.67 · K 1.00 | ✅ | 5.32 | 3234/1349 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A20-R10-K70/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A20-R10-K70/capsula.json) |
| A10-R20-K70 (10/20/70) | ✅ 2 | ✅ | ✅ | — | ✅ | ✅ A 0.25 · R 0.67 · K 1.00 | ✅ | 10.04 | 8149/2896 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A10-R20-K70/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A10-R20-K70/capsula.json) |
| A60-R30-K10 (60/30/10) | ✅ 1 | ✅ | ✅ | ✅ | ✅ | ✅ A 0.75 · R 0.33 · K 0.33 | ✅ | 3.52 | 3101/791 | 191.17 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A60-R30-K10/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A60-R30-K10/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/B_A60-R30-K10/audio.wav) |
| A60-R10-K30 (60/10/30) | ✅ 1 | ✅ | ✅ | ✅ | ❌ | ✅ A 0.75 · R 0.33 · K 0.33 | ❌ | 3.59 | 3101/766 | 179.43 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A60-R10-K30/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A60-R10-K30/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/B_A60-R10-K30/audio.wav) |
| A30-R60-K10 (30/60/10) | ✅ 1 | ✅ | ❌ | ✅ | ✅ | ❌ A 0.50 · R 0.33 · K 0.33 | ❌ | 3.34 | 3099/768 | 150.25 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A30-R60-K10/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A30-R60-K10/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/B_A30-R60-K10/audio.wav) |
| A10-R60-K30 (10/60/30) | ✅ 1 | ✅ | ❌ | — | ❌ | ❌ A 0.25 · R 0.33 · K 0.33 | ❌ | 3.83 | 3099/831 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A10-R60-K30/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A10-R60-K30/capsula.json) |
| A30-R10-K60 (30/10/60) | ✅ 1 | ✅ | ✅ | ✅ | ✅ | ✅ A 0.25 · R 0.67 · K 1.00 | ✅ | 5.23 | 3234/1225 | 229.01 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A30-R10-K60/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A30-R10-K60/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/B_A30-R10-K60/audio.wav) |
| A10-R30-K60 (10/30/60) | ✅ 1 | ✅ | ✅ | — | ✅ | ✅ A 0.00 · R 0.33 · K 1.00 | ✅ | 4.7 | 3234/1169 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A10-R30-K60/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A10-R30-K60/capsula.json) |
| A34-R33-K33 (34/33/33) | ✅ 1 | ✅ | ✅ | ✅ | ❌ | — A 0.50 · R 0.33 · K 0.33 | ❌ | 3.63 | 3130/788 | 181.87 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A34-R33-K33/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A34-R33-K33/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/B_A34-R33-K33/audio.wav) |
| A90-R5-K5 (90/5/5) | ✅ 1 | ✅ | ✅ | ✅ | ✅ | ✅ A 0.75 · R 0.67 · K 0.33 | ✅ | 4.02 | 3101/924 | 107.43 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A90-R5-K5/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A90-R5-K5/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/B_A90-R5-K5/audio.wav) |
| A5-R90-K5 (5/90/5) | ✅ 1 | ✅ | ❌ | — | ✅ | ❌ A 0.00 · R 0.33 · K 0.67 | ❌ | 4.4 | 3099/903 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A5-R90-K5/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A5-R90-K5/capsula.json) |
| A5-R5-K90 (5/5/90) | ✅ 1 | ✅ | ❌ | — | ✅ | ✅ A 0.25 · R 0.67 · K 1.00 | ❌ | 5.08 | 3234/1303 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/B_A5-R5-K90/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/B_A5-R5-K90/capsula.json) |

#### Fase C — mezclas aleatorias

| Perfil (A/R/K) | Contrato | Traz. | Texto | Audio | K | Proporción (A · R · K) | Veredicto | LLM s | Tokens in/out | Audio s | Artefactos |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C01_A75-R2-K23 (75/2/23) | ✅ 1 | ✅ | ✅ | ✅ | ✅ | ✅ A 0.50 · R 0.33 · K 0.33 | ✅ | 3.44 | 3101/733 | 79.56 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/C_C01_A75-R2-K23/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/C_C01_A75-R2-K23/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/C_C01_A75-R2-K23/audio.wav) |
| C02_A9-R49-K42 (9/49/42) | ✅ 1 | ✅ | ❌ | — | ✅ | ✅ A 0.00 · R 0.33 · K 1.00 | ❌ | 4.75 | 3311/1142 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/C_C02_A9-R49-K42/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/C_C02_A9-R49-K42/capsula.json) |
| C03_A78-R3-K19 (78/3/19) | ✅ 1 | ✅ | ✅ | ✅ | ✅ | ✅ A 0.75 · R 0.33 · K 0.33 | ✅ | 3.52 | 3101/733 | 72.06 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/C_C03_A78-R3-K19/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/C_C03_A78-R3-K19/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/C_C03_A78-R3-K19/audio.wav) |
| C04_A3-R25-K72 (3/25/72) | ✅ 1 | ✅ | ✅ | — | ✅ | ✅ A 0.00 · R 0.67 · K 1.00 | ✅ | 5.59 | 3234/1390 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/C_C04_A3-R25-K72/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/C_C04_A3-R25-K72/capsula.json) |
| C05_A2-R17-K81 (2/17/81) | ❌ | — | — | — | — | — | ❌ | — | 14594/4276 | — | [resultado](../data/pruebas_vark/20261003-235748_semilla42/C_C05_A2-R17-K81/resultado.json) |
| C06_A41-R13-K46 (41/13/46) | ✅ 2 | ✅ | ✅ | ✅ | ✅ | ✅ A 1.00 · R 0.67 · K 1.00 | ✅ | 11.09 | 8428/3145 | 77.64 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/C_C06_A41-R13-K46/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/C_C06_A41-R13-K46/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/C_C06_A41-R13-K46/audio.wav) |
| C07_A50-R0-K50 (50/0/50) | ✅ 1 | ✅ | ✅ | ✅ | ✅ | ✅ A 0.75 · R 0.67 · K 1.00 | ✅ | 5.43 | 3313/1273 | 80.03 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/C_C07_A50-R0-K50/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/C_C07_A50-R0-K50/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/C_C07_A50-R0-K50/audio.wav) |
| C08_A67-R23-K10 (67/23/10) | ✅ 1 | ✅ | ✅ | ✅ | ✅ | ✅ A 0.75 · R 0.33 · K 0.33 | ✅ | 3.52 | 3101/746 | 67.48 | [resultado](../data/pruebas_vark/20261003-235748_semilla42/C_C08_A67-R23-K10/resultado.json) · [cápsula](../data/pruebas_vark/20261003-235748_semilla42/C_C08_A67-R23-K10/capsula.json) · [wav](../data/pruebas_vark/20261003-235748_semilla42/C_C08_A67-R23-K10/audio.wav) |

#### Detalle de fallos y advertencias

- `A_A100-R0-K0` — ⚠️ canal R al 0% con marcadores: encabezados_completos, extension_larga; ⚠️ canal K al 0% con marcadores: ejemplo_resuelto
- `A_A0-R100-K0` — ❌ **texto**: 238 pal. (objetivo 270); cobertura 77%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40)
- `A_A0-R0-K100` — ⚠️ canal A al 0% con marcadores: analogia; ⚠️ canal R al 0% con marcadores: encabezados_completos, extension_larga
- `B_A50-R50-K0` — ❌ **texto**: 276 pal. (objetivo 260); cobertura 77%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40); ⚠️ canal K al 0% con marcadores: ejemplo_resuelto
- `B_A50-R0-K50` — ❌ **proporcion**: A 0.50 · R 0.67 · K 1.00; ⚠️ canal R al 0% con marcadores: encabezados_completos, extension_larga
- `B_A0-R50-K50` — ❌ **texto**: 267 pal. (objetivo 250); cobertura 64%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40)
- `B_A70-R20-K10` — ❌ **proporcion**: A 0.50 · R 0.67 · K 0.33
- `B_A20-R70-K10` — ❌ **texto**: 186 pal. (objetivo 270); cobertura 82%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40); ❌ **proporcion**: A 0.25 · R 0.33 · K 0.33
- `B_A10-R70-K20` — ❌ **texto**: 204 pal. (objetivo 270); cobertura 90%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40); ❌ **proporcion**: A 0.25 · R 0.33 · K 0.33
- `B_A60-R10-K30` — ❌ **ejercicios**: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/2; resolubles 1/1; FALLA: componentes prácticos 1 < 2
- `B_A30-R60-K10` — ❌ **texto**: 207 pal. (objetivo 260); cobertura 79%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40); ❌ **proporcion**: A 0.50 · R 0.33 · K 0.33
- `B_A10-R60-K30` — ❌ **texto**: 210 pal. (objetivo 260); cobertura 79%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40); ❌ **ejercicios**: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/2; resolubles 1/1; FALLA: componentes prácticos 1 < 2; ❌ **proporcion**: A 0.25 · R 0.33 · K 0.33
- `B_A34-R33-K33` — ❌ **ejercicios**: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/2; resolubles 1/1; FALLA: componentes prácticos 1 < 2
- `B_A5-R90-K5` — ❌ **texto**: 212 pal. (objetivo 270); cobertura 84%; glosario+encabezados exigidos; FALLA: cifras ajenas ['20.111.222-3'], falta glosario (p_R≥40); ❌ **proporcion**: A 0.00 · R 0.33 · K 0.67
- `B_A5-R5-K90` — ❌ **texto**: 295 pal. (objetivo 200); cobertura 62%; FALLA: cifras ajenas ['12.345.678-9']
- `C_C02_A9-R49-K42` — ❌ **texto**: 222 pal. (objetivo 250); cobertura 60%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40)
- `C_C04_A3-R25-K72` — ⚠️ cobertura léxica baja (49%): revisar contenido inventado
- `C_C05_A2-R17-K81` — ❌ **contrato**: agotó 3 intentos: ['el contenido tiene 316 palabras y el máximo es 300: sobran 16. Debes recortar al menos 31 palabras en total para asegurar que la suma total quede estrictamente por debajo de 300. La parte más extensa es el concepto central, con 106 palabras — recórtala primero y sintetiza de forma concisa las demás secciones (concepto_central, representacion_adaptativa y ejemplo). No agregues contenido nuevo ni reordenes lo que ya está bien: solo acorta y resume lo que sobra.']
- `C_C07_A50-R0-K50` — ⚠️ canal R al 0% con marcadores: encabezados_completos, extension_larga

#### Detalle por criterio (todas las ejecuciones)

<details>

**`A_A100-R0-K0`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ✅ texto: 250 pal. (objetivo 210); cobertura 67%
- ✅ audio: pcm_s16le 24000 Hz, 59.5s, 137 pal. (2.3 pal/s), 2789 KB; cobertura guion 77%
- — ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/0; resolubles 1/1
- ✅ proporcion: A 0.75 · R 0.67 · K 0.33

**`A_A0-R100-K0`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3239→p.2)
- ❌ texto: 238 pal. (objetivo 270); cobertura 77%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40)
- — audio: p_A<25: sin audio, como corresponde
- — ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 0/0; resolubles 0/0
- ✅ proporcion: A 0.00 · R 0.33 · K 0.00

**`A_A0-R0-K100`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ✅ texto: 262 pal. (objetivo 190); cobertura 61%
- — audio: p_A<25: sin audio, como corresponde
- ✅ ejercicios: flashcards_y_quiz: 3 tarjetas, 3 preguntas; prácticos 3/3; resolubles 1/1
- ✅ proporcion: A 0.25 · R 0.67 · K 1.00

**`B_A50-R50-K0`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ❌ texto: 276 pal. (objetivo 260); cobertura 77%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40)
- ✅ audio: pcm_s16le 24000 Hz, 52.5s, 142 pal. (2.7 pal/s), 2458 KB; cobertura guion 85%
- — ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/0; resolubles 1/1
- ✅ proporcion: A 0.50 · R 0.67 · K 0.33

**`B_A50-R0-K50`**

- ✅ contrato: intento 2 (1 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ✅ texto: 281 pal. (objetivo 200); cobertura 62%
- ✅ audio: pcm_s16le 24000 Hz, 41.5s, 87 pal. (2.1 pal/s), 1947 KB; cobertura guion 95%
- ✅ ejercicios: flashcards_y_quiz: 4 tarjetas, 3 preguntas; prácticos 3/3; resolubles 2/2
- ❌ proporcion: A 0.50 · R 0.67 · K 1.00

**`B_A0-R50-K50`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ❌ texto: 267 pal. (objetivo 250); cobertura 64%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40)
- — audio: p_A<25: sin audio, como corresponde
- ✅ ejercicios: flashcards_y_quiz: 3 tarjetas, 3 preguntas; prácticos 3/3; resolubles 2/2
- ✅ proporcion: A 0.00 · R 0.67 · K 1.00

**`B_A70-R20-K10`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ✅ texto: 250 pal. (objetivo 230); cobertura 70%
- ✅ audio: pcm_s16le 24000 Hz, 51.8s, 127 pal. (2.5 pal/s), 2429 KB; cobertura guion 72%
- ✅ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/1; resolubles 1/1
- ❌ proporcion: A 0.50 · R 0.67 · K 0.33

**`B_A70-R10-K20`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ✅ texto: 220 pal. (objetivo 220); cobertura 76%
- ✅ audio: pcm_s16le 24000 Hz, 45.0s, 103 pal. (2.3 pal/s), 2108 KB; cobertura guion 86%
- ✅ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/1; resolubles 1/1
- ✅ proporcion: A 0.50 · R 0.33 · K 0.33

**`B_A20-R70-K10`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ❌ texto: 186 pal. (objetivo 270); cobertura 82%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40)
- — audio: p_A<25: sin audio, como corresponde
- ✅ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/1; resolubles 1/1
- ❌ proporcion: A 0.25 · R 0.33 · K 0.33

**`B_A10-R70-K20`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 4/6 citados (3234→p.1, 3237→p.1, 3238→p.2, 3239→p.2)
- ❌ texto: 204 pal. (objetivo 270); cobertura 90%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40)
- — audio: p_A<25: sin audio, como corresponde
- ✅ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/1; resolubles 0/0
- ❌ proporcion: A 0.25 · R 0.33 · K 0.33

**`B_A20-R10-K70`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 2/6 citados (3234→p.1, 3236→p.1)
- ✅ texto: 245 pal. (objetivo 210); cobertura 53%
- — audio: p_A<25: sin audio, como corresponde
- ✅ ejercicios: flashcards_y_quiz: 4 tarjetas, 4 preguntas; prácticos 3/3; resolubles 3/3
- ✅ proporcion: A 0.00 · R 0.67 · K 1.00

**`B_A10-R20-K70`**

- ✅ contrato: intento 2 (1 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ✅ texto: 254 pal. (objetivo 220); cobertura 64%
- — audio: p_A<25: sin audio, como corresponde
- ✅ ejercicios: flashcards_y_quiz: 4 tarjetas, 4 preguntas; prácticos 3/3; resolubles 2/2
- ✅ proporcion: A 0.25 · R 0.67 · K 1.00

**`B_A60-R30-K10`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ✅ texto: 236 pal. (objetivo 240); cobertura 79%
- ✅ audio: pcm_s16le 24000 Hz, 48.2s, 126 pal. (2.6 pal/s), 2258 KB; cobertura guion 84%
- ✅ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/1; resolubles 1/1
- ✅ proporcion: A 0.75 · R 0.33 · K 0.33

**`B_A60-R10-K30`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3237→p.1, 3236→p.1)
- ✅ texto: 210 pal. (objetivo 220); cobertura 65%
- ✅ audio: pcm_s16le 24000 Hz, 49.2s, 104 pal. (2.1 pal/s), 2306 KB; cobertura guion 72%
- ❌ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/2; resolubles 1/1; FALLA: componentes prácticos 1 < 2
- ✅ proporcion: A 0.75 · R 0.33 · K 0.33

**`B_A30-R60-K10`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ❌ texto: 207 pal. (objetivo 260); cobertura 79%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40)
- ✅ audio: pcm_s16le 24000 Hz, 39.8s, 89 pal. (2.2 pal/s), 1866 KB; cobertura guion 96%
- ✅ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/1; resolubles 1/1
- ❌ proporcion: A 0.50 · R 0.33 · K 0.33

**`B_A10-R60-K30`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 4/6 citados (3234→p.1, 3235→p.1, 3236→p.1, 3237→p.1)
- ❌ texto: 210 pal. (objetivo 260); cobertura 79%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40)
- — audio: p_A<25: sin audio, como corresponde
- ❌ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/2; resolubles 1/1; FALLA: componentes prácticos 1 < 2
- ❌ proporcion: A 0.25 · R 0.33 · K 0.33

**`B_A30-R10-K60`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ✅ texto: 245 pal. (objetivo 210); cobertura 59%
- ✅ audio: pcm_s16le 24000 Hz, 45.4s, 101 pal. (2.2 pal/s), 2130 KB; cobertura guion 90%
- ✅ ejercicios: flashcards_y_quiz: 4 tarjetas, 3 preguntas; prácticos 3/3; resolubles 1/1
- ✅ proporcion: A 0.25 · R 0.67 · K 1.00

**`B_A10-R30-K60`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 2/6 citados (3234→p.1, 3236→p.1)
- ✅ texto: 234 pal. (objetivo 230); cobertura 56%
- — audio: p_A<25: sin audio, como corresponde
- ✅ ejercicios: flashcards_y_quiz: 4 tarjetas, 3 preguntas; prácticos 3/3; resolubles 2/2
- ✅ proporcion: A 0.00 · R 0.33 · K 1.00

**`B_A34-R33-K33`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ✅ texto: 205 pal. (objetivo 240); cobertura 69%
- ✅ audio: pcm_s16le 24000 Hz, 38.1s, 90 pal. (2.4 pal/s), 1788 KB; cobertura guion 73%
- ❌ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/2; resolubles 1/1; FALLA: componentes prácticos 1 < 2
- — proporcion: A 0.50 · R 0.33 · K 0.33 (sin canal dominante ≥40%)

**`B_A90-R5-K5`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 4/6 citados (3234→p.1, 3237→p.1, 3238→p.2, 3239→p.2)
- ✅ texto: 250 pal. (objetivo 220); cobertura 71%
- ✅ audio: pcm_s16le 24000 Hz, 55.5s, 117 pal. (2.1 pal/s), 2600 KB; cobertura guion 80%
- ✅ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/1; resolubles 1/1
- ✅ proporcion: A 0.75 · R 0.67 · K 0.33

**`B_A5-R90-K5`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 4/6 citados (3234→p.1, 3236→p.1, 3238→p.2, 3239→p.2)
- ❌ texto: 212 pal. (objetivo 270); cobertura 84%; glosario+encabezados exigidos; FALLA: cifras ajenas ['20.111.222-3'], falta glosario (p_R≥40)
- — audio: p_A<25: sin audio, como corresponde
- ✅ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 2/1; resolubles 1/1
- ❌ proporcion: A 0.00 · R 0.33 · K 0.67

**`B_A5-R5-K90`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ❌ texto: 295 pal. (objetivo 200); cobertura 62%; FALLA: cifras ajenas ['12.345.678-9']
- — audio: p_A<25: sin audio, como corresponde
- ✅ ejercicios: flashcards_y_quiz: 3 tarjetas, 3 preguntas; prácticos 3/3; resolubles 1/1
- ✅ proporcion: A 0.25 · R 0.67 · K 1.00

**`C_C01_A75-R2-K23`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ✅ texto: 199 pal. (objetivo 210); cobertura 76%
- ✅ audio: pcm_s16le 24000 Hz, 41.6s, 94 pal. (2.3 pal/s), 1948 KB; cobertura guion 83%
- ✅ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/1; resolubles 1/1
- ✅ proporcion: A 0.50 · R 0.33 · K 0.33

**`C_C02_A9-R49-K42`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 2/6 citados (3234→p.1, 3236→p.1)
- ❌ texto: 222 pal. (objetivo 250); cobertura 60%; glosario+encabezados exigidos; FALLA: falta glosario (p_R≥40)
- — audio: p_A<25: sin audio, como corresponde
- ✅ ejercicios: flashcards_y_quiz: 3 tarjetas, 3 preguntas; prácticos 3/3; resolubles 2/2
- ✅ proporcion: A 0.00 · R 0.33 · K 1.00

**`C_C03_A78-R3-K19`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ✅ texto: 180 pal. (objetivo 210); cobertura 70%
- ✅ audio: pcm_s16le 24000 Hz, 38.0s, 77 pal. (2.0 pal/s), 1782 KB; cobertura guion 70%
- ✅ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/1; resolubles 1/1
- ✅ proporcion: A 0.75 · R 0.33 · K 0.33

**`C_C04_A3-R25-K72`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 2/6 citados (3234→p.1, 3236→p.1)
- ✅ texto: 283 pal. (objetivo 220); cobertura 49%
- — audio: p_A<25: sin audio, como corresponde
- ✅ ejercicios: flashcards_y_quiz: 4 tarjetas, 4 preguntas; prácticos 3/3; resolubles 3/3
- ✅ proporcion: A 0.00 · R 0.67 · K 1.00

**`C_C05_A2-R17-K81`**

- ❌ contrato: agotó 3 intentos: ['el contenido tiene 316 palabras y el máximo es 300: sobran 16. Debes recortar al menos 31 palabras en total para asegurar que la suma total quede estrictamente por debajo de 300. La parte más extensa es el concepto central, con 106 palabras — recórtala primero y sintetiza de forma concisa las demás secciones (concepto_central, representacion_adaptativa y ejemplo). No agregues contenido nuevo ni reordenes lo que ya está bien: solo acorta y resume lo que sobra.']

**`C_C06_A41-R13-K46`**

- ✅ contrato: intento 2 (1 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ✅ texto: 272 pal. (objetivo 220); cobertura 56%
- ✅ audio: pcm_s16le 24000 Hz, 37.1s, 91 pal. (2.5 pal/s), 1740 KB; cobertura guion 84%
- ✅ ejercicios: flashcards_y_quiz: 4 tarjetas, 4 preguntas; prácticos 3/3; resolubles 3/3
- ✅ proporcion: A 1.00 · R 0.67 · K 1.00

**`C_C07_A50-R0-K50`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 3/6 citados (3234→p.1, 3236→p.1, 3237→p.1)
- ✅ texto: 283 pal. (objetivo 200); cobertura 65%
- ✅ audio: pcm_s16le 24000 Hz, 38.9s, 86 pal. (2.2 pal/s), 1821 KB; cobertura guion 67%
- ✅ ejercicios: flashcards_y_quiz: 3 tarjetas, 3 preguntas; prácticos 3/3; resolubles 1/1
- ✅ proporcion: A 0.75 · R 0.67 · K 1.00

**`C_C08_A67-R23-K10`**

- ✅ contrato: intento 1 (0 reparaciones)
- ✅ trazabilidad: 4/6 citados (3234→p.1, 3237→p.1, 3236→p.1, 3239→p.2)
- ✅ texto: 184 pal. (objetivo 230); cobertura 82%
- ✅ audio: pcm_s16le 24000 Hz, 34.0s, 71 pal. (2.1 pal/s), 1594 KB; cobertura guion 86%
- ✅ ejercicios: quiz_mc: 0 tarjetas, 0 preguntas; prácticos 1/1; resolubles 0/0
- ✅ proporcion: A 0.75 · R 0.33 · K 0.33

</details>

<!-- fin:resultados-generados -->

## Resumen de fallos y patrones

Corrida completa del 03-oct-2026 (`20261003-235748_semilla42`, 30 perfiles, con audio).
**15/30 perfiles pasan todos los criterios.** Lo que funciona y lo que no, por canal:

| Canal | Veredicto | Evidencia |
|---|---|---|
| **Motor común** | ✅ Sólido | 29/30 cápsulas válidas (26 al primer intento, 96,7 % ≥ el 95 % del criterio de la Fase 3), **0 citas inventadas** en 29 cápsulas, todas las fuentes con página, todo en español. Latencia LLM media 4,9 s. Costo total ≈ US$ 0,05. |
| **A — audio** | ✅ Funciona | 16/16 WAV válidos (PCM 24 kHz, decodificables completos, 2,0–2,7 palabras/s: ninguno truncado). La analogía aparece en 13/13 perfiles con A ≥ 40 %. **Pero** XTTS en CPU tarda 67–229 s por audio (media 142 s), y la directiva «preguntas reflexivas» se cumple en 2/13. |
| **K — ejercicios** | ✅ Funciona con p_K ≥ 40 % | 12/12 cápsulas válidas con K ≥ 40 % traen `flashcards_y_quiz`, `lista_pasos` y `ejemplo_resuelto`, con respuestas respaldadas por los fragmentos. **Falla con 25 ≤ p_K < 40 %:** 3/3 perfiles (K = 30, 30, 33) reciben «2 componentes prácticos» y entregan 1. |
| **R — texto** | ❌ No se diferencia | **El glosario no aparece en ninguna** de las 9 cápsulas con R ≥ 40 % (0/10 sumando el smoke), y las cápsulas R quedan **57 palabras bajo el objetivo** en promedio (dominante ≥ 60 %). Un R puro recibe dos párrafos con encabezado: lo mismo que cualquier otro perfil sin sus bloques propios. |

### Patrones

1. **La extensión va al revés de lo que diseña el motor.** `palabras_texto` pide más
   palabras para R (C_texto alto) y menos para K. El modelo hace lo contrario: con canal
   dominante ≥ 60 %, **R queda en −57 palabras** del objetivo, **A en −1** y **K en +48**.
   Las 4 cápsulas que necesitaron reparación o la agotaron son todas de K ≥ 40 % y todas por
   pasar de 300 palabras: `flashcards_y_quiz` + `lista_pasos` + `ejemplo_resuelto` (+ la
   analogía que el modelo agrega por su cuenta) no caben en el rango.
2. **Lo que el prompt pide como número, sin bloque concreto, se ignora.** «Componentes
   prácticos: 2» sin una directiva que nombre el bloque no produce un segundo componente
   (3/3). Es exactamente el riesgo del plan §5: el modelo obedece instrucciones
   estructurales, no cifras.
3. **El material del objetivo empuja hacia ciertos bloques.** Los fragmentos de `BD-U3-02`
   vienen rotulados por perfil («Explicación Narrativa: La Analogía del RUT (Perfil Auditivo
   - A)», «Ejercicio Guiado Resuelto»), y el modelo los reproduce: `ejemplo_resuelto`
   aparece en 28/29 cápsulas y la analogía del RUT en 8 cápsulas con A < 40 % (incluido K
   puro). La adaptación se ve, pero parte del parecido entre perfiles viene del material.
4. **El modelo inventa datos de ejemplo.** Dos cápsulas usan RUT ficticios (`20.111.222-3`,
   `12.345.678-9`) que no están en el material. Es inocuo pedagógicamente, pero contradice
   la regla 3 del prompt de sistema («no agregas datos, cifras…»), y el validador no lo
   detecta.

### Cómo leer los fallos de proporcionalidad (7)

- **5 son reales:** los perfiles con R dominante (A20-R70-K10, A10-R70-K20, A30-R60-K10,
  A10-R60-K30, A5-R90-K5) fallan porque falta el glosario, el único marcador de R que
  distingue algo. Es el mismo defecto del hallazgo H1, visto desde otro criterio.
- **2 son artefactos de la heurística** (A50-R0-K50 y A70-R20-K10): A pierde contra R por
  los marcadores «encabezados completos» y «extensión ≥ 240», que en esta corrida **no
  discriminan**: el primero aparece en 29/29 cápsulas y el segundo en todas las que tienen
  R = 0 %. Se dejan como están para no recalibrar a la medida del resultado; para la
  próxima corrida conviene reemplazar esos dos marcadores (p. ej. por «definiciones
  explícitas» o densidad de terminología del material).
- **Corrección aplicada a la heurística:** en la primera evaluación, C06 (A41/K46) fallaba
  porque el script exigía que K le ganara a A, aunque ambos superan el 40 % y reciben sus
  directivas completas. Era un defecto del script, no del motor: ahora todos los canales
  ≥ 40 % son codominantes. La corrida se reevaluó con `--informe` (sin llamar al LLM), y
  C06 pasó de ❌ a ✅.

## Correcciones

### Etapa 1 — H1 + H3: glosario de R y reparto de la extensión

**Criterios fijados el 04-oct-2026, antes de re-ejecutar** (no se modifican después de ver
resultados).

Cambio evaluado: la directiva del glosario apunta al último bloque de
`representacion_adaptativa` y se acota a 3–5 entradas; el prompt reparte el objetivo de
palabras por paso (activación ≤ 20, concepto ≈ 30 %, ejemplo ≈ 20 %, el resto para la
representación); `ejemplo_resuelto` se fija en el `ejemplo` (paso 5) y `lista_pasos` en
3–5 pasos de una oración. El objetivo de palabras de cada perfil no cambia.

**Conjuntos:**

- **S42 (comparación directa):** los 30 perfiles con semilla 42, sin audio, con el prompt
  nuevo, contra la corrida `20261003-235748_semilla42`. C1–C3 se miden sobre los **26
  perfiles con R > 0**; C4, sobre los 30.
- **S43 (validación):** las 8 mezclas de la Fase C con semilla 43, que no se usaron para
  diseñar el reparto, corridas sin audio **con el prompt anterior** (línea base, antes de
  aplicar el cambio) y con el nuevo. Se reportan por separado de S42.

| # | Criterio | Base S42 | Éxito si |
|---|---|---|---|
| C1 | Bloque `glosario` en las cápsulas válidas con R ≥ 40 % | 0/9 | todas |
| C2 | Contenido dentro de ±15 % del objetivo de palabras del prompt (cápsulas válidas) | 13/25 | ≥ 80 % |
| C2b | Desvío medio de R dominante (R ≥ 60 %) respecto del objetivo | −21 % | dentro de ±15 % |
| C2c | Desvío medio de K dominante (K ≥ 60 %) respecto del objetivo | +21 % | dentro de ±15 % |
| C3 | No regresión: cápsulas válidas / reparaciones (llamadas − perfiles) / citas inventadas | 25 / 4 / 0 | ≥ 25 / ≤ 4 / 0 |
| C4a | Cápsulas válidas con K ≥ 40 % que pasan el criterio «ejercicios» de la batería (`flashcards_y_quiz` con 3–5 tarjetas y 3–5 preguntas explicadas, `lista_pasos`, `ejemplo_resuelto`, ≥ 80 % de respuestas respaldadas) | 12/12 | todas |
| C4b | Guion de audio válido (sin sintetizar) en las cápsulas válidas con A ≥ 25 %: `activacion` + `concepto_central` no vacío, no JSON, ≥ 40 palabras y cobertura léxica ≥ 50 % | 16/16 (mín. 71 palabras, cobertura mín. 67 %) | todas |
| C4c | Bloque `analogia` en las cápsulas válidas con A ≥ 40 % | 13/13 | todas |

En S43, C2b y C2c se informan solo si hay al menos dos perfiles dominantes ≥ 60 % de ese
canal, y C3 se compara contra la línea base de S43.

Si falla C1, C3 o C4, se detiene la etapa y se reporta, sin iterar. Si fallan solo C2b o
C2c, se reporta sin tocar las fracciones. Cada perfil corre una sola vez y el modelo usa
temperatura 0,4, así que una diferencia de ±1 en un conteo puede ser ruido.

#### Intento 1 (04-oct): reparto con «unas N palabras» — detenido

Falló C3 en las dos semillas (válidas 25 → 23 y 8 → 6; reparaciones 4 → 20 y 2 → 8), y C4a
en S43. El primer intento de las cápsulas con R ≥ 40 % casi se duplicó (225 → 422 palabras
en S42): el modelo leyó «unas 80» como aproximación, agregó `lista_pasos` donde nadie lo
pidió, y la mención «(también el glosario, si se pide)» del reparto indujo **5 glosarios
sin directiva** en perfiles A. Además, el diff había borrado la frase «Sé conciso…».

#### Intento 2 (04-oct): brazos A y B con regla de cierre fijada antes de ejecutar

- **Brazo A:** solo la instrucción nueva del glosario, sin reparto por paso.
- **Brazo B:** el reparto como tope («como máximo N palabras»), la frase de concisión
  restaurada, «incluye únicamente los bloques que piden las instrucciones estructurales»,
  y un `parrafo` de reexpresión que el código antepone solo cuando ninguna directiva del
  perfil pide un bloque que reexprese el concepto (los perfiles «solo R»).
- **Regla de cierre:** aplicar B si cumple C1, C3 y C4; si no, A; si ninguno, revertir y
  analizar. C2 no es bloqueante.

Mismos conjuntos (S42 y S43, sin audio) y mismo comparador para la base y los dos brazos.

| Criterio | S42 base | S42 A | S42 B | S43 base | S43 A | S43 B |
|---|---|---|---|---|---|---|
| C1 glosario en R ≥ 40 % válidas | 0/9 | 7/7 | **9/9** | 0/5 | 5/5 | **5/5** |
| ↳ perfiles R ≥ 40 % sin cápsula válida | 0/9 | 2/9 | 0/9 | 0/5 | 0/5 | 0/5 |
| C2 ±15 % *(no bloqueante)* | 13/25 | 20/24 | 9/24 | 5/8 | 6/8 | 6/8 |
| C2b desvío R ≥ 60 % | −21 % (n=6) | +4 % (n=6) | +2 % (n=6) | −16 % (n=1) | +5 % (n=1) | +6 % (n=1) |
| C2c desvío K ≥ 60 % | +21 % (n=6) | +18 % (n=7) | −21 % (n=6) | +6 % (n=1) | +17 % (n=1) | −8 % (n=1) |
| C3 válidas (R > 0) | 25/26 | 24/26 ❌ | **24/26 ❌** | 8/8 | 8/8 | 8/8 |
| C3 reparaciones (n = perfiles R > 0) | 4 (n=26) | 10 ❌ | **5 ❌** | 2 (n=8) | 3 ❌ | 1 |
| C3 citas inventadas | 0 (n=25) | 0 (n=24) | 0 (n=24) | 0 (n=8) | 0 (n=8) | 0 (n=8) |
| C4a ejercicios K ≥ 40 % | 12/12 | 9/11 ❌ | 12/12 | 4/4 | 3/4 ❌ | 4/4 |
| C4b guion de audio A ≥ 25 % | 16/16 | 16/16 | 15/15 | 3/3 | 3/3 | 3/3 |
| C4c analogía A ≥ 40 % | 13/13 | 13/13 | 12/12 | 1/1 | 1/1 | 1/1 |
| ↳ glosarios sin directiva | 0/29 | 0/28 | 0/28 | 0/8 | 0/8 | 0/8 |

**Repeticiones de A19-R34-K47** (la falla de C4a del intento 1): A 5/5 y B 5/5 con
`flashcards_y_quiz` válido al primer intento; base 1/1. La falla del intento 1 fue ruido.

**Composición de `representacion_adaptativa` en los 9 perfiles «solo R»** (n = 1 cápsula
por perfil y brazo; informativa):

| Perfil | Base | A | B |
|---|---|---|---|
| A0-R100-K0 | parrafo | parrafo+lista_pasos+glosario | parrafo+glosario |
| A20-R70-K10 | analogia | parrafo+glosario | parrafo+glosario |
| A10-R70-K20 | analogia | parrafo+lista_pasos+glosario | parrafo+glosario |
| A30-R60-K10 | analogia | parrafo+glosario | parrafo+glosario |
| A10-R60-K30 | analogia | parrafo+lista_pasos+glosario | parrafo+glosario |
| A5-R90-K5 | lista_pasos | parrafo+glosario | parrafo+glosario |
| S43 A3-R86-K11 | analogia | parrafo+glosario | parrafo+glosario |
| S43 A29-R51-K20 | analogia | parrafo+glosario | parrafo+glosario |
| S43 A22-R48-K30 | analogia | parrafo+analogia+glosario | parrafo+glosario |

En B, los 9 traen `parrafo` + `glosario`: ninguno quedó reducido solo al glosario.

#### Decisión: ningún brazo cumple la regla de cierre → no se aplica nada

B falla C3 en S42 por **una cápsula y una reparación** (24 contra 25 válidas, 5 contra 4
reparaciones). A falla C3 y C4a en las dos semillas. Por la regla fijada antes de ejecutar,
se revierte todo: `src/` y `tests/` quedan como en `main` y **H1 y H3 siguen abiertos**.

#### Por qué falló (análisis para elegir el siguiente enfoque)

1. **El arreglo del glosario funciona.** En los dos brazos y las dos semillas aparece en
   todas las cápsulas válidas con R ≥ 40 %, y ya no se induce en perfiles que no lo piden.
   Lo que bloquea la etapa no es H1.
2. **C3 en S42 lo decide H2, no el prompt.** Las dos cápsulas que B perdió (A75-R2-K23 y
   A2-R17-K81) tuvieron un primer intento **bajo** el mínimo (129 y 142 palabras) y los
   tres intentos fueron **byte a byte idénticos**: el bucle de reparación nunca llegó a
   corregir una desviación de 8–21 palabras. La única cápsula perdida de la línea base
   (A2-R17-K81) también murió por repetición idéntica (intentos 2 y 3). Mientras el bucle
   no pueda salir de una respuesta repetida, cualquier cambio de extensión convierte una
   desviación chica en una cápsula perdida, y C3 no puede distinguir efecto de ruido con
   una corrida por perfil.
3. **El tope por paso invirtió el sesgo de K.** K pasó de +21 % a −21 % sobre su
   objetivo y C2 empeoró (13/25 → 9/24): con topes que suman el objetivo y sin un mínimo
   por paso, los perfiles de objetivo bajo (≈ 210) quedan cerca del piso de 150. Es la
   misma pérdida que describe el punto 2, vista desde la extensión.
4. **Sin el reparto (brazo A), R vuelve a pasarse:** sus dos cápsulas perdidas agotaron
   los intentos convergiendo desde arriba (372 → 305 → 304 y 431 → 348 → 337), y K sigue
   con +18 %.

**Enfoque propuesto, para decidir:** hacer primero la **Etapa 4 (H2)** —que el bucle
detecte una respuesta idéntica y cambie de estrategia— y recién después volver a medir H1
(brazo A) y H3 con estos mismos criterios y conjuntos. Hoy H2 es el mecanismo que
convierte una desviación de extensión en una cápsula perdida. Opcionalmente, repetir la
línea base de S42 para estimar cuánto varía C3 entre corridas idénticas antes de comparar.

Artefactos: `data/pruebas_vark/20261004-0128*` a `20261004-0136*`. Los brazos
(`brazo_A.patch`, `brazo_B_c1.patch`, `brazo_B.patch`) y el comparador
(`comparar_etapa1.py`) quedaron fuera del repo; se pueden versionar si se retoma la etapa.

### Etapa 4 — H2: el bucle de reparación que repite la respuesta

**Diagnóstico (04-oct-2026).** En las corridas guardadas hubo 58 pares de intentos
consecutivos. Tras un error «bajo mínimo» la respuesta salió **idéntica** en 4 de 6 pares
(67 %); tras «sobre máximo», en 1 de 52 (2 %). El mensaje «bajo mínimo» era vago («el
contenido tiene 129 palabras y el mínimo es 150: hay que desarrollarlo más»: sin cuánto
falta, ni dónde, ni hasta dónde), mientras que el de sobra ya estaba cuantificado. Al
reenviar dos veces la misma conversación (temperatura 0,4, sin semilla) se obtuvieron
dos respuestas idénticas entre sí: con la misma entrada el modelo es en la práctica
determinista, así que reintentar con el mismo mensaje no sirve.

**Cambio evaluado.**
- **A:** el mensaje «bajo mínimo» queda cuantificado igual que el de sobra: cuántas
  palabras faltan, cuántas agregar (con el mismo margen), el techo de 300 y los campos
  donde desarrollar.
- **B:** si una respuesta es idéntica a la anterior, el intento siguiente no repite la
  conversación: arranca desde el prompt original con un aviso concreto y los errores
  cuantificados. El máximo sigue en 3 intentos y la temperatura no se toca.

**Criterios fijados antes de ejecutar** (no se modifican después de ver resultados):

| # | Criterio | Cómo se mide |
|---|---|---|
| D1 (a) | 0 pares consecutivos idénticos en los que la segunda respuesta se pidió con la **misma conversación** | Test unitario con LLM falso (garantía, no medición) |
| D1 (b) | Pares consecutivos idénticos devueltos por la API | Informativo, contra 5/58 de las corridas anteriores |
| D2 | S42: promedio de válidas ≥ 29,5 y de reparaciones ≤ 4. S43: 8 válidas y promedio de reparaciones ≤ 1. Ninguno de los perfiles válidos en **ambas** líneas base (29 en S42, 8 en S43) queda inválido en ninguna corrida del cambio. 0 citas inventadas en todas las corridas | Dos corridas del cambio, sin audio, comparadas promedio contra promedio con las dos líneas base |
| D3 | De los perfiles que necesitaron reparación, cuántos convergen, separando los que activaron la detección de repetición de los que no | Informativo; se espera n pequeño |

**Líneas base** (código de `main`, sin audio, con todos los perfiles):

| Corrida | Válidas | Reparaciones | Citas inventadas | Pares idénticos |
|---|---|---|---|---|
| S42 base 1 (`20261003-235748`) | 29/30 | 5 | 0 | 1/5 |
| S42 base 2 (`20261004-015507`) | 30/30 | 3 | 0 | 0/3 |
| S43 base 1 (`20261004-010726`) | 8/8 | 2 | 0 | 0/2 |
| S43 base 2 (`20261004-015733`) | 8/8 | 0 | 0 | 0/0 |

**Ruido medido entre las dos líneas base: ±1 cápsula válida y ±2 reparaciones.** Por eso
D2 compara promedios de dos corridas y no corridas sueltas. Regla de cierre: si D1 y D2 se
cumplen, el cambio queda aplicado sin commit; si no, se revierte y se analiza, sin iterar.

#### Resultado (04-oct-2026): D1 y D2 se cumplen → el cambio queda aplicado

| Corrida | Válidas | Reparaciones | Citas inventadas | Pares idénticos | Perfiles estables perdidos |
|---|---|---|---|---|---|
| S42 cambio 1 (`20261004-020427`) | 30/30 | 1 | 0 | 0/1 | ninguno |
| S42 cambio 2 (`20261004-020729`) | 30/30 | 2 | 0 | 0/2 | ninguno |
| S43 cambio 1 (`20261004-020647`) | 8/8 | 1 | 0 | 0/1 | ninguno |
| S43 cambio 2 (`20261004-020948`) | 8/8 | 1 | 0 | 0/1 | ninguno |

| Criterio | Exigido | Medido | Estado |
|---|---|---|---|
| D1 (a) | 0 en el test | 4 tests nuevos en verde (incluye el tope de 3 intentos) | ✅ |
| D1 (b) *(informativo)* | — | 0/5 pares idénticos (antes: 5/58 histórico; 1/8 en las líneas base) | — |
| D2 S42 | válidas ≥ 29,5 y reparaciones ≤ 4 (promedios) | 30 y 1,5 | ✅ |
| D2 S43 | 8 válidas y reparaciones ≤ 1 (promedio) | 8 y 1 | ✅ |
| D2 estables | ningún perfil válido en ambas bases queda inválido | ninguno, en las 4 corridas | ✅ |
| D2 citas | 0 | 0 | ✅ |
| D3 *(informativo)* | — | sin repetición: 5/5 convergen; con repetición: n = 0 | — |

**Límite de esta medición:** las 5 reparaciones de las corridas del cambio fueron por
**exceso** de palabras. Con el prompt de `main`, el caso «bajo mínimo» —el que disparaba
las repeticiones— no apareció, así que ni el mensaje nuevo ni la detección se ejercitaron
en las corridas (D3 con n = 0, como se esperaba). D2 demuestra que el cambio no empeora
nada. Su efecto se mide por separado:

**Reproducción de los dos casos que H2 hizo perder en la Etapa 1** (brazo B, semilla 42):
primer intento = la respuesta guardada, inyectada tal cual; el resto lo respondió DeepSeek
con el bucle nuevo.

| Caso | Antes | Con el cambio |
|---|---|---|
| A75-R2-K23 | 129 → 129 → 129 (3 idénticos), cápsula perdida | 129 → **168**, válida en el intento 2 |
| A2-R17-K81 | 142 → 142 → 142 (3 idénticos), cápsula perdida | 142 → **177**, válida en el intento 2 |

En los dos casos el mensaje cuantificado («faltan 21; agrega al menos 36… sin pasar de
300; desarrolla `concepto_central` y `representacion_adaptativa`») bastó, sin que hiciera
falta la detección de repetición (n = 2). La detección queda como red de seguridad,
cubierta por los tests.

**Para la próxima ronda (H1 + H3):** todas las comparaciones se expresan como promedio de al
menos 2 corridas por brazo, con el criterio declarado antes de ejecutar.

### Etapa 2 — H5: síntesis multimedia síncrona e inútil en `POST /api/capsulas`

**Verificación (04-oct-2026, rama `fix/h5-audio`).**

- Después de persistir una cápsula **nueva**, `crear_capsula` llamaba a
  `GeneradorMultimedia.generar_activos(config, json.dumps(capsula), id)`.
  - Con `recursos_visuales > 0` generaba una imagen (`data/media/{id}_visual.png`).
  - Con `audio_activo` sintetizaba con XTTS los primeros 250 caracteres del JSON
    (`data/media/{id}_audio.wav`).
- Nada sirve esos archivos:
  - la app solo monta `/static` y `/public`;
  - ninguna plantilla, endpoint ni columna de la BD lee `media_dir`.
- El visor sintetiza **otro** audio por su cuenta, con `hx-trigger="load"` hacia
  `POST /student/viewer/{id}/generate-audio`. Su guion es `activacion + concepto_central`
  leído de la BD, y lo guarda en `src/studify/public/audio/capsula_{id}.wav`.
- Como `GET /student/viewer/{id_objetivo}` llama directamente a `crear_capsula`, la página
  del estudiante esperaba esa síntesis antes de mostrarse.
- Las cápsulas que salen del caché o del caché compartido retornan antes y nunca pasaron
  por ese bloque.

**Costo medido de la síntesis inútil** (XTTS-v2 en CPU, i5-14600KF; guion de la ruta API
de dos cápsulas de la batería):

| Cápsula | Guion | Síntesis | Audio resultante |
|---|---|---|---|
| A100 | 250 caracteres de JSON | 129,4 s | 21,5 s |
| R100 | 250 caracteres de JSON | 99,5 s | 21,0 s |

Lo narrado eran claves del JSON y una frase cortada: `{"titulo": "…", "objetivo_aprendizaje":
"…", "activacion": "¿Alguna vez has notado que si conoces el RUT de una persona,`.

**Corrección.**

- Se quita de `crear_capsula` el bloque completo de la Fase 6 (audio e imagen), decisión
  del equipo.
- No se modifican `media/audio.py`, `media/image.py` ni `media/generator.py`, ni el visor:
  la API solo deja de llamarlos. La generación de imágenes se retomará cuando se decida su
  API.
- Quedan sin uso desde la aplicación:
  - `GeneradorMultimedia` y `generar_activos` (`media/generator.py`);
  - `generar_imagen` (solo la llama `generator.py`);
  - el ajuste `media_dir` (`config.py`).
- No se eliminan.

**Antes / después.** En una cápsula nueva con p_A ≥ 25 % desaparecen **~100–130 s de
bloqueo** antes de ver la página. La síntesis de imagen con p_V > 0 tampoco se ejecuta ya,
pero no se midió, porque V está fuera de las pruebas. La espera del audio del visor
(67–229 s) no cambia: el texto ya se puede leer mientras se sintetiza.

**Tests** (`tests/test_api_capsulas.py`):

- **Dobles de multimedia.** Los módulos se reemplazan por dobles en `sys.modules`, que
  anotan la llamada y fallan. Se usan anotaciones porque el bloque antiguo se tragaba las
  excepciones.
- **Lo que cubren:**
  - con A ≥ 25 %, con V > 0 y con A + V juntos no se llama a nada;
  - la respuesta conserva exactamente los 17 campos de `CapsulaOut`;
  - el visor de un perfil A ≥ 25 % sigue pidiendo su audio.
- **Contra el código anterior**, los 4 tests nuevos fallan (anotan `GeneradorMultimedia`);
  con el cambio, pasan.

**Fuera de alcance.** `scripts/probar_perfiles_vark.py` sigue registrando
`guion_ruta_api`, que describe la ruta ya eliminada; sirve de evidencia histórica.

#### Medición para la espera del visor (sin cambios de código, script en el scratchpad)

Se usó un guion real del visor de 530 caracteres (`B_A60-R10-K30`, 179 s en la batería),
que produce ~45 s de audio. Las corridas fueron en un mismo proceso y en CPU.

| Paso | Tiempo |
|---|---|
| `import torch` + `TTS` (una vez por proceso) | 7,3 s |
| Carga del modelo XTTS (dos veces) | 19,0 s y 16,2 s (RSS: 4,6–4,7 GB) |
| Síntesis con el modelo ya cargado (dos veces) | 194,5 s y 151,4 s (RTF 4,0 y 3,2) |
| Ruta del servidor completa (`generar_audio`: carga + síntesis) | 89,8 s (síntesis 81,0 s, RTF 1,6) |

- **La carga pesa 16–19 s; la síntesis, 81–195 s.** La variación de la síntesis entre
  corridas del mismo texto es mayor que toda la carga.
- **Con RTF ≥ 1,6, XTTS en esta CPU genera audio más lento de lo que se reproduce.** Por
  eso ni un streaming por frases evitaría las pausas.
- **DirectML (AMD Radeon RX 9060 XT, `torch-directml` 0.2.5) es incompatible tal como
  está:**
  - el modelo carga en 9,3 s;
  - la síntesis falla con `Cannot set version_counter for inference tensor`;
  - reemplazando `torch.inference_mode` por `no_grad`, el proceso aborta con `Invalid or
    unsupported data type ComplexFloat`, porque la STFT de XTTS usa tensores complejos.
- **Caché por guion:** entre los estudiantes con `audio_activo` de la BD (sin los de
  test), 26 estudiantes caen en 24 huellas distintas. El caché compartido evitaría ~2 de
  26 síntesis por objetivo.

### Motor de voz del visor: experimento y decisión (04-oct-2026)

#### Experimento (d): motores livianos frente a XTTS

**Criterio fijado antes de medir** (sin cambios después). Un motor es candidato si
cumple tres condiciones:

- sintetiza en ≤ 0,3 × la duración del audio;
- su licencia permite uso académico;
- su calidad la aprueba el autor escuchando.

**Cómo se midió.**

- **Entorno:** un venv aparte, sin tocar el del proyecto, en CPU (i5-14600KF, sin GPU).
- **Guiones:** tres guiones reales del visor sacados de la batería (383, 530 y 752
  caracteres); los tres contienen «X → Y».
- **Repeticiones:** dos cargas y dos síntesis por guion.
- **Voces:**
  - Piper: las 5 voces en español de calidad media o alta del `voices.json` oficial
    (hay 9 en total; las 4 de calidad baja quedaron fuera);
  - Kokoro: las voces `ef_dora`, `em_alex` y `em_santa` de su `VOICES.md`.

| Motor y voz | Carga | Razón síntesis/audio (6 corridas) | ¿≤ 0,3? | RAM con modelo / pico |
|---|---|---|---|---|
| XTTS-v2 (referencia, medición de H5) | 16–19 s | 1,6 – 4,0 | ❌ | 4,7 GB |
| Piper `es_MX-claude-high` | 1,0 s | 0,05 – 0,10 | ✅ 6/6 | 142 / 755 MB |
| Piper `es_MX-ald-medium` | 1,4–1,7 s | 0,09 – 0,12 | ✅ 6/6 | 134 / 565 MB |
| Piper `es_ES-sharvard-medium` | 1,4 s | 0,105 – 0,113 | ✅ 6/6 | 149 / 554 MB |
| Piper `es_ES-davefx-medium` | 1,5–1,8 s | 0,11 – 0,16 | ✅ 6/6 | 134 / 541 MB |
| Piper `es_AR-daniela-high` | 1,7–3,5 s | 0,14 – 0,66 | ❌ 1/6 | 193 / 490 MB |
| Kokoro `ef_dora` / `em_alex` / `em_santa` | 0,8 s | 0,53 – 0,66 | ❌ 0/6 | 397 / 1.310 MB |

espeak-ng, que usan Piper y Kokoro, lee «Se escribe X → Y» como «se escribe équis i»: la
flecha se pierde y la «Y» suena como conjunción. De ahí sale la normalización del guion
(ver más abajo).

#### Decisión del autor

- **Motor por defecto: Kokoro**, con `ef_dora` (femenina) y `em_alex` (masculina) a
  elección del estudiante.
  - **Kokoro no cumplió el criterio ≤ 0,3 fijado antes de medir** (razón 0,53–0,66).
  - Elegirlo es una **decisión de producto del autor**, no una relajación del criterio:
    el criterio sigue igual, y Kokoro queda registrado como no candidato.
- **Opción «rápida»: Piper con `es_ES-sharvard-medium`**, hablante 0 (masculina) y
  hablante 1 (femenina). Es un solo modelo y una sola licencia de datos; el autor eligió
  esta voz el 05-oct después de escuchar los dos hablantes. `claude-high` queda descartada.
- **Acento de Kokoro: `es-419`** (seseo) por defecto (`TTS_KOKORO_IDIOMA`), y no la `es`
  que documenta Kokoro, porque los estudiantes del piloto son chilenos. Decisión del autor
  tras escuchar ambas variantes.
- **XTTS** sale de la interfaz del estudiante.
  - Queda como opción administrativa explícita (`TTS_MOTOR=xtts`), sin respaldo
    automático.
  - Necesita el extra `audio-xtts`.

**Medición posterior con el código del repo** (`generar_audio` con Kokoro y el guion
normalizado; proceso nuevo, así que la primera llamada incluye la carga):

| Voz | 383 car. | 530 car. | 752 car. |
|---|---|---|---|
| `ef_dora` | 10,1 s / 24,3 s de audio (0,41) | 9,5 s / 34,3 s (0,28) | 14,0 s / 49,5 s (0,28) |
| `em_alex` | 6,8 s / 24,2 s (0,28) | 9,4 s / 34,4 s (0,27) | 13,3 s / 49,5 s (0,27) |

**Discrepancia no explicada.** Con el mismo motor y las mismas voces, estas razones
(0,27–0,41) salen más bajas que las del experimento (0,53–0,66). Lo único distinto es el
venv, y en los dos estaba onnxruntime 1.30. **Esta medición no reemplaza a la del
criterio**: Kokoro sigue figurando como no candidato. En la Etapa 3 se vuelve a medir con
al menos 5 corridas por voz y guion, y se reporta la mediana.

Piper (`sharvard`) con el código del repo, mismas 3 cápsulas:

| Hablante | 383 car. | 530 car. | 752 car. |
|---|---|---|---|
| 1 (femenina) | 4,3 s / 25,9 s (0,17, incluye la carga) | 0,9 s / 34,9 s (0,03) | 1,3 s / 49,1 s (0,03) |
| 0 (masculina) | 0,8 s / 26,4 s (0,03) | 2,3 s / 35,1 s (0,07) | 3,2 s / 50,7 s (0,06) |

#### Voces: género y hablantes (verificado en la fuente)

| Voz | Fuente | Género | Hablantes |
|---|---|---|---|
| Kokoro `ef_dora` | `VOICES.md` de hexgrad/Kokoro-82M (Spanish: 1F 2M) | 🚺 femenina | 1 |
| Kokoro `em_alex` | mismo archivo | 🚹 masculina | 1 |
| Piper `es_ES-sharvard-medium` | MODEL_CARD («Speakers: 2») y `.onnx.json` (`speaker_id_map = {"M": 0, "F": 1}`) | uno de cada | 2 |
| Piper `es_MX-claude-high` | MODEL_CARD («Speakers: 1») y `.onnx.json` (`num_speakers 1`) | **no consta** | 1 |

- **sharvard trae 2 hablantes.** Como el `.onnx.json` no define `default_speaker_id`,
  Piper 1.8 usaría el hablante 0 («M») por defecto. El código **fija el `speaker_id`
  explícito**, 1 para femenina y 0 para masculina (`tts_hablante_rapida_*`), y un test lo
  verifica.
- **claude-high (descartada):** que sea femenina **consta solo por la escucha del autor**.
  Ni su MODEL_CARD, ni su `.onnx.json`, ni el Space de origen (`HirCoir/Piper-TTS-Spanish`)
  lo indican.

#### Licencias (riesgo abierto, sin LICENSE en el repo)

| Componente | Licencia | Condición |
|---|---|---|
| Pesos de Kokoro-82M | Apache-2.0 | Uso libre, con aviso de licencia |
| `kokoro-onnx` | MIT | Uso libre, con aviso de licencia |
| `piper-tts` 1.8 (`OHF-Voice/piper1-gpl`) | **GPL-3.0-or-later** | Ver el riesgo debajo |
| `phonemizer` 3.4 | **GPL-3.0** | Ídem |
| `espeak-ng` (vía `espeakng-loader` y `piper-tts`) | **GPL-3.0** | Ídem |
| Voz `es_ES-sharvard-medium`: sus datos | CC BY 3.0 (corpus Sharvard) | **Exige atribución** |
| Voz `es_ES-sharvard-medium`: su punto de partida | Ajustada desde la voz `en_US-lessac-medium`, entrenada con los datos Lessac de Blizzard 2013 | **Licencia de Lessac: solo para investigación, sin uso comercial** (ver debajo) |
| Voz `es_MX-claude-high` (descartada) | Declara Apache-2.0 | Sus datos apuntan a un Space de Hugging Face: procedencia menos clara que la del resto |
| Repositorio `rhasspy/piper-voices` | MIT | — |
| Modelo XTTS-v2 | **CPML** | Solo uso no comercial, también de sus audios. Coqui cerró, así que no hay licencia comercial disponible |
| Biblioteca Coqui `TTS` 0.22 | MPL-2.0 | — |

**Riesgo abierto.** Studify no declara licencia (no hay LICENSE ni campo `license` en
`pyproject.toml`). Si el código se publica importando `piper-tts`, `phonemizer` o
`espeak-ng`, que son GPL-3.0, hay dos alternativas: publicarlo con una licencia compatible
con GPL-3.0, o usar esos componentes como **programa externo por subproceso** (agregación
y no obra derivada). Conviene confirmarlo con la universidad; esto no es asesoría legal.

- **Agravante:** los Términos vigentes (`terminos.html`, «El software y sus componentes»)
  declaran que el código de RepasAi «no tiene una licencia de código abierto» y no se puede
  reutilizar sin autorización. Una obra que importa bibliotecas GPL-3.0 y se distribuye
  con esa restricción es justo el caso que la GPL no admite. La decisión de licencia del
  repo y el texto de los Términos tienen que resolverse juntos.
- **XTTS-v2:** queda limitado a usos no comerciales (CPML).
- **sharvard (encontrado al preparar los créditos):**
  - su MODEL_CARD dice «Finetuned from U.S. English lessac voice»;
  - la voz lessac se entrenó con los datos de Lessac Technologies del Blizzard Challenge
    2013, cuya licencia los autoriza «exclusively for Research Purposes» y excluye
    expresamente cualquier uso comercial, incluido el de productos o servicios de síntesis
    de voz;
  - no está claro si esa restricción se hereda en una voz ajustada desde ese punto de
    partida. Un proyecto de título es uso de investigación, pero el riesgo queda abierto,
    igual que el de XTTS, para cualquier uso fuera de lo académico;
  - Kokoro no declara ese origen.

**Créditos de atribución** (propuesto, sin implementar).

- **Qué:** una sección «Créditos» en la página de Términos con el autor, la licencia y el
  enlace de cada voz y motor:
  - sharvard: CC BY 3.0. Corpus *Sharvard_IJA* de Vincent Aubanel, María Luisa García
    Lecumberri y Martin Cooke (LISTA Consortium, 2014), publicado en Edinburgh DataShare
    (`hdl.handle.net/10283/574`). Voz de Piper ajustada desde `en_US-lessac-medium`;
  - Kokoro: Apache-2.0;
  - espeak-ng: GPL-3.0.
- **Dónde enlazarla:**
  - desde el pie de página, junto a Términos y Privacidad;
  - desde el reproductor (`_audio.html`), con una línea «Voz: … · créditos».
- **Por qué ahí:** la atribución de CC BY tiene que ser razonablemente visible donde se usa
  la obra, y el reproductor es ese lugar.
- **Antes de implementarla:** Términos y Privacidad todavía nombran a XTTS-v2. Cambiarlos
  implica una nueva versión de los documentos legales, que los estudiantes vuelven a
  aceptar (`web/legal.py`), así que queda pendiente de decisión.

#### Propuesta de actualización legal (sin aplicar)

Va en **una sola versión nueva** de Términos y Privacidad, cuando el autor lo decida.

**Decisión del equipo (05-oct-2026).** Se siguen usando las bibliotecas actuales (Kokoro,
Piper, phonemizer, espeak-ng, pymupdf…). Se mencionarán en un apartado de los Términos,
por tratarse de un prototipo académico de investigación sin cobro. El código del proyecto
será **público y abierto**, con una licencia que todavía está por elegirse.

**El diff completo está listo y probado, pero no aplicado.** Con él puesto, la suite solo
falla en los 4 casos conocidos y las dos páginas se renderizan. Cambia:

| Lugar | Cambio |
|---|---|
| `terminos.html` §1 | Declaración de **prototipo académico de investigación**: no se cobra, no hay publicidad y no se venden ni licencian el servicio ni los datos. Si eso cambiara, se avisaría en una versión nueva que habría que aceptar |
| `terminos.html` §8, «El software» | Reemplaza «No tiene una licencia de código abierto… no reutilizarlo» por: «El código fuente… está disponible públicamente en su repositorio… bajo la licencia [PENDIENTE: la elegirán sus autores]. Esa licencia cubre solo el código… no los modelos de voz, el material de estudio ni las cápsulas… Cada componente de terceros mantiene su propia licencia.» |
| `terminos.html` §8, apartado nuevo «Componentes de terceros y licencias» | Tabla con lo que usa el servicio: Kokoro-82M y kokoro-onnx (Apache-2.0 y MIT), Piper (GPL-3.0 o posterior), voz sharvard (datos CC BY 3.0), eSpeak NG y phonemizer (GPL-3.0), ONNX Runtime (MIT), PyMuPDF (AGPL-3.0), python-pptx (MIT), Psycopg (LGPL-3.0), la base web (MIT/BSD-3-Clause), **HTMX 1.9.10 (BSD-2-Clause**; los Términos actuales dicen por error «BSD de cero cláusulas», que es la licencia de HTMX 2), Lucide (ISC, con íconos de Feather bajo MIT) y las tipografías (OFL-1.1). Cada componente lleva enlace a su fuente. XTTS-v2 (CPML, solo no comercial) aparece como **opción administrativa** |
| `terminos.html` §8, «Créditos de la voz» | Atribución CC BY 3.0 de sharvard: corpus *Sharvard_IJA*, de V. Aubanel, M. L. García Lecumberri y M. Cooke (LISTA Consortium, 2014), `hdl.handle.net/10283/574`. Aclara que la voz se ajustó desde lessac, con datos **solo para investigación**. Incluye el crédito de Kokoro |
| `privacidad.html` §2, tabla de datos | Fila nueva: **preferencia de voz** (`voz_genero`, `voz_modo`). Es un dato personal nuevo y opcional: una preferencia de audio **independiente del género con que te identificas, que nunca se deduce de él** |
| `privacidad.html` §5 | La narración pasa de XTTS-v2 (y la referencia de Linda Johnson) a Kokoro y Piper, en el servidor propio |
| `privacidad.html` §9 | Derecho a cambiar la preferencia de voz desde el visor o el perfil |
| `web/legal.py` | Términos y Política suben de **0.1 a 0.2**, con fecha de publicación |
| `tests/test_web_legal.py` | El test de nueva versión deja de fijar `"0.1"`: captura la versión vigente |
| `docs/PLAN_DESARROLLO.md:244`, `docs/IMPLEMENTACION_IA_LOCAL.md:31` | Notas internas: Piper es GPL-3.0, y Kokoro y Piper reemplazan a XTTS |

**Cómo funciona hoy la re-aceptación** (`web/consentimiento.py`):

1. **Al subir la versión,** `pendientes()` compara las aceptaciones guardadas con las
   versiones vigentes, y el documento queda pendiente para todos.
2. **Al entrar a cualquier vista de `/student/*`,** `exigir_vigente` manda a
   `/aceptar?next=…`. Con HTMX responde 409, para no pegar la pantalla dentro de un
   fragmento.
3. **En `/aceptar`** se piden solo los documentos que cambiaron.
4. **Al aceptar,** se inserta una fila nueva por documento y versión. Las anteriores no se
   tocan: el historial queda.
5. **El consentimiento de género** (`documento = 'genero'`) se guarda contra la versión de
   la Política vigente al darlo, y `pendientes()` no lo vuelve a pedir.

**Advertencia:** es un borrador técnico, no asesoría legal. Las plantillas lo dicen en un
comentario HTML `<!-- BORRADOR TÉCNICO … No constituye asesoría legal -->`, junto al
`<!-- BORRADOR: requiere revisión legal… -->` que ya tenían.

**Licencia del repositorio:** pendiente de decisión. La comparación GPL-3.0 / AGPL-3.0
frente a las dependencias obligatorias, los textos oficiales listos para `LICENSE`, el
campo `license` de `pyproject.toml`, la sección de licencia del README y la revisión de
archivos versionados con derechos de terceros se entregaron aparte, sin aplicar.

#### Etapa 1 (backend): cerrada el 05-oct-2026

- **Hecho:**
  - ajustes `tts_*` en `config.py`;
  - `scripts/descargar_voces.py`: SHA-256 fijo, escritura atómica y commit fijo de
    `piper-voices`, verificado contra el MD5 de su `voices.json`;
  - `generar_audio` con Kokoro, Piper y XTTS administrativo detrás de la misma firma. El
    cuerpo de XTTS se movió sin cambios (verificado con diff).
  - `PreferenciaVoz(genero, modo)` y `resolver_voz`;
  - la normalización del guion (`media/guion.py`);
  - los extras `audio` (versiones exactas), `audio-xtts` y `media`;
  - el texto genérico en el reproductor;
  - `tests/test_audio.py`.
- **Normalización sobre la batería:** en los 269 guiones (activación + concepto central),
  ningún símbolo sobrevive (→, =, ⊆, `$`, `\`, `_`, `[ ]`, `+`). Antes había 870 «→».

#### Licencias del árbol de dependencias (05-oct-2026)

Leídas del metadato instalado (`License-Expression`, `License` o clasificador) y, si
faltaba, de la API de licencias de GitHub o del COPYING incluido en el paquete.

| Paquete | Licencia | Lo trae | ¿Obligatorio para Kokoro (motor por defecto)? |
|---|---|---|---|
| kokoro-onnx 0.6.1 | MIT (repo; sin metadato) | extra `audio` | Sí |
| espeakng-loader 0.2.4 | MIT (repo), pero **incluye `espeak-ng.dll`, que es GPL-3.0** | kokoro-onnx | Sí |
| phonemizer 3.4.0 | **GPL-3.0 o posterior** | kokoro-onnx | Sí |
| onnxruntime 1.30.0 | MIT | kokoro-onnx, piper-tts | Sí |
| numpy, flatbuffers, protobuf, packaging, joblib, attrs, dlinfo, typing-extensions | BSD, Apache-2.0, MIT o PSF (permisivas) | onnxruntime, phonemizer | Sí |
| piper-tts 1.8.0 | **GPL-3.0 o posterior** (incluye `espeakbridge.pyd`) | extra `audio` | No (modo rápido) |
| pathvalidate 3.3.1 | MIT | piper-tts | No |
| Unidecode 1.4.0 | **GPL-2.0 o posterior** | TTS (`audio-xtts`) | No |
| num2words 0.5.14 / soxr 1.1.0 | LGPL / LGPL-2.1 o posterior | TTS, gruut, librosa (`audio-xtts`) | No |
| psycopg / psycopg-binary 3.3.4 | LGPL-3.0-only | base de la app | — |
| **pymupdf 1.28.2** | **AGPL-3.0, o licencia comercial de Artifex** | extra `ingest` | — |

**Conclusión:** el motor por defecto no se libra de la GPL. Necesita `phonemizer` y
espeak-ng, este último dentro de `espeakng-loader`.

**Riesgo abierto: pymupdf es AGPL-3.0.**

- **Qué exige:** a diferencia de la GPL, la AGPL (§13) obliga también cuando el programa
  se usa **a través de la red**. Si RepasAi se ofrece como servicio web con pymupdf
  dentro, hay que ofrecer el código fuente completo a sus usuarios, bajo AGPL.
- **Dónde se usa:** solo en la ingesta (`knowledge/extract.py::extraer_pdf`), que es una
  tarea del docente y no del estudiante. Pero corre dentro de la misma aplicación
  (`/teacher`).
- **Qué hace con él:** lee bloques, líneas y spans de cada página con
  `get_text("dict")`, con el **tamaño de fuente de cada span** para detectar títulos y el
  número de página. Los tests además **escriben** PDFs con él (`new_page` e `insert_text`
  con `fontsize`).

**Alternativas permisivas** (licencias según PyPI; cobertura según su documentación,
**sin probar**):

| Paquete | Licencia | ¿Cubre la lectura? |
|---|---|---|
| `pdfminer.six` 20260107 | MIT | La más cercana: `LTTextBox` → `LTTextLine` → `LTChar`, con el tamaño de fuente de cada carácter y la página. Equivale a los bloques, líneas y spans de hoy |
| `pdfplumber` 0.11.10 | MIT (sobre pdfminer.six, MIT, y pypdfium2, BSD-3/Apache-2.0) | Sí: `extract_words(extra_attrs=["size"])` y caracteres con tamaño; agrupa líneas, no bloques |
| `pypdf` 6.19.0 | BSD-3-Clause | En parte: `extract_text(visitor_text=…)` entrega el tamaño de fuente, pero sin estructura de bloques; habría que agruparlos a mano |
| `reportlab` 5.0.1 (para generar PDFs en los tests) | BSD | Sí. `fpdf2` es LGPL-3.0 |

No se cambió nada.

#### Etapa 2 (preferencia de voz e interfaz): cerrada el 05-oct-2026

- **Base de datos:**
  - antes de migrar se respaldó la base **local**: contenedor `studify-db`,
    `localhost:5432`, volumen `studify_studify_pgdata`, con `pg_dump -Fc` (11 tablas con
    datos, 147 estudiantes);
  - la migración `c3a91f5e7d20` agrega `estudiante.voz_genero` y `voz_modo`, nullable y
    con CHECK. Se probó upgrade → downgrade → upgrade sobre esa base, y `alembic check`
    solo reporta el falso positivo conocido de `ix_fragmento_contenido_fts`;
  - un test repite el viaje de ida y vuelta en una **base temporal** del mismo servidor,
    que crea y borra.
- **La preferencia nunca sale de `estudiante.genero`:**
  - `preferencia_guardada(voz_genero, voz_modo)` recibe solo esos dos campos;
  - NULL → Dora;
  - un test cruza el género sociodemográfico con la voz y comprueba que no se mezclan.
- **Interfaz:**
  - selector con cuatro opciones (Dora, Alex, voz femenina rápida, voz masculina
    rápida), en el visor (sobre el reproductor) y en el perfil (si hay audio activo);
  - se habla de la voz, nunca del género de quien escucha;
  - las demoras son las medidas: «Natural, tarda unos segundos» (Kokoro, 7–14 s) y «Casi
    inmediata» (Piper, 1–4 s);
  - se guarda con un botón, para no sintetizar una voz por cada opción que se recorre
    con las flechas.
- **Endpoint `POST /student/preferencias/voz`:** el estudiante sale solo de la cookie.
- **Visor:** narra con la voz del **dueño** de la cápsula, también cuando la pide el
  docente.
- **Nombre del WAV:** lleva la voz (`capsula_{id}__{motor}-{voz}[-{hablante}].wav`), así
  que cambiar de voz no reusa el audio de la anterior.
- **«Mis datos»** exporta los dos campos.
- **`.gitignore`:** ignora `src/studify/public/audio/*.wav`. Los WAV ya versionados
  siguen en git hasta H10. `capsula_1904.wav` **entró al repo en el commit `4b04550`**
  junto con la documentación; se resuelve con H10 en la Etapa 3.
- **Lecturas por materia (para la Etapa 3):** los 4 `codigo_objetivo` existentes (en la
  BD y en `data/objetivos.csv`) siguen el formato `PREFIJO-Ux-NN` (`BD`, `PROG`). La API
  no lo exige (`codigo_objetivo: str`, máximo 30), así que el archivo común de respaldo es
  necesario.

#### Etapa 3, Parte A (caché del audio y H10): 05-oct-2026

**Caché por huella.**

- **Qué cambia:** el WAV del visor se llama `{huella}.wav`, donde
  `huella = sha256(versión del esquema, motor, voz, hablante, acento de Kokoro, guion
  normalizado)[:32]` (`media/audio.py::huella_de_audio`). Ya no lleva el `id_capsula`.
- **Qué se gana:**
  - las copias del caché compartido de cápsulas tienen el mismo texto, así que
    **reutilizan el mismo archivo**;
  - una base recreada con ids repetidos no puede servir el audio de otra cápsula;
  - si cambian las reglas de `media/guion.py`, cambia la huella y el audio se vuelve a
    sintetizar solo;
  - dos textos que se narran igual («X → Y» y «X -> Y») comparten archivo.
- **Tests:** 11 nuevos. Cubren la huella (estable, sobre el texto normalizado, por voz,
  hablante y acento), que un audio existente no se vuelve a sintetizar, que la copia del
  caché compartido reutiliza el WAV y que el nombre no depende del id. Los tests de
  endpoint escriben en un directorio temporal.

**WAV del esquema antiguo.** En disco hay solo cuatro:

| Archivo | Situación |
|---|---|
| `src/studify/public/audio/capsula_620.wav` (2,3 MB) | Versionado. Narración XTTS; la cápsula 620 existe |
| `src/studify/public/audio/capsula_1451.wav` (0,1 MB) | Versionado. Narración XTTS; la cápsula 1451 no existe en la BD |
| `src/studify/public/audio/capsula_1904.wav` (1,8 MB) | Versionado en `4b04550` |
| `data/media/622_audio.wav` (0,7 MB) | No versionado. Huérfano de H5, nunca servido |

- Con el esquema nuevo **ninguno se vuelve a servir**.
- No hay archivos del esquema intermedio de la Etapa 2 (`capsula_{id}__{voz}.wav`).
- Desversionarlos, y después borrarlos, queda en manos del autor.

**Medición final de los motores.**

- **Método:** 5 corridas por voz y guion, con la mediana. Mismos guiones de 383, 530 y
  752 caracteres. Un proceso por voz, así que la 1.ª llamada incluye cargar el modelo.
- **Repo:** `generar_audio`, guion normalizado, Kokoro `es-419`.
- **Experimento:** el método original, en el venv aparte, con Kokoro directo y texto
  crudo.

| Voz | 383 car. | 530 car. | 752 car. | Mediana global |
|---|---|---|---|---|
| Repo Kokoro `ef_dora` (1.er proceso de la serie) | 0,575 | 0,676 | 0,660 | **0,660** (rango 0,47–0,75) |
| Repo Kokoro `em_alex` | 0,192 | 0,188 | 0,187 | **0,188** |
| Repo Piper sharvard, hablante 1 (femenina) | 0,026 | 0,026 | 0,026 | **0,026** (0,7–1,3 s) |
| Repo Piper sharvard, hablante 0 (masculina) | 0,026 | 0,026 | 0,027 | **0,026** |
| Experimento `ef_dora` `es` / `es-419` | 0,194 / 0,193 | 0,186 / 0,186 | 0,191 / 0,191 | 0,191 / 0,190 |
| Experimento `em_alex` `es` / `es-419` | 0,195 / 0,192 | 0,188 / 0,187 | 0,192 / 0,191 | 0,192 / 0,190 |

Repetición de control: 4 procesos nuevos de `ef_dora` en el repo (guion de 530, 3 corridas
cada uno) dieron **0,186–0,189**, salvo la 1.ª llamada de cada proceso, que da 0,23–0,25
porque incluye la carga.

**Sobre la discrepancia de Kokoro (0,53–0,66 en el experimento frente a 0,27–0,41 en la
Etapa 1).**

- **Lo descartado:** el venv, la voz, el acento (`es` o `es-419`) y la normalización.
  Medido ahora, el método del experimento da 0,19 con las dos voces y los dos acentos, y
  el repo también da 0,19.
- **Lo observado:** los episodios lentos (0,5–0,75) afectan a un proceso entero, en todas
  sus llamadas, y no se repiten al relanzar.
- **Hipótesis, sin confirmar:**
  - el estado de la máquina en ese momento: durante la serie lenta había otra actividad,
    un `uvicorn --reload` de otro proyecto consumiendo ~45 % de un núcleo y el
    `uvicorn --reload` de Studify recargándose con las ediciones;
  - el reparto de hilos de ONNX Runtime entre los núcleos P y E del i5-14600KF.
- **Queda marcada como no explicada.** La razón típica de Kokoro en esta máquina es
  **~0,19**, con episodios ocasionales de ~0,6.
- **El criterio no cambia:** Kokoro sigue registrado como no candidato según la medición
  fijada de antemano, y su elección sigue siendo una decisión de producto. Que hoy mida
  0,19 no corrige ese veredicto.

## Limitaciones conocidas

### Canal Visual (excluido de esta batería)

No se ejecutó por decisión del equipo. Su comportamiento actual, leído del código
(sin ejecutarlo):

- Con p_V < 25 % no se intenta generar ninguna imagen: V solo cambia el peso
  `C_visual` que se muestra en el prompt y, si es el canal primario, el orden de los
  fragmentos.
- Con p_V ≥ 25 %, `recursos_visuales ≥ 1`: el prompt pide bloques `tabla` o `esquema`
  (el «visual» que sí funciona, porque es texto estructurado), y después de persistir la
  cápsula `POST /api/capsulas` llamaba a `GeneradorMultimedia`, que ejecuta **SDXL Base 1.0
  en local sobre DirectML** ([`media/image.py`](../src/studify/media/image.py)), de forma
  síncrona dentro del request. No hay ninguna API de imágenes de por medio. **Desde la
  corrección de H5 (04-oct) la API ya no lo llama;** lo que sigue describe el código de
  `media/`, que se conserva sin cambios.
- Si faltan dependencias o falla la carga del modelo, devuelve `None` y se sigue. Si
  falla **la inferencia**, la excepción sube hasta el `except` de
  [`capsules.py`](../src/studify/api/routers/capsules.py): la cápsula de texto se entrega
  igual, pero **el audio de ese perfil se omite**, porque la imagen se genera antes.
- La imagen se guarda en `data/media/`, que ninguna plantilla muestra.
- `docs/decicionesIAlocal.md` describe FLUX.2 Klein sobre CUDA y la imagen «en stand-by y
  desacoplada de la UI»; el código del repo sigue siendo SDXL sobre DirectML y sigue
  conectado al endpoint.

### Hallazgos reportados sin corregir

La batería no toca lógica de negocio: cada corrección se hace aparte, por etapas (ver «Correcciones»). Estado al 04-oct-2026: H2, H5 y H9 corregidos; H1 y H3 abiertos, a re-medir ahora que H2 está corregido; H10 registrado sin corregir; el resto, sin tocar. Ordenados por impacto. En H5, «el visor lo llama» se refiere a cada cápsula **nueva**: las que salen del caché no pasaban por `GeneradorMultimedia`.

| # | Hallazgo | Evidencia | Propuesta (pendiente de aprobación) |
|---|---|---|---|
| H1 | 🟡 **Abierto; arreglo validado pero no aplicado (Etapa 1).** **El perfil R nunca recibe glosario.** La directiva dice «Cierra *el contenido* con un bloque `glosario`», y `contenido` es el campo del contrato anterior a los siete pasos (19-ago), que ya no existe. | 0/10 cápsulas con R ≥ 40 %. **Experimento** (scratchpad, sin tocar el repo): reescribiendo la instrucción como «El último bloque de `representacion_adaptativa` debe ser un bloque `glosario`…», **4/4** cápsulas lo traen (3 R puro + A20-R70-K10). **Etapa 1:** con el texto nuevo, el glosario aparece en todas las cápsulas válidas con R ≥ 40 % (S42 y S43, brazos A y B), pero la etapa no cumplió C3 (ver «Correcciones»). | Cambiar ese texto en `rag/prompts/maestro.py::INSTRUCCION_POR_DIRECTIVA["glosario"]` y revisar el resto de las instrucciones que digan «contenido». **Efecto colateral medido:** las cápsulas R suben a 255–299 palabras y 2/4 necesitaron una reparación por pasar de 300, así que conviene acompañarlo con un objetivo de palabras R algo menor (`MARGEN_PALABRAS_OBJETIVO`). |
| H2 | ✅ **Corregido (Etapa 4, 04-oct).** **El bucle de reparación vuelve a repetir la respuesta byte a byte.** | C05 (A2-R17-K81): los intentos 2 y 3 son idénticos (mismo MD5, 4.930 caracteres), así que el tercer intento se desperdició y la cápsula se perdió. Es el problema que la sección 5 sedecies de AVANCE daba por corregido con el mensaje de reparación. **Etapa 1:** las 2 cápsulas que perdió el brazo B repitieron los 3 intentos idénticos, con desviaciones de solo 8–21 palabras. | En `generation/generator.py`, detectar que `crudo` es igual al anterior y, en ese caso, reintentar con otra estrategia: subir la temperatura en esa llamada o reinyectar solo el error con la cápsula anterior resumida. |
| H3 | 🟡 **Abierto (Etapa 1 sin aplicar).** **Las cápsulas K se pasan de largo y las R se quedan cortas** (patrón 1). | K +48, R −57 palabras respecto del objetivo. 4/4 reparaciones y el único contrato agotado son de K ≥ 40 % por pasar de 300 palabras. | Decisión de diseño del equipo: o bajar el objetivo de palabras de K cuando se pide `lista_pasos` + `ejemplo_resuelto`, o pedir explícitamente brevedad en esos bloques. **Etapa 1:** el reparto por paso como tope llevó R a +2 %, pero invirtió K a −21 % y acercó al piso de 150 a los perfiles de objetivo bajo. Retomar después de H2. |
| H4 | **Con 25 ≤ p_K < 40 % se ignora la cantidad de componentes prácticos** (patrón 2). | 3/3 perfiles. | Que `componentes_practicos = 2` vaya acompañado de una directiva concreta (p. ej. `paso_a_paso`) en `vark/rules.py`. Toca la lectura de la tabla 11.1 aprobada el 06-ago, así que la decide el equipo. |
| H5 | ✅ **Corregido (Etapa 2, 04-oct).** `crear_capsula` ya no llama a `GeneradorMultimedia`: se eliminan ~100–130 s de bloqueo (medidos) en cápsulas nuevas con p_A ≥ 25 % (ver «Correcciones»). **Audio en el camino de la API: narra JSON, se pierde y bloquea.** `POST /api/capsulas` (y el visor, que lo llama) ejecuta `GeneradorMultimedia` **síncrono** con `json.dumps(capsula)[:250]` como guion, guarda el WAV en `data/media/` (nada lo sirve), y después el visor sintetiza **otro** audio con el guion correcto. | 29/29 cápsulas: el guion de la ruta API empieza con `{"titulo": …`. XTTS en CPU tardó 67–229 s por audio en esta batería. Por lectura de código, un estudiante con p_A ≥ 25 % espera esa síntesis inútil antes de ver su cápsula. | Quitar la síntesis de audio de `crear_capsula` (el visor ya la hace bajo demanda con el guion correcto). Corrige a la vez el guion JSON, el archivo huérfano, la doble síntesis y la espera. |
| H6 | **El modelo inventa cifras de ejemplo** (patrón 4). | 2/29 cápsulas con RUT ficticios. | Advertencia (no rechazo) en `generation/validator.py` para cifras que no están en los fragmentos, o permitir explícitamente los datos de ejemplo en el prompt. |
| H7 | **«Preguntas reflexivas» casi nunca se cumple.** | 2/13 cápsulas con A ≥ 40 % intercalan una pregunta en la prosa. | Reformular la instrucción para que nombre dónde va (p. ej. dentro de `concepto_central`). |
| H8 | **`pytest` completo carga SDXL y XTTS.** `tests/test_visual.py` y `tests/test_voz.py` ejecutan la generación **al importarse**. | Lectura de código. | Moverlos a `scripts/` o protegerlos con `if __name__ == "__main__"`. |
| H9 | ✅ **Corregido (04-oct).** **`gruut` (dependencia de Coqui TTS) instala un paquete `tests` en site-packages** que le hacía sombra a `tests/` del repo: 12 archivos que hacen `from tests.conftest import …` no se podían ni importar. | `import tests` resolvía a `.venv/Lib/site-packages/tests/__init__.py` (instalado el 31-ago). Con `pytest`: 12 errores de colección. | `tests/__init__.py` convierte la carpeta en paquete regular y pytest antepone la raíz del repo a `sys.path`; los 4 tests que hacían `from material import` pasan a `from tests.material import`. Verificado: 432 pasan y 4 fallan (los mismos 4 previos), sin shim. |
| H11 | **`tests/test_api_diagnosticos.py` se cuelga indefinidamente sin Postgres.** Su propio `_hay_base_de_datos()` (línea 34, llamado desde la fixture `limpiar_lo_que_cree_el_test`) abre la conexión sin tiempo límite, así que la suite completa nunca termina si la BD no está arriba. | 05-oct-2026, con Docker apagado: `faulthandler` mostró el proceso detenido en `psycopg.waiting.wait_conn` dentro de esa fixture, más de 60 s, incluso con `DATABASE_URL` apuntando a un puerto cerrado. `tests/conftest.py::hay_base_de_datos` tiene el mismo patrón. | Sin aplicar: pasar `connect_args={"connect_timeout": 3}` al probar la conexión (o reutilizar `conftest.hay_base_de_datos` con ese límite), para que los tests de BD se omitan en vez de colgarse. |
| H10 | 🟡 **(2) corregido en la Etapa 3, Parte A (05-oct): el caché se indexa por la huella del guion normalizado + voz + motor; (1) pendiente de `git rm --cached` por el autor.** **Caché de audio del visor frágil.** (1) Dos WAV generados en desarrollo están versionados en git. (2) El caché del visor se indexa por `id_capsula`, no por el contenido. | (1) `git ls-files` lista `src/studify/public/audio/capsula_620.wav` (48,6 s) y `capsula_1451.wav` (2,5 s), agregados en `1dc5286`; `public/audio/` no está en `.gitignore`. La cápsula 620 existe en la BD; **la 1451 no** (el id máximo es 1599 y quedan 5 cápsulas). (2) `generate_capsule_audio` sintetiza solo si no existe `capsula_{id}.wav` ([`student.py`](../src/studify/web/routers/student.py)). Si se recrea la BD y los ids se repiten, una cápsula nueva reproduciría el audio de otra. Además, cada copia del caché compartido recibe un id nuevo y **vuelve a sintetizar el mismo texto**. | Sin aplicar: (a) agregar `src/studify/public/audio/` a `.gitignore` y sacar los dos WAV del índice con `git rm --cached` (quedan en el historial; no se reescribe); (b) nombrar el archivo por un hash del guion y de la voz de referencia (p. ej. `sha256(guion + referencia)[:16].wav`) en vez de por `id_capsula`. Así una BD recreada no puede servir un audio ajeno, y las copias del caché compartido reutilizan el WAV. |

**Aviso de XTTS, sin consecuencias en esta corrida:** 10/16 audios registraron «The text
length exceeds the character limit of 239 for language 'es'». Ninguno quedó truncado (las
velocidades de habla están todas entre 2,0 y 2,7 palabras/s), porque `tts_to_file` parte
el texto en oraciones. Conviene vigilarlo si los conceptos centrales se alargan.
