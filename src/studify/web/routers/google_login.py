"""Google OpenID Connect: recuperar o vincular el mismo `id_estudiante`.

Código de autorización, PKCE S256, state ligado al navegador y nonce. Google
verifica la identidad; el rol y todos los permisos siguen siendo de RepasAi.
No se guardan access tokens, refresh tokens ni ID tokens.
"""

import base64
import hmac
import secrets
import time
from datetime import UTC, datetime, timedelta
from functools import partial
from hashlib import sha256
from typing import Literal
from urllib.parse import urlencode, urlsplit

import httpx
import requests
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from google.auth import exceptions as google_errors
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from studify.config import get_settings
from studify.db.models import Estudiante, IntentoGoogle
from studify.db.session import get_db
from studify.web import consentimiento, sesion
from studify.web.deps import templates

router = APIRouter(
    prefix="/student", tags=["web-google"],
    dependencies=[Depends(consentimiento.exigir_vigente)],
)
COOKIE_CSRF = "google_csrf"
COOKIE_OAUTH = "google_oauth"
COOKIE_VARK = "google_vark"
SEGUNDOS = 600
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def configurado() -> bool:
    ajustes = get_settings()
    return bool(ajustes.google_client_id and ajustes.google_client_secret)


def _iguales(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _privada(respuesta: Response) -> Response:
    respuesta.headers["Cache-Control"] = "no-store"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    return respuesta


def _cookie(respuesta: Response, nombre: str, valor: str) -> None:
    respuesta.set_cookie(
        nombre, valor, max_age=SEGUNDOS, httponly=True, samesite="lax",
        secure=get_settings().app_env != "dev", path="/student",
    )


def _limpiar(respuesta: Response) -> Response:
    respuesta.delete_cookie(COOKIE_OAUTH, path="/student")
    respuesta.delete_cookie(COOKIE_CSRF, path="/student")
    return _privada(respuesta)


def _guardar_continuacion(respuesta: Response, contexto: str, enlace: str) -> None:
    # Solo un contexto opaco: las respuestas y los datos opcionales permanecen
    # en sessionStorage. La firma liga la entrega al intento OAuth y después
    # a la cuenta verificada, sin aceptar un contexto enviado por JavaScript.
    cuerpo = f"{contexto}.{sha256(enlace.encode()).hexdigest()}.{int(time.time()) + SEGUNDOS}"
    firma = hmac.new(sesion._secreto(), f"vark-google:{cuerpo}".encode(), sha256).hexdigest()
    _cookie(respuesta, COOKIE_VARK, f"{cuerpo}.{firma}")


def _leer_continuacion(request: Request, enlace: str) -> str:
    crudo = request.cookies.get(COOKIE_VARK, "")
    if len(crudo) > 256 or not crudo.isascii():
        return ""
    partes = crudo.split(".")
    if len(partes) != 4 or not partes[2].isdigit() or len(partes[0]) != 64:
        return ""
    cuerpo = ".".join(partes[:3])
    firma = hmac.new(sesion._secreto(), f"vark-google:{cuerpo}".encode(), sha256).hexdigest()
    if int(partes[2]) <= time.time() or not _iguales(partes[3], firma) or not _iguales(
        partes[1], sha256(enlace.encode()).hexdigest()
    ):
        return ""
    return partes[0]


def _enlace_estudiante(estudiante: Estudiante) -> str:
    return f"{estudiante.id_estudiante}:{sesion._microsegundos(estudiante.fecha_registro)}"


def contexto_continuado(request: Request, estudiante: Estudiante | None) -> str:
    if estudiante is None or not estudiante.google_sub or estudiante.rol != "estudiante":
        return ""
    return _leer_continuacion(request, _enlace_estudiante(estudiante))


def _firma_csrf(request: Request, cuerpo: str) -> str:
    contexto = sha256(request.cookies.get(sesion.COOKIE_ESTUDIANTE, "").encode()).hexdigest()
    return hmac.new(
        sesion._secreto(), f"google-csrf:{contexto}:{cuerpo}".encode(), sha256
    ).hexdigest()


def _csrf_valido(request: Request, token: str) -> bool:
    if len(token) > 256 or not _iguales(token, request.cookies.get(COOKIE_CSRF, "")):
        return False
    partes = token.split(".")
    if len(partes) != 3 or not partes[1].isdigit():
        return False
    cuerpo = ".".join(partes[:2])
    return int(partes[1]) > time.time() and _iguales(partes[2], _firma_csrf(request, cuerpo))


def _error(request: Request, mensaje: str, estado: int) -> Response:
    respuesta = templates.TemplateResponse(
        request=request, name="student/google_error.html",
        context={"mensaje": mensaje, "continuar_vark": bool(
            request.cookies.get(COOKIE_VARK)
        )}, status_code=estado,
    )
    return _limpiar(respuesta)


@router.get("/login", response_class=HTMLResponse)
def login(
    request: Request, rol: str = "estudiante", continuar: str = "",
    db: Session = Depends(get_db),
):
    actual = sesion.estudiante_actual(request, db)
    cuerpo = f"{secrets.token_urlsafe(32)}.{int(time.time()) + SEGUNDOS}"
    csrf = f"{cuerpo}.{_firma_csrf(request, cuerpo)}"
    respuesta = templates.TemplateResponse(
        request=request, name="student/login.html", context={
            "google_configurado": configurado(), "csrf": csrf,
            "rol_registro": "control" if rol == "control" else "estudiante",
            "estudiante": db.get(Estudiante, actual) if actual else None,
            "continuar_vark": continuar == "vark",
        },
    )
    _cookie(respuesta, COOKIE_CSRF, csrf)
    return _privada(respuesta)


@router.post("/google/iniciar")
def iniciar(
    request: Request, csrf: str = Form(default=""),
    accion: Literal["entrar", "vincular"] = Form(default="entrar"),
    rol: Literal["estudiante", "control"] = Form(default="estudiante"),
    continuar: str = Form(default=""),
    db: Session = Depends(get_db),
):
    if not configurado():
        return _error(request, "Google no está configurado en esta instalación.", 503)
    if not _csrf_valido(request, csrf):
        return _error(request, "El formulario venció. Abre el acceso e inténtalo de nuevo.", 403)
    callback = urlsplit(get_settings().google_redirect_uri)
    local = callback.hostname in {"localhost", "127.0.0.1", "::1"}
    if (callback.scheme != "https" and not (local and callback.scheme == "http")) or (
        not callback.netloc or callback.username or callback.fragment or callback.query
    ):
        return _error(
            request, "La dirección de retorno de Google no está configurada correctamente.", 503,
        )
    actual = sesion.estudiante_actual(request, db)
    estudiante = db.get(Estudiante, actual) if actual else None
    if accion == "vincular":
        if estudiante is None or estudiante.google_sub:
            return _error(
                request, "Para vincular, abre primero tu perfil local sin cuenta Google.", 409,
            )
        rol = estudiante.rol
    elif actual is not None:
        return _error(request, "Cierra la sesión actual antes de entrar con otra cuenta.", 409)
    if continuar == "vark" and accion == "entrar":
        rol = "estudiante"
    estado, nonce, verificador = (secrets.token_urlsafe(32) for _ in range(3))
    ahora = datetime.now(UTC)
    db.execute(delete(IntentoGoogle).where(IntentoGoogle.expira <= ahora))
    db.add(IntentoGoogle(
        estado_hash=sha256(estado.encode()).hexdigest(), nonce=nonce, verificador=verificador,
        expira=ahora + timedelta(seconds=SEGUNDOS), rol=rol,
        id_estudiante=actual if accion == "vincular" else None,
    ))
    db.commit()
    challenge = base64.urlsafe_b64encode(sha256(verificador.encode()).digest()).decode().rstrip("=")
    parametros = {
        "client_id": get_settings().google_client_id,
        "redirect_uri": get_settings().google_redirect_uri,
        "response_type": "code", "scope": "openid email profile", "state": estado,
        "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    respuesta = RedirectResponse(AUTH_URL + "?" + urlencode(parametros), status_code=303)
    _cookie(respuesta, COOKIE_OAUTH, estado)
    if continuar == "vark":
        _guardar_continuacion(
            respuesta, sesion.token_formulario(request, "borrador-vark"), estado,
        )
    else:
        respuesta.delete_cookie(COOKIE_VARK, path="/student")
    respuesta.delete_cookie(COOKIE_CSRF, path="/student")
    return _privada(respuesta)


def intercambiar_codigo(codigo: str, verificador: str) -> str:
    """Intercambio solo servidor a servidor; el secret nunca viaja al frontend."""
    ajustes = get_settings()
    with httpx.Client(timeout=10, follow_redirects=False) as cliente:
        respuesta = cliente.post(TOKEN_URL, data={
            "code": codigo, "client_id": ajustes.google_client_id,
            "client_secret": ajustes.google_client_secret,
            "redirect_uri": ajustes.google_redirect_uri, "grant_type": "authorization_code",
            "code_verifier": verificador,
        })
        respuesta.raise_for_status()
        token = respuesta.json().get("id_token")
    if not isinstance(token, str) or not token:
        raise ValueError("Google no devolvió una identidad.")
    return token


def verificar_token(token: str, nonce: str) -> dict:
    """La biblioteca oficial valida firma, audiencia, emisor y vencimiento."""
    with requests.Session() as transporte:
        solicitud = partial(GoogleRequest(session=transporte), timeout=10)
        identidad = id_token.verify_oauth2_token(
            token, solicitud, get_settings().google_client_id,
        )
    if identidad.get("azp", get_settings().google_client_id) != get_settings().google_client_id:
        raise ValueError("El cliente autorizado de Google no corresponde a esta aplicación.")
    if not isinstance(identidad.get("nonce"), str) or not _iguales(identidad["nonce"], nonce):
        raise ValueError("El nonce no corresponde a este inicio de sesión.")
    sub, correo = identidad.get("sub"), identidad.get("email")
    if not isinstance(sub, str) or not sub or len(sub) > 255:
        raise ValueError("Identificador de Google inválido.")
    if identidad.get("email_verified") is not True or not isinstance(correo, str):
        raise ValueError("Google no verificó el correo de esta cuenta.")
    if not correo or len(correo) > 320:
        raise ValueError("Correo de Google inválido.")
    nombre = identidad.get("name")
    return {
        "sub": sub, "email": correo,
        "nombre": nombre[:200] if isinstance(nombre, str) else None,
    }


@router.get("/google/callback")
def callback(
    request: Request, state: str = "", code: str = "", error: str = "",
    db: Session = Depends(get_db),
):
    if not configurado():
        return _error(request, "Google no está configurado en esta instalación.", 503)
    if not state or len(state) > 128 or not _iguales(
        state, request.cookies.get(COOKIE_OAUTH, "")
    ):
        return _error(
            request, "El acceso no corresponde a este navegador. Inténtalo de nuevo.", 400,
        )
    # DELETE RETURNING consume el intento incluso entre varios procesos. Una
    # segunda devolución no puede volver a vincular ni crear otra cuenta.
    intento = db.execute(delete(IntentoGoogle).where(
        IntentoGoogle.estado_hash == sha256(state.encode()).hexdigest(),
        IntentoGoogle.expira > datetime.now(UTC),
    ).returning(
        IntentoGoogle.nonce, IntentoGoogle.verificador, IntentoGoogle.rol,
        IntentoGoogle.id_estudiante,
    )).mappings().first()
    db.commit()
    if intento is None:
        return _error(request, "El acceso venció o ya fue utilizado. Inténtalo de nuevo.", 400)
    actual = sesion.estudiante_actual(request, db)
    if actual != intento["id_estudiante"]:
        return _error(request, "La sesión cambió durante el acceso. Empieza nuevamente.", 409)
    if error:
        return _error(request, "Cancelaste el acceso con Google. Puedes volver a intentarlo.", 400)
    if not code or len(code) > 2048:
        return _error(request, "Google no devolvió un código de acceso válido.", 400)
    try:
        token = intercambiar_codigo(code, intento["verificador"])
    except (httpx.HTTPError, ValueError):
        return _error(request, "No pudimos conectar con Google. Inténtalo de nuevo.", 502)
    try:
        identidad = verificar_token(token, intento["nonce"])
    except (ValueError, google_errors.GoogleAuthError, requests.RequestException):
        return _error(request, "No pudimos verificar tu identidad con Google.", 401)
    cuenta = db.scalar(select(Estudiante).where(Estudiante.google_sub == identidad["sub"]))
    if actual is not None:
        estudiante = db.get(Estudiante, actual)
        if estudiante is None or (cuenta is not None and cuenta.id_estudiante != actual) or (
            estudiante.google_sub and estudiante.google_sub != identidad["sub"]
        ):
            return _error(request, "Esta cuenta ya está vinculada. No se combinaron perfiles.", 409)
    else:
        estudiante = cuenta
        if estudiante is None:
            origen = sesion.origen_marcado(request) or (
                "sesion_vencida" if sesion.sesion_vencida(request, db) else "nuevo"
            )
            estudiante = Estudiante(rol=intento["rol"], origen_registro=origen)
            db.add(estudiante)
    estudiante.google_sub = identidad["sub"]
    estudiante.google_email = identidad["email"]
    estudiante.google_nombre = identidad["nombre"]
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Dos navegadores pueden autenticar la misma cuenta al mismo tiempo.
        # La unicidad de sub impide duplicarla; vincular nunca fusiona personas.
        if actual is not None:
            return _error(request, "Esta cuenta ya fue vinculada a otro perfil.", 409)
        estudiante = db.scalar(select(Estudiante).where(Estudiante.google_sub == identidad["sub"]))
        if estudiante is None:
            return _error(request, "No pudimos completar el acceso. Inténtalo nuevamente.", 409)
    destino = "/student/profile"
    if estudiante.rol == "estudiante" and not estudiante.diagnosticos:
        destino = "/student/vark"
    elif estudiante.rol == "control" and not estudiante.aceptaciones:
        destino = "/student/control"
    contexto = _leer_continuacion(request, state)
    if contexto and estudiante.rol == "estudiante":
        destino = "/student/vark?modo=actualizar"
    respuesta = RedirectResponse(destino, status_code=303)
    if contexto and estudiante.rol == "estudiante":
        _guardar_continuacion(respuesta, contexto, _enlace_estudiante(estudiante))
    else:
        respuesta.delete_cookie(COOKIE_VARK, path="/student")
    sesion.iniciar(respuesta, estudiante)
    sesion.borrar_origen(respuesta)
    return _limpiar(respuesta)
