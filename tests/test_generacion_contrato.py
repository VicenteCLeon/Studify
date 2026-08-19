"""Tests del contrato de la microcápsula y del validador (Fase 3).

Cada bloque contrasta contra una regla concreta de `PLAN_DESARROLLO.md` §3, no
contra el comportamiento observado del propio código.

No requieren Postgres ni `LLM_API_KEY`: el contrato, el parser y las seis reglas
son puros. El generador —lo único que habla con el modelo— se testea aparte con
un cliente falso.
"""

import copy

import pytest
from material import DOCUMENTO, EXPLICACION, FRAGMENTOS, PARRAFO, capsula_valida
from pydantic import ValidationError

from studify.generation import idioma
from studify.generation.schemas import Actividad, BloqueContenido, Microcapsula
from studify.generation.validator import (
    ErrorFormatoJSON,
    ResultadoValidacion,
    extraer_json,
    validar,
)


def validar_capsula(datos: dict) -> ResultadoValidacion:
    return validar(datos, fragmentos=FRAGMENTOS, palabras_objetivo=250)


# --- El material de prueba tiene que ser válido de verdad --------------------


def test_la_capsula_de_referencia_pasa_las_seis_reglas():
    """Si esto falla, todos los demás tests están midiendo otra cosa."""
    resultado = validar_capsula(capsula_valida())

    assert resultado.es_valida, resultado.errores
    assert 150 <= resultado.metricas["palabras_contenido"] <= 300


# --- Regla 3: título ≤ 10 palabras -------------------------------------------


def test_titulo_de_once_palabras_se_rechaza():
    datos = capsula_valida()
    datos["titulo"] = (
        "Un título deliberadamente largo que supera con claridad el límite de palabras"
    )

    resultado = validar_capsula(datos)

    assert not resultado.es_valida
    assert any("título" in e for e in resultado.errores)


def test_titulo_de_exactamente_diez_palabras_se_acepta():
    """El límite del plan §3 es «máx. 10», o sea inclusivo."""
    datos = capsula_valida()
    datos["titulo"] = "Uno dos tres cuatro cinco seis siete ocho nueve diez"

    assert validar_capsula(datos).es_valida


# --- Regla 4: la actividad de cierre es obligatoria --------------------------


def test_sin_actividad_se_rechaza():
    datos = capsula_valida()
    del datos["actividad"]

    resultado = validar_capsula(datos)

    assert not resultado.es_valida
    assert any("actividad" in e for e in resultado.errores)


def test_quiz_con_indice_correcta_fuera_de_rango_se_rechaza():
    """Rompería la UI en silencio: el estudiante no podría acertar nunca."""
    datos = capsula_valida()
    datos["actividad"]["indice_correcta"] = 7

    resultado = validar_capsula(datos)

    assert not resultado.es_valida
    assert any("indice_correcta" in e for e in resultado.errores)


def test_quiz_con_alternativas_repetidas_se_rechaza():
    """Dos alternativas iguales son dos respuestas correctas."""
    datos = capsula_valida()
    datos["actividad"]["alternativas"][1] = datos["actividad"]["alternativas"][0]

    resultado = validar_capsula(datos)

    assert not resultado.es_valida
    assert any("repetidas" in e for e in resultado.errores)


def test_intentalo_tu_con_alternativas_se_rechaza():
    """Mezclar los dos formatos deja una actividad que la UI no sabe mostrar."""
    datos = capsula_valida()
    datos["actividad"]["tipo"] = "intentalo_tu"

    resultado = validar_capsula(datos)

    assert not resultado.es_valida
    assert any("intentalo_tu" in e for e in resultado.errores)


def test_intentalo_tu_bien_formado_se_acepta():
    """Es la actividad que exige la tabla 11.1 con p_K ≥ 40%."""
    datos = capsula_valida()
    datos["actividad"] = {
        "tipo": "intentalo_tu",
        "pregunta": "Normaliza a segunda forma normal la tabla de matrículas del ejemplo.",
        "retroalimentacion": (
            "Separa el nombre del ramo en su propia tabla: dependía solo del "
            "código del ramo, no de la clave completa."
        ),
    }

    assert validar_capsula(datos).es_valida


# --- Bloques de contenido ----------------------------------------------------


