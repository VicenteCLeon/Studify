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

import json
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url

from alembic import command
from studify.config import get_settings
from studify.db.models import (
    DocumentoFuente,
    Estudiante,
    Fragmento,
    InteraccionQuiz,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.main import app
from studify.web import consentimiento, sesion
from studify.web.routers.teacher import _rendimiento_actividades
from tests.conftest import USUARIO_DOCENTE, necesita_bd
from tests.test_api_capsulas import TEXTO_LARGO

pytestmark = necesita_bd

RAIZ = Path(__file__).resolve().parents[1]

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

TARJETAS = [
    {"anverso": f"Concepto {n}", "reverso": f"Definición {n}"} for n in range(1, 4)
]

REPASO = {"tipo": "flashcards", "pregunta": "Repasa las tarjetas.", "tarjetas": TARJETAS}

# Cuatro preguntas; la correcta es siempre la primera alternativa.
CUESTIONARIO = {
    "tipo": "flashcards_y_quiz",
    "pregunta": "Repasa y responde.",
    "tarjetas": TARJETAS,
    "preguntas": [
        {
            "enunciado": f"Pregunta {n}",
            "alternativas": ["Correcta", "Incorrecta", "Tampoco"],
            "indice_correcta": 0,
            "explicacion": f"Explicación {n}",
        }
        for n in range(1, 5)
    ],
}

CONTENIDO = [{"tipo": "parrafo", "cuerpo": TEXTO_LARGO}]


@pytest.fixture
def http(clave_docente):
    """Con credencial de docente: estos tests miden la numeración de intentos,
    no quién puede responder (eso lo prueba `test_api_capsulas.py`)."""
    cliente = TestClient(app)
    cliente.auth = (USUARIO_DOCENTE, clave_docente)
    return cliente


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
    repaso = MicrocapsulaGenerada(
        id_estudiante=duenio.id_estudiante,
        id_objetivo=objetivo.id_objetivo,
        titulo="Segunda forma normal (repaso)",
        contenido_json={"contenido": CONTENIDO},
        mini_quiz_json=REPASO,
        estado_validacion="validada",
    )
    cuestionario = MicrocapsulaGenerada(
        id_estudiante=duenio.id_estudiante,
        id_objetivo=objetivo.id_objetivo,
        titulo="Segunda forma normal (cuestionario)",
        contenido_json={"contenido": CONTENIDO},
        mini_quiz_json=CUESTIONARIO,
        estado_validacion="validada",
    )
    db.add_all([capsula, abierta, repaso, cuestionario])
    db.commit()
    # Las vistas del estudiante exigen la aceptación vigente de los documentos
    # legales; sin ella el visor mandaría a /aceptar en vez de responder.
    for estudiante in (duenio, ajeno):
        consentimiento.registrar(db, estudiante.id_estudiante)

    yield {
        "capsula": capsula,
        "abierta": abierta,
        "repaso": repaso,
        "cuestionario": cuestionario,
        "duenio": duenio,
        "ajeno": ajeno,
        "objetivo": objetivo,
        "documento": documento,
    }

    db.query(InteraccionQuiz).filter(
        InteraccionQuiz.id_capsula.in_(
            [c.id_capsula for c in (capsula, abierta, repaso, cuestionario)]
        )
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


def _responder(http, escenario, alternativa: int):
    """Responde el `quiz_mc` del escenario; la correcta es la alternativa 0."""
    return http.post(
        f"/api/capsulas/{escenario['capsula'].id_capsula}/quiz",
        json={
            "id_estudiante": escenario["duenio"].id_estudiante,
            "alternativa_seleccionada": alternativa,
        },
    )


def _fila_del_tema(db, tema: str = "Segunda forma normal") -> dict:
    """La fila que el panel del docente mostraría para ese tema."""
    return next(f for f in _rendimiento_actividades(db) if f["tema"] == tema)


# --- Numeración de intentos ---------------------------------------------------


def test_el_primer_intento_es_el_uno(http, escenario):
    respuesta = _responder(http, escenario, alternativa=1)

    assert respuesta.status_code == 201
    assert respuesta.json()["numero_intento"] == 1


def test_los_reintentos_se_numeran_en_orden(http, escenario):
    """El estudiante que insiste queda registrado como lo que es: alguien que
    llegó a la respuesta en el tercer intento, no alguien que acertó."""
    numeros = [
        _responder(http, escenario, alternativa=1).json()[
            "numero_intento"
        ],
        _responder(http, escenario, alternativa=1).json()[
            "numero_intento"
        ],
        _responder(http, escenario, alternativa=0).json()[
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
    segunda = _responder(http, escenario, alternativa=0)

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


# --- La corrección la hace el servidor ----------------------------------------


def test_la_api_corrige_en_el_servidor_y_no_le_cree_al_cliente(http, escenario):
    """Antes `es_correcta` se guardaba tal como llegaba en el cuerpo."""
    respuesta = http.post(
        f"/api/capsulas/{escenario['capsula'].id_capsula}/quiz",
        json={
            "id_estudiante": escenario["duenio"].id_estudiante,
            "alternativa_seleccionada": 1,
            "es_correcta": True,
        },
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["es_correcta"] is False


def test_un_quiz_sin_alternativa_no_se_registra(http, db, escenario):
    """Sin la alternativa no hay nada que corregir: antes quedaba lo que dijera el cliente."""
    respuesta = http.post(
        f"/api/capsulas/{escenario['capsula'].id_capsula}/quiz",
        json={"id_estudiante": escenario["duenio"].id_estudiante, "es_correcta": True},
    )

    assert respuesta.status_code == 422
    assert _intentos(db, escenario["capsula"]) == []


def test_una_alternativa_que_no_existe_no_se_registra(http, db, escenario):
    respuesta = _responder(http, escenario, alternativa=7)

    assert respuesta.status_code == 422
    assert _intentos(db, escenario["capsula"]) == []


def test_la_api_corrige_un_cuestionario_pregunta_por_pregunta(http, escenario):
    respuesta = http.post(
        f"/api/capsulas/{escenario['cuestionario'].id_capsula}/quiz",
        json={"id_estudiante": escenario["duenio"].id_estudiante, "respuestas": [0, 0, 1, 0]},
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert (cuerpo["aciertos"], cuerpo["total_preguntas"]) == (3, 4)
    assert cuerpo["es_correcta"] is False  # «todas correctas», como antes


def test_un_cuestionario_incompleto_no_se_registra(http, db, escenario):
    respuesta = http.post(
        f"/api/capsulas/{escenario['cuestionario'].id_capsula}/quiz",
        json={"id_estudiante": escenario["duenio"].id_estudiante, "respuestas": [0, 0]},
    )

    assert respuesta.status_code == 422
    assert _intentos(db, escenario["cuestionario"]) == []


# --- Lo que termina viendo el docente -----------------------------------------


def test_el_panel_informa_el_acierto_al_primer_intento(http, db, escenario):
    """Tres intentos, acierto al tercero: el panel debe decir 0% de acierto al
    primer intento y dos reintentos, no 33% ni 100%."""
    _responder(http, escenario, alternativa=1)
    _responder(http, escenario, alternativa=1)
    _responder(http, escenario, alternativa=0)
    http.post(
        f"/api/capsulas/{escenario['abierta'].id_capsula}/quiz",
        json={"id_estudiante": escenario["duenio"].id_estudiante},
    )

    fila = _fila_del_tema(db)

    assert fila["unica"] == {"primeras": 1, "aciertos": 0, "porcentaje": 0.0}
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

    assert fila["unica"] == {"primeras": 0, "aciertos": 0, "porcentaje": None}
    assert fila["cuestionario"] == {"primeras": 0, "promedio": None}
    assert fila["abiertas"] == 1


def test_las_flashcards_no_cuentan_como_acierto(http, db, escenario):
    """Antes «Terminé el repaso» se registraba como respuesta correcta: un
    perfil K con flashcards sumaba 100 % de acierto sin responder nada."""
    _conectar(http, escenario["duenio"])
    http.post(
        f"/student/viewer/{escenario['repaso'].id_capsula}/submit",
        data={"answer": "completado"},
    )

    assert [i.es_correcta for i in _intentos(db, escenario["repaso"])] == [None]
    fila = _fila_del_tema(db)
    assert fila["unica"]["primeras"] == 0
    assert fila["abiertas"] == 1


def test_el_visor_guarda_el_cuestionario_pregunta_por_pregunta(http, db, escenario):
    """3 de 4 bien: antes quedaba como un intento fallido, igual que 0 de 4."""
    _conectar(http, escenario["duenio"])
    http.post(
        f"/student/viewer/{escenario['cuestionario'].id_capsula}/submit",
        data={"answer": "0,0,1,0"},
    )

    [intento] = _intentos(db, escenario["cuestionario"])
    assert (intento.aciertos, intento.total_preguntas) == (3, 4)
    assert intento.es_correcta is False
    assert [d["correcta"] for d in intento.detalle_json] == [True, True, False, True]
    assert [d["seleccion"] for d in intento.detalle_json] == [0, 0, 1, 0]


def test_el_panel_separa_seleccion_unica_y_cuestionario(http, db, escenario):
    """Un ítem de una pregunta y un cuestionario de cuatro no se promedian juntos.

    El cuestionario informa el promedio de preguntas acertadas al primer
    intento (3 de 4 = 75 %), y su reintento no cuenta.
    """
    _conectar(http, escenario["duenio"])
    _responder(http, escenario, alternativa=0)
    ruta = f"/student/viewer/{escenario['cuestionario'].id_capsula}/submit"
    http.post(ruta, data={"answer": "0,0,1,0"})
    http.post(ruta, data={"answer": "0,0,0,0"})

    fila = _fila_del_tema(db)

    assert fila["unica"] == {"primeras": 1, "aciertos": 1, "porcentaje": 100.0}
    assert fila["cuestionario"] == {"primeras": 1, "promedio": 75.0}
    assert fila["reintentos"] == 1


def test_la_exportacion_de_mis_datos_incluye_el_detalle(http, db, escenario):
    """Es un dato nuevo del estudiante: tiene que salir en el derecho de acceso."""
    _conectar(http, escenario["duenio"])
    http.post(
        f"/student/viewer/{escenario['cuestionario'].id_capsula}/submit",
        data={"answer": "0,0,1,0"},
    )

    datos = http.get("/mis-datos/exportar").json()

    [intento] = [
        i
        for i in datos["intentos_en_actividades"]
        if i["id_capsula"] == escenario["cuestionario"].id_capsula
    ]
    assert (intento["aciertos"], intento["total_preguntas"]) == (3, 4)
    assert len(intento["detalle"]) == 4


def _intentos(db, capsula) -> list[InteraccionQuiz]:
    db.expire_all()
    return list(
        db.scalars(
            select(InteraccionQuiz)
            .where(InteraccionQuiz.id_capsula == capsula.id_capsula)
            .order_by(InteraccionQuiz.numero_intento)
        ).all()
    )


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


# --- Migración: recalcula lo ya guardado --------------------------------------


def test_la_migracion_recalcula_los_intentos_ya_guardados(monkeypatch):
    """En una base temporal del mismo servidor: la de desarrollo no se toca.

    Antes de la migración, un `flashcards` quedaba como acierto y un `quiz_mc`
    registrado por la API llevaba el `es_correcta` que dijera el cliente.
    """
    url = make_url(get_settings().database_url)
    nombre = f"studify_test_migracion_{uuid.uuid4().hex[:8]}"
    servidor = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with servidor.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{nombre}"'))
    temporal = url.set(database=nombre)
    try:
        monkeypatch.setattr(
            get_settings(), "database_url", temporal.render_as_string(hide_password=False)
        )
        # Sin `alembic.ini`: su `fileConfig` reconfiguraría el logging de la suite.
        cfg = Config()
        cfg.set_main_option("script_location", str(RAIZ / "alembic"))
        motor = create_engine(temporal)

        command.upgrade(cfg, "c3a91f5e7d20")
        with motor.begin() as conn:
            conn.execute(text("INSERT INTO estudiante (id_estudiante) VALUES (1)"))
            conn.execute(
                text(
                    "INSERT INTO objetivo_aprendizaje (id_objetivo, codigo_objetivo, "
                    "asignatura, unidad, tema, estado) VALUES (1, 'X', 'A', 'U', 'T', 'activo')"
                )
            )
            for id_capsula, quiz in ((1, QUIZ_CORREGIBLE), (2, REPASO), (3, ACTIVIDAD_ABIERTA)):
                conn.execute(
                    text(
                        "INSERT INTO microcapsula_generada (id_capsula, id_estudiante, "
                        "id_objetivo, titulo, contenido_json, mini_quiz_json, "
                        "estado_validacion) VALUES (:id, 1, 1, 't', '{}', "
                        "CAST(:quiz AS JSONB), 'generada')"
                    ),
                    {"id": id_capsula, "quiz": json.dumps(quiz)},
                )
            # quiz_mc: el cliente dijo «correcta» marcando la 1 (la correcta es la 0).
            # flashcards: quedó como acierto. intentalo_tu: sin corrección.
            conn.execute(
                text(
                    "INSERT INTO interaccion_quiz (id_capsula, numero_intento, "
                    "alternativa_seleccionada, es_correcta) VALUES "
                    "(1, 1, 1, true), (1, 2, 0, false), (2, 1, NULL, true), (3, 1, NULL, NULL)"
                )
            )

        command.upgrade(cfg, "head")

        with motor.connect() as conn:
            filas = conn.execute(
                text(
                    "SELECT id_capsula, numero_intento, es_correcta FROM interaccion_quiz "
                    "ORDER BY id_capsula, numero_intento"
                )
            ).all()
        assert [tuple(f) for f in filas] == [
            (1, 1, False),
            (1, 2, True),
            (2, 1, None),
            (3, 1, None),
        ]

        command.downgrade(cfg, "-1")
        command.upgrade(cfg, "head")
        motor.dispose()
    finally:
        with servidor.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        servidor.dispose()
