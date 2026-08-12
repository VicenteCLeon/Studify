"""Registro de intentos en la actividad de cierre (Fase 5).

Lo que protegen estos tests no es una pantalla: es que el número que el panel
del docente muestra signifique lo que dice significar.

El visor deja el formulario en pantalla después de la retroalimentación, así que
el estudiante puede cambiar la alternativa y reenviar. Si todos los intentos
pesaran igual, el «porcentaje de acierto» del curso subiría a fuerza de insistir
y no mediría nada sobre lo aprendido. De ahí que el intento se numere en el
servidor y que el panel informe solo el primero.

Requieren Postgres (se saltan solos si no está).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from studify.db.models import (
    DocumentoFuente,
    Estudiante,
    Fragmento,
    InteraccionQuiz,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.main import app
from studify.web import sesion
from studify.web.routers.teacher import _rendimiento_actividades
from tests.conftest import necesita_bd
from tests.test_api_capsulas import TEXTO_LARGO

pytestmark = necesita_bd

CARRERA_PRUEBA = "Ingeniería Informática (test quiz)"

QUIZ_CORREGIBLE = {
    "tipo": "quiz_mc",
    "pregunta": "¿Cuándo una tabla incumple la segunda forma normal?",
    "alternativas": ["Depende de parte de la clave", "Tiene muchas columnas"],
    "indice_correcta": 0,
    "retroalimentacion": "Debe depender de la clave completa.",
}

ACTIVIDAD_ABIERTA = {
    "tipo": "intentalo_tu",
    "pregunta": "Normaliza esta tabla y explica qué dependencia eliminaste.",
    "alternativas": [],
    "indice_correcta": None,
    "retroalimentacion": "Se esperaba separar el atributo en su propia tabla.",
}

CONTENIDO = [{"tipo": "parrafo", "cuerpo": TEXTO_LARGO}]


@pytest.fixture
def http():
    return TestClient(app)


@pytest.fixture
def escenario(db):
    """Dos estudiantes y una cápsula de cada tipo de actividad."""
    objetivo = ObjetivoAprendizaje(
        codigo_objetivo="TEST-QUIZ-01",
        asignatura="Bases de Datos (test quiz)",
        unidad="Unidad 3",
        tema="Segunda forma normal",
        descripcion="Reconocer dependencias parciales.",
        estado="activo",
    )
    db.add(objetivo)
    documento = DocumentoFuente(
        titulo="Apunte de prueba (quiz)",
        formato="pdf",
        hash_archivo="hash-de-prueba-quiz",
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
            pagina_inicio=1,
            pagina_fin=1,
            estado_validacion="validado",
        )
    )

    duenio = Estudiante(carrera=CARRERA_PRUEBA)
    ajeno = Estudiante(carrera=CARRERA_PRUEBA)
    db.add_all([duenio, ajeno])
    db.flush()

    capsula = MicrocapsulaGenerada(
        id_estudiante=duenio.id_estudiante,
        id_objetivo=objetivo.id_objetivo,
        titulo="Segunda forma normal",
        contenido_json={"contenido": CONTENIDO},
        mini_quiz_json=QUIZ_CORREGIBLE,
        estado_validacion="validada",
    )
    abierta = MicrocapsulaGenerada(
        id_estudiante=duenio.id_estudiante,
        id_objetivo=objetivo.id_objetivo,
        titulo="Segunda forma normal (aplicada)",
        contenido_json={"contenido": CONTENIDO},
        mini_quiz_json=ACTIVIDAD_ABIERTA,
        estado_validacion="validada",
    )
    db.add_all([capsula, abierta])
    db.commit()

    yield {
        "capsula": capsula,
        "abierta": abierta,
        "duenio": duenio,
        "ajeno": ajeno,
        "objetivo": objetivo,
        "documento": documento,
    }

    db.query(InteraccionQuiz).filter(
        InteraccionQuiz.id_capsula.in_([capsula.id_capsula, abierta.id_capsula])
    ).delete(synchronize_session=False)
    db.query(MicrocapsulaGenerada).filter(
        MicrocapsulaGenerada.id_objetivo == objetivo.id_objetivo
    ).delete(synchronize_session=False)
    db.commit()
    db.delete(documento)
    db.delete(objetivo)
    for est in db.query(Estudiante).filter(Estudiante.carrera == CARRERA_PRUEBA):
        db.delete(est)
    db.commit()


def _conectar(http, estudiante) -> None:
    """Deja al cliente con la cookie de sesión firmada de ese estudiante."""
    http.cookies.set(
        sesion.COOKIE_ESTUDIANTE,
        f"{estudiante.id_estudiante}.{sesion._firma(estudiante.id_estudiante)}",
    )


def _responder(http, escenario, alternativa: int, es_correcta: bool):
    return http.post(
        f"/api/capsulas/{escenario['capsula'].id_capsula}/quiz",
        json={
            "id_estudiante": escenario["duenio"].id_estudiante,
            "alternativa_seleccionada": alternativa,
            "es_correcta": es_correcta,
        },
    )


def _fila_del_tema(db, tema: str = "Segunda forma normal") -> dict:
    """La fila que el panel del docente mostraría para ese tema."""
    return next(f for f in _rendimiento_actividades(db) if f["tema"] == tema)


# --- Numeración de intentos ---------------------------------------------------


def test_el_primer_intento_es_el_uno(http, escenario):
    respuesta = _responder(http, escenario, alternativa=1, es_correcta=False)

    assert respuesta.status_code == 201
    assert respuesta.json()["numero_intento"] == 1


def test_los_reintentos_se_numeran_en_orden(http, escenario):
    """El estudiante que insiste queda registrado como lo que es: alguien que
    llegó a la respuesta en el tercer intento, no alguien que acertó."""
    numeros = [
        _responder(http, escenario, alternativa=1, es_correcta=False).json()[
            "numero_intento"
        ],
        _responder(http, escenario, alternativa=1, es_correcta=False).json()[
            "numero_intento"
        ],
        _responder(http, escenario, alternativa=0, es_correcta=True).json()[
            "numero_intento"
        ],
    ]

    assert numeros == [1, 2, 3]


def test_el_cliente_no_puede_declarar_el_numero_de_intento(http, escenario):
    """Si el número viniera del navegador, bastaría con mandar siempre 1."""
    respuesta = http.post(
        f"/api/capsulas/{escenario['capsula'].id_capsula}/quiz",
        json={
            "id_estudiante": escenario["duenio"].id_estudiante,
            "alternativa_seleccionada": 1,
            "es_correcta": False,
            "numero_intento": 1,
        },
    )
    segunda = _responder(http, escenario, alternativa=0, es_correcta=True)

    assert respuesta.status_code == 201
    assert segunda.json()["numero_intento"] == 2


# --- Quién puede responder ----------------------------------------------------


def test_no_se_puede_responder_la_capsula_de_otro(http, db, escenario):
    """Sin esta comprobación cualquiera podía inflar desde fuera las métricas
    que el docente lee como rendimiento del curso."""
    respuesta = http.post(
        f"/api/capsulas/{escenario['capsula'].id_capsula}/quiz",
        json={
            "id_estudiante": escenario["ajeno"].id_estudiante,
            "alternativa_seleccionada": 0,
            "es_correcta": True,
        },
    )

    assert respuesta.status_code == 403
    assert db.scalars(select(InteraccionQuiz)).all() == []


def test_una_capsula_inexistente_da_404(http, escenario):
    respuesta = http.post(
        "/api/capsulas/999999/quiz",
        json={"id_estudiante": escenario["duenio"].id_estudiante, "es_correcta": True},
    )

    assert respuesta.status_code == 404


# --- Actividades sin respuesta corregible -------------------------------------


def test_la_actividad_abierta_se_registra_sin_acierto(http, escenario):
    """`intentalo_tu` no tiene alternativa correcta. Registrarla igual es lo que
    evita que los objetivos trabajados por perfiles K desaparezcan del panel."""
    respuesta = http.post(
        f"/api/capsulas/{escenario['abierta'].id_capsula}/quiz",
        json={"id_estudiante": escenario["duenio"].id_estudiante},
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["es_correcta"] is None
    assert cuerpo["alternativa_seleccionada"] is None
    assert cuerpo["numero_intento"] == 1


# --- Lo que termina viendo el docente -----------------------------------------


def test_el_panel_informa_el_acierto_al_primer_intento(http, db, escenario):
    """Tres intentos, acierto al tercero: el panel debe decir 0% de acierto al
    primer intento y dos reintentos, no 33% ni 100%."""
    _responder(http, escenario, alternativa=1, es_correcta=False)
    _responder(http, escenario, alternativa=1, es_correcta=False)
    _responder(http, escenario, alternativa=0, es_correcta=True)
    http.post(
        f"/api/capsulas/{escenario['abierta'].id_capsula}/quiz",
        json={"id_estudiante": escenario["duenio"].id_estudiante},
    )

    fila = _fila_del_tema(db)

    assert fila["primeras"] == 1
    assert fila["aciertos"] == 0
    assert fila["porcentaje"] == 0.0
    assert fila["reintentos"] == 2
    assert fila["abiertas"] == 1
    assert fila["alumnos"] == 1


def test_un_tema_solo_con_actividades_abiertas_no_reporta_porcentaje(
    http, db, escenario
):
    """0% diría que todos fallaron; lo cierto es que no hay nada que corregir."""
    http.post(
        f"/api/capsulas/{escenario['abierta'].id_capsula}/quiz",
        json={"id_estudiante": escenario["duenio"].id_estudiante},
    )

    fila = _fila_del_tema(db)

    assert fila["primeras"] == 0
    assert fila["porcentaje"] is None
    assert fila["abiertas"] == 1


def test_el_panel_responde_con_la_base_vacia(http):
    """El caso más probable en una demostración recién montada."""
    assert http.get("/teacher/analytics").status_code == 200


# --- El visor del estudiante deja el rastro -----------------------------------


def test_el_visor_registra_el_intento_del_estudiante(http, db, escenario):
    _conectar(http, escenario["duenio"])
    http.post(
        f"/student/viewer/{escenario['capsula'].id_capsula}/submit",
        data={"answer": "1"},
    )

    intentos = db.scalars(
        select(InteraccionQuiz).where(
            InteraccionQuiz.id_capsula == escenario["capsula"].id_capsula
        )
    ).all()
    assert len(intentos) == 1
    assert intentos[0].es_correcta is False
    assert intentos[0].numero_intento == 1


def test_el_visor_registra_tambien_la_actividad_abierta(http, db, escenario):
    _conectar(http, escenario["duenio"])
    http.post(
        f"/student/viewer/{escenario['abierta'].id_capsula}/submit",
        data={"answer": "lo que escribió el estudiante"},
    )

    intentos = db.scalars(
        select(InteraccionQuiz).where(
            InteraccionQuiz.id_capsula == escenario["abierta"].id_capsula
        )
    ).all()
    assert len(intentos) == 1
    assert intentos[0].es_correcta is None


def test_el_visor_no_registra_intentos_de_una_capsula_ajena(http, db, escenario):
    _conectar(http, escenario["ajeno"])
    http.post(
        f"/student/viewer/{escenario['capsula'].id_capsula}/submit",
        data={"answer": "0"},
    )

    assert db.scalars(select(InteraccionQuiz)).all() == []
