"""Fixtures compartidas.

El criterio de toda la suite: los tests que no tocan la base corren siempre, y
los que sí se **saltan** —no fallan— cuando Postgres no está levantado. Así
`pytest` queda en verde en una máquina recién clonada, antes de crear el rol y
la base, y una suite roja significa siempre un problema real.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from studify.db.session import SessionLocal, engine

# Credenciales del panel del docente durante los tests. No se leen del `.env` a
# propósito: la suite tiene que dar el mismo resultado en una máquina que aún no
# tocó `TEACHER_USERNAME`/`TEACHER_PASSWORD` (quedan en admin/admin123) y en una
# que sí, con cualquier valor.
USUARIO_DOCENTE = "usuario-docente-de-prueba"
CLAVE_DOCENTE = "clave-docente-de-prueba"


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
def clave_docente(monkeypatch) -> str:
    """Fija credenciales conocidas para `/teacher/*` durante el test."""
    from studify.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "teacher_username", USUARIO_DOCENTE)
    monkeypatch.setattr(settings, "teacher_password", CLAVE_DOCENTE)
    return CLAVE_DOCENTE


@pytest.fixture
def http_docente(clave_docente) -> TestClient:
    """Cliente HTTP con la sesión del docente ya abierta.

    Desde que `/teacher/*` exige login, cualquier test del panel que use un
    cliente anónimo recibe un 303 al login en vez de la vista. Esta fixture
    hace el login de verdad —no inyecta la cookie a mano— para que el camino
    que ejercitan los tests del panel sea el mismo que recorre el docente.
    """
    from studify.main import app
    from studify.web.routers import auth

    # El freno de fuerza bruta cuenta por IP en memoria del proceso, y todos los
    # tests salen de la misma IP ficticia: sin esto, un test que prueba claves
    # incorrectas dejaría bloqueados a los que corran después.
    auth.reiniciar_intentos()

    cliente = TestClient(app)
    respuesta = cliente.post(
        "/teacher/login",
        data={"usuario": USUARIO_DOCENTE, "clave": clave_docente},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303, "el login del docente falló en la fixture"
    return cliente


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
