"""Grupo control neutro: cápsula básica sin adaptación VARK (04-nov-2026).

El control recibe título, objetivo, un resumen en prosa del material y una
actividad `quiz_mc`, con los mismos fragmentos validados, el mismo modelo, las
mismas reglas de citas e idioma y el mismo bucle de reparación que el grupo
experimental. Lo que no recibe es nada que dependa de un perfil.

Estos tests son puros salvo los marcados con `necesita_bd`.
"""

import json
import re
from dataclasses import replace

import pytest
from pydantic import ValidationError

from studify.generation.generator import ErrorGeneracion, generar
from studify.generation.schemas import CapsulaBasica, Microcapsula, contar_palabras
from studify.generation.validator import validar
from studify.rag import orchestrator, prompts
from studify.vark.perfiles import (
    PERFIL_CONTROL,
    VARIANTE_CONTROL,
    VERSION_PERFIL_CONTROL,
)
from studify.vark.rules import aplicar_reglas
from tests.conftest import necesita_bd
from tests.material import DOCUMENTO, FRAGMENTOS, OBJETIVO, PARRAFO, capsula_valida
from tests.test_generador import ClienteFalso

# Palabras que delatarían adaptación o perfil en las instrucciones del control.
PROHIBIDAS = (
    "perfil",
    "estilo",
    "canal",
    "vark",
    "diagnostic",
    "adaptativ",
    "preferencia",
    "visual",
    "auditiv",
    "kinest",
    "narrativo",
    "práctico",
    "énfasis",
    "c_",
)


def prompt_control(fragmentos=None, modelo: str = "deepseek-chat"):
    return orchestrator.construir(
        objetivo=OBJETIVO,
        fragmentos=FRAGMENTOS if fragmentos is None else fragmentos,
        config=None,
        modelo=modelo,
        variante=VARIANTE_CONTROL,
    )


def capsula_basica() -> dict:
    """La cápsula del control: título, objetivo, resumen, quiz_mc y fuentes."""
    completa = capsula_valida()
    resumen = f"{PARRAFO} {PARRAFO}"  # ~170 palabras, dentro de 150–300
    return {
        "titulo": completa["titulo"],
        "objetivo_aprendizaje": completa["objetivo_aprendizaje"],
        "concepto_central": resumen,
        "actividad": completa["actividad"],
        "fuentes": completa["fuentes"],
    }


def json_de(datos: dict) -> str:
    return json.dumps(datos, ensure_ascii=False)


# --- Contrato: CapsulaBasica --------------------------------------------------


def test_capsula_basica_valida_sin_campos_adaptativos():
    capsula = CapsulaBasica.model_validate(capsula_basica())

    assert capsula.activacion == ""
    assert capsula.representacion_adaptativa == []
    assert capsula.ejemplo is None
    assert capsula.bloques_legibles() == []
    # La extensión se cuenta solo sobre el resumen.
    assert capsula.palabras_contenido() == contar_palabras(capsula.concepto_central)
    assert 150 <= capsula.palabras_contenido() <= 300
    # Se guarda con las mismas claves que una cápsula completa.
    volcado = capsula.model_dump()
    assert volcado["activacion"] == ""
    assert volcado["representacion_adaptativa"] == []
    assert volcado["ejemplo"] is None


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("representacion_adaptativa", [{"tipo": "tabla", "cuerpo": [["a", "b"], ["c", "d"]]}]),
        ("ejemplo", {"tipo": "ejemplo_resuelto", "cuerpo": "Un caso resuelto."}),
        ("activacion", "¿Qué sabes de la normalización?"),
    ],
)
def test_capsula_basica_rechaza_elementos_adaptativos(campo, valor):
    datos = capsula_basica() | {campo: valor}

    with pytest.raises(ValidationError, match=campo):
        CapsulaBasica.model_validate(datos)


def test_la_capsula_completa_sigue_exigiendo_sus_siete_pasos():
    """El experimental no se relaja: `Microcapsula` sigue rechazando la básica."""
    with pytest.raises(ValidationError):
        Microcapsula.model_validate(capsula_basica())


# --- Prompt del control -------------------------------------------------------


