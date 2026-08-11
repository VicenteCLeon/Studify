"""Tests del prompt maestro y del ensamblado (Fase 3).

Dos de estos tests existen para detectar **desincronización entre módulos**, que
es el tipo de fallo que no produce ningún error y sí cápsulas peores:

- `test_toda_directiva_de_rules_tiene_instruccion`: si alguien agrega una regla
  a `vark/rules.py` y no la traduce en `rag/prompts/maestro.py`, ese elemento
  del perfil desaparece de la cápsula sin dejar rastro.
- `test_el_prompt_describe_todos_los_campos_del_contrato`: si el contrato de
  `generation/schemas.py` cambia y el prompt no, el modelo entrega un JSON que
  el validador rechaza siempre, y se gastan los dos reintentos en cada llamada.

No requieren Postgres ni `LLM_API_KEY`: el ensamblado es puro.
"""

from decimal import Decimal
from itertools import product

import pytest
from material import DOCUMENTO, FRAGMENTOS, OBJETIVO

from studify.generation.schemas import Actividad, Fuente, Microcapsula
from studify.rag import orchestrator, prompts
from studify.rag.orchestrator import ErrorPrompt
from studify.vark.rules import aplicar_reglas
from studify.vark.scoring import PerfilVark

D = Decimal


def perfil(v: int, a: int, r: int, k: int) -> PerfilVark:
    return PerfilVark(v=D(v), a=D(a), r=D(r), k=D(k))


def construir(p: PerfilVark, fragmentos=None, modelo: str = "deepseek-chat"):
    return orchestrator.construir(
        objetivo=OBJETIVO,
        fragmentos=FRAGMENTOS if fragmentos is None else fragmentos,
        config=aplicar_reglas(p),
        modelo=modelo,
    )


# --- Sincronía entre módulos -------------------------------------------------


def _todas_las_directivas_posibles() -> set[str]:
    """Barrido del símplex en pasos de 10, igual que se hizo en la Fase 1.

    Se enumeran por fuerza bruta en vez de leer una lista para que el test siga
    valiendo si alguien agrega una regla nueva a `vark/rules.py`.
    """
    directivas: set[str] = set()
    for v, a, r in product(range(0, 101, 10), repeat=3):
        if v + a + r > 100:
            continue
        directivas.update(aplicar_reglas(perfil(v, a, r, 100 - v - a - r)).directivas)
    return directivas


def test_toda_directiva_de_rules_tiene_instruccion_en_el_prompt():
    """Una directiva sin instrucción se pierde en silencio."""
    sin_instruccion = _todas_las_directivas_posibles() - set(
        prompts.INSTRUCCION_POR_DIRECTIVA
    )

    assert not sin_instruccion, (
        f"estas directivas de vark/rules.py no tienen instrucción en "
        f"rag/prompts/maestro.py: {sorted(sin_instruccion)}"
    )


def test_el_prompt_describe_todos_los_campos_del_contrato():
    """El esquema del prompt y el de Pydantic tienen que nombrar lo mismo."""
    esperados = (
        set(Microcapsula.model_fields)
        | set(Actividad.model_fields)
        | set(Fuente.model_fields)
    )
    formato = orchestrator.bloque_formato()

    faltantes = {campo for campo in esperados if campo not in formato}

    assert not faltantes, (
        f"el bloque de formato no menciona estos campos del contrato: "
        f"{sorted(faltantes)}. El modelo no puede entregar lo que no se le pide."
    )


def test_todo_tono_de_rules_tiene_descripcion():
    from studify.vark import rules

    tonos = {
        rules.TONO_ORAL,
        rules.TONO_FORMAL,
        rules.TONO_PRACTICO,
        rules.TONO_ESPACIAL,
        rules.TONO_MIXTO,
    }

    assert tonos <= set(prompts.DESCRIPCION_TONO)


def test_una_directiva_sin_instruccion_levanta_error_en_vez_de_omitirse():
    """Aunque el test anterior lo previene, el fallo no puede ser silencioso."""
    config = aplicar_reglas(perfil(0, 0, 0, 100))
    roto = type(config)(
        **{**{c: getattr(config, c) for c in config.__slots__}, "directivas": ("inventada",)}
    )

    with pytest.raises(ErrorPrompt, match="inventada"):
        orchestrator.bloque_perfil(roto, palabras_objetivo=200)


# --- La diferenciación entre perfiles ----------------------------------------


