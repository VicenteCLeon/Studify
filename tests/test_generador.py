"""Tests del bucle de reparación (Fase 3).

Se ejercita con un cliente falso, no con el modelo real. Los modos de fallo que
importan —JSON truncado, cita inventada, cápsula en inglés, contenido fuera de
rango— son fáciles de provocar con respuestas guionadas e imposibles de
provocar a voluntad contra DeepSeek. Además corren sin `LLM_API_KEY`, sin red y
sin costo, que es lo que permite tenerlos en la suite.
"""

import json
from decimal import Decimal

import pytest
from material import FRAGMENTOS, OBJETIVO, capsula_valida

from studify.generation.generator import (
    ClienteOpenAILike,
    ErrorGeneracion,
    Mensaje,
    generar,
)
from studify.rag import orchestrator
from studify.vark.rules import aplicar_reglas
from studify.vark.scoring import PerfilVark


class ClienteFalso:
    """Devuelve respuestas guionadas y guarda lo que se le pidió.

    Registrar las conversaciones es lo que permite comprobar que el reintento
    recibe la realimentación correcta, que es la mitad del bucle que un test
    sobre el resultado final no ve.
    """

    def __init__(self, *respuestas: str, modelo: str = "modelo-de-prueba") -> None:
        self.respuestas = list(respuestas)
        self.modelo = modelo
        self.conversaciones: list[list[Mensaje]] = []

    def responder(self, mensajes):
        self.conversaciones.append(list(mensajes))
        if not self.respuestas:
            raise AssertionError(
                f"el generador hizo {len(self.conversaciones)} llamadas y solo "
                f"había respuestas guionadas para {len(self.conversaciones) - 1}"
            )
        return self.respuestas.pop(0)

    @property
    def llamadas(self) -> int:
        return len(self.conversaciones)


def prompt_maestro():
    perfil = PerfilVark(v=Decimal(0), a=Decimal(0), r=Decimal(0), k=Decimal(100))
    return orchestrator.construir(
        objetivo=OBJETIVO,
        fragmentos=FRAGMENTOS,
        config=aplicar_reglas(perfil),
        modelo="modelo-de-prueba",
    )


def json_de(datos: dict) -> str:
    return json.dumps(datos, ensure_ascii=False)


VALIDA = json_de(capsula_valida())


def con_defecto(**cambios) -> str:
    datos = capsula_valida()
    datos.update(cambios)
    return json_de(datos)


# --- Camino feliz ------------------------------------------------------------


def test_capsula_valida_al_primer_intento():
    cliente = ClienteFalso(VALIDA)

    resultado = generar(prompt_maestro(), cliente=cliente)

    assert resultado.intentos == 1
    assert resultado.valida_al_primer_intento
    assert cliente.llamadas == 1
    assert resultado.capsula.titulo.startswith("Segunda forma normal")
    assert resultado.modelo == "modelo-de-prueba"
    assert resultado.errores_por_intento == []


def test_el_primer_mensaje_lleva_el_prompt_maestro():
    cliente = ClienteFalso(VALIDA)
    prompt = prompt_maestro()

    generar(prompt, cliente=cliente)

    sistema, usuario = cliente.conversaciones[0]
    assert sistema.rol == "system" and sistema.contenido == prompt.sistema
    assert usuario.rol == "user" and usuario.contenido == prompt.usuario


def test_se_registran_las_metricas_de_la_corrida():
    """El criterio de término de la Fase 3 se mide con estos números."""
    resultado = generar(prompt_maestro(), cliente=ClienteFalso(VALIDA))

    assert resultado.metricas["idioma_ok"] is True
    assert 150 <= resultado.metricas["palabras_contenido"] <= 300
    assert resultado.metricas["citas_inventadas"] == 0
    assert resultado.segundos >= 0


# --- El bucle de reparación --------------------------------------------------


def test_se_repara_al_segundo_intento():
    cliente = ClienteFalso(con_defecto(titulo="uno dos tres " * 5), VALIDA)

    resultado = generar(prompt_maestro(), cliente=cliente)

    assert resultado.intentos == 2
    assert not resultado.valida_al_primer_intento
    assert cliente.llamadas == 2
    assert len(resultado.errores_por_intento) == 1


