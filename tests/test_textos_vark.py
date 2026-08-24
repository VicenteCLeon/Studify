"""Verifica que `web/textos.ENUNCIADOS` coincida con el instrumento original.

Cierra el pendiente n.º 6 de AVANCE.md §6: los 16 enunciados que ve el
estudiante en `/student/vark` deben ser el mismo texto que respondieron los 43
estudiantes del Google Forms, o los perfiles no serían comparables entre sí.

El CSV con el instrumento original (`data/data_cuestionarios_43.csv`) no está
versionado, así que estos tests se **saltan** —no fallan— cuando no está
presente en la máquina, mismo criterio que `necesita_bd` en `conftest.py` para
Postgres.
"""

import csv
from pathlib import Path

import pytest

from studify.vark.instrumento import ITEMS
from studify.web.textos import ENUNCIADOS

RUTA_CSV = Path(__file__).resolve().parent.parent / "data" / "data_cuestionarios_43.csv"

necesita_csv = pytest.mark.skipif(
    not RUTA_CSV.exists(), reason="requiere data/data_cuestionarios_43.csv (no versionado)"
)


def _enunciados_del_csv() -> list[str]:
    """Encabezados de las 16 preguntas VARK, en orden, tal como los exportó Google Forms.

    Las primeras 5 columnas son metadatos (marca temporal + 4 sociodemográficos,
    cap. 16.1); las 16 siguientes son los ítems del instrumento (cap. 10).
    """
    with RUTA_CSV.open(encoding="utf-8-sig") as f:
        header = next(csv.reader(f))
    return [h.strip() for h in header[5:21]]


def test_hay_un_enunciado_por_item():
    assert len(ENUNCIADOS) == len(ITEMS) == 16


@necesita_csv
def test_enunciados_identicos_al_csv_original():
    """Comparación carácter a carácter: no basta con que "digan lo mismo"."""
    reales = _enunciados_del_csv()
    assert len(reales) == 16, "el CSV debería tener 16 columnas de ítems (5:21)"
    for i, (mostrado, real) in enumerate(zip(ENUNCIADOS, reales, strict=True), start=1):
        assert mostrado == real, (
            f"ítem {i}: el enunciado en web/textos.py no coincide con el original\n"
            f"  textos.py: {mostrado!r}\n"
            f"  CSV      : {real!r}"
        )
