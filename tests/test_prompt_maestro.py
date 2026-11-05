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

from dataclasses import replace
from decimal import Decimal
from itertools import product

import pytest

from studify.db.models import ObjetivoAprendizaje
from studify.generation.schemas import Actividad, Fuente, Microcapsula
from studify.rag import orchestrator, prompts
from studify.rag.orchestrator import ErrorPrompt
from studify.vark.rules import aplicar_reglas
from studify.vark.scoring import PerfilVark
from tests.material import DOCUMENTO, FRAGMENTOS, OBJETIVO

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
    """`p_K ≥ 40%` exige `flashcards_y_quiz` como actividad de cierre (tabla 11.1).

    Desde `1dc5286` la directiva de actividad aplicada ya no pide `intentalo_tu`
    sino `flashcards_y_quiz`. El test mira el bloque del prompt, no el contrato:
    `intentalo_tu` sigue siendo un tipo válido de `Actividad`.
    """
    kinestesico = orchestrator.bloque_perfil(
        aplicar_reglas(perfil(0, 0, 0, 100)), palabras_objetivo=200
    )
    lector = orchestrator.bloque_perfil(
        aplicar_reglas(perfil(0, 0, 100, 0)), palabras_objetivo=200
    )

    assert "flashcards_y_quiz" in kinestesico
    assert "flashcards_y_quiz" not in lector


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


def test_editar_el_texto_de_un_fragmento_invalida_el_cache():
    """Los mismos ids con otro texto son otro material.

    El docente puede corregir un fragmento ya validado (`curation.editar_texto`).
    Si la huella solo mirara los ids, se seguiría sirviendo la cápsula escrita
    sobre el texto viejo, mientras las referencias del visor muestran el nuevo.
    """
    editado = [replace(FRAGMENTOS[0], texto=FRAGMENTOS[0].texto + " Corrección."), *FRAGMENTOS[1:]]

    original = construir(perfil(0, 0, 0, 100))
    corregido = construir(perfil(0, 0, 0, 100), fragmentos=editado)

    assert original.huella != corregido.huella


def test_cambiar_la_procedencia_de_un_fragmento_invalida_el_cache():
    """El título del documento y la página van en el prompt (la cita del fragmento)."""
    otra_pagina = [replace(FRAGMENTOS[0], pagina_inicio=99, pagina_fin=99), *FRAGMENTOS[1:]]

    assert construir(perfil(0, 0, 0, 100)).huella != construir(
        perfil(0, 0, 0, 100), fragmentos=otra_pagina
    ).huella


def test_cambiar_una_instruccion_del_prompt_invalida_el_cache(monkeypatch):
    """Una corrección del prompt (H1, H12) tiene que llegar a quien pide la cápsula.

    Con la huella vieja, cualquier tramo que ya tuviera una cápsula —propia o
    copiada del caché compartido— la seguía recibiendo escrita con el texto
    anterior del prompt.
    """
    antes = construir(perfil(0, 0, 100, 0)).huella
    monkeypatch.setitem(
        prompts.INSTRUCCION_POR_DIRECTIVA,
        "glosario",
        "El último bloque de `representacion_adaptativa` es un bloque `glosario`.",
    )

    assert construir(perfil(0, 0, 100, 0)).huella != antes


def test_cambiar_las_reglas_del_sistema_invalida_el_cache(monkeypatch):
    antes = construir(perfil(0, 0, 0, 100)).huella
    monkeypatch.setattr(prompts, "SISTEMA", prompts.SISTEMA + "\n5. Regla nueva.")

    assert construir(perfil(0, 0, 0, 100)).huella != antes


def test_cambiar_la_descripcion_del_objetivo_invalida_el_cache():
    """La descripción del objetivo va en el bloque de la tarea."""
    otro = ObjetivoAprendizaje(
        id_objetivo=OBJETIVO.id_objetivo,
        codigo_objetivo=OBJETIVO.codigo_objetivo,
        asignatura=OBJETIVO.asignatura,
        unidad=OBJETIVO.unidad,
        tema=OBJETIVO.tema,
        descripcion="Otra descripción del objetivo.",
    )
    config = aplicar_reglas(perfil(0, 0, 0, 100))
    original = orchestrator.construir(
        objetivo=OBJETIVO, fragmentos=FRAGMENTOS, config=config, modelo="deepseek-chat"
    )
    cambiado = orchestrator.construir(
        objetivo=otro, fragmentos=FRAGMENTOS, config=config, modelo="deepseek-chat"
    )

    assert original.huella != cambiado.huella