def test_el_reintento_recibe_la_respuesta_rechazada_y_el_motivo():
    """Sin la respuesta a la vista, «acorta el contenido» no tiene referente."""
    rechazada = con_defecto(titulo="uno dos tres cuatro cinco seis siete ocho nueve diez once")
    cliente = ClienteFalso(rechazada, VALIDA)

    generar(prompt_maestro(), cliente=cliente)

    segunda = cliente.conversaciones[1]
    assert len(segunda) == 4
    assert segunda[2].rol == "assistant" and segunda[2].contenido == rechazada
    assert segunda[3].rol == "user"
    assert "título" in segunda[3].contenido
    assert "11 palabras" in segunda[3].contenido


def test_la_realimentacion_insiste_en_el_espanol_en_cada_reintento():
    """El reintento arrastra la respuesta anterior; si venía en inglés, hay que
    contrarrestar el contexto que empuja a seguir en inglés."""
    cliente = ClienteFalso(con_defecto(fuentes=[{"id_fragmento": 999}]), VALIDA)

    generar(prompt_maestro(), cliente=cliente)

    assert "español" in cliente.conversaciones[1][3].contenido


def test_se_agota_tras_el_intento_inicial_y_dos_reintentos():
    """El plan §3 fija «máximo 2 reintentos»: tres llamadas en total."""
    malo = con_defecto(fuentes=[{"id_fragmento": 999, "documento": "x", "pagina": 1}])
    cliente = ClienteFalso(malo, malo, malo)

    with pytest.raises(ErrorGeneracion) as exc:
        generar(prompt_maestro(), cliente=cliente)

    assert cliente.llamadas == 3
    assert len(exc.value.errores_por_intento) == 3
    assert "999" in str(exc.value)


def test_el_numero_de_reintentos_es_configurable():
    """El bake-off necesita medir el primer intento sin reparación."""
    malo = con_defecto(titulo="uno dos tres " * 5)
    cliente = ClienteFalso(malo)

    with pytest.raises(ErrorGeneracion):
        generar(prompt_maestro(), cliente=cliente, max_reintentos=0)

    assert cliente.llamadas == 1


# --- Modos de fallo que el bucle tiene que poder reparar ---------------------


def test_repara_una_cita_alucinada():
    """El fallo que el proyecto entero existe para detectar (cap. 13)."""
    inventada = con_defecto(
        fuentes=[{"id_fragmento": 4321, "documento": "Paper inexistente", "pagina": 7}]
    )
    cliente = ClienteFalso(inventada, VALIDA)

    resultado = generar(prompt_maestro(), cliente=cliente)

    assert resultado.intentos == 2
    assert [f.id_fragmento for f in resultado.capsula.fuentes] == [161]
    # El reintento tiene que saber cuáles sí puede citar.
    assert "161" in cliente.conversaciones[1][3].contenido


def test_repara_una_respuesta_truncada():
    cliente = ClienteFalso('{"titulo": "Segunda forma", "contenido": [{"tipo"', VALIDA)

    resultado = generar(prompt_maestro(), cliente=cliente)

    assert resultado.intentos == 2
    assert "truncó" in cliente.conversaciones[1][3].contenido


