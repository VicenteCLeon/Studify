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

## Limitaciones conocidas

### Canal Visual (excluido de esta batería)

No se ejecutó por decisión del equipo. Su comportamiento actual, leído del código
(sin ejecutarlo):

- Con p_V < 25 % no se intenta generar ninguna imagen: V solo cambia el peso
  `C_visual` que se muestra en el prompt y, si es el canal primario, el orden de los
  fragmentos.
- Con p_V ≥ 25 %, `recursos_visuales ≥ 1`: el prompt pide bloques `tabla` o `esquema`
  (el «visual» que sí funciona, porque es texto estructurado), y después de persistir la
  cápsula `POST /api/capsulas` llama a `GeneradorMultimedia`, que ejecuta **SDXL Base 1.0
  en local sobre DirectML** ([`media/image.py`](../src/studify/media/image.py)), de forma
  síncrona dentro del request. No hay ninguna API de imágenes de por medio.
- Si faltan dependencias o falla la carga del modelo, devuelve `None` y se sigue. Si
  falla **la inferencia**, la excepción sube hasta el `except` de
  [`capsules.py`](../src/studify/api/routers/capsules.py): la cápsula de texto se entrega
  igual, pero **el audio de ese perfil se omite**, porque la imagen se genera antes.
- La imagen se guarda en `data/media/`, que ninguna plantilla muestra.
- `docs/decicionesIAlocal.md` describe FLUX.2 Klein sobre CUDA y la imagen «en stand-by y
  desacoplada de la UI»; el código del repo sigue siendo SDXL sobre DirectML y sigue
  conectado al endpoint.

### Hallazgos reportados sin corregir

La batería no toca lógica de negocio: cada corrección se hace aparte, por etapas (ver «Correcciones»). Estado al 04-oct-2026: H9 corregido; H1 y H3 abiertos tras la Etapa 1; el resto, sin tocar. Ordenados por impacto. En H5, «el visor lo llama» se refiere a cada cápsula **nueva**: las que salen del caché no pasan por `GeneradorMultimedia`.

