"""Páginas legales: Términos, Privacidad y la pantalla para volver a aceptarlos.

Los documentos son públicos a propósito —sin sesión ni guardián—: se tienen que
poder leer **antes** de aceptar, desde el enlace del cuestionario, y también sin
haber respondido nunca nada.

`/aceptar` es adonde manda `consentimiento.exigir_vigente` a un estudiante con
sesión que no ha aceptado la versión vigente: los 147 que ya existían cuando se
agregó el marco legal, y todos cada vez que sube una versión en `web/legal.py`.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from studify.db.models import Estudiante
from studify.db.session import get_db
from studify.web import consentimiento, exportacion, legal, sesion
from studify.web.deps import templates

logger = logging.getLogger(__name__)

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


# --- Mis datos: acceso, portabilidad, rectificación y supresión --------------
#
# Fuera del guardián de aceptación a propósito: ejercer los derechos no puede
# quedar condicionado a aceptar primero la versión nueva de los documentos.
# El estudiante se identifica con su cookie firmada —no hay otra forma, porque
# no pedimos nombre ni correo— y cada acción toca solo sus propios datos.
# Los POST van con formulario normal: la cookie es `samesite=lax`, así que un
# sitio de terceros no puede disparar el borrado en nombre del estudiante.

# Mismo directorio en que `student.generate_capsule_audio` deja los .wav.
DIRECTORIO_AUDIO = Path(__file__).resolve().parents[2] / "public" / "audio"
RANGOS_ETARIOS = ("18 - 20 años", "21 - 23 años", "24 - 26 años", "27 años o más")
GENEROS = ("Femenino", "Masculino", "No Binario / otra identidad")


def _sin_sesion_para_datos(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="legal/mis_datos.html", context={"estudiante": None}
    )


def _pantalla_mis_datos(
    request: Request,
    db: Session,
    estudiante: Estudiante,
    *,
    aviso: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    datos = exportacion.datos_de(db, estudiante)
    return templates.TemplateResponse(
        request=request,
        name="legal/mis_datos.html",
        context={
            "estudiante": estudiante,
            "datos": datos,
            "rangos": RANGOS_ETARIOS,
            "generos": GENEROS,
            "aviso": aviso,
            "error": error,
        },
    )


@router.get("/mis-datos", response_class=HTMLResponse)
def get_mis_datos(request: Request, db: Session = Depends(get_db)):
    id_estudiante = _id_con_sesion(request, db)
    if id_estudiante is None:
        return _sin_sesion_para_datos(request)
    return _pantalla_mis_datos(request, db, db.get(Estudiante, id_estudiante))


@router.get("/mis-datos/exportar")
def get_exportar(request: Request, db: Session = Depends(get_db)):
    """Acceso y portabilidad: todos los datos del estudiante en un JSON."""
    id_estudiante = _id_con_sesion(request, db)
    if id_estudiante is None:
        return RedirectResponse(url="/mis-datos", status_code=status.HTTP_303_SEE_OTHER)
    contenido = json.dumps(
        exportacion.datos_de(db, db.get(Estudiante, id_estudiante)),
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    return Response(
        content=contenido,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="repasai-mis-datos-{id_estudiante}.json"'
        },
    )


@router.post("/mis-datos/rectificar", response_class=HTMLResponse)
def post_rectificar(
    request: Request,
    rango_etario: str = Form(default=""),
    genero: str = Form(default=""),
    consiento_genero: str = Form(default=""),
    carrera: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Rectificación de los datos opcionales, y retiro del consentimiento del género.

    Dejar un campo vacío lo borra. Solo se tocan estos tres: el perfil VARK se
    corrige respondiendo de nuevo el cuestionario, que es la única forma de que
    siga siendo el resultado del instrumento.
    """
    id_estudiante = _id_con_sesion(request, db)
    if id_estudiante is None:
        return RedirectResponse(url="/mis-datos", status_code=status.HTTP_303_SEE_OTHER)
    estudiante = db.get(Estudiante, id_estudiante)

    rango, gen, car = rango_etario.strip(), genero.strip(), carrera.strip()
    invalido = (rango and rango not in RANGOS_ETARIOS) or (gen and gen not in GENEROS)
    if invalido or len(car) > 80:
        return _pantalla_mis_datos(
            request, db, estudiante, error="Alguno de los valores no es válido."
        )
    if gen and consiento_genero != "si":
        return _pantalla_mis_datos(
            request,
            db,
            estudiante,
            error=(
                "Para guardar tu género marca la casilla que autoriza su uso, "
                "o déjalo en «Prefiero no decirlo»."
            ),
        )

    estudiante.rango_etario = rango or None
    estudiante.carrera = car or None
    estudiante.genero = gen or None
    db.commit()
    if gen:
        consentimiento.registrar(db, id_estudiante, (), genero=True)
    return _pantalla_mis_datos(request, db, estudiante, aviso="Guardamos tus cambios.")


@router.post("/mis-datos/eliminar", response_class=HTMLResponse)
def post_eliminar(
    request: Request,
    confirmo: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Supresión: borra al estudiante y, en cascada, todo lo asociado a él.

    Diagnósticos, respuestas, configuraciones, cápsulas, intentos y aceptaciones
    caen por `ON DELETE CASCADE`; los audios narrados son archivos y se borran
    a mano. Después se cierra la sesión: la cookie ya no apunta a nadie.
    """
    id_estudiante = _id_con_sesion(request, db)
    if id_estudiante is None:
        return RedirectResponse(url="/mis-datos", status_code=status.HTTP_303_SEE_OTHER)
    estudiante = db.get(Estudiante, id_estudiante)
    if confirmo != "si":
        return _pantalla_mis_datos(
            request,
            db,
            estudiante,
            error="Para eliminar tus datos marca la casilla de confirmación.",
        )

    ids_capsulas = [c.id_capsula for c in estudiante.capsulas]
    db.delete(estudiante)
    db.commit()
    for id_capsula in ids_capsulas:
        (DIRECTORIO_AUDIO / f"capsula_{id_capsula}.wav").unlink(missing_ok=True)
    logger.info("estudiante %s eliminó sus datos (%s cápsulas)", id_estudiante, len(ids_capsulas))

    respuesta = templates.TemplateResponse(request=request, name="legal/datos_eliminados.html")
    sesion.cerrar(respuesta)
    return respuesta
