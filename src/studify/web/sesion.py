"""Sesiones de la UI: quién está usando la aplicación y con qué permiso.

Son **dos cookies con propósitos distintos**, y la diferencia importa:

- `id_estudiante` responde *quién es* el visitante. No es una credencial: el
  cap. 9 identifica al estudiante por su diagnóstico VARK, no por una clave, y
  este módulo solo hace que el navegador recuerde cuál diagnóstico es el suyo.
- `docente` responde *qué puede hacer*. Sí es una credencial —se obtiene
  presentando `TEACHER_USERNAME`/`TEACHER_PASSWORD` en `/teacher/login`— y es lo
  único que separa las vistas del estudiante de las del profesor, incluida la
  bandeja de curación, que es la barrera del cap. 12/13.

**Por qué ambas van firmadas.** Su contenido lo edita cualquiera desde las
herramientas del navegador: poner `id_estudiante=7` bastaría para ver el perfil
de otra persona, y `docente=1` para entrar al panel sin la clave. Con una firma
HMAC el servidor detecta el cambio y trata la cookie como inexistente.

Se firma con `hmac` de la biblioteca estándar y no con `itsdangerous` para no
agregar una dependencia por unas pocas líneas.
"""

import hmac
import logging
import secrets
import time
from hashlib import sha256

from fastapi import Request, Response

from studify.config import get_settings

logger = logging.getLogger(__name__)

COOKIE_ESTUDIANTE = "id_estudiante"
COOKIE_DOCENTE = "docente"

# 30 días. El diagnóstico VARK no caduca —el perfil de aprendizaje no cambia de
# una semana a otra— así que la sesión dura lo que dura el estudio de la unidad.
DURACION_SEGUNDOS = 60 * 60 * 24 * 30

# 12 horas para el docente, muy por debajo de los 30 días del estudiante. Las
# dos cookies no arriesgan lo mismo: la del estudiante recuerda un perfil de
# aprendizaje, la del docente concede permiso para curar material y ver los
# datos de la cohorte. Un notebook prestado o una sesión olvidada en un
# computador de laboratorio dejan de ser una puerta abierta al día siguiente.
DURACION_DOCENTE_SEGUNDOS = 60 * 60 * 12

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


# --- Sesión del docente -------------------------------------------------------


def credenciales_docente_configuradas() -> bool:
    """Si `TEACHER_PASSWORD` quedó vacía a propósito, el panel no abre para nadie.

    Solo mira la clave: `teacher_username` tiene un valor por defecto que nunca
    queda vacío por accidente (`""` en un `.env` sigue siendo un usuario, aunque
    sea uno raro), así que la clave es la única señal confiable de "esto se
    desactivó a propósito".
    """
    return bool(get_settings().teacher_password)


def verificar_credenciales_docente(usuario: str, clave: str) -> bool:
    """Compara usuario y clave con los configurados, en tiempo constante.

    `compare_digest` en vez de `==` porque la comparación normal de Python corta
    en el primer carácter distinto, y ese tiempo distinto es medible: filtra la
    credencial carácter a carácter. Con una credencial compartida —que nadie va
    a rotar seguido— cerrar esa filtración cuesta dos líneas. Se comparan
    **ambos** valores siempre, sin cortocircuitar en el usuario, para no dejar
    un canal por tiempo que confirme "el usuario es correcto" antes de tocar la
    clave.

    Sin clave configurada devuelve `False` siempre, incluida una petición con la
    cadena vacía: si no, un `.env` con `TEACHER_PASSWORD=` dejaría el panel
    abierto a quien mandara el formulario en blanco.
    """
    settings = get_settings()
    if not settings.teacher_password:
        return False
    usuario_ok = hmac.compare_digest(usuario, settings.teacher_username)
    clave_ok = hmac.compare_digest(clave, settings.teacher_password)
    return usuario_ok and clave_ok


def _huella_credenciales() -> str:
    """Marca de la credencial vigente, para meterla dentro de la firma.

    Hace que **cambiar `TEACHER_USERNAME` o `TEACHER_PASSWORD` invalide las
    sesiones ya abiertas**. Sin esto, rotar la credencial —el único remedio
    disponible si se filtra— no expulsaría a quien ya tuviera la cookie, que es
    exactamente el escenario en que uno la rota. Es la huella y no la clave la
    que entra en el mensaje firmado; la clave no sale nunca del servidor.
    """
    settings = get_settings()
    cruda = f"{settings.teacher_username}:{settings.teacher_password}"
    return sha256(cruda.encode("utf-8")).hexdigest()


def _firma_docente(expira: int) -> str:
    return hmac.new(
        _secreto(), f"docente:{_huella_credenciales()}:{expira}".encode(), sha256
    ).hexdigest()


def iniciar_docente(response: Response) -> None:
    """Abre la sesión del panel. Solo se llama tras verificar la clave."""
    expira = int(time.time()) + DURACION_DOCENTE_SEGUNDOS
    response.set_cookie(
        key=COOKIE_DOCENTE,
        # El vencimiento viaja **dentro del mensaje firmado**, no solo en el
        # `max_age`: el `max_age` lo respeta el navegador, y un navegador es lo
        # que estamos tratando de no tener que creerle. Editar la fecha rompe la
        # firma, así que la sesión no se puede extender desde el cliente.
        value=f"{expira}.{_firma_docente(expira)}",
        max_age=DURACION_DOCENTE_SEGUNDOS,
        httponly=True,
        samesite="lax",
        secure=get_settings().app_env != "dev",
        path="/",
    )


def cerrar_docente(response: Response) -> None:
    response.delete_cookie(COOKIE_DOCENTE, path="/")


def es_docente(request: Request) -> bool:
    """Si el visitante presentó la clave del panel y la sesión sigue vigente.

    Devuelve un booleano y no levanta: la usan tanto el guardián de
    `/teacher/*` (que decide el redirect) como `base.html` a través del
    procesador de contexto (que decide qué pestañas dibujar), y para la segunda
    "no hay sesión" es un estado normal, no un error.
    """
    if not credenciales_docente_configuradas():
        return False

    crudo = request.cookies.get(COOKIE_DOCENTE)
    if not crudo or "." not in crudo:
        return False

    valor, _, firma = crudo.partition(".")
    if not valor.isdigit():
        return False

    expira = int(valor)
    if expira <= int(time.time()):
        return False

    if not hmac.compare_digest(firma, _firma_docente(expira)):
        # También pasa de forma legítima al rotar la clave o al reiniciar sin
        # `SESSION_SECRET` fijo: en ambos casos lo correcto es pedir el login de
        # nuevo, no mostrar una pantalla de fallo.
        logger.warning("cookie de docente con firma inválida; se ignora")
        return False

    return True
