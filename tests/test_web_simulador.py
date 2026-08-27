"""Simulador VARK del docente (Fase 5).

El simulador reusa el mismo partial que ve el estudiante, y esa reutilización
es justamente lo que hay que proteger, porque los dos contextos son opuestos:

- al estudiante **no** le pueden llegar `indice_correcta` ni `retroalimentacion`
  (si viajan al HTML, el quiz deja de medir nada);
- al docente **sí**, porque vino a revisar la calidad de la actividad, no a
  responderla.

Además la cápsula simulada no se persiste: no existe `id_capsula` contra el
cual corregir, así que la pantalla no puede ofrecer el formulario de respuesta.

Requieren Postgres (se saltan solos si no está). El LLM se sustituye por el
cliente falso de `test_api_capsulas`, así que estos tests no gastan créditos.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from studify.api.routers.capsules import get_cliente_llm
from studify.db.models import (
    DocumentoFuente,
    Fragmento,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.main import app
from tests.conftest import necesita_bd
from tests.test_api_capsulas import TEXTO_LARGO, ClienteObediente, cliente_falso  # noqa: F401

pytestmark = necesita_bd

ASIGNATURA_PRUEBA = "Bases de Datos (test simulador)"


@pytest.fixture
def http(http_docente) -> TestClient:
    """El simulador cuelga de `/teacher/*`, que exige sesión de docente."""
    return http_docente


@pytest.fixture
def objetivo_con_material(db):
    """Lo mínimo que el simulador necesita: un objetivo con material validado."""
    objetivo = ObjetivoAprendizaje(
        codigo_objetivo="TEST-SIM-01",
        asignatura=ASIGNATURA_PRUEBA,
        unidad="Unidad 3",
        tema="Segunda forma normal",
        descripcion="Reconocer dependencias parciales.",
        estado="activo",
    )
    db.add(objetivo)
    db.flush()

    documento = DocumentoFuente(
        titulo="Apunte de prueba (simulador)",
        formato="pdf",
        hash_archivo="hash-de-prueba-simulador",
        estado_curacion="validado",
    )
    db.add(documento)
    db.flush()

    db.add(
        Fragmento(
            id_documento=documento.id_documento,
            id_objetivo=objetivo.id_objetivo,
            numero_fragmento=1,
            tipo_fragmento="texto",
            contenido_texto=TEXTO_LARGO,
            pagina_inicio=12,
            pagina_fin=12,
            estado_validacion="validado",
        )
    )
    db.commit()

    yield objetivo

    db.delete(documento)
    db.delete(objetivo)
    db.commit()


def _simular(http, objetivo, canal: str = "v"):
    return http.post(
        "/teacher/simulator/generate",
        data={"id_objetivo": objetivo.id_objetivo, "canal": canal},
    )


def test_devuelve_un_fragmento_y_no_una_pagina_completa(
    http, objetivo_con_material, cliente_falso  # noqa: F811
):
    """HTMX lo inyecta en un div: una página entera metería otro <head> dentro
    del body y duplicaría la cabecera de navegación."""
    respuesta = _simular(http, objetivo_con_material)

    assert respuesta.status_code == 200
    cuerpo = respuesta.text
    assert "<head" not in cuerpo
    assert "<html" not in cuerpo
    assert "nav-links" not in cuerpo


def test_la_capsula_simulada_no_ofrece_responder(
    http, objetivo_con_material, cliente_falso  # noqa: F811
):
    """La simulación no está persistida: un formulario apuntaría a
    `/student/viewer//submit` y daría 404 al hacer clic."""
    cuerpo = _simular(http, objetivo_con_material).text

    assert "<form" not in cuerpo
    assert "/student/viewer//submit" not in cuerpo


def test_el_docente_ve_la_clave_de_la_actividad(
    http, objetivo_con_material, cliente_falso  # noqa: F811
):
    """Lo contrario del estudiante: acá la respuesta correcta y la
    retroalimentación son el objeto de la revisión."""
    cuerpo = _simular(http, objetivo_con_material).text

    assert "Debe depender de la clave completa." in cuerpo
    # La alternativa correcta (índice 0 en el cliente falso) queda marcada.
    assert "checked" in cuerpo


def test_la_capsula_se_marca_como_simulacion(
    http, objetivo_con_material, cliente_falso  # noqa: F811
):
    """El badge de origen del estudiante ('generada'/'caché') no aplica y, mal
    resuelto, mentía diciendo que la cápsula recién generada venía de caché."""
    cuerpo = _simular(http, objetivo_con_material).text

    assert "Simulación" in cuerpo
    assert "Recuperada de caché" not in cuerpo


def test_un_canal_que_no_es_vark_no_llega_al_modelo(
    http, objetivo_con_material, cliente_falso  # noqa: F811
):
    """Un canal desconocido dejaba el vector en 0/0/0/0 —que viola el invariante
    de PerfilVark y que `derivar()` lee como multimodal con primario V— y
    generaba igual una cápsula para un perfil inexistente."""
    respuesta = _simular(http, objetivo_con_material, canal="x")

    assert respuesta.status_code == 200
    assert "no es un canal VARK" in respuesta.text
    assert cliente_falso.llamadas == 0


def test_acepta_los_cuatro_canales(
    http, objetivo_con_material, cliente_falso  # noqa: F811
):
    for canal in ("v", "a", "r", "k"):
        respuesta = _simular(http, objetivo_con_material, canal=canal)
        assert respuesta.status_code == 200, canal
        assert "no es un canal VARK" not in respuesta.text, canal
    assert cliente_falso.llamadas == 4


def test_la_simulacion_no_ensucia_el_historial(
    http, db, objetivo_con_material, cliente_falso  # noqa: F811
):
    """La cápsula del docente no es de nadie: si se guardara, aparecería en el
    historial y en las métricas como si un estudiante la hubiera recibido."""
    antes = db.scalar(select(func.count(MicrocapsulaGenerada.id_capsula)))

    _simular(http, objetivo_con_material)

    db.expire_all()
    assert db.scalar(select(func.count(MicrocapsulaGenerada.id_capsula))) == antes


def test_un_objetivo_inexistente_no_llega_al_modelo(
    http, cliente_falso  # noqa: F811
):
    respuesta = http.post(
        "/teacher/simulator/generate", data={"id_objetivo": 999_999, "canal": "v"}
    )

    assert respuesta.status_code == 200
    assert "Objetivo no encontrado" in respuesta.text
    assert cliente_falso.llamadas == 0


# --- Comparación V/A/R/K lado a lado ------------------------------------------
#
# Cierra el pendiente n.º 10 de AVANCE.md §6, que es literalmente el criterio de
# término de la Fase 3 en PLAN_DESARROLLO.md §4: "comparar visualmente cuatro
# cápsulas del mismo objetivo generadas para V, A, R y K: si no se distinguen
# entre sí, la adaptación no está funcionando". Antes solo se podía generar una
# cápsula a la vez y compararlas de memoria entre pestañas.


def _comparar(http, objetivo):
    return http.post(
        "/teacher/simulator/compare", data={"id_objetivo": objetivo.id_objetivo}
    )


def test_compare_genera_las_cuatro_columnas(
    http, objetivo_con_material, cliente_falso  # noqa: F811
):
    respuesta = _comparar(http, objetivo_con_material)

    assert respuesta.status_code == 200
    cuerpo = respuesta.text
    for nombre in ("Visual", "Auditivo", "Lectura / Escritura", "Kinestésico"):
        assert nombre in cuerpo
    assert cliente_falso.llamadas == 4


def test_compare_no_ofrece_formulario_de_respuesta(
    http, objetivo_con_material, cliente_falso  # noqa: F811
):
    """Igual que el simulador de un solo canal: nada de esto está persistido,
    así que no hay `id_capsula` contra el cual corregir."""
    cuerpo = _comparar(http, objetivo_con_material).text

    assert "<form" not in cuerpo


def test_compare_no_ensucia_el_historial(
    http, db, objetivo_con_material, cliente_falso  # noqa: F811
):
    antes = db.scalar(select(func.count(MicrocapsulaGenerada.id_capsula)))

    _comparar(http, objetivo_con_material)

    db.expire_all()
    assert db.scalar(select(func.count(MicrocapsulaGenerada.id_capsula))) == antes


def test_compare_un_objetivo_inexistente_no_llega_al_modelo(http, cliente_falso):  # noqa: F811
    respuesta = http.post(
        "/teacher/simulator/compare", data={"id_objetivo": 999_999}
    )

    assert respuesta.status_code == 200
    assert "Objetivo no encontrado" in respuesta.text
    assert cliente_falso.llamadas == 0


def test_compare_una_columna_que_falla_no_tumba_a_las_otras(http, objetivo_con_material):
    """Cuatro llamadas al LLM son cuatro oportunidades de que una falle. Si el
    modelo se agota reparando una columna, las otras tres —que sí se pagaron—
    tienen que seguir mostrándose: abortar toda la comparación por un solo
    fallo desperdiciaría el trabajo que sí funcionó.

    El cliente falso se porta bien en las dos primeras llamadas (canales V y
    A, en el orden fijo de `CANALES`) y devuelve basura sin parar desde la
    tercera en adelante, así que las columnas R y K agotan sus reintentos y
    quedan en error mientras V y A sí producen cápsula.
    """
    falso = ClienteObediente()
    original = falso.responder

    def responder_con_falla_desde_la_tercera(mensajes):
        falso.llamadas += 1
        if falso.llamadas >= 3:
            return "esto no es un JSON válido"
        falso.llamadas -= 1  # el `responder` original vuelve a contarla
        return original(mensajes)

    falso.responder = responder_con_falla_desde_la_tercera
    app.dependency_overrides[get_cliente_llm] = lambda: falso
    try:
        respuesta = _comparar(http, objetivo_con_material)
    finally:
        app.dependency_overrides.pop(get_cliente_llm, None)

    assert respuesta.status_code == 200
    cuerpo = respuesta.text
    assert "Falló la generación" in cuerpo
    # El título que devuelve el cliente falso solo aparece cuando la
    # generación tuvo éxito: dos veces, una por columna que sí funcionó.
    assert cuerpo.count("Segunda forma normal y dependencias parciales") == 2
