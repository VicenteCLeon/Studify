"""Dos personas en el mismo navegador: «Salir», «¿Eres tú?» y el origen del registro (R2).

Hasta el 24-oct-2026, con una cookie válida el cuestionario se **agregaba al
estudiante de la cookie**: una segunda persona en el mismo computador pisaba el
perfil vigente de la primera, su aceptación legal quedaba a nombre de la otra y
podía ver, exportar o eliminar sus datos en `/mis-datos`. Estos tests fijan lo
que lo impide:

- el servidor exige Google y un formulario ligado a esa cuenta para guardar;
  un envío antiguo sin esa firma nunca escribe en el perfil de otra persona;
- «Salir» olvida la cookie sin borrar datos;
- la sesión vence según `SESION_ESTUDIANTE_HORAS` y la firma incluye la
  `fecha_registro`, así que una cookie de una base recreada no vale;
- cada estudiante nuevo guarda de dónde salió (`origen_registro`), para poder
  filtrar posibles duplicados en el A/B.
"""

import re
import time
from datetime import timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from studify.config import get_settings
from studify.db.models import AceptacionLegal, DiagnosticoVark, Estudiante
from studify.main import app
from studify.web import legal, sesion, textos
from tests.conftest import necesita_bd
from tests.identidad_web import enviar_vark
from tests.test_google_login import (
    _iniciar,
    _volver,
    google_configurado,  # noqa: F401
)
from tests.test_google_login import cuentas as cuentas_google  # noqa: F401

pytestmark = necesita_bd

RESPUESTAS = {"q1": ["a"], "q2": ["b"], "q3": ["c"]}
ACEPTA = {"acepto": "si"}
TREINTA_DIAS = 60 * 60 * 24 * 30


@pytest.fixture(name="cuentas")
def cuentas_para_r2(request):
    return request.getfixturevalue("cuentas_google")


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


def _responder(cliente: TestClient, creados: list[int], *, cuentas, **extra) -> int:
    """Entra con una cuenta Google de prueba y confirma el cuestionario real."""
    cookie = cliente.cookies.get(sesion.COOKIE_ESTUDIANTE)
    if not cookie or int(cookie.split(".")[2]) <= time.time():
        cuentas.identidad["sub"] = "google-r2-" + uuid4().hex
        assert _volver(cliente, cuentas, _iniciar(cliente, cuentas)).status_code == 303
    respuesta = enviar_vark(cliente, data=RESPUESTAS | ACEPTA | extra)
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


# --- 1. Solo Google y un formulario ligado a su cuenta permiten guardar ------


def test_otro_formulario_no_modifica_el_perfil_ni_su_aceptacion(
    navegador, db, creados, cuentas):
    """B envía un formulario anterior en el navegador de A: A queda intacto."""
    a = _responder(navegador, creados, cuentas=cuentas)
    diagnosticos_a = _diagnosticos(db, a)
    aceptaciones_a = _aceptaciones(db, a)

    respuesta = navegador.post("/student/vark", data=RESPUESTAS | ACEPTA | {"modo": "nuevo"})
    assert respuesta.status_code == 403
    assert _diagnosticos(db, a) == diagnosticos_a
    assert _aceptaciones(db, a) == aceptaciones_a
    assert _id_de_la_cookie(navegador) == a


def test_un_envio_sin_modo_no_toca_al_estudiante_de_la_cookie(navegador, db, creados, cuentas):
    """Un formulario viejo (o un POST armado a mano) no escribe en el perfil de otro."""
    a = _responder(navegador, creados, cuentas=cuentas)
    diagnosticos_a = _diagnosticos(db, a)

    respuesta = navegador.post("/student/vark", data=RESPUESTAS | ACEPTA)
    assert respuesta.status_code == 403
    assert _id_de_la_cookie(navegador) == a
    assert _diagnosticos(db, a) == diagnosticos_a


