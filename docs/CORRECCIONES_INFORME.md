# Correcciones al informe

> Qué hay que corregir, actualizar o agregar en el informe final respecto del
> **informe de avance** (`seminario_titulo.md`, abril de 2026). Junta las dos
> listas que había (`AVANCE.md` §8 y `PLAN_DESARROLLO.md` §7) y las diferencias
> entre lo que el informe describe y lo que quedó implementado.
>
> Cada ítem cita el capítulo del informe y el **origen** en este repo, donde está
> la evidencia. Cuando se aplique una corrección al informe, se tacha o se borra
> acá.
>
> Última revisión: 17-oct-2026.

Hay cinco tipos de cambio:

- **A. Errores de forma:** se corrigen sin discutir.
- **B. Definiciones ambiguas o contradictorias** dentro del propio informe.
- **C. Datos que no se reproducen:** requieren una decisión con la profesora.
- **I. Diferencias con la implementación:** el informe describe algo que se hizo de otra forma.
- **N. Temas nuevos:** lo que el informe final tiene que contar y el de avance no tiene.

---

## A. Errores de forma

- **A1. Referencias cruzadas desfasadas**, que parecen de una numeración
  anterior:
  - §16.4 remite a la «sección 12.2»: las reglas de mapeo están en la **11.2**.
  - §17 remite a la «sección 14» para la justificación de la base, que es la
    **13**, y a una «sección 12.3» que no existe.
  - §17.1 remite a la «sección 10» para los datos sociodemográficos, que están
    en la **9**, y a la «sección 11» para la calificación, que está en la **10**.
- **A2. Resumen y Abstract dicen cosas distintas.** El resumen es condicional
  («se espera que el sistema contribuya a mejorar la retención»); el abstract
  afirma en indicativo («Preliminary findings […] indicate that […]
  **effectively improves** knowledge retention»). Sin validación empírica, el
  abstract debería ir en condicional. En el informe final, ajustar ambos a lo
  que muestren los resultados.
- **A3. Cita de Saha et al.:** §11.1 dice «50 a 70 minutos» y §2 cita la misma
  fuente como «50 a 75 minutos». Verificar contra la fuente.
- **A4. Tabla 16.2 (muestra total):** suma 43 estudiantes pero no tiene columna
  de porcentaje, a diferencia de la de Ing. Informática. Homologar.
- **A5. Distribución por año (§16.1):** 20 + 9 + 7 + 7 = 43, pero los
  porcentajes (47 + 21 + 16 + 16) suman 100 solo por redondeo. Aclararlo con
  una nota al pie.

Origen: `PLAN_DESARROLLO.md` §7 y `AVANCE.md` §8.

## B. Definiciones ambiguas o contradictorias

- **B1. El criterio de multimodalidad está definido dos veces, y no son
  equivalentes.** §10 habla de «empates o diferencias mínimas», sin
  cuantificar y sobre puntajes crudos. §11.1 dice «diferencia ≤ 10 puntos
  porcentuales», sobre el vector porcentual. Diez puntos sobre ~16 selecciones
  son ~1,6 selecciones de diferencia, mientras que «empate» exige 0. Unificar
  con el criterio de §11.1, que es el implementado.
  Origen: `AVANCE.md` §8; `vark/hierarchy.py`.
- **B2. Las reglas de la tabla 11.1 no son mutuamente excluyentes.** Las filas
  1–5 (umbrales por canal) y la 7 («tres o más dimensiones sobre el 20 %»)
  pueden cumplirse a la vez, como en `{0V, 21A, 21R, 58K}`. El informe debería
  decir que se aplican en capas: las 1–5 fijan los elementos de contenido y la
  6–7 la etiqueta de modalidad. **Ojo:** hoy la fila 7 no se aplica como regla
  de contenido en el código; es una decisión pendiente (`PENDIENTES.md` D4).
  Origen: `AVANCE.md` §2 bis y §8.
- **B3. Componentes prácticos: bloques del cuerpo frente a actividad de
  cierre.** Con p_K ≥ 40 % la tabla 11.1 cuenta tres (ejemplo aplicado,
  secuencia paso a paso y actividad «inténtalo tú»), pero la tercera no es un
  bloque del cuerpo de la cápsula. Leída al pie de la letra, pide tres bloques
  donde corresponden dos. Origen: `AVANCE.md` §8.
- **B4. §7.2 contradice a §17.2.** §7.2 dice que si un estudiante es
  diagnosticado como «Kinestésico», el sistema «guarda este atributo»; §17.2
  establece que el perfil se guarda solo como vector y la jerarquía se deriva
  en cada consulta. Lo implementado es §17.2. Origen: `db/models.py`, docstring.
- **B5. `palabras_texto` no lo determina el informe.** §11.1 fija el rango
  150–300 pero no cómo repartirlo entre perfiles. El sistema lo interpola
  sobre C_texto dentro de su rango alcanzable [40, 75]; lo aprobó el equipo el
  06-ago-2026. Hay que declararlo como decisión de diseño.
  Origen: `AVANCE.md` §2 bis; `vark/rules.py`.

