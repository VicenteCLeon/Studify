"""Dos personas en el mismo navegador: «Salir», «¿Eres tú?» y el origen del registro (R2).

Hasta el 24-oct-2026, con una cookie válida el cuestionario se **agregaba al
estudiante de la cookie**: una segunda persona en el mismo computador pisaba el
perfil vigente de la primera, su aceptación legal quedaba a nombre de la otra y
podía ver, exportar o eliminar sus datos en `/mis-datos`. Estos tests fijan lo
que lo impide:

- el servidor solo agrega un diagnóstico al estudiante de la cookie cuando el
  formulario dice `modo=actualizar`; cualquier otro envío crea un estudiante;
- «Salir» olvida la cookie sin borrar datos;
- la sesión vence según `SESION_ESTUDIANTE_HORAS` y la firma incluye la
  `fecha_registro`, así que una cookie de una base recreada no vale;
- cada estudiante nuevo guarda de dónde salió (`origen_registro`), para poder
  filtrar posibles duplicados en el A/B.
"""

import re
import time
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from studify.config import get_settings
from studify.db.models import AceptacionLegal, DiagnosticoVark, Estudiante
from studify.main import app
from studify.web import legal, sesion, textos
from tests.conftest import necesita_bd

pytestmark = necesita_bd

RESPUESTAS = {"q1": ["a"], "q2": ["b"], "q3": ["c"]}
ACEPTA = {"acepto": "si"}
TREINTA_DIAS = 60 * 60 * 24 * 30


@pytest.fixture
def navegador() -> TestClient:
    return TestClient(app)


@pytest.fixture
def creados(db):
    """Ids de los estudiantes que cree el test; se borran al final (CASCADE)."""
    ids: list[int] = []
    yield ids
    db.expire_all()
    for id_estudiante in ids:
        fila = db.get(Estudiante, id_estudiante)
        if fila is not None:
            db.delete(fila)
    db.commit()


def _id_de_la_cookie(cliente: TestClient) -> int | None:
    crudo = cliente.cookies.get(sesion.COOKIE_ESTUDIANTE)
    return int(crudo.split(".")[0]) if crudo else None


def _responder(cliente: TestClient, creados: list[int], **extra) -> int:
    """Envía el cuestionario y devuelve el estudiante que quedó en la cookie."""
    respuesta = cliente.post("/student/vark", data=RESPUESTAS | ACEPTA | extra)
    assert respuesta.status_code == 204, respuesta.text
    id_estudiante = _id_de_la_cookie(cliente)
    assert id_estudiante is not None
    if id_estudiante not in creados:
        creados.append(id_estudiante)
    return id_estudiante


def _diagnosticos(db, id_estudiante: int) -> int:
    db.expire_all()
    return db.scalar(
        select(func.count())
        .select_from(DiagnosticoVark)
        .where(DiagnosticoVark.id_estudiante == id_estudiante)
    )


def _aceptaciones(db, id_estudiante: int) -> set[tuple[str, str]]:
    db.expire_all()
    return set(
        db.execute(
            select(AceptacionLegal.documento, AceptacionLegal.version).where(
                AceptacionLegal.id_estudiante == id_estudiante
            )
        ).all()
    )


def _origen(db, id_estudiante: int) -> str | None:
    db.expire_all()
    return db.get(Estudiante, id_estudiante).origen_registro


def _vigentes() -> set[tuple[str, str]]:
    return {(d.clave, d.version) for d in legal.DOCUMENTOS}


# --- 1. El servidor nunca reutiliza la sesión sin `modo=actualizar` -----------


def test_otra_persona_crea_un_estudiante_nuevo_con_su_propia_aceptacion(
    navegador, db, creados
):
    """B responde en el navegador de A: B es otra persona y A queda intacto."""
    a = _responder(navegador, creados)
    diagnosticos_a = _diagnosticos(db, a)
    aceptaciones_a = _aceptaciones(db, a)

    b = _responder(navegador, creados, modo="nuevo")

    assert b != a
    assert _diagnosticos(db, a) == diagnosticos_a
    assert _diagnosticos(db, b) == 1
    # La aceptación queda a nombre de B, y A no recibe filas nuevas.
    assert _vigentes() <= _aceptaciones(db, b)
    assert _aceptaciones(db, a) == aceptaciones_a
    assert _id_de_la_cookie(navegador) == b


def test_un_envio_sin_modo_no_toca_al_estudiante_de_la_cookie(navegador, db, creados):
    """Un formulario viejo (o un POST armado a mano) no escribe en el perfil de otro."""
    a = _responder(navegador, creados)
    diagnosticos_a = _diagnosticos(db, a)

    b = _responder(navegador, creados)

    assert b != a
    assert _diagnosticos(db, a) == diagnosticos_a


def test_actualizar_agrega_el_diagnostico_al_mismo_estudiante(navegador, db, creados):
    a = _responder(navegador, creados)

    de_nuevo = _responder(navegador, creados, modo="actualizar")

    assert de_nuevo == a
    assert _diagnosticos(db, a) == 2
    assert _origen(db, a) == "nuevo"


