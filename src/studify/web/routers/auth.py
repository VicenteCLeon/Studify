"""Acceso al panel del docente: login, logout y el guardián de `/teacher/*`.

Hasta ahora la UI no separaba roles: las pestañas del docente colgaban de la
misma cabecera que las del estudiante y cualquiera que escribiera la URL entraba
a curar material, ver las analíticas de la cohorte y gastar créditos del LLM en
el simulador. `web/sesion.py` firmaba la cookie del estudiante justamente para
que un entero editado a mano no diera acceso al perfil ajeno, pero el panel que
controla **qué material llega a las cápsulas** —la barrera del cap. 12/13— no
tenía ninguna puerta.

Este módulo es esa puerta, y nada más que eso:

- **Una clave compartida, no un sistema de usuarios.** El informe no modela
  docentes: el cap. 9 identifica al estudiante por su diagnóstico y el docente
  aparece solo como el rol que cura y valida. Con una o dos personas en el
  piloto, una tabla de usuarios con hashes y recuperación de clave sería
  infraestructura que nadie va a usar y que hay que mantener y explicar. Si el
  proyecto llegara a tener varios docentes con material propio, esto se cambia
  por autenticación real — y el punto de cambio es solo
  `sesion.verificar_credenciales_docente`.
- **Cierra por omisión.** El guardián va como dependencia del *router* de
  `teacher.py`, no de cada handler: un endpoint nuevo del panel queda protegido
  por el solo hecho de colgar de ese router. Si fuera decorador por decorador,
  olvidarse de uno abriría un agujero silencioso, que es exactamente el modo de
  fallo que este cambio viene a cerrar.
"""

import logging
import time

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from studify.web import sesion
from studify.web.deps import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teacher", tags=["web-auth"])

RUTA_LOGIN = "/teacher/login"
DESTINO_POR_DEFECTO = "/teacher/curation"

# Freno de fuerza bruta. Una clave compartida se elige corta y no se rota
# seguido, así que sin freno un script la encuentra en minutos. Es deliberadamente
# modesto —cuenta en memoria del proceso, se reinicia con el servidor y agrupa
# por IP, de modo que no sirve contra un atacante distribuido—, pero convierte un
# ataque de minutos en uno de días, que para un prototipo de piloto es la
# diferencia que importa. Un `Retry-After` real pediría almacenamiento
# compartido, y esto corre en un solo proceso.
INTENTOS_MAXIMOS = 5
VENTANA_BLOQUEO_SEGUNDOS = 60

_fallos_por_origen: dict[str, list[float]] = {}


def _origen(request: Request) -> str:
    return request.client.host if request.client else "desconocido"


def _segundos_de_bloqueo(origen: str) -> int:
    """Cuánto falta para poder reintentar; 0 si se puede ahora."""
    limite = time.time() - VENTANA_BLOQUEO_SEGUNDOS
    recientes = [t for t in _fallos_por_origen.get(origen, []) if t > limite]
    if recientes:
        _fallos_por_origen[origen] = recientes
    else:
        _fallos_por_origen.pop(origen, None)

    if len(recientes) < INTENTOS_MAXIMOS:
        return 0
    return max(1, int(recientes[0] + VENTANA_BLOQUEO_SEGUNDOS - time.time()))


def reiniciar_intentos() -> None:
    """Limpia el contador de intentos fallidos (lo usan los tests)."""
    _fallos_por_origen.clear()


def destino_seguro(destino: str | None) -> str:
    """Acota el `next` del login a rutas internas del panel.

    `next` llega desde la URL, así que lo escribe quien mande el enlace. Sin
    esta comprobación, `/teacher/login?next=https://sitio-falso` convertiría el
    login en un redirector abierto: el patrón clásico para hacer pasar un enlace
    de phishing por un enlace legítimo del sistema. Se descarta también
    `//otro-sitio`, que el navegador lee como URL absoluta pese a empezar con
    `/`, y las propias rutas de login/logout, que dejarían al docente en un
    rebote.
    """
    if not destino or not destino.startswith("/teacher/") or destino.startswith("//"):
        return DESTINO_POR_DEFECTO
    if destino.startswith((RUTA_LOGIN, "/teacher/logout")):
        return DESTINO_POR_DEFECTO
    return destino