def test_misma_huella_es_el_mismo_prompt_salvo_los_pesos():
    """La única diferencia que la huella ignora a propósito son los pesos C_*.

    Van al prompt para indicar cuánto énfasis lleva cada canal (H13), pero son
    continuos: si entraran a la huella, casi cada estudiante tendría la suya y
    el caché compartido por tramo dejaría de servir. Este test fija esa
    excepción para que no aparezca otra sin que nadie lo decida.
    """
    uno = construir(perfil(0, 0, 100, 0))
    otro = construir(perfil(1, 0, 99, 0))

    def sin_pesos(texto: str) -> str:
        nombres = ("- Texto:", "- Visual:", "- Narrativo:", "- Práctico:")
        return "\n".join(ln for ln in texto.splitlines() if not ln.startswith(nombres))

    assert uno.huella == otro.huella
    assert uno.usuario != otro.usuario
    assert sin_pesos(uno.usuario) == sin_pesos(otro.usuario)
    assert uno.sistema == otro.sistema


def test_el_objetivo_de_palabras_no_llega_pegado_al_maximo():
    """Pendiente n.º 15 de AVANCE.md, investigado el 24-ago-2026.

    `aplicar_reglas` interpola el perfil lector-escritor puro exactamente en
    300 palabras — el mismo número que `capsula_max_palabras` — porque su
    C_texto (0.75) es el máximo de la matriz del cap. 11.2. Pedirle al modelo
    "apunta a 300, no pases de 300" no deja margen para la variación normal de
    redacción; contra el modelo real, ese perfil falló la validación 3 de 4
    veces por exceso de palabras mientras los otros tres no fallaron ninguna.
    `construir` tiene que pedir un número por debajo del techo real, sin tocar
    el `palabras_texto` que persiste `vark/rules.py` (el que sí está en
    tabla 17.4 y quedó aprobado por el equipo el 06-ago-2026).
    """
    puro = aplicar_reglas(perfil(0, 0, 100, 0))
    assert puro.palabras_texto == 300  # sigue igual: no se tocó rules.py

    maestro = construir(perfil(0, 0, 100, 0))
    assert maestro.palabras_objetivo < 300
    assert f"aproximadamente {maestro.palabras_objetivo} palabras" in maestro.usuario
    # El máximo duro se sigue mostrando tal cual: solo el objetivo baja, el
    # techo real que exige el validador no se le oculta al modelo.
    assert "máximo 300" in maestro.usuario


def test_el_margen_de_seguridad_no_afecta_a_los_perfiles_que_no_lo_necesitan():
    """Solo el tramo alto (cerca del techo real) se ve afectado por el margen."""
    for vector in [(100, 0, 0, 0), (0, 100, 0, 0), (0, 0, 0, 100), (25, 25, 25, 25)]:
        config = aplicar_reglas(perfil(*vector))
        maestro = construir(perfil(*vector))
        # Ninguno de estos perfiles se acerca al techo, así que el objetivo que
        # entra al prompt es el mismo que sin margen (redondeado a tramos de 10).
        assert maestro.palabras_objetivo == round(config.palabras_texto / 10) * 10


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


# --- Huella experimental fija (grupo control neutro, 04-nov-2026) -------------

# Calculadas sobre el código de `0808a35`, ANTES de agregar las plantillas del
# grupo control. Si cambian, todas las cápsulas experimentales ya guardadas
# dejan de reutilizarse del caché: cualquier cambio del control tiene que
# dejarlas idénticas. Se fijan también el prompt completo (sistema + usuario),
# para que el texto que ve el modelo no cambie aunque la huella coincidiera.
HUELLAS_EXPERIMENTALES = {
    # Actualizada a propósito el 05-nov-2026 (punto 1c): la huella de los
    # perfiles con `actividad_aplicada` incluye la actividad exigida, para que
    # sus cápsulas guardadas que no cumplen se regeneren. Antes era
    # 5f7581c309ccd02c23a1e49c23c548dc4498de4286c911546312c37546a0c169. El
    # prompt (segunda cifra) no cambió.
    (0, 0, 0, 100): (
        "e110421a949c7d17f197edf01f3f06502d82f68167d416f43f9f036d7f04f094",
        "f5c000e8fba52ccf382bd8914ea286f4e1d7c2dd57cd5fc159155798aa35c987",
    ),
    (30, 30, 20, 20): (
        "bb374eb9ebfb82b0c7b637f56693a6bf7158904f5a2efca1ae52bd5ec7c7831c",
        "33249036c61eb70b237ea57d1c08dcbdfd75ef70c3019c98730ac65be96bb1cf",
    ),
}


@pytest.mark.parametrize("vector", sorted(HUELLAS_EXPERIMENTALES))
def test_huella_y_prompt_experimentales_no_cambian(vector):
    import hashlib

    from studify.config import get_settings

    # Las cifras de arriba se calcularon con el rango 150–300 de `.env.example`.
    ajustes = get_settings()
    assert (ajustes.capsula_min_palabras, ajustes.capsula_max_palabras) == (150, 300)

    maestro = construir(perfil(*vector))
    huella, texto = HUELLAS_EXPERIMENTALES[vector]
    assert maestro.huella == huella
    completo = f"{maestro.sistema}\x1f{maestro.usuario}"
    assert hashlib.sha256(completo.encode()).hexdigest() == texto


