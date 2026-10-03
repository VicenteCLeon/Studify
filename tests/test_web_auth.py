"""Acceso al panel del docente (26-ago-2026).

Lo que protegen estos tests es la separación entre las dos vistas del sistema.
Hasta ahora `/teacher/*` estaba abierto: cualquiera que escribiera la URL podía
validar fragmentos —y **lo que se valida es lo único que el retriever recupera**
(cap. 12/13)—, ver las analíticas de la cohorte y gastar créditos del LLM en el
simulador. La puerta que cierra eso es una sola dependencia; estos tests fijan
que siga puesta, que cubra también las rutas que se agreguen después y que los
modos de fallo conocidos de un login (redirector abierto, cookie falsificada,
sesión que sobrevive a la rotación de la clave, fuerza bruta) queden cerrados.

Casi ninguno necesita Postgres: el guardián rechaza **antes** de que el handler
pida la base, y eso mismo es una propiedad que vale la pena tener.
"""

import time

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from studify.config import get_settings
from studify.main import app
from studify.web import sesion
from studify.web.routers import auth
from tests.conftest import CLAVE_DOCENTE, USUARIO_DOCENTE, necesita_bd

# Rutas de `/teacher/*` que tienen que quedar abiertas: el login, porque es la
# forma de entrar, y el logout, porque cerrar sesión debe funcionar aunque la
# sesión ya haya vencido.
RUTAS_ABIERTAS = {"/teacher/login", "/teacher/logout"}


@pytest.fixture(autouse=True)
def sin_bloqueo_previo():
    """El freno de fuerza bruta cuenta en memoria del proceso y por IP.

    Todos los tests salen de la misma IP ficticia de `TestClient`, así que sin
    esto el que prueba claves incorrectas dejaría bloqueados a los siguientes.
    """
    auth.reiniciar_intentos()
    yield
    auth.reiniciar_intentos()


@pytest.fixture
def http() -> TestClient:
    return TestClient(app)


@pytest.fixture
def sin_clave(monkeypatch):
    """Simula una instalación con `TEACHER_PASSWORD=` puesta vacía a propósito."""
    monkeypatch.setattr(get_settings(), "teacher_password", "")