def test_los_cuatro_perfiles_producen_prompts_distintos():
    """Es la condición previa al criterio de término de la Fase 3.

    Si los prompts fueran iguales, las cuatro cápsulas saldrían indistinguibles
    por construcción y no habría nada que ajustar después en el modelo.
    """
    prompts_por_canal = {
        canal: construir(p).usuario
        for canal, p in {
            "V": perfil(100, 0, 0, 0),
            "A": perfil(0, 100, 0, 0),
            "R": perfil(0, 0, 100, 0),
            "K": perfil(0, 0, 0, 100),
        }.items()
    }

    textos = list(prompts_por_canal.values())
    assert len(set(textos)) == 4, "dos perfiles generan exactamente el mismo prompt"


def test_la_diferencia_entre_perfiles_es_estructural_y_no_de_tono():
    """El riesgo del plan §5 se mitiga pidiendo bloques, no adjetivos."""
    visual = orchestrator.bloque_perfil(
        aplicar_reglas(perfil(100, 0, 0, 0)), palabras_objetivo=200
    )
    lector = orchestrator.bloque_perfil(
        aplicar_reglas(perfil(0, 0, 100, 0)), palabras_objetivo=200
    )

    # Se comparan las instrucciones, no la cabecera: la línea "Recursos
    # visuales (bloques `tabla` o `esquema`): N" aparece en los cuatro perfiles
    # con la cantidad que corresponda, así que buscar el tipo suelto no
    # distingue nada.
    tabla = prompts.INSTRUCCION_POR_DIRECTIVA["tabla_comparativa"]
    mapa = prompts.INSTRUCCION_POR_DIRECTIVA["incluir_mapa_conceptual"]
    glosario = prompts.INSTRUCCION_POR_DIRECTIVA["glosario"]
    definiciones = prompts.INSTRUCCION_POR_DIRECTIVA["definiciones_exactas"]

    assert tabla in visual and mapa in visual
    assert glosario not in visual and definiciones not in visual

    assert glosario in lector and definiciones in lector
    assert tabla not in lector and mapa not in lector

    # Y la cantidad de recursos visuales cae a cero para el lector-escritor.
    assert "Recursos visuales (bloques `tabla` o `esquema`): 2" in visual
    assert "Recursos visuales (bloques `tabla` o `esquema`): 0" in lector


def test_el_perfil_kinestesico_cambia_el_tipo_de_actividad_de_cierre():
    """`p_K ≥ 40%` convierte el quiz en un ejercicio aplicado (tabla 11.1)."""
    kinestesico = orchestrator.bloque_perfil(
        aplicar_reglas(perfil(0, 0, 0, 100)), palabras_objetivo=200
    )
    lector = orchestrator.bloque_perfil(
        aplicar_reglas(perfil(0, 0, 100, 0)), palabras_objetivo=200
    )

    assert "intentalo_tu" in kinestesico
    assert "intentalo_tu" not in lector


def test_el_prompt_no_le_dice_al_modelo_la_etiqueta_del_perfil():
    """El cap. 17.2 prohíbe persistir la etiqueta; el prompt tampoco la usa.

    Además, nombrar el canal invita al modelo a comentar el estilo de
    aprendizaje del estudiante en vez de aplicarlo.
    """
    texto = construir(perfil(0, 0, 0, 100)).usuario.lower()

    for etiqueta in ("kinestésico", "kinestesico", "visual,", "perfil vark"):
        assert etiqueta not in texto


def test_el_numero_de_recursos_sale_de_la_configuracion():
    """`recursos_visuales` y `componentes_practicos` llegan como cantidad exacta."""
    texto = orchestrator.bloque_perfil(
        aplicar_reglas(perfil(100, 0, 0, 0)), palabras_objetivo=200
    )

    # p_V = 100 ≥ 40 → dos recursos visuales (tabla 11.1, fila 1).
    assert "Recursos visuales (bloques `tabla` o `esquema`): 2" in texto


def test_los_componentes_practicos_no_se_piden_como_bloques_de_contenido():
    """Con p_K ≥ 40% la tabla 11.1 cuenta tres componentes prácticos, pero el
    tercero es la actividad de cierre, que no es un bloque de `contenido`.

    Pedir «3 bloques» dejaría al modelo con dos instrucciones de bloque y una
    cuenta que solo cuadra inventándose un tercero.
    """
    config = aplicar_reglas(perfil(0, 0, 0, 100))
    texto = orchestrator.bloque_perfil(config, palabras_objetivo=200)

    assert config.componentes_practicos == 3
    assert "Componentes prácticos, contando los bloques aplicados y la actividad" in texto
    # Y las instrucciones que sí nombran bloques son solo dos.
    bloques = [d for d in config.directivas if d in ("ejemplo_resuelto", "paso_a_paso")]
    assert len(bloques) == 2