def test_actualizar_agrega_el_diagnostico_al_mismo_estudiante(navegador, db, creados, cuentas):
    a = _responder(navegador, creados, cuentas=cuentas)

    de_nuevo = _responder(navegador, creados, cuentas=cuentas, modo="actualizar")

    assert de_nuevo == a
    assert _diagnosticos(db, a) == 2
    assert _origen(db, a) == "nuevo"


def test_actualizar_sin_sesion_exige_google(navegador, db, creados):
    """`modo=actualizar` no es una credencial: sin cookie válida no hay a quién actualizar."""
    antes = db.scalar(select(func.count()).select_from(Estudiante))
    respuesta = navegador.post("/student/vark", data=RESPUESTAS | ACEPTA | {"modo": "actualizar"})
    assert respuesta.status_code == 200
    assert "Continuar con Google" in respuesta.text
    assert _id_de_la_cookie(navegador) is None
    assert db.scalar(select(func.count()).select_from(Estudiante)) == antes


# --- 2. «Salir» ---------------------------------------------------------------


def test_salir_olvida_la_cookie_y_no_borra_datos(navegador, db, creados, cuentas):
    a = _responder(navegador, creados, cuentas=cuentas)

    respuesta = navegador.post("/student/salir", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/?salio=1"
    assert navegador.cookies.get(sesion.COOKIE_ESTUDIANTE) is None
    db.expire_all()
    assert db.get(Estudiante, a) is not None
    assert _diagnosticos(db, a) == 1


def test_salir_conserva_la_sesion_del_docente(http_docente, creados, cuentas):
    _responder(http_docente, creados, cuentas=cuentas)
    assert http_docente.cookies.get(sesion.COOKIE_DOCENTE) is not None

    http_docente.post("/student/salir", follow_redirects=False)

    assert http_docente.cookies.get(sesion.COOKIE_ESTUDIANTE) is None
    assert http_docente.cookies.get(sesion.COOKIE_DOCENTE) is not None


def test_la_confirmacion_de_salir(navegador, creados, cuentas):
    _responder(navegador, creados, cuentas=cuentas)

    respuesta = navegador.get("/student/salir")

    assert respuesta.status_code == 200
    assert re.search(r'<form[^>]*method="post"[^>]*action="/student/salir"', respuesta.text)
    assert "cuenta de Google" in respuesta.text


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


def test_el_cuestionario_con_sesion_pregunta_si_eres_tu(navegador, db, creados, cuentas):
    a = _responder(navegador, creados, cuentas=cuentas)
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


def test_soy_yo_muestra_el_cuestionario_sin_los_datos_opcionales(navegador, creados, cuentas):
    """Al actualizar, los datos sociodemográficos se descartan: no se piden."""
    _responder(navegador, creados, cuentas=cuentas)

    html = navegador.get("/student/vark?modo=actualizar").text

    assert re.search(r'name="modo"\s+value="actualizar"', html)
    assert 'name="q1"' in html
    assert 'name="carrera"' not in html
    assert 'name="acepto"' in html


def test_soy_otra_persona_cierra_la_sesion_y_vuelve_al_cuestionario(
    navegador, db, creados, cuentas,
):
    a = _responder(navegador, creados, cuentas=cuentas)

    respuesta = navegador.post(
        "/student/salir", data={"motivo": "otra_persona"}, follow_redirects=False
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/student/vark"
    assert navegador.cookies.get(sesion.COOKIE_ESTUDIANTE) is None

    b = _responder(navegador, creados, cuentas=cuentas, modo="nuevo")
    assert b != a
    assert _origen(db, b) == "otra_persona"


# --- 4. Origen del estudiante -------------------------------------------------


def test_origen_nuevo(navegador, db, creados, cuentas):
    assert _origen(db, _responder(navegador, creados, cuentas=cuentas, modo="nuevo")) == "nuevo"


def test_el_origen_aparece_en_la_exportacion_de_mis_datos(navegador, creados, cuentas):
    """Es un dato del estudiante: el derecho de acceso lo incluye (Política §2)."""
    _responder(navegador, creados, cuentas=cuentas, modo="nuevo")

    datos = navegador.get("/mis-datos/exportar").json()

    assert datos["estudiante"]["origen_registro"] == "nuevo"


def test_origen_tras_salir(navegador, db, creados, cuentas):
    _responder(navegador, creados, cuentas=cuentas)
    navegador.post("/student/salir")

    b = _responder(navegador, creados, cuentas=cuentas, modo="nuevo")

    assert _origen(db, b) == "tras_salir"
    # La marca se usa una vez: el siguiente registro ya no la hereda.
    assert navegador.cookies.get(sesion.COOKIE_ORIGEN) is None


def test_origen_con_la_sesion_de_otro_abierta(navegador, db, creados, cuentas):
    """Una pestaña cargada antes de que el otro abriera sesión: es otra persona."""
    a = _responder(navegador, creados, cuentas=cuentas)
    respuesta = navegador.post("/student/vark", data=RESPUESTAS | ACEPTA | {"modo": "nuevo"})
    assert respuesta.status_code == 403
    assert _origen(db, a) == "nuevo"
    assert _diagnosticos(db, a) == 1


def test_origen_tras_una_sesion_vencida(navegador, db, creados, cuentas):
    a = _responder(navegador, creados, cuentas=cuentas)
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

    b = _responder(navegador, creados, cuentas=cuentas, modo="nuevo")

    assert b != a
    assert _origen(db, b) == "sesion_vencida"
    assert _diagnosticos(db, a) == 1


# --- 5. Vencimiento configurable ----------------------------------------------


def test_la_sesion_vence_segun_la_configuracion(navegador, monkeypatch, creados, cuentas):
    monkeypatch.setattr(get_settings(), "sesion_estudiante_horas", 1)

    _responder(navegador, creados, cuentas=cuentas)
    respuesta = enviar_vark(navegador, data=RESPUESTAS | ACEPTA)

    expira = int(navegador.cookies.get(sesion.COOKIE_ESTUDIANTE).split(".")[2])
    assert abs(expira - (time.time() + 3600)) < 60
    # El navegador la guarda 30 días (lo que dice la Política); lo que vence es
    # la sesión, y una cookie vencida todavía permite marcar `sesion_vencida`.
    assert f"Max-Age={TREINTA_DIAS}" in respuesta.headers["set-cookie"]


def test_una_sesion_vencida_no_da_acceso(navegador, db, creados, cuentas):
    a = _responder(navegador, creados, cuentas=cuentas)
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


def test_la_cookie_no_vale_si_cambia_la_fecha_de_registro(navegador, db, creados, cuentas):
    """Tras `reset_db.py` los ids vuelven a 1: la cookie vieja no puede abrir otro perfil.

    Basta un microsegundo de diferencia en `fecha_registro` para que deje de valer.
    """
    a = _responder(navegador, creados, cuentas=cuentas)
    assert navegador.get("/student/profile", follow_redirects=False).status_code == 200

    db.expire_all()
    estudiante = db.get(Estudiante, a)
    estudiante.fecha_registro = estudiante.fecha_registro + timedelta(microseconds=1)
    db.commit()

    respuesta = navegador.get("/student/profile", follow_redirects=False)
    assert respuesta.status_code == 303


# --- 7. Pistas «¿No eres tú? Salir» -------------------------------------------


def test_la_cabecera_ofrece_salir_solo_con_sesion(navegador, creados, cuentas):
    assert 'href="/student/salir"' not in navegador.get("/").text

    _responder(navegador, creados, cuentas=cuentas)

    assert 'href="/student/salir"' in navegador.get("/student/catalog").text


def test_la_portada_con_sesion_pregunta_si_no_eres_tu(navegador, creados, cuentas):
    _responder(navegador, creados, cuentas=cuentas)

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