def _instrucciones(maestro) -> str:
    """El prompt sin el texto de los fragmentos ni la tarea curricular."""
    texto = f"{maestro.sistema}\n{maestro.usuario}"
    for f in FRAGMENTOS:
        texto = texto.replace(f.texto.strip(), "")
    return texto


def test_el_prompt_del_control_no_menciona_perfil_ni_adaptacion():
    instrucciones = _instrucciones(prompt_control()).lower()

    encontradas = [p for p in PROHIBIDAS if p in instrucciones]
    assert not encontradas, f"el prompt del control menciona: {encontradas}"
    # Ni los pesos C_* ni el bloque de perfil del experimental.
    assert "%" not in instrucciones
    assert "cómo debe estar construida" not in instrucciones


def test_el_prompt_del_control_conserva_las_reglas_del_sistema():
    maestro = prompt_control()

    assert maestro.sistema == prompts.SISTEMA
    for regla in (
        "ÍNTEGRAMENTE en español",
        "ÚNICAMENTE con un objeto JSON válido",
        "Solo puedes afirmar lo que aparece en los fragmentos",
        "Inventar un identificador",
    ):
        assert regla in maestro.sistema
    # Los mismos fragmentos, rotulados con el id que hay que citar.
    for f in FRAGMENTOS:
        assert f"id_fragmento: {f.id_fragmento}" in maestro.usuario
        assert f.texto.strip() in maestro.usuario
    assert "Material curado disponible" in maestro.usuario
    assert "Objetivo de aprendizaje a cubrir" in maestro.usuario


def test_el_prompt_del_control_pide_resumen_y_quiz_mc():
    maestro = prompt_control()

    assert maestro.actividad_requerida == "quiz_mc"
    assert maestro.basica is True
    assert maestro.palabras_objetivo == 220
    assert "aproximadamente 220 palabras" in maestro.usuario
    assert "`quiz_mc`" in maestro.usuario
    for otra in ("intentalo_tu", "flashcards", "quiz_multi"):
        assert otra not in maestro.usuario
    for bloque in ("analogia", "glosario", "lista_pasos", "esquema", "tabla", "ejemplo_resuelto"):
        assert f"`{bloque}`" not in maestro.usuario
        assert f'"{bloque}' not in maestro.usuario


def test_el_esquema_basico_nombra_solo_los_campos_del_control():
    """Si el prompt describe un campo que `CapsulaBasica` rechaza, el modelo falla siempre."""
    esquema = prompts.ESQUEMA_JSON_BASICO
    for campo in ("titulo", "objetivo_aprendizaje", "concepto_central", "actividad", "fuentes"):
        assert f'"{campo}"' in esquema
    for campo in ("activacion", "representacion_adaptativa", "ejemplo", "tarjetas", "preguntas"):
        assert f'"{campo}"' not in esquema


def test_el_prompt_del_control_pide_lo_mismo_en_todas_sus_secciones():
    """«Extensión y actividad», el esquema y la verificación final piden entre 3 y
    5 alternativas, que es lo que acepta el validador (`MIN/MAX_ALTERNATIVAS`).
    Antes el esquema decía «4 alternativas distintas» y contradecía al resto.
    """
    from studify.generation.schemas import MAX_ALTERNATIVAS, MIN_ALTERNATIVAS

    assert (MIN_ALTERNATIVAS, MAX_ALTERNATIVAS) == (3, 5)
    assert '"alternativas": ["entre 3 y 5 alternativas distintas"]' in prompts.ESQUEMA_JSON_BASICO
    usuario = re.sub(r"\s+", " ", prompt_control().usuario)
    assert "4 alternativas" not in usuario
    assert "entre 3 y 5 alternativas distintas" in usuario
    assert "entre 3 y 5 `alternativas` distintas" in usuario


def test_el_prompt_experimental_no_cambia_de_forma():
    """El experimental sigue sin actividad exigida y con su contrato completo."""
    maestro = orchestrator.construir(
        objetivo=OBJETIVO, fragmentos=FRAGMENTOS,
        config=aplicar_reglas(PERFIL_CONTROL), modelo="deepseek-chat",
    )
    assert maestro.actividad_requerida is None
    assert maestro.basica is False


