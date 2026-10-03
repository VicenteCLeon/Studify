"""Páginas legales: Términos y Condiciones y Política de Privacidad.

Son públicas a propósito —sin sesión ni guardián—: se tienen que poder leer
**antes** de aceptar, desde el enlace del cuestionario, y también sin haber
respondido nunca nada.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from studify.web import legal
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
