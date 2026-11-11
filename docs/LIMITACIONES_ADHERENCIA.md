# Limitaciones y evidencia de adherencia de la adaptación VARK

Todas las cifras provienen de `data/adherencia/resumen.md` y `data/adherencia/detalle.csv`, generados por
`scripts/adherencia/medir_adherencia.py` (solo lectura). Cada cifra indica entre corchetes la sección y la tabla
de `resumen.md` de donde se obtuvo. Los decimales se escriben con coma; los valores son los mismos de la fuente.

## 1. Alcance y método

Este apartado mide el cumplimiento de instrucciones, no el efecto en el aprendizaje. Para cada cápsula guardada
se recalcularon con las reglas vigentes de `vark/rules.py` las directivas que correspondían a su vector VARK, y
se comprobó en su JSON la presencia del bloque o la actividad que cada una exige. El conjunto principal reúne
502 cápsulas: 15 de la prueba de usuario, de 4 estudiantes y sin las 2 de una cuenta del equipo, y 487 de la
batería automatizada generadas con un prompt idéntico al que el código produce hoy para el mismo vector [resumen:
Tamaño de muestra]. Las 388 cápsulas de la batería con prompts experimentales o anteriores se informan aparte
[resumen: Tamaño de muestra]. La adherencia se expresa como cápsulas que cumplen sobre cápsulas donde la
directiva correspondía y era verificable.

## 2. Evidencia a favor de la adaptación

En la batería comparable, la presencia del bloque `analogia` sube de 79/207 cápsulas (38 %) con p_A < 25 a 46/82
(56 %) con 25 ≤ p_A < 40 y a 198/198 (100 %) con p_A ≥ 40 [resumen: Dosis-respuesta, Batería comparable
(principal), Canal A]. Para K, el elemento característico (`lista_pasos` o la actividad `flashcards_y_quiz`)
pasa de 12/244 (5 %) a 23/73 (32 %) y a 170/170 (100 %) en los mismos tramos. El `ejemplo_resuelto` se excluyó de
esa medida porque aparece en 237/244 cápsulas (97 %) incluso con p_K < 25 y no distingue entre tramos [resumen:
Dosis-respuesta, Batería comparable (principal), Canal K]. Donde eran obligatorias, `analogias_cotidianas`
alcanza 211/211 (100,0 %), `paso_a_paso` 180/183 (98,4 %), `actividad_aplicada` 183/183 (100,0 %) y
`encabezados_jerarquicos` 183/183 (100,0 %) [resumen: Batería comparable (principal), Todas las clases]. Toda la
batería usa el objetivo BD-U3-02 [resumen: Modelo y objetivo de aprendizaje] y, dentro de cada base de datos, el
mismo conjunto de fragmentos para todos los perfiles, de modo que la diferencia entre tramos no puede atribuirse
al material.

## 3. Cumplimiento parcial o insuficiente

El glosario exigido con p_R ≥ 40 aparece en 2 de 183 cápsulas (1,1 %) de la batería comparable [resumen: Batería
comparable (principal), Todas las clases]. Su presencia tampoco crece con p_R: 0/227 (0 %), 2/77 (3 %) y 2/183
(1 %) según el tramo [resumen: Dosis-respuesta, Batería comparable (principal), Canal R]. El 49,9 % que muestra la
batería completa [resumen: Batería completa (secundaria), Todas las clases] proviene de los brazos experimentales
de redacción del glosario, donde alcanzó 190/202 (94,1 %) [resumen: Batería con prompt distinto del vigente (no
comparable), Todas las clases]. Esa diferencia indica que el resultado depende de cómo está redactada la
instrucción, y la redacción que hoy está en producción no lo consigue. La pregunta reflexiva intercalada en el
concepto central se cumple en 18/198 cápsulas (9,1 %), y en 20/198 (10,1 %) con la variante amplia, que también la
busca en párrafos, analogías y ejemplos [resumen: Batería comparable (principal), Todas las clases]. Los
componentes prácticos pedidos se entregan en 404/463 cápsulas (87,3 %) del conjunto principal, pero solo en 9/24
(38 %) de las multimodales [resumen: Total principal (usuario + batería comparable), Todas las clases; Por clase
de perfil]. En la prueba de usuario la proporción baja a 9/15 (60,0 %) [resumen: Prueba de usuario, Todas las
clases].

## 4. Extensión