# --- Huella del control -------------------------------------------------------


def test_huella_del_control_es_estable_y_propia():
    uno, otro = prompt_control(), prompt_control()
    assert uno.huella == otro.huella

    # Distinta de cualquier perfil, incluido el promedio de los 43.
    experimental = orchestrator.construir(
        objetivo=OBJETIVO, fragmentos=FRAGMENTOS,
        config=aplicar_reglas(PERFIL_CONTROL), modelo="deepseek-chat",
    )
    assert uno.huella != experimental.huella
    # Y distinta del control anterior: sus cápsulas no se reutilizan.
    anterior = orchestrator.construir(
        objetivo=OBJETIVO, fragmentos=FRAGMENTOS,
        config=aplicar_reglas(PERFIL_CONTROL), modelo="deepseek-chat",
        variante=VERSION_PERFIL_CONTROL,
    )
    assert uno.huella != anterior.huella


def test_huella_del_control_cambia_con_material_modelo_y_variante():
    base = prompt_control()
    assert base.huella != prompt_control(fragmentos=FRAGMENTOS[:1]).huella
    assert base.huella != prompt_control(modelo="otro-modelo").huella
    sin_variante = orchestrator.construir(
        objetivo=OBJETIVO, fragmentos=FRAGMENTOS, config=None, modelo="deepseek-chat",
    )
    assert base.huella != sin_variante.huella


def test_las_plantillas_neutras_no_entran_a_la_huella_experimental(monkeypatch):
    """Editar una plantilla del control no puede invalidar el caché experimental."""
    config = aplicar_reglas(PERFIL_CONTROL)

    def experimental():
        return orchestrator.construir(
            objetivo=OBJETIVO, fragmentos=FRAGMENTOS, config=config, modelo="deepseek-chat",
        ).huella

    antes, control_antes = experimental(), prompt_control().huella
    monkeypatch.setattr(prompts, "SECUENCIA_NEUTRA", prompts.SECUENCIA_NEUTRA + " ")
    assert experimental() == antes
    assert prompt_control().huella != control_antes


# --- Validador: actividad exigida ---------------------------------------------


def test_validador_acepta_la_basica_con_quiz_mc():
    resultado = validar(
        json_de(capsula_basica()), FRAGMENTOS,
        actividad_requerida="quiz_mc", esquema=CapsulaBasica,
    )

    assert resultado.es_valida, resultado.errores
    assert isinstance(resultado.capsula, CapsulaBasica)
    assert resultado.metricas["palabras_contenido"] == contar_palabras(
        capsula_basica()["concepto_central"]
    )


def test_validador_rechaza_otro_tipo_de_actividad():
    datos = capsula_basica()
    datos["actividad"] = {
        "tipo": "intentalo_tu",
        "pregunta": "Normaliza una tabla de matrículas.",
        "retroalimentacion": "Separa el nombre del ramo.",
    }

    resultado = validar(
        json_de(datos), FRAGMENTOS, actividad_requerida="quiz_mc", esquema=CapsulaBasica,
    )

    assert not resultado.es_valida
    assert any("quiz_mc" in e and "intentalo_tu" in e for e in resultado.errores)


def test_sin_actividad_requerida_el_validador_no_cambia():
    """El experimental no recibe la regla nueva."""
    datos = capsula_valida()
    datos["actividad"] = {
        "tipo": "intentalo_tu",
        "pregunta": "Normaliza una tabla de matrículas.",
        "retroalimentacion": "Separa el nombre del ramo.",
    }
    assert validar(json_de(datos), FRAGMENTOS).es_valida


def test_mensaje_de_extension_del_control_solo_nombra_el_resumen():
    datos = capsula_basica() | {"concepto_central": PARRAFO[:200]}

    resultado = validar(
        json_de(datos), FRAGMENTOS, actividad_requerida="quiz_mc", esquema=CapsulaBasica,
    )

    assert not resultado.es_valida
    mensaje = next(e for e in resultado.errores if "palabras" in e)
    assert "concepto_central" in mensaje
    assert "representacion_adaptativa" not in mensaje
    assert "ejemplo" not in mensaje


