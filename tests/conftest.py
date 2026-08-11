"""Fixtures compartidas.

El criterio de toda la suite: los tests que no tocan la base corren siempre, y
los que sí se **saltan** —no fallan— cuando Postgres no está levantado. Así
`pytest` queda en verde en una máquina recién clonada, antes de crear el rol y
la base, y una suite roja significa siempre un problema real.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from studify.db.session import SessionLocal, engine


def hay_base_de_datos() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


necesita_bd = pytest.mark.skipif(
    not hay_base_de_datos(), reason="requiere Postgres levantado"
)


@pytest.fixture
def db() -> Iterator[Session]:
    """Sesión de base de datos para un test."""
    sesion = SessionLocal()
    try:
        yield sesion
    finally:
        sesion.close()


@pytest.fixture
def almacen_temporal(tmp_path, monkeypatch) -> str:
    """Redirige el almacén de documentos a un directorio desechable.

    Sin esto, cada corrida de los tests dejaría copias de los PDF de prueba en
    `data/documentos/` del repositorio.
    """
    from studify.config import get_settings

    destino = str(tmp_path / "documentos")
    monkeypatch.setattr(get_settings(), "documentos_dir", destino)
    return destino
