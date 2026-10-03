"""Páginas legales: Términos, Privacidad y la pantalla para volver a aceptarlos.

Los documentos son públicos a propósito —sin sesión ni guardián—: se tienen que
poder leer **antes** de aceptar, desde el enlace del cuestionario, y también sin
haber respondido nunca nada.

`/aceptar` es adonde manda `consentimiento.exigir_vigente` a un estudiante con
sesión que no ha aceptado la versión vigente: los 147 que ya existían cuando se
agregó el marco legal, y todos cada vez que sube una versión en `web/legal.py`.
"""

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from studify.db.models import Estudiante
from studify.db.session import get_db
from studify.web import consentimiento, legal, sesion
from studify.web.deps import templates

router = APIRouter(tags=["web-legal"])


def _documento(request: Request, documento: legal.Documento) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name=documento.template,
        context={"documento": documento},
    )


@router.get("/terminos", response_class=HTMLResponse)
def get_terminos(request: Request):
    return _documento(request, legal.TERMINOS)


@router.get("/privacidad", response_class=HTMLResponse)
def get_privacidad(request: Request):
    return _documento(request, legal.PRIVACIDAD)


def _id_con_sesion(request: Request, db: Session) -> int | None:
    id_estudiante = sesion.estudiante_actual(request)
    if id_estudiante is None or db.get(Estudiante, id_estudiante) is None:
        return None
    return id_estudiante


def _pantalla_aceptar(
    request: Request,
    pendientes: list[legal.Documento],
    destino: str,
    error: str | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="legal/aceptar.html",
        context={"pendientes": pendientes, "destino": destino, "error": error},
    )


@router.get("/aceptar", response_class=HTMLResponse)
def get_aceptar(request: Request, next: str | None = None, db: Session = Depends(get_db)):
    destino = consentimiento.destino_seguro(next)
    id_estudiante = _id_con_sesion(request, db)
    if id_estudiante is None:
        # Sin sesión no hay a quién asociar la aceptación: se acepta en el
        # primer paso del cuestionario.
        return RedirectResponse(url="/student/vark", status_code=status.HTTP_303_SEE_OTHER)

    pendientes = consentimiento.pendientes(db, id_estudiante)
    if not pendientes:
        return RedirectResponse(url=destino, status_code=status.HTTP_303_SEE_OTHER)
    return _pantalla_aceptar(request, pendientes, destino)


@router.post("/aceptar", response_class=HTMLResponse)
def post_aceptar(
    request: Request,
    acepto: str = Form(default=""),
    next: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Formulario normal (no HTMX): tras aceptar hay que volver a navegar."""
    destino = consentimiento.destino_seguro(next)
    id_estudiante = _id_con_sesion(request, db)
    if id_estudiante is None:
        return RedirectResponse(url="/student/vark", status_code=status.HTTP_303_SEE_OTHER)

    pendientes = consentimiento.pendientes(db, id_estudiante)
    if acepto != "si":
        return _pantalla_aceptar(
            request,
            pendientes,
            destino,
            error="Para seguir usando RepasAi tienes que marcar la casilla de aceptación.",
        )

    consentimiento.registrar(db, id_estudiante, tuple(pendientes))
    return RedirectResponse(url=destino, status_code=status.HTTP_303_SEE_OTHER)
