"""Arranque con credenciales y secretos de sesión (O1, 27-oct-2026).

Fuera de `APP_ENV=dev` la app no arranca sin un `SESSION_SECRET` fuerte ni con
una `TEACHER_PASSWORD` débil, y `admin123` dejó de ser el valor de fábrica. Los
mensajes de error y los avisos nunca incluyen los valores configurados.

Los `Settings` se construyen con `_env_file=None` y sin las variables del
entorno, para no depender del `.env` de la máquina que corre la suite.
"""

import logging
import os
import subprocess
import sys

import pytest

from studify.config import (
    ConfiguracionInsegura,
    Settings,
    problemas_de_seguridad,
    verificar_configuracion,
)

SECRETO_FUERTE = "secreto-de-prueba-de-mas-de-32-caracteres"
CLAVE_FUERTE = "clave-de-prueba-larga"
VARIABLES = ("APP_ENV", "SESSION_SECRET", "TEACHER_USERNAME", "TEACHER_PASSWORD")


@pytest.fixture
def ajustes(monkeypatch):
    """`Settings` de fábrica, sin `.env` ni variables de entorno, con cambios puntuales."""
    for variable in VARIABLES:
        monkeypatch.delenv(variable, raising=False)

    def construir(**valores) -> Settings:
        return Settings(_env_file=None, **valores)

    return construir


def test_sin_configurar_nada_es_produccion_y_sin_clave_de_docente(ajustes):
    settings = ajustes()

    assert settings.app_env == "prod"
    assert settings.teacher_password == ""
    assert settings.session_secret == ""


def test_produccion_sin_secreto_no_arranca(ajustes):
    with pytest.raises(ConfiguracionInsegura, match="SESSION_SECRET no está fijada"):
        verificar_configuracion(ajustes())


@pytest.mark.parametrize(
    ("secreto", "motivo"),
    [
        ("   ", "no está fijada"),
        ("corto-pero-no-vacio", "menos de 32"),
        ("changeme", "valor de ejemplo"),
        ("replace-me-with-a-random-secret", "valor de ejemplo"),
    ],
    ids=["solo-espacios", "corto", "ejemplo-corto", "ejemplo-largo"],
)
def test_produccion_con_secreto_debil_no_arranca(ajustes, secreto, motivo):
    with pytest.raises(ConfiguracionInsegura, match=motivo) as error:
        verificar_configuracion(ajustes(session_secret=secreto))

    if secreto.strip():
        assert secreto not in str(error.value)


@pytest.mark.parametrize("clave", ["admin123", "Admin123", "corta"])
def test_produccion_con_clave_de_docente_debil_no_arranca(ajustes, clave):
    with pytest.raises(ConfiguracionInsegura, match="TEACHER_PASSWORD es débil") as error:
        verificar_configuracion(ajustes(session_secret=SECRETO_FUERTE, teacher_password=clave))

    assert clave not in str(error.value)


def test_produccion_con_secreto_y_clave_fuertes_arranca(ajustes):
    settings = ajustes(session_secret=SECRETO_FUERTE, teacher_password=CLAVE_FUERTE)

    assert problemas_de_seguridad(settings) == []
    verificar_configuracion(settings)


def test_produccion_sin_clave_de_docente_arranca_con_el_panel_cerrado(ajustes):
    """Sin clave el panel no abre para nadie: es seguro, no impide arrancar."""
    verificar_configuracion(ajustes(session_secret=SECRETO_FUERTE))


def test_el_error_no_muestra_ningun_secreto(ajustes):
    secreto = "secreto-corto-que-no-se-ve"
    with pytest.raises(ConfiguracionInsegura) as error:
        verificar_configuracion(ajustes(session_secret=secreto, teacher_password="admin123"))

    mensaje = str(error.value)
    assert secreto not in mensaje
    assert "admin123" not in mensaje


def test_desarrollo_arranca_sin_secreto_y_avisa(ajustes, caplog):
    settings = ajustes(app_env="dev", teacher_password="admin123")

    with caplog.at_level(logging.WARNING, logger="studify.config"):
        verificar_configuracion(settings)

    avisos = caplog.text
    assert "SESSION_SECRET efímero" in avisos
    assert "TEACHER_PASSWORD es débil" in avisos
    assert "admin123" not in avisos


def test_desarrollo_es_explicito(ajustes):
    """Un valor parecido no es desarrollo: solo `dev` lo es."""
    with pytest.raises(ConfiguracionInsegura):
        verificar_configuracion(ajustes(app_env="development"))


# --- Arranque real --------------------------------------------------------------


def _importar_la_app(tmp_path, **variables) -> subprocess.CompletedProcess:
    """Importa `studify.main` en otro proceso, desde una carpeta sin `.env`."""
    entorno = {k: v for k, v in os.environ.items() if k not in VARIABLES}
    entorno.update(variables, PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, "-c", "import studify.main"],
        cwd=tmp_path,
        env=entorno,
        capture_output=True,
        encoding="utf-8",
        timeout=180,
    )


def test_la_app_no_arranca_en_produccion_sin_secreto(tmp_path):
    resultado = _importar_la_app(tmp_path, APP_ENV="prod")

    assert resultado.returncode != 0
    assert "ConfiguracionInsegura" in resultado.stderr
    assert "SESSION_SECRET no está fijada" in resultado.stderr


def test_la_app_arranca_en_desarrollo_sin_secreto(tmp_path):
    resultado = _importar_la_app(tmp_path, APP_ENV="dev")

    assert resultado.returncode == 0, resultado.stderr
    assert "SESSION_SECRET efímero" in resultado.stderr