# --- Bloque de contexto ------------------------------------------------------


def test_cada_fragmento_entra_con_el_id_que_hay_que_citar():
    contexto = orchestrator.bloque_contexto(FRAGMENTOS)

    assert "id_fragmento: 161" in contexto
    assert "id_fragmento: 162" in contexto


def test_la_procedencia_del_fragmento_viaja_en_el_prompt():
    """El modelo necesita la cita para poder devolverla en `fuentes`."""
    contexto = orchestrator.bloque_contexto(FRAGMENTOS)

    assert f"{DOCUMENTO}, p. 12" in contexto
    assert f"{DOCUMENTO}, pp. 13–14" in contexto


def test_sin_fragmentos_no_se_construye_prompt():
    """Generar sin material es pedirle al modelo que responda de memoria."""
    with pytest.raises(ErrorPrompt, match="sin material"):
        orchestrator.bloque_contexto([])


def test_los_fragmentos_viajan_con_el_prompt_para_validar_contra_los_mismos():
    """La regla 5 solo es exacta si prompt y validación miran el mismo conjunto."""
    maestro = construir(perfil(0, 0, 0, 100))

    assert [f.id_fragmento for f in maestro.fragmentos] == [161, 162]


# --- Huella de caché ---------------------------------------------------------


def test_la_huella_es_estable_entre_llamadas_identicas():
    assert construir(perfil(0, 0, 0, 100)).huella == construir(perfil(0, 0, 0, 100)).huella


def test_perfiles_distintos_dan_huellas_distintas():
    assert construir(perfil(100, 0, 0, 0)).huella != construir(perfil(0, 0, 0, 100)).huella


def test_material_nuevo_invalida_el_cache():
    """Si el docente cura un fragmento más, la cápsula cacheada quedó obsoleta."""
    completo = construir(perfil(0, 0, 0, 100))
    parcial = construir(perfil(0, 0, 0, 100), fragmentos=FRAGMENTOS[:1])

    assert completo.huella != parcial.huella


def test_el_orden_de_los_fragmentos_no_cambia_la_huella():
    """Los mismos fragmentos son el mismo material, los ordene como los ordene."""
    directo = construir(perfil(0, 0, 0, 100))
    invertido = construir(perfil(0, 0, 0, 100), fragmentos=list(reversed(FRAGMENTOS)))

    assert directo.huella == invertido.huella


def test_el_modelo_entra_en_la_huella():
    """El bake-off corre la misma configuración contra tres modelos.

    Sin el modelo en la clave, el segundo leería del caché la cápsula del
    primero y la comparación no mediría nada.
    """
    uno = construir(perfil(0, 0, 0, 100), modelo="deepseek-chat")
    otro = construir(perfil(0, 0, 0, 100), modelo="qwen-plus")

    assert uno.huella != otro.huella


def test_dos_perfiles_casi_iguales_comparten_cache():
    """El redondeo a tramos de 10 palabras es lo que hace útil el caché.

    Sin él, dos estudiantes cuyo `palabras_texto` difiere en una palabra
    pagarían dos generaciones para una cápsula idéntica.
    """
    uno = aplicar_reglas(perfil(0, 0, 100, 0))
    otro = aplicar_reglas(perfil(1, 0, 99, 0))

    assert uno.palabras_texto != otro.palabras_texto  # el perfil sí cambia
    assert construir(perfil(0, 0, 100, 0)).huella == construir(perfil(1, 0, 99, 0)).huella


# --- Invariantes del prompt completo -----------------------------------------


def test_el_prompt_lleva_los_cuatro_bloques():
    maestro = construir(perfil(25, 25, 25, 25))

    for encabezado in (
        "Objetivo de aprendizaje a cubrir",
        "Material curado disponible",
        "Cómo debe estar construida esta cápsula",
        "Formato de la respuesta",
    ):
        assert encabezado in maestro.usuario


def test_el_prompt_exige_espanol_en_sistema_y_en_formato():
    """La deriva de idioma se ataca en los dos extremos del prompt."""
    maestro = construir(perfil(25, 25, 25, 25))

    assert "español" in maestro.sistema
    assert "español" in maestro.usuario


def test_el_prompt_prohibe_citar_identificadores_no_entregados():
    """Es la contraparte de la regla 5 del validador."""
    assert "Inventar un identificador" in construir(perfil(25, 25, 25, 25)).sistema
