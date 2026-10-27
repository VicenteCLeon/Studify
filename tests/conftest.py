"""Fixtures compartidas.

El criterio de toda la suite: los tests que no tocan la base corren siempre, y
los que sí se **saltan** —no fallan— cuando Postgres no está levantado. Así
`pytest` queda en verde en una máquina recién clonada, antes de crear el rol y
la base, y una suite roja significa siempre un problema real.
"""

import os
from collections.abc import Iterator

# Antes de importar `studify`: la suite corre en modo desarrollo aunque el `.env`
# local diga otra cosa, para que importar `studify.main` no dependa de que esa
# máquina tenga un SESSION_SECRET fuerte (O1). Los tests de
# `test_config_seguridad.py` construyen sus propios `Settings`.
os.environ["APP_ENV"] = "dev"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from studify.db.session import SessionLocal, engine  # noqa: E402

# Credenciales del panel del docente durante los tests. No se leen del `.env` a
# propósito: la suite tiene que dar el mismo resultado en una máquina sin
# `TEACHER_PASSWORD` (panel cerrado) y en una que la fijó, con cualquier valor.
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


def cookie_de(id_estudiante: int) -> str:
    """La cookie de sesión firmada y vigente de un estudiante que existe en la base.

    Desde el 24-oct-2026 (R2) la firma incluye la `fecha_registro` del
    estudiante y el vencimiento, así que ya no se arma solo con el id.
    """
    from studify.db.models import Estudiante
    from studify.web import sesion

    with SessionLocal() as db:
        estudiante = db.get(Estudiante, id_estudiante)
        assert estudiante is not None, f"no existe el estudiante {id_estudiante}"
        return sesion.valor_cookie(estudiante.id_estudiante, estudiante.fecha_registro)


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


class _LLMCaido:
    """Sustituto de `OpenAILike` que falla como falla el proveedor de verdad.

    Lanza las excepciones del SDK de `openai`, que es lo que llega desde
    llama-index cuando hay un timeout, el proveedor rechaza la llamada (sin
    saldo, límite de uso) o no hay red. Cuenta las llamadas para poder
    comprobar que una caída no se reintenta en el bucle de reparación.
    """

    def __init__(self, falla: str) -> None:
        self.falla = falla
        self.llamadas = 0

    def chat(self, mensajes):
        import httpx
        import openai

        self.llamadas += 1
        peticion = httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions")
        if self.falla == "timeout":
            raise openai.APITimeoutError(request=peticion)
        if self.falla == "conexion":
            raise openai.APIConnectionError(request=peticion)
        if self.falla == "sin_saldo":
            raise openai.APIStatusError(
                "Insufficient Balance",
                response=httpx.Response(402, request=peticion),
                body=None,
            )
        raise ValueError(f"falla desconocida: {self.falla}")


def cliente_con_proveedor_caido(falla: str = "timeout"):
    """Un `ClienteOpenAILike` real cuyo proveedor no responde.

    Se usa el cliente real —no un doble que imite su contrato— para que el
    test recorra exactamente el camino de producción: `responder` → `generar`
    → el handler que corresponda.
    """
    from studify.generation.generator import ClienteOpenAILike

    cliente = ClienteOpenAILike(api_key="clave-de-prueba")
    cliente._llm = _LLMCaido(falla)
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