def test_tabla_con_cuerpo_de_texto_se_rechaza():
    """La tabla comparativa es el recurso que pide la tabla 11.1 con p_V ≥ 40%.

    Si llega como prosa, la UI no tiene filas que dibujar y el perfil visual se
    queda sin su recurso, sin ningún error visible.
    """
    with pytest.raises(ValidationError, match="lista de filas"):
        BloqueContenido(tipo="tabla", cuerpo="1FN: valores atómicos; 2FN: sin parciales")


def test_tabla_con_filas_desiguales_se_rechaza():
    with pytest.raises(ValidationError, match="distinto número de columnas"):
        BloqueContenido(
            tipo="tabla",
            cuerpo=[["Forma", "Exige"], ["1FN", "valores atómicos", "extra"]],
        )


def test_tabla_bien_formada_se_acepta_y_sus_celdas_cuentan_palabras():
    bloque = BloqueContenido(
        tipo="tabla",
        encabezado="Comparación de formas normales",
        cuerpo=[["Forma", "Exige"], ["1FN", "valores atómicos"]],
    )

    # 4 del encabezado + 5 repartidas en las cuatro celdas.
    assert bloque.palabras() == 9


def test_bloque_con_cuerpo_vacio_se_rechaza():
    with pytest.raises(ValidationError, match="cuerpo vacío"):
        BloqueContenido(tipo="parrafo", cuerpo="   ")


def test_los_campos_desconocidos_se_ignoran_en_vez_de_rechazarse():
    """Un campo de más no justifica gastar un reintento con el modelo."""
    datos = capsula_valida()
    datos["dificultad"] = "media"
    datos["representacion_adaptativa"][0]["color"] = "azul"

    assert validar_capsula(datos).es_valida


# --- Estructura pedagógica de siete pasos (14-ago-2026) ----------------------


@pytest.mark.parametrize(
    "paso",
    ["objetivo_aprendizaje", "activacion", "concepto_central",
     "representacion_adaptativa", "ejemplo", "actividad"],
)
def test_cada_paso_de_la_estructura_es_obligatorio(paso):
    """Ninguno de los siete pasos puede faltar.

    Es el punto de la estructura fija: que la ausencia de la activación o del
    concepto central sea un error de validación, y no algo que haya que
    descubrir leyendo la cápsula.
    """
    datos = capsula_valida()
    del datos[paso]

    resultado = validar_capsula(datos)

    assert not resultado.es_valida
    assert any(paso in e for e in resultado.errores)


def test_la_activacion_tiene_que_ser_una_pregunta():
    """El paso 2 activa conocimiento previo, y para eso tiene que preguntar."""
    datos = capsula_valida()
    datos["activacion"] = "Vamos a estudiar las dependencias parciales."

    resultado = validar_capsula(datos)

    assert not resultado.es_valida
    assert any("pregunta" in e for e in resultado.errores)


def test_la_activacion_no_puede_ser_la_explicacion_completa():
    datos = capsula_valida()
    datos["activacion"] = PARRAFO + " ¿Lo tenías claro?"

    resultado = validar_capsula(datos)

    assert not resultado.es_valida
    assert any("activacion" in e and "máximo" in e for e in resultado.errores)


def test_el_ejemplo_es_un_bloque_tipado_y_se_adapta_al_perfil():
    """`ejemplo` no es texto plano: así un perfil K recibe `lista_pasos`.

    Es lo que permite que la adaptación VARK no quede encerrada en la sección
    de representación adaptativa (decisión del 14-ago-2026).
    """
    datos = capsula_valida()
    datos["ejemplo"] = {
        "tipo": "lista_pasos",
        "encabezado": "Cómo corregirlo",
        "cuerpo": ["Identifica la clave completa.", "Separa el atributo dependiente."],
    }

    resultado = validar_capsula(datos)

    assert resultado.es_valida, resultado.errores
    assert resultado.capsula.ejemplo.tipo == "lista_pasos"


def test_los_bloques_legibles_van_en_orden_de_lectura():
    """Representación adaptativa primero, ejemplo después."""
    capsula = Microcapsula.model_validate(capsula_valida())

    bloques = capsula.bloques_legibles()

    assert bloques[-1] is capsula.ejemplo
    assert bloques[:-1] == capsula.representacion_adaptativa


def test_capsula_sin_fuentes_se_rechaza():
    """Sin material citado no es RAG: es el modelo respondiendo de memoria."""
    datos = capsula_valida()
    datos["fuentes"] = []

    resultado = validar_capsula(datos)

    assert not resultado.es_valida
    assert any("fuentes" in e for e in resultado.errores)


# --- Regla 2: extensión 150–300 palabras (cap. 11.1) -------------------------