# --- Generador: el bucle de reparación sirve también al control ---------------


def test_generar_repara_una_actividad_de_otro_tipo():
    mala = capsula_basica()
    mala["actividad"] = {
        "tipo": "flashcards",
        "tarjetas": [{"anverso": f"t{i}", "reverso": f"r{i}"} for i in range(3)],
    }
    cliente = ClienteFalso(json_de(mala), json_de(capsula_basica()))

    resultado = generar(prompt_control(), cliente=cliente)

    assert resultado.intentos == 2
    assert isinstance(resultado.capsula, CapsulaBasica)
    assert resultado.capsula.actividad.tipo == "quiz_mc"
    realimentacion = cliente.conversaciones[1][-1].contenido
    assert "quiz_mc" in realimentacion and "flashcards" in realimentacion


def test_generar_control_rechaza_la_capsula_completa():
    """Una cápsula de siete pasos no pasa como básica: se repara o se agota."""
    cliente = ClienteFalso(*[json_de(capsula_valida())] * 3)

    with pytest.raises(ErrorGeneracion):
        generar(prompt_control(), cliente=cliente, max_reintentos=2)


def test_generar_control_sigue_rechazando_citas_inventadas():
    datos = capsula_basica()
    datos["fuentes"] = [{"id_fragmento": 999, "documento": DOCUMENTO, "pagina": 1}]
    cliente = ClienteFalso(json_de(datos), json_de(capsula_basica()))

    resultado = generar(prompt_control(), cliente=cliente)

    assert resultado.intentos == 2
    assert "999" in cliente.conversaciones[1][-1].contenido


def test_prompt_maestro_conserva_los_fragmentos_del_control():
    maestro = prompt_control()
    assert maestro.fragmentos == tuple(FRAGMENTOS)
    assert replace(maestro, huella="x").fragmentos == tuple(FRAGMENTOS)


# --- Retriever neutro (con Postgres) ------------------------------------------


@pytest.fixture
def objetivo_con_diez_fragmentos(db):
    from studify.db.models import DocumentoFuente, Fragmento, ObjetivoAprendizaje

    objetivo = ObjetivoAprendizaje(
        codigo_objetivo="TEST-NEUTRO-01", asignatura="Bases de Datos (test neutro)",
        unidad="Unidad 3", tema="Retriever neutro", estado="activo",
    )
    documento = DocumentoFuente(
        titulo="Apunte (test neutro)", formato="pdf",
        hash_archivo="hash-test-neutro", estado_curacion="validado",
    )
    db.add_all([objetivo, documento])
    db.flush()
    # Las tablas quedan al final del documento: un canal V las subiría.
    tipos = ["texto"] * 8 + ["tabla", "tabla"]
    for numero, tipo in enumerate(tipos, start=1):
        db.add(Fragmento(
            id_documento=documento.id_documento, id_objetivo=objetivo.id_objetivo,
            numero_fragmento=numero, tipo_fragmento=tipo,
            contenido_texto=f"Fragmento {numero} sobre normalización.",
            pagina_inicio=numero, pagina_fin=numero, estado_validacion="validado",
        ))
    db.commit()
    yield objetivo
    db.delete(documento)
    db.delete(objetivo)
    db.commit()


@necesita_bd
def test_recuperar_sin_canal_toma_los_ocho_primeros_por_documento_y_numero(
    db, objetivo_con_diez_fragmentos
):
    from studify.rag.retriever import recuperar

    neutros = recuperar(db, id_objetivo=objetivo_con_diez_fragmentos.id_objetivo)
    visuales = recuperar(
        db, id_objetivo=objetivo_con_diez_fragmentos.id_objetivo, canal_primario="V",
    )

    # Limitación conocida: con más de 8 entran los 8 primeros del documento.
    assert [re.search(r"\d+", f.texto).group() for f in neutros] == [
        str(n) for n in range(1, 9)
    ]
    assert all(f.tipo == "texto" for f in neutros)
    assert [f.tipo for f in visuales[:2]] == ["tabla", "tabla"]
