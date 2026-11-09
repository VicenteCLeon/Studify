"""El registro de la app queda en un archivo rotativo con fecha y hora."""

import logging
import re
from logging.handlers import RotatingFileHandler

import pytest

from studify.registro import configurar_registro


@pytest.fixture
def logger_studify():
    """Restituye los handlers y el nivel del logger `studify` después del test."""
    logger = logging.getLogger("studify")
    handlers, nivel = list(logger.handlers), logger.level
    yield logger
    for handler in logger.handlers:
        if handler not in handlers:
            handler.close()
    logger.handlers[:] = handlers
    logger.setLevel(nivel)


def test_un_error_de_studify_queda_en_el_archivo_con_fecha_y_hora(tmp_path, logger_studify):
    ruta = configurar_registro(tmp_path)

    logging.getLogger("studify.api.routers.capsules").error(
        "generación agotada para estudiante=%s objetivo=%s (%s)", 7, 42, "UX-07-05"
    )
    for handler in logger_studify.handlers:
        handler.flush()

    linea = ruta.read_text(encoding="utf-8").strip()
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", linea), linea
    assert "ERROR studify.api.routers.capsules" in linea
    assert "objetivo=42 (UX-07-05)" in linea


def test_los_loggers_ajenos_a_studify_no_van_al_archivo(tmp_path, logger_studify):
    ruta = configurar_registro(tmp_path)

    logging.getLogger("uvicorn.access").error("GET /student/viewer/1 200")
    for handler in logger_studify.handlers:
        handler.flush()

    assert ruta.read_text(encoding="utf-8") == ""


def test_configurar_dos_veces_no_duplica_las_lineas(tmp_path, logger_studify):
    """Con `uvicorn --reload` el módulo principal se importa de nuevo."""
    configurar_registro(tmp_path)
    configurar_registro(tmp_path)

    archivos = [h for h in logger_studify.handlers if isinstance(h, RotatingFileHandler)]
    assert len(archivos) == 1