def test_contenido_demasiado_corto_se_rechaza():
    datos = capsula_valida()
    datos["concepto_central"] = "Muy breve."
    datos["representacion_adaptativa"] = [{"tipo": "parrafo", "cuerpo": "También breve."}]
    datos["ejemplo"] = {"tipo": "parrafo", "cuerpo": "Un caso."}

    resultado = validar_capsula(datos)

    assert not resultado.es_valida
    assert any("mínimo es 150" in e for e in resultado.errores)


def test_contenido_demasiado_largo_se_rechaza():
    datos = capsula_valida()
    datos["representacion_adaptativa"] = [
        {"tipo": "parrafo", "cuerpo": PARRAFO},
        {"tipo": "parrafo", "cuerpo": EXPLICACION},
        {"tipo": "parrafo", "cuerpo": PARRAFO},
    ]

    resultado = validar_capsula(datos)

    assert not resultado.es_valida
    assert any("máximo es 300" in e for e in resultado.errores)


def test_los_cuatro_pasos_del_cuerpo_suman_para_el_rango():
    """La cuenta incluye activación, concepto, representación y ejemplo.

    Si solo contara uno de ellos, una cápsula podría pasar el rango con tres
    secciones casi vacías.
    """
    datos = capsula_valida()
    base = validar_capsula(datos).metricas["palabras_contenido"]

    datos["activacion"] = datos["activacion"] + " ¿Y en tu experiencia?"
    assert validar_capsula(datos).metricas["palabras_contenido"] == base + 4


def test_el_encabezado_cuenta_como_contenido_leido():
    """El rango del cap. 11.1 mide tiempo de consumo, no solo prosa."""
    sin = BloqueContenido(tipo="parrafo", cuerpo="uno dos tres")
    con = BloqueContenido(tipo="parrafo", encabezado="Título del bloque", cuerpo="uno dos tres")

    assert con.palabras() == sin.palabras() + 3


def test_la_actividad_no_cuenta_para_el_rango_de_palabras():
    """El plan §3 dice `contar_palabras(contenido)`: el quiz se mide aparte."""
    datos = capsula_valida()
    base = validar_capsula(datos).metricas["palabras_contenido"]

    datos["actividad"]["retroalimentacion"] += " " + EXPLICACION
    assert validar_capsula(datos).metricas["palabras_contenido"] == base


def test_la_desviacion_respecto_del_objetivo_se_mide_pero_no_rechaza():
    """`palabras_texto` es la meta del perfil; 150–300 es el límite duro.

    Rechazar por no dar en la meta agotaría los dos reintentos en cápsulas que
    el informe considera válidas. La desviación se registra para la tabla
    comparativa de modelos de la Fase 3.
    """
    resultado = validar(capsula_valida(), fragmentos=FRAGMENTOS, palabras_objetivo=300)

    assert resultado.es_valida
    assert resultado.metricas["desviacion_palabras"] < 0


# --- Regla 5: citas verificables (cap. 13) -----------------------------------


def test_cita_a_un_fragmento_no_inyectado_se_rechaza():
    """Es la detección de citas alucinadas que advierte Hashiyada et al."""
    datos = capsula_valida()
    datos["fuentes"] = [{"id_fragmento": 999, "documento": "Apunte inventado", "pagina": 3}]

    resultado = validar_capsula(datos)

    assert not resultado.es_valida
    assert any("999" in e for e in resultado.errores)
    # El mensaje tiene que decir cuáles sí puede citar, o el reintento adivina.
    assert any("161" in e and "162" in e for e in resultado.errores)


def test_la_procedencia_la_afirma_el_sistema_no_el_modelo():
    """Documento y página se reescriben desde la base.

    El modelo acertó el `id_fragmento` pero inventó el título del documento y
    la página. La cápsula queda con la procedencia real, que es lo que hace
    verificable la trazabilidad del cap. 13.
    """
    datos = capsula_valida()
    datos["fuentes"] = [
        {"id_fragmento": 162, "documento": "Otro apunte cualquiera", "pagina": 99}
    ]

    resultado = validar_capsula(datos)

    assert resultado.es_valida
    fuente = resultado.capsula.fuentes[0]
    assert fuente.documento == DOCUMENTO
    assert fuente.pagina == 13
    assert resultado.metricas["citas_corregidas"] == 1


