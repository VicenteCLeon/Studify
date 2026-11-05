"""Acceso con Google y recuperación del mismo estudiante, sin llamadas externas."""

import re
import time
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from studify.config import get_settings
from studify.db.models import DiagnosticoVark, Estudiante, IntentoGoogle
from studify.main import app
from studify.web import sesion
from studify.web.routers import google_login
from tests import test_api_capsulas as pruebas_capsulas
from tests.conftest import necesita_bd
from tests.identidad_web import control_local_anterior, perfil_local_anterior

escenario = pruebas_capsulas.escenario
cliente_falso = pruebas_capsulas.cliente_falso


@pytest.fixture
def google_configurado(monkeypatch):
    ajustes = get_settings()
    monkeypatch.setattr(ajustes, "google_client_id", "cliente-de-prueba.apps.googleusercontent.com")
    monkeypatch.setattr(ajustes, "google_client_secret", "secreto-de-prueba")
    monkeypatch.setattr(
        ajustes, "google_redirect_uri", "https://testserver/student/google/callback"
    )


def _csrf(cliente):
    respuesta = cliente.get("/student/login")
    assert respuesta.status_code == 200
    return re.search(r'name="csrf" value="([^"]+)"', respuesta.text).group(1)


def test_login_existe_y_explica_si_falta_configuracion(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "", raising=False)
    monkeypatch.setattr(get_settings(), "google_client_secret", "", raising=False)
    respuesta = TestClient(app).get("/student/login")
    assert respuesta.status_code == 200
    assert "Google no está configurado" in respuesta.text


def test_iniciar_google_sin_configuracion_no_redirige_a_proveedor(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "", raising=False)
    monkeypatch.setattr(get_settings(), "google_client_secret", "", raising=False)
    respuesta = TestClient(app).post("/student/google/iniciar", follow_redirects=False)
    assert respuesta.status_code == 503


