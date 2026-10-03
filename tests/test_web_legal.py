"""Marco legal: Términos, Privacidad y el footer que los enlaza (02-oct-2026).

Fijan lo que no puede romperse sin que nadie lo note: que los documentos se
puedan leer sin sesión (se leen *antes* de aceptar), que muestren la versión
contra la que se guarda la aceptación, que su tabla de contenidos apunte a
secciones que existen, y que el footer con los enlaces y el aviso de IA esté en
todas las páginas.

La segunda mitad fija el consentimiento: la casilla nunca viene marcada, sin
ella no se crea nada, la aceptación queda guardada con versión y hora UTC, el
género pide su propio consentimiento y una versión nueva se vuelve a pedir.
"""

import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from studify.db.models import AceptacionLegal, DiagnosticoVark, Estudiante
from studify.main import app
from studify.web import consentimiento, legal, sesion
from tests.conftest import necesita_bd
from tests.test_web_auth import rutas_montadas

AVISO_IA = (
    "Las cápsulas son generadas con IA y pueden contener errores; "
    "verifica con tu material oficial."
)
ENLACES_FOOTER = (
    'href="/terminos"',
    'href="/privacidad"',
    'href="/mis-datos"',
    'href="/privacidad#contacto"',
)


@pytest.fixture
def http() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize("documento", legal.DOCUMENTOS, ids=lambda d: d.clave)
def test_el_documento_se_lee_sin_sesion(http, documento):
    respuesta = http.get(documento.ruta, follow_redirects=False)

    assert respuesta.status_code == 200
    assert f"<h1>{documento.titulo}</h1>" in respuesta.text


@pytest.mark.parametrize("documento", legal.DOCUMENTOS, ids=lambda d: d.clave)
def test_muestra_version_y_fecha_de_actualizacion(http, documento):
    """Son las mismas que `web/legal.py`, contra las que se guarda la aceptación."""
    html = http.get(documento.ruta).text

    assert f"Versión {documento.version}" in html
    assert f'datetime="{documento.actualizado.isoformat()}"' in html
    assert documento.actualizado_texto in html


@pytest.mark.parametrize("documento", legal.DOCUMENTOS, ids=lambda d: d.clave)
def test_lleva_la_marca_interna_de_borrador(http, documento):
    """Comentario HTML: no se ve en la página, pero viaja con ella."""
    html = http.get(documento.ruta).text

    assert "<!-- BORRADOR: requiere revisión legal antes de publicación -->" in html


@pytest.mark.parametrize("documento", legal.DOCUMENTOS, ids=lambda d: d.clave)
def test_la_tabla_de_contenidos_apunta_a_secciones_que_existen(http, documento):
    html = http.get(documento.ruta).text
    toc = html[html.index('class="legal-toc"') : html.index('class="legal-doc"')]

    anclas = re.findall(r'href="#([\w-]+)"', toc)
    ids = set(re.findall(r'\sid="([\w-]+)"', html))

    assert len(anclas) >= 10
    assert [a for a in anclas if a not in ids] == []


def test_no_quedan_placeholders_sin_completar(http):
    """Los datos del proyecto ya están completos: un `ui.placeholder()` nuevo
    tiene que resolverse antes de mostrar los documentos a estudiantes."""
    for documento in legal.DOCUMENTOS:
        assert "[PLACEHOLDER:" not in http.get(documento.ruta).text, documento.clave


def test_la_privacidad_nombra_al_proveedor_y_a_la_agencia(http):
    html = http.get("/privacidad").text

    assert "DeepSeek" in html
    assert "Agencia de Protección de Datos Personales" in html
    assert "Ley N.º 21.719" in html
    for cookie in ("id_estudiante", "docente", "repasai-theme", "repasai-vark-borrador"):
        assert f"<code>{cookie}</code>" in html, cookie


@pytest.mark.parametrize(
    "ruta", ["/", "/student/vark", "/teacher/login", "/terminos", "/privacidad"]
)
def test_el_footer_legal_esta_en_todas_las_paginas(http, ruta):
    html = http.get(ruta).text
    footer = html[html.index('<footer class="site-footer') :]

    for enlace in ENLACES_FOOTER:
        assert enlace in footer, enlace
    assert AVISO_IA in footer


