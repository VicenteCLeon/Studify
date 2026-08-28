"""Analíticas y simulador del docente por HTTP (migración a React).

La lógica ya está probada por `test_cobertura_curricular.py` y
`test_interaccion_quiz.py`, que llaman a `studify.analytics` directamente. Lo que
falta comprobar acá es lo que agrega el transporte:

- que los endpoints **exijan credenciales** (son datos de la cohorte y el
  simulador gasta créditos del LLM en cada llamada);
- que el JSON tenga la forma que el cliente TypeScript declara, que es lo único
  que evita que un cambio del backend rompa el navegador en silencio;
- que **una columna que falla no tumbe a las otras tres** en la comparación, que
  es el criterio de término de la Fase 3.
"""

import pytest
from fastapi.testclient import TestClient

from studify.api.routers.capsules import get_cliente_llm
from studify.db.models import (
    DocumentoFuente,
    Estudiante,
    Fragmento,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.main import app
from studify.vark.scoring import CANALES
from tests.conftest import necesita_bd
from tests.test_api_capsulas import TEXTO_LARGO, ClienteObediente

pytestmark = necesita_bd

ASIGNATURA_PRUEBA = "Bases de Datos (test api panel)"


@pytest.fixture
def objetivo_con_material(db):
    """Lo mínimo que el simulador necesita: un objetivo con material validado."""
    objetivo = ObjetivoAprendizaje(
        codigo_objetivo="TEST-PANEL-01",
        asignatura=ASIGNATURA_PRUEBA,
        unidad="Unidad 3",
        tema="Segunda forma normal",
        descripcion="Reconocer dependencias parciales.",
        estado="activo",
    )
    documento = DocumentoFuente(
        titulo="Apunte de prueba (api panel)",
        formato="pdf",
        hash_archivo="hash-de-prueba-api-panel",
        estado_curacion="validado",
    )
    db.add_all([objetivo, documento])
    db.flush()
    for numero in range(1, 4):
        db.add(
            Fragmento(
                id_documento=documento.id_documento,
                id_objetivo=objetivo.id_objetivo,
                numero_fragmento=numero,
                tipo_fragmento="texto",
                contenido_texto=TEXTO_LARGO,
                pagina_inicio=numero,
                pagina_fin=numero,
                estado_validacion="validado",
            )
        )
    db.commit()

    yield objetivo

    db.query(MicrocapsulaGenerada).filter(
        MicrocapsulaGenerada.id_objetivo == objetivo.id_objetivo
    ).delete(synchronize_session=False)
    db.query(Fragmento).filter(
        Fragmento.id_documento == documento.id_documento
    ).delete(synchronize_session=False)
    db.commit()
    db.delete(documento)
    db.delete(objetivo)
    db.query(Estudiante).filter(Estudiante.carrera == ASIGNATURA_PRUEBA).delete()
    db.commit()


@pytest.fixture
def cliente_falso():
    """Sustituye el LLM: estos tests no gastan créditos ni dependen de la red."""
    falso = ClienteObediente()
    app.dependency_overrides[get_cliente_llm] = lambda: falso
    yield falso
    app.dependency_overrides.pop(get_cliente_llm, None)


# --- Quién puede llamar -------------------------------------------------------


def test_las_analiticas_exigen_credenciales(clave_docente):
    """Es el perfil agregado de la cohorte, no un dato del estudiante."""
    anonimo = TestClient(app)

    assert anonimo.get("/api/analiticas").status_code == 401


def test_el_simulador_exige_credenciales(clave_docente):
    """Cada llamada gasta créditos del LLM: no puede quedar abierta."""
    anonimo = TestClient(app)

    assert anonimo.post("/api/simulador/generar", json={"id_objetivo": 1}).status_code == 401
    assert anonimo.post("/api/simulador/comparar", json={"id_objetivo": 1}).status_code == 401


# --- Analíticas ---------------------------------------------------------------


def test_las_analiticas_traen_las_cinco_metricas(http_docente, objetivo_con_material):
    """Van en una sola respuesta porque la pantalla las muestra todas a la vez."""
    respuesta = http_docente.get("/api/analiticas")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert set(datos) == {
        "cobertura",
        "sin_clasificar",
        "rendimiento",
        "vark_total",
        "vark_barras",
        "capsulas",
    }


def test_la_cobertura_nombra_los_tipos_en_vez_de_usar_tuplas(
    http_docente, objetivo_con_material
):
    """El dominio los devuelve como tuplas `(tipo, cantidad)`; el JSON los nombra.

    Un array de dos posiciones obligaría al cliente a depender del orden dentro
    del array, que es exactamente el tipo de acoplamiento que un contrato
    tipado viene a eliminar.
    """
    cobertura = http_docente.get("/api/analiticas").json()["cobertura"]
    fila = next(
        f for f in cobertura if f["objetivo"]["asignatura"] == ASIGNATURA_PRUEBA
    )

    assert fila["total"] == 3
    assert fila["estado"] == "escaso"
    assert fila["tipos"] == [{"tipo": "texto", "cantidad": 3}]
    assert {c["canal"] for c in fila["canales"]} == set(CANALES)


def test_un_objetivo_sin_material_aparece_como_falta(
    http_docente, db, objetivo_con_material
):
    vacio = ObjetivoAprendizaje(
        codigo_objetivo="TEST-PANEL-02",
        asignatura=ASIGNATURA_PRUEBA,
        unidad="Unidad 4",
        tema="Tercera forma normal",
        estado="activo",
    )
    db.add(vacio)
    db.commit()

    try:
        cobertura = http_docente.get("/api/analiticas").json()["cobertura"]
        fila = next(
            f for f in cobertura if f["objetivo"]["codigo_objetivo"] == "TEST-PANEL-02"
        )
        assert fila["estado"] == "sin_material"
        assert fila["total"] == 0
    finally:
        db.delete(vacio)
        db.commit()


# --- Simulador ----------------------------------------------------------------


def test_generar_un_canal_devuelve_la_capsula_con_su_clave(
    http_docente, objetivo_con_material, cliente_falso
):
    """Acá la actividad sí viaja entera: el docente vino a revisar la pregunta.

    Es lo contrario de lo que recibe el estudiante, y a propósito: la cápsula
    simulada no se persiste, así que no hay nada que responder ni que corregir.
    """
    respuesta = http_docente.post(
        "/api/simulador/generar",
        json={"id_objetivo": objetivo_con_material.id_objetivo, "canal": "V"},
    )

    assert respuesta.status_code == 200
    columna = respuesta.json()
    assert columna["canal"] == "V"
    assert columna["error"] is None
    assert columna["capsula"]["actividad"]["indice_correcta"] is not None


def test_la_capsula_simulada_no_se_persiste(
    http_docente, db, objetivo_con_material, cliente_falso
):
    """Si se guardara, el historial y el A/B de la Fase 5 contarían pruebas del
    docente como cápsulas que un estudiante realmente vio."""
    antes = db.query(MicrocapsulaGenerada).count()

    http_docente.post(
        "/api/simulador/generar",
        json={"id_objetivo": objetivo_con_material.id_objetivo, "canal": "K"},
    )

    assert db.query(MicrocapsulaGenerada).count() == antes


def test_un_canal_invalido_se_rechaza(http_docente, objetivo_con_material, cliente_falso):
    """Un canal desconocido dejaría el vector en 0/0/0/0, que `derivar()` lee
    como multimodal con primario V: se generaría una cápsula para un perfil que
    no existe, sin error visible."""
    respuesta = http_docente.post(
        "/api/simulador/generar",
        json={"id_objetivo": objetivo_con_material.id_objetivo, "canal": "Z"},
    )

    assert respuesta.status_code == 422


def test_un_objetivo_inexistente_da_404(http_docente, cliente_falso):
    respuesta = http_docente.post(
        "/api/simulador/generar", json={"id_objetivo": 99999999, "canal": "V"}
    )

    assert respuesta.status_code == 404


def test_comparar_devuelve_las_cuatro_columnas_en_orden(
    http_docente, objetivo_con_material, cliente_falso
):
    """El criterio de término de la Fase 3: los cuatro perfiles lado a lado."""
    respuesta = http_docente.post(
        "/api/simulador/comparar",
        json={"id_objetivo": objetivo_con_material.id_objetivo},
    )

    assert respuesta.status_code == 200
    columnas = respuesta.json()
    assert [c["canal"] for c in columnas] == list(CANALES)
    assert all(c["capsula"] is not None for c in columnas)
    assert cliente_falso.llamadas == 4


def test_sin_material_la_columna_falla_sola_y_no_tumba_al_endpoint(
    http_docente, db, cliente_falso
):
    """Una columna que revienta no puede llevarse las otras tres.

    Son cuatro llamadas al modelo y cuatro oportunidades de fallar; las que sí
    salieron son exactamente las que ya se pagaron.
    """
    sin_material = ObjetivoAprendizaje(
        codigo_objetivo="TEST-PANEL-03",
        asignatura=ASIGNATURA_PRUEBA,
        unidad="Unidad 9",
        tema="Sin material",
        estado="activo",
    )
    db.add(sin_material)
    db.commit()

    try:
        respuesta = http_docente.post(
            "/api/simulador/comparar", json={"id_objetivo": sin_material.id_objetivo}
        )

        assert respuesta.status_code == 200
        columnas = respuesta.json()
        assert len(columnas) == 4
        # Sin fragmentos, las cuatro fallan — pero cada una con su motivo y sin
        # que el endpoint devuelva un 500.
        assert all(c["error"] for c in columnas)
        assert all(c["capsula"] is None for c in columnas)
    finally:
        db.delete(sin_material)
        db.commit()


def test_sin_credencial_del_llm_avisa_con_503(http_docente, objetivo_con_material):
    """Sin `LLM_API_KEY` no se puede simular, pero el mensaje tiene que decir eso
    y no un error genérico."""
    app.dependency_overrides[get_cliente_llm] = lambda: None
    try:
        respuesta = http_docente.post(
            "/api/simulador/generar",
            json={"id_objetivo": objetivo_con_material.id_objetivo, "canal": "V"},
        )
        assert respuesta.status_code == 503
        assert "LLM_API_KEY" in respuesta.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_cliente_llm, None)