def test_las_citas_repetidas_se_deduplican_conservando_el_orden():
    datos = capsula_valida()
    datos["fuentes"] = [
        {"id_fragmento": 162, "documento": "x", "pagina": 1},
        {"id_fragmento": 161, "documento": "x", "pagina": 1},
        {"id_fragmento": 162, "documento": "x", "pagina": 1},
    ]

    resultado = validar_capsula(datos)

    assert [f.id_fragmento for f in resultado.capsula.fuentes] == [162, 161]


# --- Regla 6: idioma español -------------------------------------------------


def test_texto_en_espanol_se_acepta():
    assert idioma.analizar(PARRAFO).es_espanol


def test_texto_en_ingles_se_rechaza():
    analisis = idioma.analizar(
        "Normalization is the process that organizes the attributes of a "
        "relational database to reduce redundancy. Each normal form adds a "
        "condition on top of the previous one, so that a table which is in "
        "third normal form also satisfies the first two of them."
    )

    assert not analisis.es_espanol
    assert "inglés" in analisis.motivo


def test_texto_con_caracteres_chinos_se_rechaza():
    """Es el riesgo declarado del stack: los tres modelos candidatos son chinos."""
    analisis = idioma.analizar("La normalización 是一个过程 que organiza los datos.")

    assert not analisis.es_espanol
    assert "CJK" in analisis.motivo
    assert analisis.caracteres_cjk > 0


def test_espanol_tecnico_con_palabras_clave_sql_no_es_falso_positivo():
    """El caso que rompería un detector ingenuo.

    Una cápsula legítima sobre SQL contiene SELECT, FROM, WHERE, ON y JOIN.
    Varias de esas son también palabras funcionales del inglés, así que están
    deliberadamente fuera de la lista de marcadores (ver `idioma.py`).
    """
    analisis = idioma.analizar(
        "Para consultar las filas de la tabla se escribe SELECT nombre FROM "
        "estudiante WHERE carrera = 'Informática'. La cláusula JOIN combina dos "
        "tablas cuando la clave foránea de una coincide con la clave primaria "
        "de la otra, y el resultado conserva solo las filas que cumplen la "
        "condición indicada en ON."
    )

    assert analisis.es_espanol, analisis.motivo


def test_capsula_esquematica_con_pocas_palabras_funcionales_se_acepta():
    """Un perfil visual puede recibir casi puras tablas y glosario.

    Ahí el ratio de palabras funcionales cae, y sin el escape por ortografía
    española sería un falso rechazo.
    """
    analisis = idioma.analizar(
        "1FN: valores atómicos. 2FN: sin dependencias parciales. "
        "3FN: sin dependencias transitivas. Clave foránea. Índice único."
    )

    assert analisis.es_espanol, analisis.motivo


def test_las_tildes_faltantes_no_se_confunden_con_otro_idioma():
    """Omitir tildes es un problema ortográfico, no una deriva de idioma."""
    assert idioma.es_espanol(
        "La normalizacion organiza los atributos de una base de datos "
        "relacional para reducir la redundancia y evitar anomalias cuando se "
        "insertan o se eliminan filas de la tabla."
    )


def test_capsula_redactada_en_ingles_se_rechaza_por_la_regla_6():
    datos = capsula_valida()
    datos["activacion"] = "Have you ever had to fix the same value in many rows?"
    datos["concepto_central"] = (
        "Normalization is the process that organizes the attributes of "
        "a relational database in order to reduce redundancy and to "
        "avoid anomalies when rows are inserted, updated or deleted "
        "from the table. Each normal form adds one condition on top of "
        "the previous one, so that a table which is in third normal "
        "form also satisfies the first two forms."
    )
    datos["representacion_adaptativa"] = [
        {
            "tipo": "parrafo",
            "cuerpo": (
                "The goal is not to have many tables, but that each fact is "
                "stored only once and in the place where it truly belongs, "
                "next to the key which determines it. When this is done well, "
                "any correction has to be applied at a single point and every "
                "query that reads the data will see the corrected value "
                "immediately, because there are no stale copies left behind."
            ),
        }
    ]

    resultado = validar_capsula(datos)

    assert not resultado.es_valida
    assert any("español" in e for e in resultado.errores)
    assert resultado.metricas["idioma_ok"] is False


# --- Parser tolerante --------------------------------------------------------


def test_extrae_json_envuelto_en_cercas_markdown():
    crudo = '```json\n{"titulo": "x"}\n```'

    assert extraer_json(crudo) == {"titulo": "x"}


