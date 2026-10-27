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

**Qué firma la cookie del estudiante** (24-oct-2026, R2): el id, la
`fecha_registro` del estudiante en microsegundos y el vencimiento de la sesión.
La fecha hace que una cookie emitida contra otra base —tras `reset_db.py` los
ids vuelven a 1— no abra el perfil de quien hoy tenga ese id; el vencimiento,
que una sesión olvidada en un computador compartido no le quede abierta al
siguiente. Por eso `estudiante_actual` consulta la base.
"""

import hmac
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from fastapi import Request, Response
from sqlalchemy.orm import Session

from studify.config import get_settings
from studify.db.models import Estudiante

logger = logging.getLogger(__name__)

COOKIE_ESTUDIANTE = "id_estudiante"
COOKIE_DOCENTE = "docente"
# Marca que deja «Salir» para que el siguiente registro del navegador quede con
# su `origen_registro` (ver `db/models.py`). No identifica a nadie: solo dice
# por qué se cerró la sesión anterior, y se borra al usarse.
COOKIE_ORIGEN = "origen_registro"
ORIGENES_MARCADOS = ("tras_salir", "otra_persona")

# 30 días: cuánto **guarda** el navegador la cookie, que es lo que declara la
# Política de Privacidad. Cuánto **vale** la sesión lo fija aparte
# `SESION_ESTUDIANTE_HORAS` (720 por defecto, los mismos 30 días). Que la cookie
# dure más que la sesión es a propósito: una cookie vencida todavía llega al
# servidor y deja marcar al siguiente registro como `sesion_vencida`.
DURACION_SEGUNDOS = 60 * 60 * 24 * 30

# 12 horas para el docente, muy por debajo de los 30 días del estudiante. Las
# dos cookies no arriesgan lo mismo: la del estudiante recuerda un perfil de
# aprendizaje, la del docente concede permiso para curar material y ver los
# datos de la cohorte. Un notebook prestado o una sesión olvidada en un
# computador de laboratorio dejan de ser una puerta abierta al día siguiente.
DURACION_DOCENTE_SEGUNDOS = 60 * 60 * 12

# Secreto de respaldo cuando `SESSION_SECRET` no está en el `.env`. Es aleatorio
# por proceso a propósito: un valor fijo escrito en el código sería un secreto
# público, y firmar con un secreto público es lo mismo que no firmar. Solo llega
# a usarse con `APP_ENV=dev`: fuera de desarrollo `config.verificar_configuracion`
# no deja arrancar sin secreto.
_SECRETO_EFIMERO = secrets.token_bytes(32)


def _secreto() -> bytes:
    configurado = get_settings().session_secret
    if configurado:
        return configurado.encode("utf-8")
    return _SECRETO_EFIMERO


_EPOCA = datetime(1970, 1, 1, tzinfo=UTC)


def _microsegundos(fecha: datetime) -> int:
    """La fecha como entero exacto: con `timestamp()` (float) se perderían µs."""
    return (fecha - _EPOCA) // timedelta(microseconds=1)


def _firma(id_estudiante: int, registro: int, expira: int) -> str:
    mensaje = f"estudiante:{id_estudiante}:{registro}:{expira}"
    return hmac.new(_secreto(), mensaje.encode("utf-8"), sha256).hexdigest()


def _duracion_sesion() -> int:
    return get_settings().sesion_estudiante_horas * 60 * 60


def valor_cookie(id_estudiante: int, fecha_registro: datetime, *, expira: int | None = None) -> str:
    """`<id>.<registro en µs>.<vence>.<firma>`; sin `expira`, la sesión empieza ahora."""
    if expira is None:
        expira = int(time.time()) + _duracion_sesion()
    registro = _microsegundos(fecha_registro)
    return f"{id_estudiante}.{registro}.{expira}.{_firma(id_estudiante, registro, expira)}"


def iniciar(response: Response, estudiante: Estudiante) -> None:
    """Deja al estudiante conectado en las siguientes vistas."""
    response.set_cookie(
        key=COOKIE_ESTUDIANTE,
        value=valor_cookie(estudiante.id_estudiante, estudiante.fecha_registro),
        max_age=max(DURACION_SEGUNDOS, _duracion_sesion()),
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


@dataclass(frozen=True, slots=True)
class _CookieEstudiante:
    id_estudiante: int
    registro: int
    expira: int

    @property
    def vencida(self) -> bool:
        return self.expira <= int(time.time())


def _leer(request: Request) -> _CookieEstudiante | None:
    """La cookie del estudiante si su firma es auténtica, vencida o no.

    Una firma que no calza se trata como "no hay sesión" y no como un error:
    también ocurre de forma legítima cuando el servidor se reinicia sin
    `SESSION_SECRET` fijo, y en ese caso lo correcto es mandar al estudiante a
    responder el cuestionario, no mostrarle una pantalla de fallo. Las cookies
    del formato anterior (`<id>.<firma>`) caen acá y se ignoran.
    """
    crudo = request.cookies.get(COOKIE_ESTUDIANTE)
    if not crudo:
        return None

    partes = crudo.split(".")
    if len(partes) != 4 or not all(p.isdigit() for p in partes[:3]):
        return None

    id_estudiante, registro, expira = (int(p) for p in partes[:3])
    if not hmac.compare_digest(partes[3], _firma(id_estudiante, registro, expira)):
        logger.warning("cookie de sesión con firma inválida; se ignora")
        return None

    return _CookieEstudiante(id_estudiante, registro, expira)


def _es_de_la_base(cookie: _CookieEstudiante, db: Session) -> bool:
    """Que el estudiante exista y sea el mismo que recibió la cookie."""
    estudiante = db.get(Estudiante, cookie.id_estudiante)
    return estudiante is not None and _microsegundos(estudiante.fecha_registro) == cookie.registro


def estudiante_actual(request: Request, db: Session) -> int | None:
    """El `id_estudiante` de la sesión, o None si no hay, venció o no es de fiar."""
    cookie = _leer(request)
    if cookie is None or cookie.vencida or not _es_de_la_base(cookie, db):
        return None
    return cookie.id_estudiante


def sesion_vencida(request: Request, db: Session) -> bool:
    """Si el navegador trae la sesión auténtica de un estudiante, pero vencida."""
    cookie = _leer(request)
    return cookie is not None and cookie.vencida and _es_de_la_base(cookie, db)


def tiene_sesion(request: Request) -> bool:
    """Si hay una sesión firmada y vigente, sin consultar la base.

    Es para la cabecera, que se dibuja en cada página: basta para decidir si
    se ofrece «Salir». Para saber **quién** es, `estudiante_actual`.
    """
    cookie = _leer(request)
    return cookie is not None and not cookie.vencida


def marcar_origen(response: Response, origen: str) -> None:
    """Deja dicho por qué se cerró la sesión, para el siguiente registro."""
    response.set_cookie(
        key=COOKIE_ORIGEN,
        value=origen,
        max_age=DURACION_SEGUNDOS,
        httponly=True,
        samesite="lax",
        secure=get_settings().app_env != "dev",
        path="/",
    )


def origen_marcado(request: Request) -> str | None:
    valor = request.cookies.get(COOKIE_ORIGEN)
    return valor if valor in ORIGENES_MARCADOS else None


def borrar_origen(response: Response) -> None:
    response.delete_cookie(COOKIE_ORIGEN, path="/")


# --- Sesión del docente -------------------------------------------------------


def credenciales_docente_configuradas() -> bool:
    """Sin `TEACHER_PASSWORD` (no fijada o vacía) el panel no abre para nadie.

    Solo mira la clave: `teacher_username` tiene un valor por defecto que nunca
    queda vacío por accidente (`""` en un `.env` sigue siendo un usuario, aunque
    sea uno raro). La clave no tiene valor por defecto desde O1.
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

    Se comparan los **bytes UTF-8** y no los `str`: con `str`,
    `compare_digest` solo acepta ASCII y levanta `TypeError` ante una «ñ» o una
    tilde, de modo que el login respondía 500 en vez de rechazar la clave.
    """
    settings = get_settings()
    if not settings.teacher_password:
        return False
    usuario_ok = hmac.compare_digest(
        usuario.encode("utf-8"), settings.teacher_username.encode("utf-8")
    )
    clave_ok = hmac.compare_digest(
        clave.encode("utf-8"), settings.teacher_password.encode("utf-8")
    )
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
