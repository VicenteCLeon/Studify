"""El pie de página ofrece el código fuente en todas las páginas (AGPL-3.0, §13).

La AGPL pide ofrecer el código fuente a todo el que use el servicio por la red.
RepasAi lo hace con un enlace al repositorio y otro a la licencia en el pie, que
`base.html` dibuja en todas las páginas. Los enlaces van en la lista legal porque
es la única parte del pie que sigue visible en el pie compacto (cuestionario y
cápsula).
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studify.main import app

REPOSITORIO = "https://github.com/VicenteCLeon/Studify"
LICENCIA = f"{REPOSITORIO}/blob/main/LICENSE"
RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def http() -> TestClient:
    return TestClient(app)


def _lista_legal(html: str) -> str:
    """La lista de enlaces del pie (`nav.site-footer-legal`)."""
    pie = html[html.index('<footer class="site-footer') :]
    inicio = pie.index('<nav class="site-footer-legal"')
    return pie[inicio : pie.index("</nav>", inicio)]


@pytest.mark.parametrize(
    "ruta",
    ["/", "/student/vark", "/teacher/login", "/terminos", "/privacidad"],
)
def test_el_pie_ofrece_el_codigo_fuente_y_la_licencia(http, ruta):
    lista = _lista_legal(http.get(ruta).text)

    assert f'<a href="{REPOSITORIO}">Código fuente</a>' in lista
    assert f'<a href="{LICENCIA}">Licencia AGPL-3.0</a>' in lista


def test_tambien_en_el_pie_compacto(http):
    """El cuestionario usa el pie compacto, que oculta la marca pero no la lista legal."""
    html = http.get("/student/vark").text

    assert 'class="site-footer site-footer-compacto"' in html
    assert "Código fuente" in _lista_legal(html)


def test_los_enlaces_se_alcanzan_con_el_teclado(http):
    """Enlaces nativos, sin tabindex negativo ni aria-hidden."""
    lista = _lista_legal(http.get("/").text)

    for etiqueta in re.findall(r"<a [^>]*>(?:Código fuente|Licencia AGPL-3.0)</a>", lista):
        assert 'tabindex="-1"' not in etiqueta
        assert "aria-hidden" not in etiqueta


def test_el_archivo_al_que_apunta_la_licencia_existe_y_es_la_agpl():
    licencia = (RAIZ / "LICENSE").read_text(encoding="utf-8")

    assert licencia.lstrip().startswith("GNU AFFERO GENERAL PUBLIC LICENSE")
    assert "Version 3, 19 November 2007" in licencia