def requiere_docente(request: Request) -> None:
    """Deja pasar solo a quien tenga sesión de docente vigente.

    **El caso HTMX no es un detalle cosmético.** Casi todo el panel se mueve por
    HTMX (`hx-post` a la bandeja, `hx-get` a los fragmentos), y HTMX sigue los
    303 dentro del mismo XHR: con la sesión vencida, el docente vería la página
    de login entera incrustada dentro del `<div>` de estado de la bandeja, sin
    entender qué pasó y sin forma de escribir la clave ahí. `HX-Redirect` le
    pide al navegador una navegación completa, que es lo que corresponde.
    """
    if sesion.es_docente(request):
        return

    destino = RUTA_LOGIN
    # Solo se recuerda el origen de un GET: un POST no se puede repetir después
    # del login (el cuerpo ya se perdió), así que devolver ahí sería mandar al
    # docente a una página que no sabe responder a una visita normal.
    if request.method == "GET" and request.url.path != RUTA_LOGIN:
        destino = f"{RUTA_LOGIN}?next={request.url.path}"

    if request.headers.get("HX-Request") == "true":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión del docente venció. Vuelve a entrar.",
            headers={"HX-Redirect": destino},
        )

    raise HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        detail="Se requiere sesión de docente.",
        headers={"Location": destino},
    )


# `auto_error=False` para poder decidir nosotros la respuesta: con el valor por
# defecto, FastAPI corta con su propio 401 antes de que podamos considerar la
# cookie, y quien ya inició sesión en el panel tendría que autenticarse otra vez.
_basic = HTTPBasic(auto_error=False, description="Credenciales del panel del docente")


def requiere_docente_api(
    request: Request,
    credenciales: HTTPBasicCredentials | None = Depends(_basic),
) -> None:
    """Igual que `requiere_docente`, pero para clientes que esperan JSON.

    **Por qué no se reutiliza el mismo guardián.** El de la web responde con un
    303 a `/teacher/login` o con `HX-Redirect`, y las dos cosas están mal acá:
    un script que llama a `/api/fragmentos` recibiría un 200 con una página HTML
    de login —porque los clientes HTTP siguen los redirects solos— y creería que
    la llamada funcionó. Un 401 con `WWW-Authenticate` es lo que un cliente de
    API puede entender y reintentar.

    Acepta **dos formas** de presentar la credencial, y esa es la razón de que
    exista `auto_error=False`:

    - la **cookie** del panel, para que Swagger (`/docs`) y el navegador sigan
      funcionando sin pedir la clave de nuevo a quien ya entró por la UI;
    - **HTTP Basic**, para `curl -u admin:clave …` y para los scripts de
      `scripts/`, que no tienen dónde guardar una cookie.

    El freno de fuerza bruta del login web se aplica también acá: sin él,
    `/api/*` quedaría como un canal de adivinación de contraseñas sin límite,
    justo al lado de un formulario que sí lo tiene.
    """
    if sesion.es_docente(request):
        return

    origen = _origen(request)
    espera = _segundos_de_bloqueo(origen)
    if espera:
        logger.warning("acceso a /api bloqueado por intentos fallidos: %s", origen)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Demasiados intentos fallidos. Reintenta en {espera} segundo(s).",
            headers={"Retry-After": str(espera)},
        )

    if credenciales and sesion.verificar_credenciales_docente(
        credenciales.username, credenciales.password
    ):
        _fallos_por_origen.pop(origen, None)
        return

    # Solo cuenta como intento fallido si de verdad se presentó una credencial:
    # una petición anónima es el caso normal de "esta ruta pide autenticación",
    # y contarla dejaría el panel bloqueado por un rastreador cualquiera.
    if credenciales:
        _fallos_por_origen.setdefault(origen, []).append(time.time())
        logger.warning("credenciales de docente incorrectas en /api desde %s", origen)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Esta operación requiere credenciales de docente.",
        headers={"WWW-Authenticate": "Basic"},
    )