def test_el_footer_es_compacto_en_el_cuestionario(http):
    """Vista de flujo enfocado: mismo contenido legal, presentación discreta."""
    assert 'class="site-footer site-footer-compacto"' in http.get("/student/vark").text
    assert "site-footer-compacto" not in http.get("/").text


def test_el_footer_marca_la_pagina_legal_actual(http):
    html = http.get("/terminos").text

    assert 'href="/terminos" aria-current="page"' in html


# --- Consentimiento y trazabilidad (requieren Postgres) -----------------------

RESPUESTAS = {f"q{n}": ["a"] for n in range(1, 17)}


@pytest.fixture
def creados(db):
    """Ids de los estudiantes que cree el test; se borran al final (CASCADE)."""
    ids: list[int] = []
    yield ids
    for id_estudiante in ids:
        fila = db.get(Estudiante, id_estudiante)
        if fila is not None:
            db.delete(fila)
    db.commit()


def _id_de_la_cookie(cliente: TestClient) -> int | None:
    crudo = cliente.cookies.get(sesion.COOKIE_ESTUDIANTE)
    return int(crudo.split(".")[0]) if crudo else None


def _aceptaciones(db, id_estudiante: int) -> list[AceptacionLegal]:
    db.expire_all()
    return list(
        db.scalars(
            select(AceptacionLegal)
            .where(AceptacionLegal.id_estudiante == id_estudiante)
            .order_by(AceptacionLegal.id_aceptacion)
        )
    )


def _nueva_version_de_terminos(monkeypatch, version: str = "9.9") -> legal.Documento:
    nuevo = replace(legal.TERMINOS, version=version)
    monkeypatch.setattr(legal, "TERMINOS", nuevo)
    monkeypatch.setattr(legal, "DOCUMENTOS", (nuevo, legal.PRIVACIDAD))
    return nuevo


def test_la_casilla_de_aceptacion_no_viene_marcada(http):
    html = http.get("/student/vark").text
    casilla = re.search(r'<input type="checkbox" name="acepto"[^>]*>', html)

    assert casilla is not None
    assert "checked" not in casilla.group(0)
    assert 'href="/terminos"' in html and 'href="/privacidad"' in html
    # El envío espera a la casilla (con JS); el servidor lo comprueba igual.
    assert "data-requiere-acepto" in html


@necesita_bd
def test_sin_aceptar_no_se_crea_el_estudiante(http, db):
    antes = db.scalar(select(func.count()).select_from(Estudiante))

    respuesta = http.post("/student/vark", data=RESPUESTAS)

    assert respuesta.status_code == 200
    assert "alerta-error" in respuesta.text
    assert "Términos y Condiciones" in respuesta.text
    assert _id_de_la_cookie(http) is None
    assert db.scalar(select(func.count()).select_from(Estudiante)) == antes


@necesita_bd
def test_la_aceptacion_queda_registrada_con_version_y_hora_utc(http, db, creados):
    antes = datetime.now(UTC)

    respuesta = http.post("/student/vark", data=RESPUESTAS | {"acepto": "si"})

    assert respuesta.status_code == 204
    id_estudiante = _id_de_la_cookie(http)
    creados.append(id_estudiante)

    filas = _aceptaciones(db, id_estudiante)
    assert {(f.documento, f.version) for f in filas} == {
        ("terminos", legal.TERMINOS.version),
        ("privacidad", legal.PRIVACIDAD.version),
    }
    for fila in filas:
        assert fila.aceptado_en.utcoffset() == timedelta(0)
        assert antes - timedelta(seconds=5) <= fila.aceptado_en <= datetime.now(UTC)


@necesita_bd
def test_el_genero_exige_su_propio_consentimiento(http, db, creados):
    datos = RESPUESTAS | {"acepto": "si", "genero": "Femenino"}

    sin_consentimiento = http.post("/student/vark", data=datos)
    assert "alerta-error" in sin_consentimiento.text
    assert _id_de_la_cookie(http) is None

    con_consentimiento = http.post("/student/vark", data=datos | {"consiento_genero": "si"})
    assert con_consentimiento.status_code == 204
    id_estudiante = _id_de_la_cookie(http)
    creados.append(id_estudiante)

    assert db.get(Estudiante, id_estudiante).genero == "Femenino"
    assert ("genero", legal.PRIVACIDAD.version) in {
        (f.documento, f.version) for f in _aceptaciones(db, id_estudiante)
    }


