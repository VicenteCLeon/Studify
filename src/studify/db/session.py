"""Sesión de base de datos.

Se usa SQLAlchemy **síncrono** de forma deliberada: los endpoints se declaran con `def`
(no `async def`), así FastAPI los ejecuta en su threadpool. Esto evita el problema clásico
de bloquear el event loop con I/O síncrono y mantiene el código simple, que es lo que
conviene para un prototipo desarrollado por dos personas.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from studify.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    echo=_settings.app_env == "dev",
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: entrega una sesión y la cierra al terminar el request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
