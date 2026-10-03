"""Marco legal: Términos, Privacidad y el footer que los enlaza (02-oct-2026).

Fijan lo que no puede romperse sin que nadie lo note: que los documentos se
puedan leer sin sesión (se leen *antes* de aceptar), que muestren la versión
contra la que se guarda la aceptación, que su tabla de contenidos apunte a
secciones que existen, y que el footer con los enlaces y el aviso de IA esté en
todas las páginas. Ninguno necesita Postgres.
"""

import re

import pytest
from fastapi.testclient import TestClient

from studify.main import app
from studify.web import legal

AVISO_IA = (
    "Las cápsulas son generadas con IA y pueden contener errores; "
    "verifica con tu material oficial."
)
ENLACES_FOOTER = (
    'href="/terminos"',
    'href="/privacidad"',
    'href="/privacidad#derechos"',
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


def test_los_pendientes_quedan_marcados_como_placeholder(http):
    """Lo que el equipo debe completar se encuentra con un grep, en ambos documentos."""
    for documento in legal.DOCUMENTOS:
        assert "[PLACEHOLDER:" in http.get(documento.ruta).text, documento.clave


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