def test_repara_una_capsula_en_ingles():
    # Todos los pasos en inglés: con solo uno traducido, los demás siguen
    # aportando marcadores del español y el detector acepta la cápsula, que es
    # el comportamiento correcto (una palabra suelta no es deriva de idioma).
    en_ingles = con_defecto(
        activacion="Have you ever had to fix the same value in many rows?",
        concepto_central=(
            "A partial dependency happens when a non key attribute depends only "
            "on part of the composite primary key, and not on the whole key."
        ),
        ejemplo={
            "tipo": "ejemplo_resuelto",
            "cuerpo": (
                "In an enrolment table keyed by student and course, the course "
                "name depends only on the course, so it must be moved out."
            ),
        },
        actividad={
            "tipo": "quiz_mc",
            "pregunta": "When does a table break the second normal form?",
            "alternativas": [
                "When a non key attribute depends on part of the key",
                "When the table has more than five columns",
                "When the primary key is an integer",
            ],
            "indice_correcta": 0,
            "retroalimentacion": "It must depend on the whole key, not on a part.",
        },
        representacion_adaptativa=[
            {
                "tipo": "parrafo",
                "cuerpo": (
                    "Normalization is the process that organizes the attributes "
                    "of a relational database in order to reduce redundancy and "
                    "to avoid anomalies when rows are inserted, updated or "
                    "deleted from the table. Each normal form adds one "
                    "condition on top of the previous one, so that a table "
                    "which is in third normal form also satisfies the first two "
                    "forms. The goal is not to have many tables, but that each "
                    "fact is stored only once and in the place where it truly "
                    "belongs, next to the key which determines it. When this is "
                    "done well, any correction has to be applied at a single "
                    "point and every query that reads the data will see the "
                    "corrected value immediately."
                ),
            }
        ]
    )
    cliente = ClienteFalso(en_ingles, VALIDA)

    resultado = generar(prompt_maestro(), cliente=cliente)

    assert resultado.intentos == 2
    assert "inglés" in cliente.conversaciones[1][3].contenido


def test_repara_un_contenido_fuera_del_rango_de_palabras():
    corta = con_defecto(
        concepto_central="Muy breve.",
        representacion_adaptativa=[{"tipo": "parrafo", "cuerpo": "También breve."}],
        ejemplo={"tipo": "parrafo", "cuerpo": "Un caso."},
    )
    cliente = ClienteFalso(corta, VALIDA)

    resultado = generar(prompt_maestro(), cliente=cliente)

    assert resultado.intentos == 2
    assert "mínimo es 150" in cliente.conversaciones[1][3].contenido


def test_repara_una_capsula_sin_pregunta_de_activacion():
    """El paso 2 de la estructura pedagógica, reparado por el bucle."""
    sin_pregunta = con_defecto(activacion="Vamos a ver las dependencias parciales.")
    cliente = ClienteFalso(sin_pregunta, VALIDA)

    resultado = generar(prompt_maestro(), cliente=cliente)

    assert resultado.intentos == 2
    assert "activacion" in cliente.conversaciones[1][3].contenido


def test_tolera_las_cercas_markdown_sin_gastar_un_reintento():
    """Envolver el JSON en ```json es lo más común y no es un defecto real."""
    cliente = ClienteFalso(f"```json\n{VALIDA}\n```")

    resultado = generar(prompt_maestro(), cliente=cliente)

    assert resultado.intentos == 1


# --- La regla 5 se valida contra los fragmentos del propio prompt ------------


def test_las_citas_se_contrastan_contra_los_fragmentos_inyectados():
    """Si el prompt llevó menos material, citar de más es igualmente inválido.

    Es el motivo por el que `PromptMaestro` acarrea sus fragmentos en vez de
    que el llamador se los pase por separado al validador.
    """
    prompt = orchestrator.construir(
        objetivo=OBJETIVO,
        fragmentos=FRAGMENTOS[:1],  # solo el 161
        config=aplicar_reglas(PerfilVark(v=Decimal(0), a=Decimal(0), r=Decimal(0), k=Decimal(100))),
        modelo="modelo-de-prueba",
    )
    cita_162 = con_defecto(fuentes=[{"id_fragmento": 162, "documento": "x", "pagina": 1}])
    cliente = ClienteFalso(cita_162, VALIDA)

    generar(prompt, cliente=cliente)

    assert "162" in cliente.conversaciones[1][3].contenido


# --- Cliente real -------------------------------------------------------------


def test_sin_api_key_el_error_dice_que_falta_la_key():
    """Es el estado actual del proyecto: conviene que no falle con un 401 opaco."""
    with pytest.raises(ErrorGeneracion, match="LLM_API_KEY"):
        ClienteOpenAILike(api_key="")