@pytest.fixture
def credenciales_de_fabrica(monkeypatch):
    """Fuerza los valores por defecto del código, sin depender del `.env` local.

    Los defaults de `config.Settings` ya son admin/admin123, así que en teoría
    ni haría falta esta fixture — pero un `.env` real (el de esta máquina, por
    ejemplo) puede traer otro valor, y este test verifica el comportamiento de
    fábrica, no el de una máquina en particular.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "teacher_username", "admin")
    monkeypatch.setattr(settings, "teacher_password", "admin123")


def _login(
    http: TestClient, usuario: str = USUARIO_DOCENTE, clave: str = CLAVE_DOCENTE, **datos
):
    return http.post(
        "/teacher/login",
        data={"usuario": usuario, "clave": clave, **datos},
        follow_redirects=False,
    )


# --- El guardián --------------------------------------------------------------


def test_el_panel_sin_sesion_redirige_al_login(http, clave_docente):
    respuesta = http.get("/teacher/curation", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/teacher/login?next=/teacher/curation"


def test_htmx_sin_sesion_pide_una_navegacion_completa(http, clave_docente):
    """Un 303 lo seguiría el propio XHR y metería el login dentro de un `<div>`.

    Es el fallo que hace que una sesión vencida se vea como una pantalla rota en
    vez de como una pantalla de login: la bandeja de curación se refresca por
    HTMX, y el swap le habría inyectado la página entera al `<div>` de estado.
    """
    respuesta = http.get(
        "/teacher/curation/fragmentos",
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    assert respuesta.status_code == 401
    assert respuesta.headers["HX-Redirect"].startswith("/teacher/login")


def rutas_montadas() -> list[APIRoute]:
    """Todas las `APIRoute` de la app, incluidas las de routers incluidos.

    **No se puede recorrer `app.routes` a secas.** FastAPI 0.141 no aplana lo
    que entra por `include_router`: deja un envoltorio `_IncludedRouter` que no
    es `APIRoute` y que no expone `.routes`, sino el `APIRouter` original en
    `.original_router`. Un filtro `isinstance(r, APIRoute)` sobre `app.routes`
    ve **2 de las 41** rutas reales, y un test de cobertura escrito así pasa sin
    comprobar nada — que es exactamente lo que hacía este archivo hasta el
    26-ago-2026, cuando se descubrió al listar las rutas de `/api` para el
    pendiente n.º 17 y salir cero.
    """
    encontradas: list[APIRoute] = []
    for ruta in app.routes:
        if isinstance(ruta, APIRoute):
            encontradas.append(ruta)
        elif (interno := getattr(ruta, "original_router", None)) is not None:
            encontradas.extend(r for r in interno.routes if isinstance(r, APIRoute))
    return encontradas


def test_el_recorrido_de_rutas_ve_la_app_completa():
    """Guarda del guarda: si esto se rompe, los dos tests de cobertura mienten.

    Ambos afirman «ninguna ruta quedó sin guardián» recorriendo `rutas_montadas()`;
    si ese recorrido devolviera una lista vacía o casi vacía, seguirían pasando
    sin mirar nada. El número exacto no importa —crece con cada endpoint nuevo—,
    sí que sea del orden de la app real y que incluya rutas conocidas de los tres
    prefijos.
    """
    rutas = rutas_montadas()
    caminos = {r.path for r in rutas}

    assert len(rutas) > 30, f"solo se vieron {len(rutas)} rutas: el recorrido se rompió"
    assert "/teacher/curation" in caminos
    assert "/api/catalogo" in caminos
    assert "/student/vark" in caminos


def test_todas_las_rutas_del_panel_exigen_sesion():
    """El guardián cubre `/teacher/*` completo, no una lista escrita a mano.

    Va sobre la app ya montada y no sobre el código fuente, así que una vista
    nueva que se cuelgue de otro router —o del mismo router sin la dependencia—
    aparece acá como fallo en vez de quedar abierta en silencio. Es la razón por
    la que `requiere_docente` se declara en el `APIRouter` y no handler por
    handler.
    """
    desprotegidas = []
    for ruta in rutas_montadas():
        if not ruta.path.startswith("/teacher/") or ruta.path in RUTAS_ABIERTAS:
            continue
        llamables = {dep.call for dep in ruta.dependant.dependencies}
        if auth.requiere_docente not in llamables:
            desprotegidas.append(f"{sorted(ruta.methods)} {ruta.path}")

    assert not desprotegidas, f"rutas del panel sin guardián: {desprotegidas}"


def _llamables(dependant) -> set:
    """Todas las dependencias de una ruta, incluidas las anidadas.

    `solo_su_capsula` cuelga de `estudiante_o_docente_api`, así que mirar solo
    el primer nivel no vería el guardián.
    """
    encontrados = set()
    pendientes = list(dependant.dependencies)
    while pendientes:
        dep = pendientes.pop()
        encontrados.add(dep.call)
        pendientes.extend(dep.dependencies)
    return encontrados


def test_la_api_separa_lo_abierto_lo_del_dueno_y_lo_del_docente():
    """Cierra el pendiente n.º 17 y la auditoría de datos del 02-oct-2026.

    Las listas se escriben **explícitas** a propósito. Es la única forma de que
    agregar un endpoint nuevo a `/api` sea una decisión consciente: si cuelga
    de un router sin guardián y no está acá, este test falla y obliga a
    justificar por qué un anónimo puede llamarlo.

    - **Abierto**: solo el catálogo de temas, que no tiene datos de nadie.
    - **Del dueño o del docente**: lo que tiene `id_estudiante`. Antes era
      anónimo y el dueño lo declaraba el cliente, así que recorriendo ids se
      leía el perfil VARK de toda la cohorte.
    - `POST /api/diagnosticos` pasó al docente: el estudiante se diagnostica
      por `/student/vark`, que no usa HTTP para esto.
    """
    abiertas_esperadas = {("GET", "/api/catalogo")}
    del_dueno_esperadas = {
        ("GET", "/api/diagnosticos/{id_diagnostico}"),
        ("POST", "/api/capsulas"),
        ("GET", "/api/capsulas/{id_capsula}"),
        ("POST", "/api/capsulas/{id_capsula}/quiz"),
    }

    abiertas_reales, del_dueno_reales = set(), set()
    for ruta in rutas_montadas():
        if not ruta.path.startswith("/api"):
            continue
        llamables = _llamables(ruta.dependant)
        if auth.requiere_docente_api in llamables and (
            auth.estudiante_o_docente_api not in llamables
        ):
            continue
        destino = (
            del_dueno_reales if auth.estudiante_o_docente_api in llamables else abiertas_reales
        )
        for metodo in ruta.methods - {"HEAD", "OPTIONS"}:
            destino.add((metodo, ruta.path))

    assert abiertas_reales == abiertas_esperadas, (
        f"abiertas de más: {sorted(abiertas_reales - abiertas_esperadas)}; "
        f"de menos: {sorted(abiertas_esperadas - abiertas_reales)}"
    )
    assert del_dueno_reales == del_dueno_esperadas, (
        f"del dueño de más: {sorted(del_dueno_reales - del_dueno_esperadas)}; "
        f"de menos: {sorted(del_dueno_esperadas - del_dueno_reales)}"
    )


def test_los_endpoints_con_dueno_rechazan_al_anonimo(http):
    """Sin cookie del estudiante ni del docente, 401 antes de tocar la base."""
    assert http.get("/api/diagnosticos/1").status_code == 401
    assert http.get("/api/capsulas/1").status_code == 401
    cuerpo = {"id_estudiante": 1, "id_objetivo": 1}
    assert http.post("/api/capsulas", json=cuerpo).status_code == 401
    assert http.post(
        "/api/capsulas/1/quiz", json={"id_estudiante": 1, "alternativa_seleccionada": 0}
    ).status_code == 401
    assert http.post("/api/diagnosticos", json={"respuestas": []}).status_code == 401


def test_no_se_pide_una_capsula_a_nombre_de_otro(http):
    """Con sesión de estudiante, el `id_estudiante` del cuerpo tiene que ser el suyo."""
    http.cookies.set(sesion.COOKIE_ESTUDIANTE, f"7.{sesion._firma(7)}")

    respuesta = http.post("/api/capsulas", json={"id_estudiante": 8, "id_objetivo": 1})

    assert respuesta.status_code == 403


def test_el_audio_del_simulador_es_del_docente(http):
    """El simulador manda su propio texto: abierto, cualquiera haría hablar a la voz clonada."""
    respuesta = http.post("/student/viewer/0/generate-audio", data={"texto_override": "hola"})

    assert respuesta.status_code == 403


# --- Login --------------------------------------------------------------------


def test_el_formulario_pide_usuario_y_clave(http, clave_docente):
    respuesta = http.get("/teacher/login")

    assert respuesta.status_code == 200
    assert 'name="usuario"' in respuesta.text
    assert 'type="password"' in respuesta.text


def test_la_clave_correcta_abre_la_sesion(http, clave_docente):
    respuesta = _login(http)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/teacher/curation"
    assert sesion.COOKIE_DOCENTE in respuesta.cookies

    # Con la sesión abierta el login ya no tiene nada que preguntar.
    ya_dentro = http.get("/teacher/login", follow_redirects=False)
    assert ya_dentro.status_code == 303


def test_la_clave_incorrecta_no_abre_nada(http, clave_docente):
    respuesta = _login(http, clave="la-que-no-es")

    assert respuesta.status_code == 401
    assert sesion.COOKIE_DOCENTE not in respuesta.cookies
    assert "incorrecto" in respuesta.text.lower()


def test_el_usuario_incorrecto_no_abre_nada(http, clave_docente):
    """La clave sola no basta: el usuario también se verifica."""
    respuesta = _login(http, usuario="otro-usuario")

    assert respuesta.status_code == 401
    assert sesion.COOKIE_DOCENTE not in respuesta.cookies


def test_el_login_recuerda_a_donde_iba_el_docente(http, clave_docente):
    respuesta = _login(http, next="/teacher/analytics")

    assert respuesta.headers["location"] == "/teacher/analytics"


def test_no_se_puede_usar_el_login_como_redirector_a_otro_sitio(http, clave_docente):
    """Un `next` externo convertiría el login en tapadera de un enlace falso."""
    for destino in ("https://sitio-falso.example", "//sitio-falso.example", "/etc"):
        respuesta = _login(http, next=destino)
        assert respuesta.headers["location"] == "/teacher/curation", destino


def test_el_login_no_rebota_sobre_si_mismo(http, clave_docente):
    respuesta = _login(http, next="/teacher/login")

    assert respuesta.headers["location"] == "/teacher/curation"


def test_las_credenciales_de_fabrica_son_admin_admin123(http, credenciales_de_fabrica):
    """El panel tiene que ser usable nada más clonar el repo, sin tocar el `.env`.

    Son credenciales de demo, no un secreto — el propio `config.py` lo dice —
    pero mientras sigan siendo el valor por defecto documentado (`.env.example`,
    `AVANCE.md`), un cambio accidental acá dejaría a cualquiera que las siga
    fuera del panel sin ningún aviso.
    """
    respuesta = _login(http, usuario="admin", clave="admin123")

    assert respuesta.status_code == 303
    assert sesion.COOKIE_DOCENTE in respuesta.cookies


# --- Sin clave configurada ----------------------------------------------------


def test_sin_clave_en_el_env_el_panel_queda_cerrado(http, sin_clave):
    """Fallar cerrado: `TEACHER_PASSWORD=` vacía a propósito no abre la puerta.

    Se comprueba además con la clave vacía, que es lo que manda un formulario en
    blanco: si `verificar_credenciales_docente` comparara sin más, `"" == ""`
    daría acceso a cualquiera en una instalación con la variable puesta vacía.
    """
    respuesta = _login(http, usuario="", clave="")

    assert respuesta.status_code == 503
    assert sesion.COOKIE_DOCENTE not in respuesta.cookies
    assert "TEACHER_PASSWORD" in respuesta.text
    assert http.get("/teacher/curation", follow_redirects=False).status_code == 303


# --- Integridad de la cookie --------------------------------------------------


def test_una_cookie_inventada_no_sirve(http, clave_docente):
    vencimiento = int(time.time()) + 3600
    for falsa in ("1", "true", f"{vencimiento}.firma-inventada", f"{vencimiento}."):
        http.cookies.set(sesion.COOKIE_DOCENTE, falsa)
        respuesta = http.get("/teacher/curation", follow_redirects=False)
        assert respuesta.status_code == 303, falsa


def test_una_sesion_vencida_no_sirve_aunque_la_firma_sea_legitima(http, clave_docente):
    """El vencimiento va firmado, así que no se puede estirar desde el cliente."""
    vencido = int(time.time()) - 1
    http.cookies.set(
        sesion.COOKIE_DOCENTE, f"{vencido}.{sesion._firma_docente(vencido)}"
    )

    assert http.get("/teacher/curation", follow_redirects=False).status_code == 303


def test_cambiar_la_clave_expulsa_a_las_sesiones_abiertas(http, clave_docente, monkeypatch):
    """Rotar la clave es el único remedio si se filtra; tiene que echar a alguien.

    Sin la huella de la credencial dentro de la firma, quien ya tuviera la
    cookie seguiría dentro justo en el escenario en que uno rota la clave.
    """
    assert _login(http).status_code == 303
    assert http.get("/teacher/login", follow_redirects=False).status_code == 303

    monkeypatch.setattr(get_settings(), "teacher_password", "otra-clave-distinta")

    assert http.get("/teacher/login", follow_redirects=False).status_code == 200


def test_cambiar_el_usuario_tambien_expulsa_a_las_sesiones_abiertas(
    http, clave_docente, monkeypatch
):
    assert _login(http).status_code == 303

    monkeypatch.setattr(get_settings(), "teacher_username", "otro-usuario-distinto")

    assert http.get("/teacher/login", follow_redirects=False).status_code == 200


def test_el_logout_borra_la_sesion(http, clave_docente):
    assert _login(http).status_code == 303

    respuesta = http.post("/teacher/logout", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/student/catalog"
    assert http.get("/teacher/curation", follow_redirects=False).status_code == 303


# --- Freno de fuerza bruta ----------------------------------------------------


def test_los_intentos_fallidos_se_frenan(http, clave_docente):
    for _ in range(auth.INTENTOS_MAXIMOS):
        assert _login(http, clave="mala").status_code == 401

    frenado = _login(http, clave="mala")
    assert frenado.status_code == 429

    # El freno no distingue claves: mientras dura, tampoco pasa la correcta.
    # Es a propósito — si la buena pasara, el freno no frenaría nada.
    assert _login(http).status_code == 429


def test_un_login_exitoso_limpia_el_contador(http, clave_docente):
    for _ in range(auth.INTENTOS_MAXIMOS - 1):
        _login(http, clave="mala")

    assert _login(http).status_code == 303

    http.cookies.clear()
    for _ in range(auth.INTENTOS_MAXIMOS - 1):
        assert _login(http, clave="mala").status_code == 401


# --- La cabecera compartida ---------------------------------------------------


def test_el_estudiante_ve_el_boton_y_no_las_pestanas_del_docente(http, clave_docente):
    respuesta = http.get("/student/vark")

    assert "/teacher/login" in respuesta.text
    assert "Soy docente" in respuesta.text
    assert "/teacher/curation" not in respuesta.text
    assert "/teacher/analytics" not in respuesta.text


def test_el_docente_conectado_ve_sus_pestanas(http, clave_docente):
    assert _login(http).status_code == 303

    respuesta = http.get("/student/vark")

    assert "/teacher/curation" in respuesta.text
    assert "/teacher/analytics" in respuesta.text
    assert "/teacher/simulator" in respuesta.text
    assert "/teacher/logout" in respuesta.text
    assert "Soy docente" not in respuesta.text


# --- La API del docente (pendiente n.º 17) ------------------------------------


def test_la_api_de_curacion_responde_401_y_no_redirige(http, clave_docente):
    """Un cliente de API tiene que recibir 401, no la página de login.

    Es la diferencia con el guardián de la web: los clientes HTTP siguen los
    redirects solos, así que un 303 le habría entregado a un script un 200 con
    HTML de login dentro — y el script habría creído que la llamada funcionó.
    """
    respuesta = http.get("/api/fragmentos", follow_redirects=False)

    assert respuesta.status_code == 401
    assert respuesta.headers["WWW-Authenticate"] == "Basic"
    assert "text/html" not in respuesta.headers.get("content-type", "")


def test_la_api_de_curacion_acepta_http_basic(http, clave_docente):
    """Para `curl -u` y los scripts, que no tienen dónde guardar una cookie."""
    sin_credencial = http.get("/api/objetivos")
    con_credencial = http.get("/api/objetivos", auth=(USUARIO_DOCENTE, clave_docente))

    assert sin_credencial.status_code == 401
    assert con_credencial.status_code == 200


def test_la_api_de_curacion_acepta_la_cookie_del_panel(http, clave_docente):
    """Quien ya entró por la UI no debería tener que autenticarse otra vez en /docs."""
    assert http.get("/api/objetivos").status_code == 401

    assert _login(http).status_code == 303

    assert http.get("/api/objetivos").status_code == 200


def test_una_credencial_mala_en_la_api_no_pasa(http, clave_docente):
    respuesta = http.get("/api/objetivos", auth=(USUARIO_DOCENTE, "clave-que-no-es"))

    assert respuesta.status_code == 401


def test_los_endpoints_del_estudiante_siguen_abiertos(http, clave_docente):
    """Cerrar la curación no puede cerrarle la puerta al estudiante.

    `/api/catalogo` es el que elige el tema y es el más fácil de romper sin
    darse cuenta al mover endpoints entre routers.
    """
    respuesta = http.get("/api/catalogo")

    assert respuesta.status_code == 200


def test_adivinar_la_clave_por_la_api_tambien_se_frena(http, clave_docente):
    """Sin esto, `/api` sería un canal de fuerza bruta sin límite al lado de un
    formulario que sí lo tiene."""
    for _ in range(auth.INTENTOS_MAXIMOS):
        assert http.get("/api/objetivos", auth=("admin", "mala")).status_code == 401

    frenada = http.get("/api/objetivos", auth=("admin", "mala"))
    assert frenada.status_code == 429
    assert "Retry-After" in frenada.headers


def test_una_peticion_anonima_no_gasta_intentos(http, clave_docente):
    """Un rastreador cualquiera no puede dejar bloqueado al docente.

    Solo cuenta como intento fallido el que **presenta** una credencial: pedir
    una ruta protegida sin credencial es el caso normal de «esto pide login».
    """
    for _ in range(auth.INTENTOS_MAXIMOS * 2):
        assert http.get("/api/objetivos").status_code == 401

    assert http.get("/api/objetivos", auth=(USUARIO_DOCENTE, clave_docente)).status_code == 200


# --- El panel, ya con sesión --------------------------------------------------


@necesita_bd
def test_con_sesion_el_panel_responde(http_docente):
    """El camino completo: login real y la vista servida, no solo el guardián."""
    respuesta = http_docente.get("/teacher/curation")

    assert respuesta.status_code == 200
    assert "Bandeja de revisión" in respuesta.text
