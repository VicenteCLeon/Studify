"""Prompt del paso LLM del módulo Visual: del material curado a un esquema.

El modelo no dibuja nada. Entrega una especificación JSON —conceptos y
relaciones— que la plataforma valida y dibuja con plantillas propias. El
diseño, el contrato y las mediciones están en
`docs/modulo-visual/analisis-modulo-visual.md` (§3 y §10).

**Va en una llamada aparte del prompt maestro.** Ese prompt ya está al límite
de su presupuesto de palabras, y además la cápsula es por perfil y el esquema
es por lección: se genera una vez y lo ven todos los estudiantes del objetivo.

Todavía no lo usa la aplicación. Lo ejercita
`docs/modulo-visual/pruebas/generar_specs_llm.py`, que es con lo que se midió.
"""

from llama_index.core import PromptTemplate

# Mensaje de sistema. Las cuatro reglas son las del prompt maestro, reducidas a
# lo que un esquema necesita.
SISTEMA = """\
Eres un diseñador instruccional que convierte material de estudio universitario en
esquemas visuales. Reglas que no puedes incumplir:
1. Escribes ÍNTEGRAMENTE en español, con tildes y ñ correctas.
2. Respondes ÚNICAMENTE con un objeto JSON válido, sin texto antes ni después.
3. Solo usas conceptos y relaciones que aparecen en los fragmentos entregados.
   No agregas datos, ejemplos ni términos propios.
4. Menos es más: un esquema con 5 nodos claros es mejor que uno con 7 forzados."""

# Mensaje de usuario. `fragmentos` lleva cada fragmento con su `id_fragmento`
# (el mismo formato que `maestro.FRAGMENTO`) y `esquema_json`, el contrato.
#
# El primer límite —no usar títulos de sección como nodos— salió de medir 12
# especificaciones (§10.3 del análisis): las 6 relaciones que no tenían respaldo
# en ningún fragmento apuntaban a «Paso a Paso» o a «Ejemplo RUT», que son
# rótulos del apunte y no conceptos del tema.
USUARIO = PromptTemplate(
    """\
## Objetivo de aprendizaje
Asignatura: {asignatura}
Unidad: {unidad}
Tema: {tema}

## Material curado
{fragmentos}

## Tarea
Diseña UN esquema que muestre la estructura del tema: qué conceptos hay y cómo se relacionan.

Elige `tipo_de_diagrama` según la naturaleza del contenido:
- flujo: pasos de un procedimiento, en orden.
- ciclo: etapas que se repiten y vuelven al inicio.
- jerarquia: una categoría que se divide en subtipos.
- comparacion: dos a cuatro elementos contrastados por sus rasgos.
- linea_de_tiempo: hitos ordenados en el tiempo.
- causa_efecto: causas que producen consecuencias.
- mapa_conceptual: cuando ninguno de los anteriores calza.

Límites estrictos:
- Cada nodo es un concepto del contenido. No uses como nodo el título de una sección
  del apunte («Paso a paso», «Definición», «Ejemplo», «Resumen»).
- `titulo`: 6 palabras o menos.
- `nodos`: entre 3 y 7. Cada `etiqueta`, 4 palabras o menos, usando el término exacto del material.
- `detalle` (opcional): 8 palabras o menos.
- `relaciones`: cada `verbo` con 3 palabras o menos («produce», «se divide en»).
- Exactamente un nodo con rol `principal`.
- `texto_alternativo`: 1 o 2 oraciones que describan el esquema a quien no puede verlo.
- `fuentes`: los id_fragmento de donde salió cada concepto.

## Formato
{esquema_json}"""
)