@necesita_bd
def test_sin_genero_no_se_registra_consentimiento_de_genero(http, db, creados):
    http.post("/student/vark", data=RESPUESTAS | {"acepto": "si", "consiento_genero": "si"})
    id_estudiante = _id_de_la_cookie(http)
    creados.append(id_estudiante)

    assert "genero" not in {f.documento for f in _aceptaciones(db, id_estudiante)}


@necesita_bd
def test_un_estudiante_sin_aceptacion_va_primero_a_aceptar(http, db, creados):
    """Los estudiantes anteriores al marco legal no tienen ninguna fila."""
    estudiante = Estudiante()
    db.add(estudiante)
    db.commit()
    creados.append(estudiante.id_estudiante)
    http.cookies.set(
        sesion.COOKIE_ESTUDIANTE,
        f"{estudiante.id_estudiante}.{sesion._firma(estudiante.id_estudiante)}",
    )

    normal = http.get("/student/catalog", follow_redirects=False)
    assert normal.status_code == 303
    assert normal.headers["location"] == "/aceptar?next=/student/catalog"

    por_htmx = http.post("/student/viewer/1/submit", headers={"HX-Request": "true"})
    assert por_htmx.headers["HX-Redirect"] == "/aceptar"

    # El cuestionario sigue abierto: es donde se acepta.
    assert http.get("/student/vark", follow_redirects=False).status_code == 200


@necesita_bd
def test_una_version_nueva_se_vuelve_a_pedir_y_conserva_el_historial(
    http, db, creados, monkeypatch
):
    http.post("/student/vark", data=RESPUESTAS | {"acepto": "si"})
    id_estudiante = _id_de_la_cookie(http)
    creados.append(id_estudiante)
    assert http.get("/student/catalog", follow_redirects=False).status_code == 200

    nuevo = _nueva_version_de_terminos(monkeypatch)

    bloqueado = http.get("/student/catalog", follow_redirects=False)
    assert bloqueado.headers["location"] == "/aceptar?next=/student/catalog"

    pantalla = http.get("/aceptar?next=/student/catalog")
    assert pantalla.status_code == 200
    lista = pantalla.text.split('class="aceptar-docs"')[1].split("</ul>")[0]
    assert f"Versión {nuevo.version}" in lista
    # Solo se pide lo que cambió: la Política sigue vigente.
    assert "Política de Privacidad" not in lista

    sin_marcar = http.post("/aceptar", data={"next": "/student/catalog"})
    assert "alerta-error" in sin_marcar.text

    aceptada = http.post(
        "/aceptar", data={"acepto": "si", "next": "/student/catalog"}, follow_redirects=False
    )
    assert aceptada.status_code == 303
    assert aceptada.headers["location"] == "/student/catalog"
    assert http.get("/student/catalog", follow_redirects=False).status_code == 200

    versiones = [(f.documento, f.version) for f in _aceptaciones(db, id_estudiante)]
    assert ("terminos", "0.1") in versiones
    assert ("terminos", nuevo.version) in versiones


@necesita_bd
def test_aceptar_no_sirve_de_redirector_a_otro_sitio(http, db, creados, monkeypatch):
    http.post("/student/vark", data=RESPUESTAS | {"acepto": "si"})
    creados.append(_id_de_la_cookie(http))
    _nueva_version_de_terminos(monkeypatch)

    respuesta = http.post(
        "/aceptar",
        data={"acepto": "si", "next": "https://sitio-falso.example"},
        follow_redirects=False,
    )

    assert respuesta.headers["location"] == "/student/catalog"