## C. Datos que no se reproducen

- **C1. Las tablas 16.2 y 16.3 no se reproducen desde el CSV de respuestas**,
  aunque el dataset es verificablemente el mismo (todos los datos
  sociodemográficos de §16.1 calzan). O se corrige el informe con los valores
  recalculados, o aparece la planilla que explique la diferencia. **Es la más
  importante de esta lista**, y se decide con la profesora (`PENDIENTES.md` D1).
  Origen: `AVANCE.md` §5 ter.

## I. Diferencias con la implementación

### Arquitectura y generación (§7, §15, §18)

- **I1. El prompt no nombra el perfil (§7.4).** El ejemplo del informe pide
  «una cápsula de 3 párrafos enfocada en un estudiante visual». El prompt real
  nunca le pasa la etiqueta al modelo: le da instrucciones estructurales (qué
  bloques construir, cuántos, con qué tono) derivadas de
  `configuracion_contenido`, que es la mitigación del riesgo «las cuatro
  cápsulas salen indistinguibles». Origen: `rag/prompts/maestro.py`, docstring.
- **I2. No hay una plantilla por estilo dominante (§15).** Cada canal que
  supera su umbral aporta sus directivas, y los perfiles multimodales reciben
  además las de equilibrio. Origen: `vark/rules.py::_directivas`.
- **I3. El perfil reordena los fragmentos, no los filtra (§7.3).** El informe
  dice que la consulta recupera los fragmentos «que coinciden con el tema
  solicitado y con el perfil VARK». En la implementación filtra solo por
  objetivo y estado de validación; el perfil sube primero los tipos que
  prefiere (tablas para V). Origen: `rag/retriever.py`.
- **I4. La validación es más que comprobar la estructura (§15, §18).**
  - Son seis reglas: esquema, extensión 150–300, título, actividad, **citas
    que tienen que ser fragmentos realmente inyectados** e idioma español.
  - Cuando una falla, se reinyecta el error en un bucle de reparación con dos
    reintentos.
  - Hay caché por huella y versionado: la regeneración conserva la versión
    anterior.

  Origen: `generation/validator.py`; `AVANCE.md` §5 octies.
- **I5. No hay fragmentos ni proporciones de imagen (§18).** La ingesta solo
  extrae texto (las tablas de PPTX se serializan); las imágenes y diagramas se
  omiten. La cápsula no tiene «proporciones de texto/imagen». El recurso
  visual del perfil V son bloques `tabla` y `esquema`. Origen: `AVANCE.md` §7
  n.º 3; `PENDIENTES.md` X2.

### Estructura de la microcápsula (§11.1)

- **I6. La anatomía pasó de cinco partes a siete pasos pedagógicos**, a
  propuesta de la profesora guía (14-ago-2026): objetivo → activación →
  concepto central → representación adaptativa → ejemplo → pregunta de
  comprobación → retroalimentación. Cada paso es un campo obligatorio del
  contrato. Origen: `AVANCE.md` §5 terdecies; `generation/schemas.py`.
- **I7. La actividad de cierre tiene cinco formas**, no solo «pregunta de
  verificación o mini-quiz»: `quiz_mc`, `intentalo_tu`, `flashcards`,
  `quiz_multi` y `flashcards_y_quiz`. Con p_K ≥ 40 % se pide
  `flashcards_y_quiz`. Origen: `docs/historico/2026-09-03_sesion_de_testeo_y_mejoras.md`.
- **I8. La duración de 3–7 minutos mide el cuerpo, no la actividad.** El rango
  150–300 cuenta activación, concepto, representación y ejemplo. Una cápsula K
  con 3–5 tarjetas y 3–5 preguntas toma bastante más. Conviene decirlo.
  Origen: `generation/schemas.py::Microcapsula.palabras_contenido`.

### Perfil y datos (§16.4, §17)

- **I9. El perfil por defecto K→A (§16.4) no está implementado.** Sin
  diagnóstico no se genera nada: el sistema manda a responder el cuestionario
  (`POST /api/capsulas` responde 422). O se implementa, o se saca del informe.
  Origen: `api/routers/capsules.py::crear_capsula`.
- **I10. El diccionario de datos (tablas 17.1–17.8) cambió:**
  - `estudiante.genero` es `VARCHAR(50)` y no 20: la alternativa «No Binario /
    otra identidad» tiene 27 caracteres (migración `8eb6f0399fee`).
  - `estudiante.ano_ingreso` se definió como «año de ingreso a la universidad»,
    pero el formulario preguntó el **año de carrera**. La columna queda en
    NULL: decidir si el atributo pasa a «año de carrera» o si se agrega la
    pregunta.
  - `estudiante` suma `voz_genero` y `voz_modo` (preferencia de voz, 05-oct).
  - `microcapsula_generada` suma `huella_generacion` (clave de caché) y
    `modelo_llm`.
  - **Dos entidades nuevas:** `interaccion_quiz` (intentos numerados de la
    actividad de cierre, con detalle por pregunta) y `aceptacion_legal`
    (versión aceptada de cada documento legal). El modelo pasa de 8 a 10
    entidades.
  - Notación: `DATETIME` → `TIMESTAMP WITH TIME ZONE`, y los vocabularios
    controlados van con CHECK en vez de ENUM.

  Origen: `AVANCE.md` §2 bis y §8; `db/models.py`; migraciones en `alembic/versions/`.