# --- Actividad exigida por directiva (punto 1c, 05-nov-2026) ------------------

# Resúmenes del barrido del símplex (pasos de 10, 286 perfiles) calculados sobre
# `a75a798`, ANTES del punto 1c. Los perfiles sin `actividad_aplicada` (202) y
# el control neutro conservan la huella; ningún prompt cambia; los 84 perfiles
# con la directiva cambian de huella a propósito.
DIGEST_HUELLAS_SIN_ACTIVIDAD = "7418ae82205afa1619e061da8b09c85caa83590613f9b3b81754d467ab6b8171"
DIGEST_HUELLAS_CON_ACTIVIDAD_ANTES = (
    "9d12690f204d91a63423491385817b9f4fb7c4fb5f21e3a8f756a24a42103dcb"
)
DIGEST_PROMPTS = "414150ced3006e6f7c793f1d7a8c6eabf26a2e116b1ab1db214e2020dc66bdb0"


def _barrido_del_simplex():
    for v, a, r in product(range(0, 101, 10), repeat=3):
        if v + a + r <= 100:
            yield (v, a, r, 100 - v - a - r)


def test_barrido_huellas_y_prompts_solo_cambian_los_perfiles_con_actividad():
    import hashlib

    from studify.config import get_settings
    from studify.vark.perfiles import VARIANTE_CONTROL

    ajustes = get_settings()
    assert (ajustes.capsula_min_palabras, ajustes.capsula_max_palabras) == (150, 300)

    def sha(texto: str) -> str:
        return hashlib.sha256(texto.encode()).hexdigest()

    sin, con, textos = [], [], []
    for vector in _barrido_del_simplex():
        config = aplicar_reglas(perfil(*vector))
        maestro = construir(perfil(*vector))
        textos.append(f"{vector}:{sha(maestro.sistema + chr(31) + maestro.usuario)}")
        destino = con if "actividad_aplicada" in config.directivas else sin
        destino.append(f"{vector}:{maestro.huella}")
    control = orchestrator.construir(
        objetivo=OBJETIVO, fragmentos=FRAGMENTOS, config=None,
        modelo="deepseek-chat", variante=VARIANTE_CONTROL,
    )
    sin.append(f"control:{control.huella}")
    textos.append(f"control:{sha(control.sistema + chr(31) + control.usuario)}")

    assert (len(sin), len(con)) == (203, 84)
    assert sha("\n".join(sin)) == DIGEST_HUELLAS_SIN_ACTIVIDAD
    assert sha("\n".join(textos)) == DIGEST_PROMPTS
    assert sha("\n".join(con)) != DIGEST_HUELLAS_CON_ACTIVIDAD_ANTES


def test_actividad_requerida_exactamente_con_la_directiva_actividad_aplicada():
    """Lo que el prompt exige es lo que el validador exige.

    En la grilla de 10 en 10 coincide con p_K ≥ 40. Fuera de ella, la regla de
    respaldo de `rules._directivas` también la da a perfiles sin ningún canal
    sobre 40 y con K como primario: (0, 23, 38, 39) es uno.
    """
    for vector in [*_barrido_del_simplex(), (0, 23, 38, 39)]:
        config = aplicar_reglas(perfil(*vector))
        maestro = construir(perfil(*vector))
        if "actividad_aplicada" in config.directivas:
            assert maestro.actividad_requerida == "flashcards_y_quiz", vector
            assert "DEBE SER `flashcards_y_quiz`" in maestro.usuario
        else:
            assert maestro.actividad_requerida is None, vector
        if vector != (0, 23, 38, 39):
            assert (maestro.actividad_requerida is not None) == (vector[3] >= 40), vector


def test_la_directiva_de_respaldo_tambien_exige_la_actividad():
    config = aplicar_reglas(perfil(0, 23, 38, 39))
    assert "actividad_aplicada" in config.directivas  # regla de respaldo, p_K < 40
    assert construir(perfil(0, 23, 38, 39)).actividad_requerida == "flashcards_y_quiz"


def test_toda_actividad_por_directiva_es_un_tipo_del_contrato():
    from typing import get_args

    from studify.generation.schemas import TipoActividad

    assert set(orchestrator.ACTIVIDAD_POR_DIRECTIVA.values()) <= set(get_args(TipoActividad))
    assert set(orchestrator.ACTIVIDAD_POR_DIRECTIVA) <= set(prompts.INSTRUCCION_POR_DIRECTIVA)