La diferencia media entre las palabras entregadas y el objetivo del conjunto principal es de −7,1 palabras, pero
el error absoluto medio llega a 36,2 [resumen: Extensión por perfil — conjunto principal]. Esto significa que
los excesos y las faltas se compensan en el promedio con signo. Por perfil, los unimodales R quedan 50,9 palabras
bajo su objetivo (error absoluto 53,8; n = 127). Los bimodales A+K lo superan en 45,3 (error absoluto 52,3;
n = 46). Los multimodales A+K+R lo superan en 24,2 (n = 16), y los A+K+V y A+K+R+V en 65,0 y 74,6, ambos con
n < 10 [resumen: Extensión por perfil — conjunto principal]. Las cápsulas de la prueba de usuario exceden el
objetivo en 69,6 palabras de media [resumen: Prueba de usuario, Extensión por clase]. Hay además 27 corridas de
la batería que no produjeron cápsula: 25 superaron el máximo de palabras y 2 no alcanzaron el mínimo. De ellas,
24 tienen p_R ≥ 49, y por perfil se reparten en R 11, K+R 9 y A+R 4 [resumen: Cápsulas excluidas]. En la prueba
de usuario, el registro parcial muestra 45 rechazos por exceso de palabras y 6 generaciones agotadas tras tres
intentos [resumen: Registro de la aplicación (prueba de usuario)].

## 5. Aspectos no verificables

Cuatro exigencias no pueden comprobarse con certeza a partir del contenido guardado. La primera es `tono_oral`,
que correspondía en 198 cápsulas y es un rasgo de estilo sin un umbral definido en el código. La segunda es
`definiciones_exactas`, que correspondía en 207 cápsulas y cuya exactitud requiere juicio experto [resumen: Total
principal (usuario + batería comparable), Todas las clases]. La tercera es el orden de lo general a lo
particular que pide `estructura_jerarquica`, de la que solo se verificó el encabezado de cada bloque. La cuarta
es que la pregunta reflexiva reciba respuesta a continuación. La narración se informa solo como dato
descriptivo: las 15 cápsulas de usuario tienen archivo de audio [resumen: Prueba de usuario, Narración (audio_activo)],
mientras que en 267 cápsulas de la batería no es verificable porque esas corridas se hicieron sin audio [resumen:
Batería comparable (principal), Narración (audio_activo)].

## 6. Cobertura visual

El canal visual queda sin evaluar. Las directivas `incluir_mapa_conceptual` y `tabla_comparativa` no
correspondieron a ninguna cápsula, y `recurso_visual_complementario` solo a 4 [resumen: Total principal (usuario +
batería comparable), Todas las clases]. Ninguna cápsula del conjunto principal tiene p_V ≥ 40 [resumen:
Dosis-respuesta, Total principal, Canal V], y 874 de las 875 cápsulas de la batería tienen p_V = 0 [resumen:
Advertencias, 2].

## 7. Amenazas a la validez

La muestra de usuarios es pequeña y no independiente: 15 cápsulas de 4 estudiantes que comparten vector dentro de
cada estudiante [resumen: Tamaño de muestra]. La batería emplea un único objetivo [resumen: Modelo y objetivo de
aprendizaje] con fragmentos rotulados por perfil, lo que puede elevar la presencia de analogías y ejemplos
resueltos donde no se exigen. Hay sesgo de supervivencia, porque solo se analizan cápsulas que pasaron el
validador: quedan fuera las 27 corridas sin cápsula [resumen: Cápsulas excluidas], las 6 generaciones agotadas
y las cápsulas de 3 estudiantes que eliminaron sus datos [resumen: Registro de la aplicación (prueba de
usuario)]. El modelo difiere entre conjuntos: 481 cápsulas de la batería comparable se generaron con
`deepseek-chat` y 6 con `deepseek-flash`, el modelo de producción y de las 15 cápsulas de usuario [resumen: Modelo
y objetivo de aprendizaje]. El prompt cambió después de octubre, y 388 de las 875 cápsulas de la batería se
generaron con otra redacción [resumen: Tamaño de muestra]. Las cápsulas de usuario no guardan su prompt, de modo
que su equivalencia con el vigente se supone.

## 8. Trabajo futuro

Con más tiempo, el equipo incorporaría al validador las directivas verificables, primero como métricas y luego
como exigencias. Repetiría la batería con `deepseek-flash`, con perfiles que tengan p_V > 0 y con material sin
rótulos de perfil. Finalmente, diseñaría una evaluación controlada del efecto en el aprendizaje, que este
análisis de adherencia no aborda.