| # | Hallazgo | Evidencia | Propuesta (pendiente de aprobación) |
|---|---|---|---|
| H1 | 🟡 **Abierto; arreglo validado pero no aplicado (Etapa 1).** **El perfil R nunca recibe glosario.** La directiva dice «Cierra *el contenido* con un bloque `glosario`», y `contenido` es el campo del contrato anterior a los siete pasos (19-ago), que ya no existe. | 0/10 cápsulas con R ≥ 40 %. **Experimento** (scratchpad, sin tocar el repo): reescribiendo la instrucción como «El último bloque de `representacion_adaptativa` debe ser un bloque `glosario`…», **4/4** cápsulas lo traen (3 R puro + A20-R70-K10). **Etapa 1:** con el texto nuevo, el glosario aparece en todas las cápsulas válidas con R ≥ 40 % (S42 y S43, brazos A y B), pero la etapa no cumplió C3 (ver «Correcciones»). | Cambiar ese texto en `rag/prompts/maestro.py::INSTRUCCION_POR_DIRECTIVA["glosario"]` y revisar el resto de las instrucciones que digan «contenido». **Efecto colateral medido:** las cápsulas R suben a 255–299 palabras y 2/4 necesitaron una reparación por pasar de 300, así que conviene acompañarlo con un objetivo de palabras R algo menor (`MARGEN_PALABRAS_OBJETIVO`). |
| H2 | 🔴 **Abierto y prioritario: bloquea H1 y H3.** **El bucle de reparación vuelve a repetir la respuesta byte a byte.** | C05 (A2-R17-K81): los intentos 2 y 3 son idénticos (mismo MD5, 4.930 caracteres), así que el tercer intento se desperdició y la cápsula se perdió. Es el problema que la sección 5 sedecies de AVANCE daba por corregido con el mensaje de reparación. **Etapa 1:** las 2 cápsulas que perdió el brazo B repitieron los 3 intentos idénticos, con desviaciones de solo 8–21 palabras. | En `generation/generator.py`, detectar que `crudo` es igual al anterior y, en ese caso, reintentar con otra estrategia: subir la temperatura en esa llamada o reinyectar solo el error con la cápsula anterior resumida. |
| H3 | 🟡 **Abierto (Etapa 1 sin aplicar).** **Las cápsulas K se pasan de largo y las R se quedan cortas** (patrón 1). | K +48, R −57 palabras respecto del objetivo. 4/4 reparaciones y el único contrato agotado son de K ≥ 40 % por pasar de 300 palabras. | Decisión de diseño del equipo: o bajar el objetivo de palabras de K cuando se pide `lista_pasos` + `ejemplo_resuelto`, o pedir explícitamente brevedad en esos bloques. **Etapa 1:** el reparto por paso como tope llevó R a +2 %, pero invirtió K a −21 % y acercó al piso de 150 a los perfiles de objetivo bajo. Retomar después de H2. |
| H4 | **Con 25 ≤ p_K < 40 % se ignora la cantidad de componentes prácticos** (patrón 2). | 3/3 perfiles. | Que `componentes_practicos = 2` vaya acompañado de una directiva concreta (p. ej. `paso_a_paso`) en `vark/rules.py`. Toca la lectura de la tabla 11.1 aprobada el 06-ago, así que la decide el equipo. |
| H5 | **Audio en el camino de la API: narra JSON, se pierde y bloquea.** `POST /api/capsulas` (y el visor, que lo llama) ejecuta `GeneradorMultimedia` **síncrono** con `json.dumps(capsula)[:250]` como guion, guarda el WAV en `data/media/` (nada lo sirve), y después el visor sintetiza **otro** audio con el guion correcto. | 29/29 cápsulas: el guion de la ruta API empieza con `{"titulo": …`. XTTS en CPU tardó 67–229 s por audio en esta batería. Por lectura de código, un estudiante con p_A ≥ 25 % espera esa síntesis inútil antes de ver su cápsula. | Quitar la síntesis de audio de `crear_capsula` (el visor ya la hace bajo demanda con el guion correcto). Corrige a la vez el guion JSON, el archivo huérfano, la doble síntesis y la espera. |
| H6 | **El modelo inventa cifras de ejemplo** (patrón 4). | 2/29 cápsulas con RUT ficticios. | Advertencia (no rechazo) en `generation/validator.py` para cifras que no están en los fragmentos, o permitir explícitamente los datos de ejemplo en el prompt. |
| H7 | **«Preguntas reflexivas» casi nunca se cumple.** | 2/13 cápsulas con A ≥ 40 % intercalan una pregunta en la prosa. | Reformular la instrucción para que nombre dónde va (p. ej. dentro de `concepto_central`). |
| H8 | **`pytest` completo carga SDXL y XTTS.** `tests/test_visual.py` y `tests/test_voz.py` ejecutan la generación **al importarse**. | Lectura de código. | Moverlos a `scripts/` o protegerlos con `if __name__ == "__main__"`. |
| H9 | ✅ **Corregido (04-oct).** **`gruut` (dependencia de Coqui TTS) instala un paquete `tests` en site-packages** que le hacía sombra a `tests/` del repo: 12 archivos que hacen `from tests.conftest import …` no se podían ni importar. | `import tests` resolvía a `.venv/Lib/site-packages/tests/__init__.py` (instalado el 31-ago). Con `pytest`: 12 errores de colección. | `tests/__init__.py` convierte la carpeta en paquete regular y pytest antepone la raíz del repo a `sys.path`; los 4 tests que hacían `from material import` pasan a `from tests.material import`. Verificado: 432 pasan y 4 fallan (los mismos 4 previos), sin shim. |

**Aviso de XTTS, sin consecuencias en esta corrida:** 10/16 audios registraron «The text
length exceeds the character limit of 239 for language 'es'». Ninguno quedó truncado (las
velocidades de habla están todas entre 2,0 y 2,7 palabras/s), porque `tts_to_file` parte
el texto en oraciones. Conviene vigilarlo si los conceptos centrales se alargan.