def estudiante_o_docente_api(
    request: Request,
    credenciales: HTTPBasicCredentials | None = Depends(_basic),
) -> int | None:
    """Quién llama a un endpoint de `/api` que tiene dueño.

    Devuelve el `id_estudiante` de la cookie, o `None` si quien llama es el
    docente (por cookie del panel o por HTTP Basic). **No decide si puede**:
    eso depende del recurso —el diagnóstico, la cápsula—, así que lo resuelve
    la dependencia de cada endpoint comparando el dueño con lo que devuelve
    esta. Sin ninguna de las dos credenciales responde 401.

    Existe porque esos endpoints eran anónimos y el dueño lo declaraba el
    propio cliente (`id_estudiante` en el cuerpo, o un id correlativo en la
    URL): bastaba recorrer números para leer el perfil VARK de toda la cohorte
    o generar cápsulas —y gastar créditos del LLM— a nombre de otro.
    """
    if sesion.es_docente(request):
        return None

    if credenciales:
        # Mismo camino que el resto de `/api` del docente, con su freno de
        # fuerza bruta: una clave incorrecta no puede caer acá a "anónimo".
        requiere_docente_api(request, credenciales)
        return None

    id_estudiante = sesion.estudiante_actual(request)
    if id_estudiante is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Esta operación requiere la sesión del estudiante o credenciales de docente.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return id_estudiante


def _pantalla_login(
    request: Request,
    destino: str,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="teacher/login.html",
        context={
            "destino": destino,
            "error": error,
            "clave_configurada": sesion.credenciales_docente_configuradas(),
        },
        status_code=status_code,
    )


@router.get("/login", response_class=HTMLResponse)
def get_login(request: Request, next: str | None = None):
    """Formulario de acceso. Es la única ruta de `/teacher/*` sin guardián."""
    destino = destino_seguro(next)
    if sesion.es_docente(request):
        return RedirectResponse(url=destino, status_code=status.HTTP_303_SEE_OTHER)
    return _pantalla_login(request, destino)


@router.post("/login", response_class=HTMLResponse)
def post_login(
    request: Request,
    usuario: str = Form(default=""),
    clave: str = Form(default=""),
    next: str = Form(default=""),
):
    """Verifica usuario y clave, y abre la sesión del panel.

    Es un `<form>` normal y no HTMX a propósito: el login tiene que provocar una
    navegación completa para que el navegador guarde la cookie y la cabecera se
    redibuje con las pestañas del docente. Un swap de HTMX dejaría media
    pantalla con la sesión nueva y la cabecera con la anterior.
    """
    destino = destino_seguro(next)

    if not sesion.credenciales_docente_configuradas():
        # No es un error del docente: es `TEACHER_PASSWORD` puesta vacía a
        # propósito. La pantalla lo explica con el nombre exacto de la variable
        # en vez de decir "credenciales incorrectas", que mandaría a buscar el
        # problema donde no está.
        return _pantalla_login(
            request, destino, status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    origen = _origen(request)
    espera = _segundos_de_bloqueo(origen)
    if espera:
        logger.warning("login de docente bloqueado por intentos fallidos: %s", origen)
        return _pantalla_login(
            request,
            destino,
            error=(
                f"Demasiados intentos fallidos. Espera {espera} segundo(s) "
                f"antes de volver a probar."
            ),
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    if not sesion.verificar_credenciales_docente(usuario, clave):
        _fallos_por_origen.setdefault(origen, []).append(time.time())
        logger.warning("credenciales de docente incorrectas desde %s", origen)
        return _pantalla_login(
            request,
            destino,
            error="Usuario o clave incorrectos.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    _fallos_por_origen.pop(origen, None)
    respuesta = RedirectResponse(url=destino, status_code=status.HTTP_303_SEE_OTHER)
    sesion.iniciar_docente(respuesta)
    return respuesta


@router.post("/logout")
def post_logout():
    """Cierra la sesión y devuelve al estudiante al catálogo.

    Queda fuera del guardián para que sea idempotente: cerrar sesión dos veces
    —o con la cookie ya vencida— tiene que borrar la cookie igual, no rebotar a
    un login que el docente justamente está tratando de dejar atrás.
    """
    respuesta = RedirectResponse(
        url="/student/catalog", status_code=status.HTTP_303_SEE_OTHER
    )
    sesion.cerrar_docente(respuesta)
    return respuesta