def test_actualizar_sin_sesion_crea_un_estudiante(navegador, db, creados):
    """`modo=actualizar` no es una credencial: sin cookie válida no hay a quién actualizar."""
    nuevo = _responder(navegador, creados, modo="actualizar")

    assert _diagnosticos(db, nuevo) == 1
    assert _origen(db, nuevo) == "nuevo"


# --- 2. «Salir» ---------------------------------------------------------------


def test_salir_olvida_la_cookie_y_no_borra_datos(navegador, db, creados):
    a = _responder(navegador, creados)

    respuesta = navegador.post("/student/salir", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/?salio=1"
    assert navegador.cookies.get(sesion.COOKIE_ESTUDIANTE) is None
    db.expire_all()
    assert db.get(Estudiante, a) is not None
    assert _diagnosticos(db, a) == 1


def test_salir_conserva_la_sesion_del_docente(http_docente, creados):
    _responder(http_docente, creados)
    assert http_docente.cookies.get(sesion.COOKIE_DOCENTE) is not None

    http_docente.post("/student/salir", follow_redirects=False)

    assert http_docente.cookies.get(sesion.COOKIE_ESTUDIANTE) is None
    assert http_docente.cookies.get(sesion.COOKIE_DOCENTE) is not None


def test_la_confirmacion_de_salir(navegador, creados):
    _responder(navegador, creados)

    respuesta = navegador.get("/student/salir")

    assert respuesta.status_code == 200
    assert re.search(r'<form[^>]*method="post"[^>]*action="/student/salir"', respuesta.text)
    assert "responder el cuestionario de nuevo" in respuesta.text


def test_salir_sin_sesion_vuelve_a_la_portada(navegador):
    respuesta = navegador.get("/student/salir", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/"


def test_salir_no_exige_aceptar_antes(navegador, db, creados):
    """B no tiene que aceptar los documentos a nombre de A para poder irse."""
    estudiante = Estudiante()
    db.add(estudiante)
    db.commit()
    creados.append(estudiante.id_estudiante)
    navegador.cookies.set(
        sesion.COOKIE_ESTUDIANTE,
        sesion.valor_cookie(estudiante.id_estudiante, estudiante.fecha_registro),
    )

    respuesta = navegador.get("/student/salir", follow_redirects=False)

    assert respuesta.status_code == 200


def test_la_portada_avisa_que_saliste(navegador):
    assert "Saliste" in navegador.get("/?salio=1").text


# --- 3. «¿Eres tú?» -----------------------------------------------------------


def test_el_cuestionario_con_sesion_pregunta_si_eres_tu(navegador, db, creados):
    a = _responder(navegador, creados)
    db.expire_all()
    fecha = db.scalars(
        select(DiagnosticoVark.fecha_diagnostico).where(DiagnosticoVark.id_estudiante == a)
    ).one()
    local = fecha.astimezone(ZoneInfo("America/Santiago"))

    html = navegador.get("/student/vark").text

    assert "Soy yo" in html
    assert "Soy otra persona" in html
    assert 'href="/student/vark?modo=actualizar"' in html
    assert re.search(r'name="motivo"\s+value="otra_persona"', html)
    assert f"{local:%H:%M}" in html
    assert legal.MESES[local.month - 1] in html
    # Solo la fecha y la hora: nada del perfil de quien respondió antes.
    for nombre in textos.NOMBRE_CANAL.values():
        assert nombre not in html
    assert 'name="q1"' not in html


def test_el_cuestionario_sin_sesion_es_para_alguien_nuevo(navegador):
    html = navegador.get("/student/vark").text

    assert re.search(r'name="modo"\s+value="nuevo"', html)
    assert 'name="carrera"' in html
    assert "Soy otra persona" not in html


def test_soy_yo_muestra_el_cuestionario_sin_los_datos_opcionales(navegador, creados):
    """Al actualizar, los datos sociodemográficos se descartan: no se piden."""
    _responder(navegador, creados)

    html = navegador.get("/student/vark?modo=actualizar").text

    assert re.search(r'name="modo"\s+value="actualizar"', html)
    assert 'name="q1"' in html
    assert 'name="carrera"' not in html
    assert 'name="acepto"' in html


def test_soy_otra_persona_cierra_la_sesion_y_vuelve_al_cuestionario(navegador, db, creados):
    a = _responder(navegador, creados)

    respuesta = navegador.post(
        "/student/salir", data={"motivo": "otra_persona"}, follow_redirects=False
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/student/vark"
    assert navegador.cookies.get(sesion.COOKIE_ESTUDIANTE) is None

    b = _responder(navegador, creados, modo="nuevo")
    assert b != a
    assert _origen(db, b) == "otra_persona"


# --- 4. Origen del estudiante -------------------------------------------------


def test_origen_nuevo(navegador, db, creados):
    assert _origen(db, _responder(navegador, creados, modo="nuevo")) == "nuevo"


def test_el_origen_aparece_en_la_exportacion_de_mis_datos(navegador, creados):
    """Es un dato del estudiante: el derecho de acceso lo incluye (Política §2)."""
    _responder(navegador, creados, modo="nuevo")

    datos = navegador.get("/mis-datos/exportar").json()

    assert datos["estudiante"]["origen_registro"] == "nuevo"


def test_origen_tras_salir(navegador, db, creados):
    _responder(navegador, creados)
    navegador.post("/student/salir")

    b = _responder(navegador, creados, modo="nuevo")

    assert _origen(db, b) == "tras_salir"
    # La marca se usa una vez: el siguiente registro ya no la hereda.
    assert navegador.cookies.get(sesion.COOKIE_ORIGEN) is None


def test_origen_con_la_sesion_de_otro_abierta(navegador, db, creados):
    """Una pestaña cargada antes de que el otro abriera sesión: es otra persona."""
    _responder(navegador, creados)

    b = _responder(navegador, creados, modo="nuevo")

    assert _origen(db, b) == "otra_persona"


def test_origen_tras_una_sesion_vencida(navegador, db, creados):
    a = _responder(navegador, creados)
    db.expire_all()
    estudiante = db.get(Estudiante, a)
    # Se reemplaza la cookie que dejó el servidor por la misma, ya vencida. Con
    # el dominio con que `httpx` guarda las del servidor, para que la próxima
    # que llegue la pise en vez de quedar dos con el mismo nombre.
    navegador.cookies.set(
        sesion.COOKIE_ESTUDIANTE,
        sesion.valor_cookie(a, estudiante.fecha_registro, expira=int(time.time()) - 10),
        domain="testserver.local",
    )

    b = _responder(navegador, creados, modo="nuevo")

    assert b != a
    assert _origen(db, b) == "sesion_vencida"
    assert _diagnosticos(db, a) == 1


# --- 5. Vencimiento configurable ----------------------------------------------


def test_la_sesion_vence_segun_la_configuracion(navegador, monkeypatch, creados):
    monkeypatch.setattr(get_settings(), "sesion_estudiante_horas", 1)

    respuesta = navegador.post("/student/vark", data=RESPUESTAS | ACEPTA)
    creados.append(_id_de_la_cookie(navegador))

    expira = int(navegador.cookies.get(sesion.COOKIE_ESTUDIANTE).split(".")[2])
    assert abs(expira - (time.time() + 3600)) < 60
    # El navegador la guarda 30 días (lo que dice la Política); lo que vence es
    # la sesión, y una cookie vencida todavía permite marcar `sesion_vencida`.
    assert f"Max-Age={TREINTA_DIAS}" in respuesta.headers["set-cookie"]


def test_una_sesion_vencida_no_da_acceso(navegador, db, creados):
    a = _responder(navegador, creados)
    db.expire_all()
    estudiante = db.get(Estudiante, a)
    # Se reemplaza la cookie que dejó el servidor por la misma, ya vencida. Con
    # el dominio con que `httpx` guarda las del servidor, para que la próxima
    # que llegue la pise en vez de quedar dos con el mismo nombre.
    navegador.cookies.set(
        sesion.COOKIE_ESTUDIANTE,
        sesion.valor_cookie(a, estudiante.fecha_registro, expira=int(time.time()) - 10),
        domain="testserver.local",
    )

    respuesta = navegador.get("/student/profile", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/student/vark"


# --- 6. Cookie de una base recreada -------------------------------------------


def test_la_cookie_no_vale_si_cambia_la_fecha_de_registro(navegador, db, creados):
    """Tras `reset_db.py` los ids vuelven a 1: la cookie vieja no puede abrir otro perfil.

    Basta un microsegundo de diferencia en `fecha_registro` para que deje de valer.
    """
    a = _responder(navegador, creados)
    assert navegador.get("/student/profile", follow_redirects=False).status_code == 200

    db.expire_all()
    estudiante = db.get(Estudiante, a)
    estudiante.fecha_registro = estudiante.fecha_registro + timedelta(microseconds=1)
    db.commit()

    respuesta = navegador.get("/student/profile", follow_redirects=False)
    assert respuesta.status_code == 303


# --- 7. Pistas «¿No eres tú? Salir» -------------------------------------------


def test_la_cabecera_ofrece_salir_solo_con_sesion(navegador, creados):
    assert 'href="/student/salir"' not in navegador.get("/").text

    _responder(navegador, creados)

    assert 'href="/student/salir"' in navegador.get("/student/catalog").text


def test_la_portada_con_sesion_pregunta_si_no_eres_tu(navegador, creados):
    _responder(navegador, creados)

    html = navegador.get("/").text

    assert "¿No eres tú?" in html


def test_aceptar_y_mis_datos_ofrecen_salir(navegador, db, creados):
    """Los dos lugares donde B podría actuar a nombre de A: aceptar o eliminar."""
    estudiante = Estudiante()
    db.add(estudiante)
    db.commit()
    creados.append(estudiante.id_estudiante)
    navegador.cookies.set(
        sesion.COOKIE_ESTUDIANTE,
        sesion.valor_cookie(estudiante.id_estudiante, estudiante.fecha_registro),
    )

    for ruta in ("/aceptar", "/mis-datos"):
        html = navegador.get(ruta).text
        assert "¿No eres tú?" in html, ruta
        assert 'href="/student/salir"' in html, ruta
