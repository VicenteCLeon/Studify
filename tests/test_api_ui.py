"""Los endpoints que la migración a React sacó de los handlers Jinja.

Lo que protegen no es una pantalla: son **dos invariantes del informe** que la
capa Jinja garantizaba por construcción y que, al pasar a una API que cualquiera
puede llamar, hay que defender explícitamente:

1. **La matriz de puntuación no se filtra al cliente** (cap. 17.1). El
   cuestionario viaja con letras `a|b|c|d`; si viajara el canal V/A/R/K,
   cualquiera podría responder mirando la pestaña de red y los perfiles dejarían
   de medir nada.
2. **La respuesta correcta del quiz no viaja al navegador.** La corrección se
   hace en el servidor contra `mini_quiz_json`. Si `indice_correcta` llegara al
   cliente, el quiz sería decorativo.

Los que tocan la base se saltan solos sin Postgres, como el resto de la suite.
"""

import pytest
from fastapi.testclient import TestClient

from studify.db.models import (
    DocumentoFuente,
    Estudiante,
    Fragmento,
    InteraccionQuiz,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.main import app
from studify.vark import instrumento
from studify.web import sesion, textos
from tests.conftest import necesita_bd
from tests.test_api_capsulas import TEXTO_LARGO

CARRERA_PRUEBA = "Ingeniería Informática (test api ui)"

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


@pytest.fixture
def http():
    return TestClient(app)


# --- Instrumento (sin base de datos) ------------------------------------------


def test_el_instrumento_trae_los_16_items(http):
    respuesta = http.get("/api/instrumento")

    assert respuesta.status_code == 200
    items = respuesta.json()
    assert len(items) == len(instrumento.ITEMS) == 16
    assert [i["numero"] for i in items] == list(range(1, 17))


def test_los_enunciados_salen_de_la_misma_fuente_que_la_calificacion(http):
    """Si la pantalla tuviera su propia copia, podría desalinearse del scoring."""
    items = http.get("/api/instrumento").json()

    assert [i["enunciado"] for i in items] == list(textos.ENUNCIADOS)
    for item, alternativas in zip(items, instrumento.ITEMS, strict=True):
        assert [a["texto"] for a in item["alternativas"]] == list(alternativas)


def test_el_canal_vark_no_viaja_al_cliente(http):
    """Cap. 17.1: la matriz de puntuación no se filtra al frontend.

    Es la razón por la que `respuesta_vark` guarda la posición marcada y no el
    canal: permite recalcular los perfiles sin volver a aplicar el cuestionario.
    Si el canal viniera en esta respuesta, responder "bien" sería trivial.
    """
    crudo = http.get("/api/instrumento").text
    items = http.get("/api/instrumento").json()

    for item in items:
        assert [a["letra"] for a in item["alternativas"]] == ["a", "b", "c", "d"]
        assert all("canal" not in a for a in item["alternativas"])
    assert '"canal"' not in crudo


def test_los_textos_compartidos_vienen_del_servidor(http):
    """El color de cada canal es uno solo para las dos interfaces.

    Duplicar el mapa en TypeScript garantiza que en algún momento el gráfico del
    docente y el del estudiante pinten el mismo canal de colores distintos.
    """
    datos = http.get("/api/textos").json()

    assert datos["nombre_canal"] == textos.NOMBRE_CANAL
    assert datos["color_canal"] == textos.COLOR_CANAL


# --- Sesión del estudiante ----------------------------------------------------


def test_sin_sesion_responde_200_y_no_401(http):
    """No tener sesión es el estado normal de quien no respondió el cuestionario.

    Un 401 obligaría al cliente a tratar como error el arranque más común.
    """
    respuesta = http.get("/api/sesion")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"id_estudiante": None, "tiene_diagnostico": False}


@necesita_bd
def test_abrir_sesion_emite_la_cookie_firmada(http, db):
    estudiante = Estudiante(carrera=CARRERA_PRUEBA)
    db.add(estudiante)
    db.commit()

    try:
        respuesta = http.post(f"/api/sesion/{estudiante.id_estudiante}")

        assert respuesta.status_code == 200
        assert sesion.COOKIE_ESTUDIANTE in respuesta.cookies
        assert http.get("/api/sesion").json()["id_estudiante"] == estudiante.id_estudiante

        http.delete("/api/sesion")
        assert http.get("/api/sesion").json()["id_estudiante"] is None
    finally:
        db.delete(estudiante)
        db.commit()


@necesita_bd
def test_no_se_puede_abrir_sesion_de_un_estudiante_inexistente(http):
    assert http.post("/api/sesion/99999999").status_code == 404


def test_el_perfil_sin_sesion_da_401(http):
    assert http.get("/api/perfil").status_code == 401


# --- Corrección de la actividad -----------------------------------------------


