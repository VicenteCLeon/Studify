"""Sesión mínima de la UI: qué estudiante está usando la aplicación (Fase 4).

El backend ya sabe generar contenido para un `id_estudiante`; lo que faltaba
era que el navegador recordara **cuál**. Este módulo es ese puente y nada más:
no hay usuarios, contraseñas ni roles, porque el sistema no los tiene — el
cap. 9 identifica al estudiante por su diagnóstico, no por una credencial.

**Por qué la cookie va firmada.** El valor que interesa es un entero, y un
entero en una cookie lo edita cualquiera desde las herramientas del navegador:
poner `id_estudiante=7` bastaría para ver el perfil y las cápsulas de otra
persona. Con una firma HMAC el servidor detecta el cambio y trata la cookie
como inexistente. No es autenticación —quien tenga la cookie es el estudiante—
pero cierra la manipulación trivial, que es el riesgo real de una demo abierta.

Se firma con `hmac` de la biblioteca estándar y no con `itsdangerous` para no
agregar una dependencia por veinte líneas.
"""

import hmac
import logging
import secrets
from hashlib import sha256

from fastapi import Request, Response

from studify.config import get_settings

logger = logging.getLogger(__name__)

COOKIE_ESTUDIANTE = "id_estudiante"

# 30 días. El diagnóstico VARK no caduca —el perfil de aprendizaje no cambia de
# una semana a otra— así que la sesión dura lo que dura el estudio de la unidad.
DURACION_SEGUNDOS = 60 * 60 * 24 * 30

# Secreto de respaldo cuando `SESSION_SECRET` no está en el `.env`. Es aleatorio
# por proceso a propósito: un valor fijo escrito en el código sería un secreto
# público, y firmar con un secreto público es lo mismo que no firmar.
_SECRETO_EFIMERO = secrets.token_bytes(32)


def _secreto() -> bytes:
    configurado = get_settings().session_secret
    if configurado:
        return configurado.encode("utf-8")
    return _SECRETO_EFIMERO


def _firma(id_estudiante: int) -> str:
    return hmac.new(_secreto(), str(id_estudiante).encode("utf-8"), sha256).hexdigest()


def iniciar(response: Response, id_estudiante: int) -> None:
    """Deja al estudiante conectado en las siguientes vistas."""
    response.set_cookie(
        key=COOKIE_ESTUDIANTE,
        value=f"{id_estudiante}.{_firma(id_estudiante)}",
        max_age=DURACION_SEGUNDOS,
        # Ningún script de la página necesita leerla: la UI es HTML renderizado
        # en el servidor y HTMX manda las cookies solo.
        httponly=True,
        # `lax` deja pasar la navegación normal y bloquea el envío desde un
        # sitio de terceros. `strict` rompería la vuelta desde un enlace externo.
        samesite="lax",
        # En desarrollo la demo corre sobre http://127.0.0.1 y `secure` haría
        # que el navegador descartara la cookie sin decir nada.
        secure=get_settings().app_env != "dev",
        path="/",
    )


def cerrar(response: Response) -> None:
    response.delete_cookie(COOKIE_ESTUDIANTE, path="/")


def estudiante_actual(request: Request) -> int | None:
    """El `id_estudiante` de la cookie, o None si no hay o no es de fiar.

    Una firma que no calza se trata como "no hay sesión" y no como un error:
    también ocurre de forma legítima cuando el servidor se reinicia sin
    `SESSION_SECRET` fijo, y en ese caso lo correcto es mandar al estudiante a
    responder el cuestionario, no mostrarle una pantalla de fallo.
    """
    crudo = request.cookies.get(COOKIE_ESTUDIANTE)
    if not crudo or "." not in crudo:
        return None

    valor, _, firma = crudo.partition(".")
    if not valor.isdigit():
        return None

    if not hmac.compare_digest(firma, _firma(int(valor))):
        logger.warning("cookie de sesión con firma inválida; se ignora")
        return None

    return int(valor)