def test_extrae_json_con_preambulo_del_modelo():
    """Los modelos anteponen frases pese a la instrucción de responder solo JSON."""
    crudo = 'Claro, aquí está el JSON solicitado:\n\n{"titulo": "x"}\n\n¡Espero que sirva!'

    assert extraer_json(crudo) == {"titulo": "x"}


def test_una_llave_dentro_de_una_cadena_no_confunde_al_parser():
    """El caso que rompe un contador de llaves ingenuo."""
    crudo = '{"cuerpo": "el conjunto {a, b} tiene dos elementos", "n": 2}'

    assert extraer_json(crudo)["n"] == 2


def test_una_llave_escapada_dentro_de_una_cadena_tampoco():
    crudo = '{"cuerpo": "comillas \\" y llave {", "n": 3}'

    assert extraer_json(crudo)["n"] == 3


def test_la_coma_colgante_se_repara_sin_gastar_un_reintento():
    crudo = '{"lista": [1, 2, 3,], "n": 1,}'

    assert extraer_json(crudo) == {"lista": [1, 2, 3], "n": 1}


def test_respuesta_truncada_avisa_que_se_trunco():
    """Distinguir truncamiento de JSON mal formado ahorra depurar a ciegas:
    lo primero se arregla subiendo `max_tokens`, lo segundo cambiando el prompt."""
    with pytest.raises(ErrorFormatoJSON, match="truncó"):
        extraer_json('{"titulo": "x", "contenido": [{"tipo": "parrafo"')


def test_respuesta_sin_json_se_rechaza_con_mensaje_claro():
    with pytest.raises(ErrorFormatoJSON, match="no contiene ningún objeto JSON"):
        extraer_json("No puedo ayudarte con esa solicitud.")


def test_respuesta_no_parseable_se_reporta_como_error_no_como_excepcion():
    """El generador necesita un resultado con errores, no un crash."""
    resultado = validar("esto no es JSON", fragmentos=FRAGMENTOS)

    assert not resultado.es_valida
    assert resultado.capsula is None
    assert resultado.metricas["parseo"] is False


# --- Realimentación al bucle de reparación -----------------------------------


def test_el_mensaje_de_reparacion_enumera_todos_los_defectos():
    """Corregir de a uno agotaría los dos reintentos disponibles."""
    datos = capsula_valida()
    datos["concepto_central"] = "Muy breve."
    datos["representacion_adaptativa"] = [{"tipo": "parrafo", "cuerpo": "También breve."}]
    datos["ejemplo"] = {"tipo": "parrafo", "cuerpo": "Un caso."}
    datos["fuentes"] = [{"id_fragmento": 999, "documento": "x", "pagina": 1}]

    resultado = validar_capsula(datos)
    mensaje = resultado.mensaje_para_reparacion()

    assert len(resultado.errores) == 2
    assert "1." in mensaje and "2." in mensaje
    assert "999" in mensaje
    assert "español" in mensaje  # recuerda el idioma en cada reintento


def test_el_error_de_esquema_llega_en_espanol():
    """El mensaje se reinyecta en el prompt; en inglés empujaría la deriva
    de idioma que la regla 6 justamente persigue."""
    datos = capsula_valida()
    del datos["titulo"]

    resultado = validar_capsula(datos)

    assert resultado.errores == ["campo 'titulo': falta este campo obligatorio"]


# --- Invariantes del contrato ------------------------------------------------


def test_el_texto_plano_incluye_la_actividad():
    """La deriva al inglés suele empezar en lo que el modelo redacta al final."""
    capsula = Microcapsula.model_validate(capsula_valida())
    plano = capsula.texto_plano()

    assert "¿Cuándo una tabla incumple" in plano
    assert "La segunda forma normal exige" in plano


def test_validar_no_muta_el_diccionario_de_entrada():
    datos = capsula_valida()
    original = copy.deepcopy(datos)

    validar_capsula(datos)

    assert datos == original


def test_actividad_acepta_entre_tres_y_cinco_alternativas():
    base = {
        "tipo": "quiz_mc",
        "pregunta": "¿Cuál corresponde?",
        "indice_correcta": 0,
        "retroalimentacion": "Porque sí corresponde.",
    }

    Actividad(**base, alternativas=["una", "dos", "tres"])
    Actividad(**base, alternativas=["una", "dos", "tres", "cuatro", "cinco"])

    with pytest.raises(ValidationError, match="alternativas"):
        Actividad(**base, alternativas=["una", "dos"])