### Stack (§7.5, §14)

- **I11. El stack quedó definido:**
  - **Base de datos:** PostgreSQL 16, no «PostgreSQL o MySQL», por `JSONB` y
    búsqueda de texto en español.
  - **Acceso a datos:** SQLAlchemy 2.0 con migraciones Alembic, y validación
    con Pydantic v2.
  - **Interfaz:** Jinja2 + HTMX servidos por el mismo FastAPI, sin build.
  - **Modelo de lenguaje:** DeepSeek por API compatible con OpenAI, no GPT-4o,
    Claude ni Llama. En el bake-off, Qwen y GLM fallaron por autorización, así
    que DeepSeek fue **el único candidato que se pudo medir**, no el ganador de
    una comparación. Desde el 11-oct se usa `deepseek-flash`.
  - **Narración:** Kokoro y Piper, en local.
  - **Concurrencia:** §14 destaca el «manejo asíncrono nativo» de FastAPI, pero
    los endpoints son síncronos a propósito.

  Origen: `AVANCE.md` §2 y §5 octies; `pyproject.toml`.

### Evaluación (§8)

- **I12. El diseño del A/B cambió (§8.2).** El informe compara un grupo
  control con «material genérico» y uno experimental con cápsulas adaptadas,
  ambos dentro del sistema. Lo decidido el 06-ago-2026: el grupo experimental
  usa la app y el de control estudia de forma tradicional, sin tocar el
  sistema, y se comparan calificaciones. Origen: `PLAN_DESARROLLO.md` Fase 5.
- **I13. No hay «microcápsula genérica» (§8.5).** El sistema no tiene un modo
  sin personalizar, por la misma decisión; la comparación simple que propone
  §8.5 habría que reformularla. Origen: `PLAN_DESARROLLO.md` Fase 5.
- **I14. La validación docente tiene que incluir la adaptación VARK (§8.5,
  tabla 8.1).** El profesor revisa, para un mismo objetivo, las cápsulas de los
  distintos perfiles. Hoy la tabla 8.1 separa «adaptabilidad pedagógica» de
  «validación docente» sin decir quién compara. Ajustar la rúbrica.
  Origen: `PLAN_DESARROLLO.md` Fase 5.
- **I15. Cómo se mide el rendimiento en la actividad de cierre.** Al primer
  intento, y separado por tipo: «selección única» (% de acierto en `quiz_mc`)
  y «cuestionario» (promedio de preguntas acertadas en los de varias
  preguntas). Son instrumentos distintos y no se promedian juntos.
  Origen: `AVANCE.md` §5 quintricies.

## N. Temas nuevos que el informe final tiene que incorporar

- **N1. Resultados de la batería VARK** (03-oct-2026, 30 perfiles A/R/K):
  - 29/30 cápsulas válidas, 26 a la primera (96,7 %) y 0 citas inventadas.
  - K funciona con p_K ≥ 40 %.
  - Limitaciones medidas: R no recibe glosario (H1), K se alarga y R se queda
    corto (H3), y H4. Repetir con `deepseek-flash` (`PENDIENTES.md` G1).

  Origen: `PRUEBAS_VARK.md`.
- **N2. Narración en audio para el perfil auditivo:** motores locales, la
  preferencia de voz independiente del género y sus licencias.
  Origen: `AVANCE.md` §5 duodetricies a §5 duotricies.
- **N3. Por qué no se generan imágenes con difusión:** el texto sale ilegible
  en diagramas educativos. La alternativa es el módulo Visual, un SVG dibujado
  a partir de una especificación del LLM.
  Origen: `docs/historico/2026-09-03_experimento_flux2_klein.md` §10;
  `docs/modulo-visual/analisis-modulo-visual.md`.
- **N4. Marco legal y ético:**
  - Términos y Política (Ley 19.628 y 21.719).
  - Consentimiento registrado con su versión.
  - Consentimiento separado para el dato sensible de género.
  - Derechos en `/mis-datos`.
  - Riesgos abiertos, entre ellos el consentimiento de los 43 diagnósticos de
    Google Forms.

  Origen: `AVANCE.md` §5 tervicies; `PENDIENTES.md` L.
- **N5. Licencia del código:** AGPL-3.0-or-later y por qué (componentes GPL en
  la narración). Origen: `AVANCE.md` §5 tritricies.
- **N6. Limitaciones técnicas encontradas** para §8.6:
  - el modelo inventa datos de ejemplo (H6);
  - el glosario de R no aparece (H1);
  - la fila 7 de la tabla 11.1 no se aplica como regla de contenido (B2);
  - la curación es trabajo humano fragmento a fragmento.