@pytest.fixture
def escenario(db):
    """Una cápsula de cada tipo de actividad, y un estudiante ajeno."""
    objetivo = ObjetivoAprendizaje(
        codigo_objetivo="TEST-UI-01",
        asignatura="Bases de Datos (test api ui)",
        unidad="Unidad 3",
        tema="Segunda forma normal",
        estado="activo",
    )
    documento = DocumentoFuente(
        titulo="Apunte de prueba (api ui)",
        formato="pdf",
        hash_archivo="hash-de-prueba-api-ui",
        estado_curacion="validado",
    )
    db.add_all([objetivo, documento])
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
        contenido_json={"contenido": [{"tipo": "parrafo", "cuerpo": TEXTO_LARGO}]},
        mini_quiz_json=QUIZ_CORREGIBLE,
        estado_validacion="validada",
    )
    abierta = MicrocapsulaGenerada(
        id_estudiante=duenio.id_estudiante,
        id_objetivo=objetivo.id_objetivo,
        titulo="Segunda forma normal (aplicada)",
        contenido_json={"contenido": [{"tipo": "parrafo", "cuerpo": TEXTO_LARGO}]},
        mini_quiz_json=ACTIVIDAD_ABIERTA,
        estado_validacion="validada",
    )
    db.add_all([capsula, abierta])
    db.commit()

    yield {"capsula": capsula, "abierta": abierta, "duenio": duenio, "ajeno": ajeno}

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
    http.cookies.set(
        sesion.COOKIE_ESTUDIANTE,
        f"{estudiante.id_estudiante}.{sesion._firma(estudiante.id_estudiante)}",
    )


@necesita_bd
def test_acertar_devuelve_ok_y_no_revela_la_correcta(http, escenario):
    """Al acertar no hace falta decir cuál era: ya la eligió."""
    _conectar(http, escenario["duenio"])

    respuesta = http.post(
        f"/api/capsulas/{escenario['capsula'].id_capsula}/responder",
        json={"alternativa": 0},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "ok"
    assert cuerpo["correcta"] is None
    assert cuerpo["numero_intento"] == 1


@necesita_bd
def test_fallar_devuelve_la_correcta_solo_despues_de_contestar(http, escenario):
    _conectar(http, escenario["duenio"])

    respuesta = http.post(
        f"/api/capsulas/{escenario['capsula'].id_capsula}/responder",
        json={"alternativa": 1},
    )

    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "error"
    assert cuerpo["correcta"] == "Depende de parte de la clave"


@necesita_bd
def test_el_indice_correcto_nunca_viaja_en_la_respuesta(http, escenario):
    """La invariante que hace que el quiz mida algo.

    Se comprueba sobre el **texto crudo** y no sobre el JSON parseado: si algún
    día se agregara un campo anidado con la clave, un `assert` por clave podría
    no verlo.
    """
    _conectar(http, escenario["duenio"])

    crudo = http.post(
        f"/api/capsulas/{escenario['capsula'].id_capsula}/responder",
        json={"alternativa": 1},
    ).text

    assert "indice_correcta" not in crudo


@necesita_bd
def test_no_se_puede_responder_la_capsula_de_otro(http, escenario):
    """Sin esto, la respuesta correcta se podría sondear con ids ajenos."""
    _conectar(http, escenario["ajeno"])

    respuesta = http.post(
        f"/api/capsulas/{escenario['capsula'].id_capsula}/responder",
        json={"alternativa": 0},
    )

    assert respuesta.status_code == 403


@necesita_bd
def test_sin_sesion_tampoco_se_puede_responder(http, escenario):
    http.cookies.clear()

    respuesta = http.post(
        f"/api/capsulas/{escenario['capsula'].id_capsula}/responder",
        json={"alternativa": 0},
    )

    assert respuesta.status_code == 403


@necesita_bd
def test_la_actividad_abierta_se_registra_aunque_no_se_corrija(http, escenario):
    """`intentalo_tu` no tiene respuesta única, pero el intento sí se cuenta.

    Sin esto, los objetivos trabajados solo por perfiles K se verían en el panel
    del docente como si nadie los hubiera abierto.
    """
    _conectar(http, escenario["duenio"])

    respuesta = http.post(
        f"/api/capsulas/{escenario['abierta'].id_capsula}/responder",
        json={"alternativa": None},
    )

    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "esperada"
    assert cuerpo["numero_intento"] == 1


@necesita_bd
def test_sin_elegir_alternativa_avisa_en_vez_de_reventar(http, escenario):
    _conectar(http, escenario["duenio"])

    respuesta = http.post(
        f"/api/capsulas/{escenario['capsula'].id_capsula}/responder",
        json={"alternativa": None},
    )

    assert respuesta.status_code == 422
    assert "alternativa" in respuesta.json()["detail"].lower()
