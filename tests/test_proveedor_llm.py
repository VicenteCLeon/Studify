"""Fallas del proveedor del LLM: timeout, rechazo de la llamada, sin red.

Hasta el 16-oct-2026, una caída del proveedor llegaba como excepción del SDK de
`openai` —no como `ErrorGeneracion`— y ningún handler la capturaba: el visor
del estudiante, `POST /api/capsulas`, el comparador del simulador y el lote del
tagger respondían 500. Además había dos capas de reintentos anidadas (las del
SDK y las de tenacity en llama-index), así que la espera antes del error podía
durar minutos.

Estos tests no necesitan Postgres. Los del visor, la API y el tagger están en
sus propios archivos y sí la necesitan.
"""

import pytest

from studify.config import get_settings
from studify.db.models import ObjetivoAprendizaje
from studify.generation.generator import (
    ClienteOpenAILike,
    ErrorGeneracion,
    ErrorProveedorLLM,
    Mensaje,
    generar,
)
from studify.rag import orchestrator
from studify.rag.retriever import FragmentoRecuperado
from studify.vark.rules import aplicar_reglas
from studify.vark.scoring import PerfilVark
from studify.web.routers import teacher
from tests.conftest import cliente_con_proveedor_caido

FALLAS = ["timeout", "conexion", "sin_saldo"]


@pytest.mark.parametrize("falla", FALLAS)
def test_una_falla_del_proveedor_llega_como_error_propio(falla):
    """El resto del sistema no tiene por qué conocer las excepciones de `openai`."""
    cliente = cliente_con_proveedor_caido(falla)

    with pytest.raises(ErrorProveedorLLM) as excinfo:
        cliente.responder([Mensaje("user", "hola")])

    # Subclase de `ErrorGeneracion`: los handlers que ya la capturan dejan de
    # dejarla escapar como 500.
    assert isinstance(excinfo.value, ErrorGeneracion)
    assert "proveedor" in str(excinfo.value)


def test_el_402_dice_que_falta_saldo():
    """Sin saldo no se arregla reintentando: el mensaje tiene que decirlo."""
    cliente = cliente_con_proveedor_caido("sin_saldo")

    with pytest.raises(ErrorProveedorLLM) as excinfo:
        cliente.responder([Mensaje("user", "hola")])

    assert "402" in str(excinfo.value)


def test_los_reintentos_de_red_son_los_configurados(monkeypatch):
    """Una sola capa de reintentos acotada, y no 3 del SDK por 3 de llama-index."""
    assert get_settings().llm_max_retries == 1

    monkeypatch.setattr(get_settings(), "llm_max_retries", 0)
    cliente = ClienteOpenAILike(api_key="clave-de-prueba")

    assert cliente._llm.max_retries == 0


def test_una_caida_no_gasta_los_intentos_de_reparacion():
    """El bucle de reparación es para respuestas inválidas, no para un proveedor caído.

    Reintentar ahí solo alargaría la espera: el mismo timeout se repetiría
    tres veces más antes del error.
    """
    cliente = cliente_con_proveedor_caido("timeout")
    prompt = _prompt()

    with pytest.raises(ErrorProveedorLLM):
        generar(prompt, cliente=cliente)

    assert cliente._llm.llamadas == 1


def test_el_simulador_muestra_la_columna_en_error_en_vez_de_tumbar_la_comparacion(
    monkeypatch,
):
    """Es lo que promete el docstring de `/simulator/compare` para un timeout."""
    monkeypatch.setattr(teacher.retriever, "recuperar", lambda db, **_: list(_FRAGMENTOS))

    columna = teacher._generar_capsula_pura(
        None, _objetivo(), "V", cliente_con_proveedor_caido("timeout")
    )

    assert columna["capsula"] is None
    assert "proveedor" in columna["error"]


# --- Auxiliares ---------------------------------------------------------------

_FRAGMENTOS = (
    FragmentoRecuperado(
        id_fragmento=1,
        texto="La segunda forma normal elimina las dependencias parciales.",
        tipo="texto",
        documento="Apunte de prueba",
        id_documento=1,
        pagina_inicio=1,
        pagina_fin=1,
        etiqueta_tematica=None,
    ),
)


def _objetivo() -> ObjetivoAprendizaje:
    """Un objetivo en memoria: `construir` solo lee sus atributos."""
    return ObjetivoAprendizaje(
        id_objetivo=1,
        codigo_objetivo="TEST-PROV-01",
        asignatura="Bases de Datos",
        unidad="Unidad 3",
        tema="Segunda forma normal",
    )


def _prompt():
    perfil = PerfilVark(v=100, a=0, r=0, k=0)
    return orchestrator.construir(
        objetivo=_objetivo(),
        fragmentos=_FRAGMENTOS,
        config=aplicar_reglas(perfil),
        modelo="modelo-de-prueba",
    )