@necesita_bd
def test_inicio_exige_csrf_y_envia_nonce_pkce(db, google_configurado):
    cliente = TestClient(app)
    assert cliente.post("/student/google/iniciar", data={"csrf": "inventado"}).status_code == 403
    respuesta = cliente.post(
        "/student/google/iniciar", data={"csrf": _csrf(cliente), "rol": "estudiante"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    destino = urlsplit(respuesta.headers["location"])
    assert destino.netloc == "accounts.google.com"
    parametros = parse_qs(destino.query)
    assert parametros["scope"] == ["openid email profile"]
    assert parametros["code_challenge_method"] == ["S256"]
    assert parametros["nonce"] and parametros["state"]
    assert "secreto-de-prueba" not in respuesta.headers["location"]
    assert "HttpOnly" in respuesta.headers["set-cookie"]
    estado = parametros["state"][0]
    db.execute(delete(IntentoGoogle).where(
        IntentoGoogle.estado_hash == sha256(estado.encode()).hexdigest()
    ))
    db.commit()


@pytest.fixture
def cuentas(db, google_configurado, monkeypatch):
    """Google falso; se limpian solo los estudiantes e intentos de este test."""
    sub = "google-test-" + uuid4().hex
    identidad = {"sub": sub, "email": "cuenta@example.test", "nombre": "Estudiante"}
    llamadas = []
    estados, estudiantes = [], []

    def intercambio(codigo, verificador):
        llamadas.append((codigo, verificador))
        return "token-de-prueba"

    monkeypatch.setattr(google_login, "intercambiar_codigo", intercambio)
    monkeypatch.setattr(google_login, "verificar_token", lambda token, nonce: dict(identidad))
    contexto = SimpleNamespace(
        identidad=identidad, llamadas=llamadas, estados=estados, estudiantes=estudiantes,
    )
    yield contexto
    db.rollback()
    db.expire_all()
    db.execute(delete(IntentoGoogle).where(IntentoGoogle.estado_hash.in_(estados)))
    # Identidades creadas sin cookie por una respuesta que falló también se limpian.
    ids = set(estudiantes) | set(db.scalars(select(Estudiante.id_estudiante).where(
        Estudiante.google_sub == sub
    )).all())
    for id_estudiante in ids:
        estudiante = db.get(Estudiante, id_estudiante)
        if estudiante is not None:
            db.delete(estudiante)
    db.commit()


def _iniciar(cliente, cuentas, **datos):
    # Desde el punto 2a elegir grupo es obligatorio al entrar: los tests que no
    # prueban la elección eligen el experimental, como lo haría el usuario.
    if datos.get("accion", "entrar") == "entrar":
        datos.setdefault("rol", "estudiante")
    respuesta = cliente.post(
        "/student/google/iniciar", data={"csrf": _csrf(cliente)} | datos,
        follow_redirects=False,
    )
    assert respuesta.status_code == 303, respuesta.text
    state = parse_qs(urlsplit(respuesta.headers["location"]).query)["state"][0]
    cuentas.estados.append(sha256(state.encode()).hexdigest())
    return state


def _volver(cliente, cuentas, state, **datos):
    respuesta = cliente.get(
        "/student/google/callback", params={"state": state, "code": "codigo"} | datos,
        follow_redirects=False,
    )
    cookie = cliente.cookies.get(sesion.COOKIE_ESTUDIANTE)
    if cookie:
        cuentas.estudiantes.append(int(cookie.split(".")[0]))
    return respuesta


def _id(cliente):
    return int(cliente.cookies.get(sesion.COOKIE_ESTUDIANTE).split(".")[0])


def _formulario(cliente, ruta):
    return {"token_sesion": re.search(
        r'name="token_sesion" value="([^"]+)"', cliente.get(ruta).text
    ).group(1)}


@necesita_bd
def test_descubrir_no_guarda_datos_antes_de_google(db, google_configurado):
    cliente = TestClient(app)
    antes = db.scalar(select(func.count()).select_from(Estudiante))
    respuesta = cliente.post("/student/vark", data={
        "acepto": "si", "q1": "a", "carrera": "Informática",
    })
    assert respuesta.status_code == 200
    assert '/student/login?continuar=vark' in respuesta.text
    assert not cliente.cookies.get(sesion.COOKIE_ESTUDIANTE)
    assert db.scalar(select(func.count()).select_from(Estudiante)) == antes
    htmx = cliente.post("/student/vark", data={"acepto": "si", "q1": "a"}, headers={
        "HX-Request": "true",
    })
    assert htmx.status_code == 200  # 204 borraría el borrador antes de autenticar.
    assert htmx.headers["HX-Redirect"] == "/student/login?continuar=vark"
    assert db.scalar(select(func.count()).select_from(Estudiante)) == antes


@necesita_bd
def test_google_sin_configurar_tampoco_permite_guardar_vark(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    cliente = TestClient(app)
    antes = db.scalar(select(func.count()).select_from(Estudiante))
    respuesta = cliente.post("/student/vark", data={"acepto": "si", "q1": "a"})
    assert "Continuar con Google" in respuesta.text
    assert not cliente.cookies.get(sesion.COOKIE_ESTUDIANTE)
    assert db.scalar(select(func.count()).select_from(Estudiante)) == antes


@necesita_bd
def test_perfil_local_debe_vincularse_antes_de_guardar_otro_vark(db, cuentas):
    cliente = TestClient(app)
    original = perfil_local_anterior(cliente)
    cuentas.estudiantes.append(original)
    respuesta = cliente.post("/student/vark", data={
        "acepto": "si", "q1": "a", "modo": "actualizar",
    })
    assert "Continuar con Google" in respuesta.text
    assert len(db.get(Estudiante, original).diagnosticos) == 1
    state = _iniciar(cliente, cuentas, accion="vincular", continuar="vark")
    assert _volver(cliente, cuentas, state).headers["location"] == "/student/vark?modo=actualizar"
    assert _id(cliente) == original
    assert len(db.get(Estudiante, original).diagnosticos) == 1


@necesita_bd
def test_continuar_cuestionario_google_recupera_borrador_sin_guardarlo(db, cuentas):
    cliente = TestClient(app)
    previo = cliente.get("/student/vark").text
    contexto = re.search(r'data-contexto-borrador="([^"]+)"', previo).group(1)
    login = cliente.get("/student/login?continuar=vark")
    assert 'data-olvidar-borrador' not in login.text
    csrf = re.search(r'name="csrf" value="([^"]+)"', login.text).group(1)
    inicio = cliente.post("/student/google/iniciar", data={
        "csrf": csrf, "continuar": "vark", "rol": "estudiante",
    }, follow_redirects=False)
    state = parse_qs(urlsplit(inicio.headers["location"]).query)["state"][0]
    cuentas.estados.append(sha256(state.encode()).hexdigest())
    vuelta = _volver(cliente, cuentas, state)
    assert vuelta.headers["location"] == "/student/vark?modo=actualizar"
    formulario = cliente.get(vuelta.headers["location"])
    assert f'data-contexto-anterior="{contexto}"' in formulario.text
    estudiante = db.get(Estudiante, _id(cliente))
    assert estudiante.rol == "estudiante"
    assert not estudiante.diagnosticos
    assert not estudiante.aceptaciones
    assert cliente.post("/student/vark", data=_formulario(cliente, vuelta.headers["location"]) | {
        "acepto": "si", "q1": "a", "carrera": "Informática",
    }).status_code == 204
    db.expire_all()
    assert len(estudiante.diagnosticos) == 1
    assert estudiante.carrera == "Informática"
    assert not cliente.cookies.get(google_login.COOKIE_VARK)


@necesita_bd
@pytest.mark.parametrize("caso", ["alterada", "otro_intento", "vencida", "excesiva"])
def test_continuidad_invalida_no_recupera_el_borrador(db, cuentas, monkeypatch, caso):
    cliente = TestClient(app)
    state = _iniciar(cliente, cuentas, continuar="vark")
    cookie = cliente.cookies.get(google_login.COOKIE_VARK)
    if caso == "alterada":
        cookie = cookie[:-1] + ("0" if cookie[-1] != "0" else "1")
    elif caso == "excesiva":
        cookie = "a.a." + "1" * 5000 + ".a"
    else:
        respuesta = Response()
        reloj = google_login.time.time
        if caso == "vencida":
            monkeypatch.setattr(google_login.time, "time", lambda: 0)
        google_login._guardar_continuacion(
            respuesta, "a" * 64, "otro-intento" if caso == "otro_intento" else state,
        )
        monkeypatch.setattr(google_login.time, "time", reloj)
        cookie = respuesta.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    cliente.cookies.set(google_login.COOKIE_VARK, cookie,
                        domain="testserver.local", path="/student")
    vuelta = _volver(cliente, cuentas, state)
    assert vuelta.status_code == 303
    assert vuelta.headers["location"] == "/student/vark"
    assert 'data-contexto-anterior=""' in cliente.get("/student/vark").text
    assert not db.get(Estudiante, _id(cliente)).diagnosticos


@necesita_bd
def test_borrador_no_se_entrega_a_otra_cuenta_y_salir_lo_olvida(db, cuentas):
    cliente = TestClient(app)
    _volver(cliente, cuentas, _iniciar(cliente, cuentas, continuar="vark"))
    antigua = cliente.cookies.get(google_login.COOKIE_VARK)
    cliente.post("/student/salir")
    assert not cliente.cookies.get(google_login.COOKIE_VARK)
    cuentas.identidad["sub"] = "otra-google-" + uuid4().hex
    _volver(cliente, cuentas, _iniciar(cliente, cuentas))
    cliente.cookies.set(google_login.COOKIE_VARK, antigua,
                        domain="testserver.local", path="/student")
    assert 'data-contexto-anterior=""' in cliente.get("/student/vark").text


@necesita_bd
def test_continuar_con_cuenta_existente_no_reemplaza_perfil_hasta_confirmar(db, cuentas):
    cliente = TestClient(app)
    _volver(cliente, cuentas, _iniciar(cliente, cuentas))
    cliente.post("/student/vark", data=_formulario(cliente, "/student/vark") | {
        "acepto": "si", "q1": "d", "carrera": "Carrera original",
    })
    original = _id(cliente)
    cliente.post("/student/salir")
    vuelta = _volver(cliente, cuentas, _iniciar(cliente, cuentas, continuar="vark"))
    assert vuelta.headers["location"] == "/student/vark?modo=actualizar"
    assert _id(cliente) == original
    db.expire_all()
    estudiante = db.get(Estudiante, original)
    assert len(estudiante.diagnosticos) == 1
    formulario = cliente.get(vuelta.headers["location"]).text
    assert "Vas a actualizar tu perfil" in formulario
    assert 'data-contexto-anterior=""' not in formulario
    assert cliente.post("/student/vark", data=_formulario(cliente, vuelta.headers["location"]) | {
        "acepto": "si", "q1": "a", "carrera": "Otra carrera",
    }).status_code == 204
    db.expire_all()
    assert len(estudiante.diagnosticos) == 2
    assert estudiante.carrera == "Carrera original"


@necesita_bd
def test_continuar_con_cuenta_control_no_habilita_personalizacion(db, cuentas):
    cliente = TestClient(app)
    _volver(cliente, cuentas, _iniciar(cliente, cuentas, rol="control"))
    cliente.post("/student/control", data=_formulario(cliente, "/student/control") | {
        "acepto": "si",
    })
    original = _id(cliente)
    cliente.post("/student/salir")
    vuelta = _volver(cliente, cuentas, _iniciar(cliente, cuentas, continuar="vark"))
    assert vuelta.headers["location"] == "/student/profile"
    assert not cliente.cookies.get(google_login.COOKIE_VARK)
    assert cliente.post("/student/vark", data={"acepto": "si", "q1": "a"}).status_code == 403
    db.expire_all()
    assert db.get(Estudiante, original).rol == "control"
    assert not db.get(Estudiante, original).diagnosticos


@necesita_bd
def test_cancelar_google_permite_reintentar_sin_perder_continuidad(db, cuentas):
    cliente = TestClient(app)
    cancelacion = _volver(cliente, cuentas, _iniciar(cliente, cuentas, continuar="vark"),
                         error="access_denied")
    assert cancelacion.status_code == 400
    assert 'href="/student/login?continuar=vark"' in cancelacion.text
    login = cliente.get("/student/login?continuar=vark").text
    assert "data-olvidar-borrador" not in login
    vuelta = _volver(cliente, cuentas, _iniciar(cliente, cuentas, continuar="vark"))
    assert vuelta.headers["location"] == "/student/vark?modo=actualizar"


@necesita_bd
def test_registro_google_y_cuestionario_conservan_un_solo_estudiante(db, cuentas):
    cliente = TestClient(app)
    respuesta = _volver(cliente, cuentas, _iniciar(cliente, cuentas))
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/student/vark"
    id_estudiante = _id(cliente)
    formulario = cliente.get("/student/vark").text
    assert "Antes de empezar" in formulario
    for campo in ("rango_etario", "genero", "carrera", "consiento_genero"):
        assert f'name="{campo}"' in formulario
    assert cliente.post("/student/vark", data=_formulario(cliente, "/student/vark") | {
        "acepto": "si", "q1": "a", "modo": "nuevo", "carrera": "Informática",
        "genero": "Femenino", "consiento_genero": "si",
        "rango_etario": "21 - 23 años",
    }).status_code == 204
    assert _id(cliente) == id_estudiante
    db.expire_all()
    estudiante = db.get(Estudiante, id_estudiante)
    assert estudiante.google_email == "cuenta@example.test"
    assert estudiante.carrera == "Informática"
    assert estudiante.rango_etario == "21 - 23 años"
    assert estudiante.genero == "Femenino"
    assert len(estudiante.diagnosticos) == 1
    assert {a.documento for a in estudiante.aceptaciones} == {"terminos", "privacidad", "genero"}
    assert "docente" not in cliente.cookies


@necesita_bd
def test_entrar_despues_de_salir_recupera_id_perfil_y_rol(db, cuentas):
    cliente = TestClient(app)
    _volver(cliente, cuentas, _iniciar(cliente, cuentas))
    id_estudiante = _id(cliente)
    cliente.post("/student/vark", data=_formulario(cliente, "/student/vark") | {
        "acepto": "si", "q1": "a", "rango_etario": "24 - 26 años",
        "genero": "Masculino", "consiento_genero": "si", "carrera": "Informática",
    })
    cliente.post("/student/salir")
    assert not cliente.cookies.get(sesion.COOKIE_ESTUDIANTE)
    otro = TestClient(app)
    respuesta = _volver(otro, cuentas, _iniciar(otro, cuentas, rol="control"))
    assert respuesta.status_code == 303
    assert _id(otro) == id_estudiante
    db.expire_all()
    estudiante = db.get(Estudiante, id_estudiante)
    assert estudiante.rol == "estudiante"
    assert len(estudiante.diagnosticos) == 1
    assert estudiante.rango_etario == "24 - 26 años"
    assert estudiante.genero == "Masculino"
    assert estudiante.carrera == "Informática"
    assert respuesta.headers["location"] == "/student/profile"


@necesita_bd
def test_google_control_conserva_grupo_y_completa_aceptacion_sin_duplicarse(db, cuentas):
    cliente = TestClient(app)
    respuesta = _volver(cliente, cuentas, _iniciar(cliente, cuentas, rol="control"))
    assert respuesta.headers["location"] == "/student/control"
    primero = _id(cliente)
    formulario = cliente.get("/student/control").text
    assert "Entrar al grupo control" in formulario
    for campo in ("rango_etario", "genero", "carrera", "consiento_genero"):
        assert f'name="{campo}"' in formulario
    assert cliente.post("/student/control", data=_formulario(cliente, "/student/control") | {
        "acepto": "si", "carrera": "Curso de prueba", "rango_etario": "18 - 20 años",
        "genero": "Femenino", "consiento_genero": "si",
    }).status_code == 204
    assert _id(cliente) == primero
    cliente.post("/student/salir")
    otro = TestClient(app)
    _volver(otro, cuentas, _iniciar(otro, cuentas, rol="estudiante"))
    assert _id(otro) == primero
    assert otro.post("/student/vark", data={"acepto": "si", "q1": "a"}).status_code == 403
    db.expire_all()
    estudiante = db.get(Estudiante, primero)
    assert estudiante.rol == "control" and not estudiante.diagnosticos
    assert estudiante.carrera == "Curso de prueba"
    assert estudiante.rango_etario == "18 - 20 años"
    assert estudiante.genero == "Femenino"


@necesita_bd
def test_vincular_perfil_local_conserva_diagnostico_y_aceptaciones(db, cuentas):
    cliente = TestClient(app)
    original = perfil_local_anterior(cliente)
    cuentas.estudiantes.append(original)
    diagnostico = db.scalar(select(DiagnosticoVark.id_diagnostico).where(
        DiagnosticoVark.id_estudiante == original
    ))
    state = _iniciar(cliente, cuentas, accion="vincular", rol="control")
    respuesta = _volver(cliente, cuentas, state)
    assert respuesta.status_code == 303
    assert _id(cliente) == original
    db.expire_all()
    estudiante = db.get(Estudiante, original)
    assert estudiante.google_sub == cuentas.identidad["sub"]
    assert estudiante.rol == "estudiante"
    assert estudiante.diagnosticos[0].id_diagnostico == diagnostico
    assert len(estudiante.aceptaciones) == 2


@necesita_bd
def test_no_se_fusionan_dos_perfiles_por_correo_ni_por_sub(db, cuentas):
    propietario = Estudiante(
        google_sub=cuentas.identidad["sub"], google_email=cuentas.identidad["email"],
    )
    db.add(propietario)
    db.commit()
    cuentas.estudiantes.append(propietario.id_estudiante)
    cliente = TestClient(app)
    local = control_local_anterior(cliente)
    cuentas.estudiantes.append(local)
    respuesta = _volver(cliente, cuentas, _iniciar(cliente, cuentas, accion="vincular"))
    assert respuesta.status_code == 409
    assert _id(cliente) == local
    db.expire_all()
    assert db.get(Estudiante, local).google_sub is None
    assert db.get(Estudiante, local).rol == "control"


@necesita_bd
@pytest.mark.parametrize("state", ["", "falso", "ñ"])
def test_state_ajeno_no_llega_a_google(cuentas, state):
    cliente = TestClient(app)
    respuesta = _volver(cliente, cuentas, state)
    assert respuesta.status_code == 400
    assert cuentas.llamadas == []
    assert not cliente.cookies.get(sesion.COOKIE_ESTUDIANTE)


@necesita_bd
def test_intento_vencido_y_repetido_no_autentican(db, cuentas):
    cliente = TestClient(app)
    state = _iniciar(cliente, cuentas)
    intento = db.get(IntentoGoogle, sha256(state.encode()).hexdigest())
    intento.expira = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert _volver(cliente, cuentas, state).status_code == 400
    assert cuentas.llamadas == []
    state = _iniciar(cliente, cuentas)
    assert _volver(cliente, cuentas, state).status_code == 303
    cliente.cookies.set(google_login.COOKIE_OAUTH, state, path="/student")
    assert _volver(cliente, cuentas, state).status_code == 400
    assert len(cuentas.llamadas) == 1


@necesita_bd
def test_cancelacion_y_caida_del_proveedor_no_crean_cuenta(db, cuentas, monkeypatch):
    cliente = TestClient(app)
    cancelada = _volver(cliente, cuentas, _iniciar(cliente, cuentas), error="access_denied")
    assert cancelada.status_code == 400
    assert cuentas.llamadas == []

    def caido(*args):
        raise httpx.ReadTimeout("detalle privado")

    monkeypatch.setattr(google_login, "intercambiar_codigo", caido)
    respuesta = _volver(cliente, cuentas, _iniciar(cliente, cuentas))
    assert respuesta.status_code == 502
    assert "detalle privado" not in respuesta.text
    assert db.scalar(select(func.count()).select_from(Estudiante).where(
        Estudiante.google_sub == cuentas.identidad["sub"]
    )) == 0


@necesita_bd
def test_sesion_cambiada_durante_vinculacion_se_rechaza(cuentas):
    cliente = TestClient(app)
    cuentas.estudiantes.append(control_local_anterior(cliente))
    state = _iniciar(cliente, cuentas, accion="vincular")
    cliente.post("/student/salir")
    cliente.cookies.set(google_login.COOKIE_OAUTH, state, path="/student")
    assert _volver(cliente, cuentas, state).status_code == 409
    assert cuentas.llamadas == []


@necesita_bd
@pytest.mark.parametrize("rol,ruta,datos", [
    ("estudiante", "/student/vark", {"acepto": "si", "q1": "a"}),
    ("control", "/student/control", {"acepto": "si", "carrera": "Otra persona"}),
])
def test_formulario_de_otra_cuenta_no_modifica_el_perfil(db, cuentas, rol, ruta, datos):
    cliente = TestClient(app)
    _volver(cliente, cuentas, _iniciar(cliente, cuentas, rol=rol))
    html = cliente.get(ruta).text
    anterior = re.search(r'name="token_sesion" value="([^"]+)"', html)
    token_anterior = anterior.group(1) if anterior else ""
    cliente.post("/student/salir")
    cuentas.identidad["sub"] = "google-test-" + uuid4().hex
    _volver(cliente, cuentas, _iniciar(cliente, cuentas, rol=rol))
    id_actual = _id(cliente)
    respuesta = cliente.post(ruta, data=datos | {"token_sesion": token_anterior})
    assert respuesta.status_code == 403
    db.expire_all()
    actual = db.get(Estudiante, id_actual)
    assert not actual.diagnosticos and not actual.aceptaciones
    assert actual.carrera is None
    token_actual = re.search(
        r'name="token_sesion" value="([^"]+)"', cliente.get(ruta).text
    ).group(1)
    assert cliente.post(ruta, data=datos | {"token_sesion": token_actual}).status_code == 204
    assert _id(cliente) == id_actual


@necesita_bd
def test_token_invalido_no_crea_ni_vincula_estudiante(db, cuentas, monkeypatch):
    def invalido(*args):
        raise ValueError("token malicioso")

    monkeypatch.setattr(google_login, "verificar_token", invalido)
    cliente = TestClient(app)
    respuesta = _volver(cliente, cuentas, _iniciar(cliente, cuentas))
    assert respuesta.status_code == 401
    assert "token malicioso" not in respuesta.text
    assert not cliente.cookies.get(sesion.COOKIE_ESTUDIANTE)


@necesita_bd
def test_correo_compartido_no_se_utiliza_para_fusionar_cuentas(db, cuentas):
    otro = Estudiante(google_sub="otro-" + uuid4().hex, google_email=cuentas.identidad["email"])
    db.add(otro)
    db.commit()
    cuentas.estudiantes.append(otro.id_estudiante)
    cliente = TestClient(app)
    assert _volver(cliente, cuentas, _iniciar(cliente, cuentas)).status_code == 303
    assert _id(cliente) != otro.id_estudiante


@necesita_bd
def test_capsulas_exportacion_y_supresion_siguen_en_el_mismo_estudiante(
    db, cuentas, escenario, cliente_falso
):
    from studify.api.routers.capsules import crear_capsula
    from studify.api.schemas_capsulas import CapsulaIn
    from studify.web import consentimiento

    estudiante = escenario["estudiante"]
    cuentas.estudiantes.append(estudiante.id_estudiante)
    capsula = crear_capsula(
        CapsulaIn(id_estudiante=estudiante.id_estudiante,
                  id_objetivo=escenario["objetivo"].id_objetivo),
        regenerar=False, db=db, cliente=cliente_falso,
    )
    consentimiento.registrar(db, estudiante.id_estudiante)
    cliente = TestClient(app)
    cliente.cookies.set(sesion.COOKIE_ESTUDIANTE, sesion.valor_cookie(
        estudiante.id_estudiante, estudiante.fecha_registro
    ), domain="testserver.local", path="/")
    vinculada = _volver(cliente, cuentas, _iniciar(cliente, cuentas, accion="vincular"))
    assert vinculada.status_code == 303
    cliente.post("/student/salir")
    recuperado = TestClient(app)
    assert _volver(recuperado, cuentas, _iniciar(recuperado, cuentas)).status_code == 303
    exportado = recuperado.get("/mis-datos/exportar").json()
    assert exportado["estudiante"]["google_sub"] == cuentas.identidad["sub"]
    assert exportado["estudiante"]["google_email"] == "cuenta@example.test"
    assert exportado["estudiante"]["google_nombre"] == "Estudiante"
    assert exportado["capsulas"][0]["id_capsula"] == capsula.id_capsula
    assert len(exportado["diagnosticos_vark"]) == 1
    db.add(IntentoGoogle(
        estado_hash=sha256(uuid4().bytes).hexdigest(), nonce="nonce", verificador="verificador",
        expira=datetime.now(UTC) + timedelta(minutes=1), rol=estudiante.rol,
        id_estudiante=estudiante.id_estudiante,
    ))
    db.commit()
    respuesta = recuperado.post("/mis-datos/eliminar", data={"confirmo": "si"})
    assert respuesta.status_code == 200
    assert not recuperado.cookies.get(sesion.COOKIE_ESTUDIANTE)
    db.expire_all()
    assert db.get(Estudiante, cuentas.estudiantes[0]) is None
    assert db.scalar(select(func.count()).select_from(IntentoGoogle).where(
        IntentoGoogle.id_estudiante == cuentas.estudiantes[0]
    )) == 0


@necesita_bd
@pytest.mark.parametrize("uri", ["http://atacante.invalid/callback", "javascript:alert(1)"])
def test_callback_configurado_inseguro_se_rechaza(cuentas, monkeypatch, uri):
    monkeypatch.setattr(get_settings(), "google_redirect_uri", uri)
    cliente = TestClient(app)
    respuesta = cliente.post("/student/google/iniciar", data={"csrf": _csrf(cliente)})
    assert respuesta.status_code == 503
    assert cuentas.llamadas == []


def test_codigo_se_intercambia_con_secret_y_pkce_solo_en_servidor(
    google_configurado, monkeypatch
):
    solicitudes = []
    cliente_real = httpx.Client

    def responder(request):
        solicitudes.append(request)
        return httpx.Response(200, json={"id_token": "identidad-firmada"})

    monkeypatch.setattr(google_login.httpx, "Client", lambda **kwargs: cliente_real(
        transport=httpx.MockTransport(responder), **kwargs
    ))
    token = google_login.intercambiar_codigo("codigo-unico", "verificador-unico")
    assert token == "identidad-firmada"
    assert str(solicitudes[0].url) == google_login.TOKEN_URL
    datos = parse_qs(solicitudes[0].content.decode())
    assert datos["client_secret"] == ["secreto-de-prueba"]
    assert datos["code_verifier"] == ["verificador-unico"]
    assert datos["grant_type"] == ["authorization_code"]


@pytest.fixture
def firma_google(monkeypatch, google_configurado):
    """JWT RSA firmado localmente; se ejecuta la verificación oficial completa."""
    import json

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from google.auth.crypt import RSASigner
    from google.auth.jwt import encode

    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_privada = privada.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pem_publica = privada.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    class Certificados:
        def __init__(self, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return SimpleNamespace(status=200, data=json.dumps({"clave": pem_publica}).encode())

    monkeypatch.setattr(google_login, "GoogleRequest", Certificados)
    firmante = RSASigner.from_string(pem_privada, key_id="clave")

    def token(**cambios):
        claims = {
            "iss": "https://accounts.google.com", "sub": "sub-verificado",
            "aud": get_settings().google_client_id, "iat": int(time.time()),
            "exp": int(time.time()) + 300, "email": "cuenta@example.test",
            "email_verified": True, "nonce": "nonce-correcto", "name": "Nombre",
        } | cambios
        return encode(firmante, claims).decode()

    return token


def test_verifica_jwt_real_con_firma_audiencia_y_nonce(firma_google):
    identidad = google_login.verificar_token(firma_google(), "nonce-correcto")
    assert identidad == {
        "sub": "sub-verificado", "email": "cuenta@example.test", "nombre": "Nombre",
    }


@pytest.mark.parametrize("cambios", [
    {"aud": "otro-cliente"}, {"iss": "https://atacante.invalid"},
    {"exp": 1}, {"iat": 9999999999}, {"nonce": "otro"},
    {"email_verified": False}, {"email_verified": "true"},
    {"sub": ""}, {"email": None},
    {"azp": "otro-cliente"},
])
def test_rechaza_jwt_invalido(firma_google, cambios):
    from google.auth.exceptions import GoogleAuthError

    with pytest.raises((ValueError, GoogleAuthError)):
        google_login.verificar_token(firma_google(**cambios), "nonce-correcto")


def test_rechaza_firma_alterada(firma_google):
    token = firma_google()
    cabecera, cuerpo, firma = token.split(".")
    firma = ("a" if firma[0] != "a" else "b") + firma[1:]
    with pytest.raises(ValueError):
        google_login.verificar_token(f"{cabecera}.{cuerpo}.{firma}", "nonce-correcto")


@necesita_bd
def test_migracion_google_preserva_rol_unicidad_y_es_reversible():
    import runpy
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy.exc import IntegrityError

    from studify.db.session import engine

    migracion = runpy.run_path(str(Path(__file__).resolve().parents[1]
        / "alembic/versions/a7c3d9e51f64_identidad_google.py"))
    with engine.connect() as conn:
        transaccion = conn.begin()
        try:
            esquema = "test_google_" + uuid4().hex
            conn.exec_driver_sql(f'CREATE SCHEMA "{esquema}"')
            conn.exec_driver_sql(f'SET LOCAL search_path TO "{esquema}"')
            conn.exec_driver_sql(
                "CREATE TABLE estudiante (id_estudiante integer PRIMARY KEY, rol varchar(20))"
            )
            conn.exec_driver_sql("INSERT INTO estudiante VALUES (1, 'estudiante'), (2, 'control')")
            with Operations.context(MigrationContext.configure(conn)):
                migracion["upgrade"]()
                assert conn.exec_driver_sql(
                    "SELECT count(*) FROM estudiante WHERE google_sub IS NULL"
                ).scalar() == 2
                conn.exec_driver_sql(
                    "UPDATE estudiante SET google_sub = 'sub-unico' WHERE id_estudiante = 1"
                )
                with pytest.raises(IntegrityError), conn.begin_nested():
                    conn.exec_driver_sql(
                        "UPDATE estudiante SET google_sub = 'sub-unico' WHERE id_estudiante = 2"
                    )
                conn.exec_driver_sql(
                    "INSERT INTO intento_google VALUES "
                    "('hash', 'nonce', 'verificador', now(), 'estudiante', 1)"
                )
                conn.exec_driver_sql("DELETE FROM estudiante WHERE id_estudiante = 1")
                assert conn.exec_driver_sql("SELECT count(*) FROM intento_google").scalar() == 0
                migracion["downgrade"]()
                assert conn.exec_driver_sql("SELECT rol FROM estudiante").scalar() == "control"
                migracion["upgrade"]()
                assert conn.exec_driver_sql("SELECT rol FROM estudiante").scalar() == "control"
        finally:
            transaccion.rollback()


# --- Selección de grupo (punto 2a) --------------------------------------------


def _radio(html: str, valor: str) -> str:
    return re.search(rf'<input[^>]*name="rol"[^>]*value="{valor}"[^>]*>', html).group(0)


@pytest.mark.parametrize("ruta", ["/student/login", "/student/login?continuar=vark"])
def test_login_pide_elegir_grupo_sin_preseleccion(google_configurado, ruta):
    html = TestClient(app).get(ruta).text

    assert "Selecciona tu grupo" in html
    assert "<select" not in html
    control, experimental = _radio(html, "control"), _radio(html, "estudiante")
    assert html.index(control) < html.index(experimental)  # Control primero (equipo)
    for radio in (control, experimental):
        assert 'type="radio"' in radio and "required" in radio
        assert "checked" not in radio
    assert "El contenido es un resumen estándar, igual para todos." in html
    assert "El contenido se adapta a tu estilo de aprendizaje." in html
    assert "data-borrador-segun-grupo" in html


def test_login_preselecciona_control_desde_su_entrada(google_configurado):
    html = TestClient(app).get("/student/login?rol=control").text

    assert "checked" in _radio(html, "control")
    assert "checked" not in _radio(html, "estudiante")


@necesita_bd
def test_iniciar_sin_grupo_no_va_a_google(db, google_configurado):
    cliente = TestClient(app)
    antes = db.scalar(select(func.count()).select_from(IntentoGoogle))
    for datos in ({}, {"rol": ""}, {"rol": "otro"}):
        respuesta = cliente.post(
            "/student/google/iniciar", data={"csrf": _csrf(cliente)} | datos,
            follow_redirects=False,
        )
        assert respuesta.status_code in (400, 422)
        assert "accounts.google.com" not in respuesta.headers.get("location", "")
    assert db.scalar(select(func.count()).select_from(IntentoGoogle)) == antes


@necesita_bd
@pytest.mark.parametrize(("rol", "destino"), [
    ("control", "/student/control"), ("estudiante", "/student/vark"),
])
def test_el_grupo_elegido_queda_en_la_cuenta_nueva(db, cuentas, rol, destino):
    cliente = TestClient(app)
    respuesta = _volver(cliente, cuentas, _iniciar(cliente, cuentas, rol=rol))

    assert respuesta.headers["location"] == destino
    db.expire_all()
    estudiante = db.get(Estudiante, _id(cliente))
    assert estudiante.rol == rol
    assert not estudiante.diagnosticos


@necesita_bd
def test_elegir_control_descarta_el_borrador_vark(db, cuentas):
    """Si responde «Descubre tu estilo» y elige Control, no se guarda nada del VARK."""
    cliente = TestClient(app)
    cliente.post("/student/vark", data={"acepto": "si", "q1": "a", "carrera": "Informática"})
    state = _iniciar(cliente, cuentas, continuar="vark", rol="control")
    assert not cliente.cookies.get(google_login.COOKIE_VARK)

    vuelta = _volver(cliente, cuentas, state)

    assert vuelta.headers["location"] == "/student/control"
    assert not cliente.cookies.get(google_login.COOKIE_VARK)
    estudiante = db.get(Estudiante, _id(cliente))
    assert estudiante.rol == "control"
    assert estudiante.carrera is None
    assert not estudiante.diagnosticos
    assert cliente.get("/student/vark", follow_redirects=False).headers["location"] == (
        "/student/profile"
    )
    assert cliente.post("/student/vark", data={"acepto": "si", "q1": "a"}).status_code == 403
    assert db.scalar(select(func.count()).select_from(DiagnosticoVark).where(
        DiagnosticoVark.id_estudiante == estudiante.id_estudiante
    )) == 0


@necesita_bd
def test_cuenta_existente_que_elige_control_con_borrador_no_lo_recupera(db, cuentas):
    """La cuenta conserva su grupo; el borrador se descarta igual al elegir Control."""
    cliente = TestClient(app)
    _volver(cliente, cuentas, _iniciar(cliente, cuentas, rol="estudiante"))
    original = _id(cliente)
    cliente.post("/student/salir")

    vuelta = _volver(cliente, cuentas, _iniciar(cliente, cuentas, continuar="vark", rol="control"))

    assert _id(cliente) == original
    assert vuelta.headers["location"] == "/student/vark"
    assert not cliente.cookies.get(google_login.COOKIE_VARK)
    db.expire_all()
    assert db.get(Estudiante, original).rol == "estudiante"
    assert 'data-contexto-anterior=""' in cliente.get("/student/vark").text