def test_aceptar_sin_sesion_lleva_al_cuestionario(http):
    respuesta = http.get("/aceptar", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/student/vark"


def test_todas_las_vistas_del_estudiante_exigen_la_aceptacion():
    """Como el guardián del docente: va en el router, así una vista nueva queda cubierta."""
    sin_guardian = []
    for ruta in rutas_montadas():
        if not ruta.path.startswith("/student/"):
            continue
        if ruta.path in consentimiento.RUTAS_SIN_ACEPTACION:
            continue
        if consentimiento.exigir_vigente not in {d.call for d in ruta.dependant.dependencies}:
            sin_guardian.append(ruta.path)

    assert sin_guardian == []


# --- Mis datos: acceso, portabilidad, rectificación y supresión ----------------


def _conectado(http, creados) -> int:
    http.post("/student/vark", data=RESPUESTAS | {"acepto": "si", "carrera": "Carrera de prueba"})
    id_estudiante = _id_de_la_cookie(http)
    creados.append(id_estudiante)
    return id_estudiante


def test_mis_datos_sin_sesion_explica_por_que_no_hay_nada(http):
    respuesta = http.get("/mis-datos")

    assert respuesta.status_code == 200
    assert "No encontramos una sesión" in respuesta.text


@necesita_bd
def test_mis_datos_no_exige_aceptar_antes(http, db, creados):
    """Ejercer derechos no puede quedar condicionado a aceptar la versión nueva."""
    estudiante = Estudiante()
    db.add(estudiante)
    db.commit()
    creados.append(estudiante.id_estudiante)
    http.cookies.set(
        sesion.COOKIE_ESTUDIANTE,
        f"{estudiante.id_estudiante}.{sesion._firma(estudiante.id_estudiante)}",
    )

    respuesta = http.get("/mis-datos", follow_redirects=False)

    assert respuesta.status_code == 200
    assert f"Estudiante n.º {estudiante.id_estudiante}" in respuesta.text


@necesita_bd
def test_la_exportacion_trae_todos_los_datos_en_json(http, creados):
    id_estudiante = _conectado(http, creados)

    respuesta = http.get("/mis-datos/exportar")

    assert respuesta.status_code == 200
    assert "attachment" in respuesta.headers["content-disposition"]
    datos = respuesta.json()
    assert datos["estudiante"]["id_estudiante"] == id_estudiante
    assert datos["estudiante"]["carrera"] == "Carrera de prueba"
    assert len(datos["diagnosticos_vark"]) == 1
    assert len(datos["diagnosticos_vark"][0]["respuestas"]) == 16
    assert {a["documento"] for a in datos["aceptaciones"]} == {"terminos", "privacidad"}
    assert set(datos) == {
        "estudiante", "diagnosticos_vark", "capsulas", "intentos_en_actividades", "aceptaciones",
    }  # fmt: skip


@necesita_bd
def test_rectificar_corrige_y_el_genero_pide_consentimiento(http, db, creados):
    id_estudiante = _conectado(http, creados)

    sin_consentir = http.post("/mis-datos/rectificar", data={"genero": "Masculino"})
    assert "alerta-error" in sin_consentir.text

    http.post(
        "/mis-datos/rectificar",
        data={"genero": "Masculino", "consiento_genero": "si", "rango_etario": "21 - 23 años"},
    )
    db.expire_all()
    estudiante = db.get(Estudiante, id_estudiante)
    assert (estudiante.genero, estudiante.rango_etario, estudiante.carrera) == (
        "Masculino", "21 - 23 años", None,
    )  # fmt: skip
    assert "genero" in {f.documento for f in _aceptaciones(db, id_estudiante)}

    http.post("/mis-datos/rectificar", data={})
    db.expire_all()
    assert db.get(Estudiante, id_estudiante).genero is None


@necesita_bd
def test_eliminar_borra_todo_en_cascada_y_cierra_la_sesion(http, db, creados):
    id_estudiante = _conectado(http, creados)

    sin_confirmar = http.post("/mis-datos/eliminar")
    assert "alerta-error" in sin_confirmar.text
    assert db.get(Estudiante, id_estudiante) is not None

    respuesta = http.post("/mis-datos/eliminar", data={"confirmo": "si"})

    assert respuesta.status_code == 200
    assert "Eliminamos tus datos" in respuesta.text
    assert _id_de_la_cookie(http) is None
    db.expire_all()
    assert db.get(Estudiante, id_estudiante) is None
    assert _aceptaciones(db, id_estudiante) == []
    assert db.scalar(
        select(func.count()).select_from(DiagnosticoVark).where(
            DiagnosticoVark.id_estudiante == id_estudiante
        )
    ) == 0
