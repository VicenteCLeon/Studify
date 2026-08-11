"""Panel de curación del docente (Fase 4).

Es la única puerta por la que el material institucional entra al sistema: se
sube un PDF/PPTX, la ingesta lo fragmenta y el docente decide fragmento a
fragmento qué queda disponible para el retriever. Ningún fragmento sin validar
llega jamás al prompt (cap. 12/13), así que esta pantalla no es administrativa:
es la barrera de seguridad del proyecto.

Como en `student.py`, los endpoints son síncronos (`def`) porque tocan
SQLAlchemy, y no reimplementan lógica: llaman a `knowledge.ingest`,
`knowledge.curation` y a los mismos handlers que expone `/api/*`.

**La decisión de diseño que se ve en la pantalla:** el botón de aprobar no
existe por sí solo, va junto al selector de objetivo de aprendizaje. Validar un
fragmento sin objetivo lo dejaría inalcanzable para siempre —el retriever
recupera por `id_objetivo`—, aprobado, sin error visible y sin llegar nunca a
una cápsula. `curation.validar` lo bloquea; acá se hace además imposible de
intentar.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from studify.api.routers.knowledge import (
    listar_documentos,
    listar_objetivos,
    subir_documento,
)
from studify.db.session import get_db
from studify.knowledge import curation
from studify.web.deps import templates

router = APIRouter(prefix="/teacher", tags=["web-teacher"])

# Cuántos fragmentos muestra la bandeja de una vez. La curación es trabajo
# humano y el techo del plan es de 40–60 fragmentos por unidad, así que una
# página basta para revisar un documento completo sin paginar.
LIMITE_BANDEJA = 60


@router.get("/curation", response_class=HTMLResponse)
def get_curation(
    request: Request,
    id_documento: int | None = None,
    db: Session = Depends(get_db),
):
    """Documentos cargados, objetivos disponibles y la bandeja de revisión."""
    return templates.TemplateResponse(
        request=request,
        name="teacher/curation.html",
        context=_contexto_panel(db, id_documento),
    )


@router.get("/curation/fragmentos", response_class=HTMLResponse)
def get_fragmentos(
    request: Request,
    id_documento: int | None = None,
    db: Session = Depends(get_db),
):
    """Solo la bandeja, para que HTMX la refresque tras subir un documento."""
    return templates.TemplateResponse(
        request=request,
        name="teacher/_bandeja.html",
        context=_contexto_panel(db, id_documento),
    )


@router.post("/curation/upload", response_class=HTMLResponse)
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    asignatura: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Ingesta real: el archivo se fragmenta y queda **pendiente** de curación.

    Reutiliza `subir_documento`, el handler de `POST /api/documentos`, con todo
    lo que trae: deduplicación por SHA-256, copia al almacén y trazabilidad de
    página. Nada de lo que entra por acá queda disponible para el retriever
    hasta que alguien lo valide.
    """
    try:
        resultado = subir_documento(
            archivo=file,
            asignatura=asignatura.strip() or None,
            db=db,
        )
    except HTTPException as exc:
        return _aviso(request, "error", _explicar_ingesta(exc))
    except ModuleNotFoundError as exc:
        # `pymupdf` y `python-pptx` son dependencias opcionales del proyecto
        # (grupo `ingest` en pyproject.toml). Sin ellas la extracción revienta
        # con un error que no dice qué hacer.
        return _aviso(
            request,
            "error",
            f"Falta una dependencia de ingesta ({exc.name}). Instálala con: "
            f'pip install -e ".[ingest]"',
        )

    respuesta = _aviso(
        request,
        "ok",
        f"«{resultado.titulo}» quedó ingerido: {resultado.total_fragmentos} "
        f"fragmentos sobre {resultado.pagina_maxima} página(s), "
        f"{resultado.palabras_totales} palabras. Todos están pendientes de "
        f"revisión: ninguno llegará a una cápsula hasta que lo valides.",
    )
    # La bandeja se recarga sola en vez de pedirle al docente que refresque.
    respuesta.headers["HX-Trigger"] = "fragmentos-actualizados"
    return respuesta


@router.post("/curation/{id_fragmento}/approve", response_class=HTMLResponse)
def approve_fragment(
    request: Request,
    id_fragmento: int,
    id_objetivo: int | None = Form(default=None),
    db: Session = Depends(get_db),
):
    """Habilita el fragmento para el retriever, con su objetivo asignado."""
    try:
        fragmento = curation.validar(db, id_fragmento, id_objetivo=id_objetivo)
    except curation.ErrorCuracion as exc:
        return _fila_con_error(request, db, id_fragmento, str(exc))

    return _fila(request, db, fragmento.id_fragmento)


@router.post("/curation/{id_fragmento}/reject", response_class=HTMLResponse)
def reject_fragment(request: Request, id_fragmento: int, db: Session = Depends(get_db)):
    """Marca el fragmento como no utilizable. No lo borra.

    El cap. 12 exige trazabilidad del proceso de curación: saber qué se descartó
    (y que se revisó) es parte de eso.
    """
    try:
        fragmento = curation.descartar(db, id_fragmento)
    except curation.ErrorCuracion as exc:
        return _fila_con_error(request, db, id_fragmento, str(exc))

    return _fila(request, db, fragmento.id_fragmento)


# --- Auxiliares ---------------------------------------------------------------


def _contexto_panel(db: Session, id_documento: int | None) -> dict:
    fragmentos = curation.listar_fragmentos(
        db, id_documento=id_documento, estado="pendiente", limite=LIMITE_BANDEJA
    )
    return {
        "fragmentos": [_a_fila(f) for f in fragmentos],
        "documentos": _documentos_con_avance(db),
        "objetivos": listar_objetivos(db=db),
        "id_documento": id_documento,
    }


def _documentos_con_avance(db: Session) -> list[dict]:
    """Cada documento con su conteo por estado, para ver cuánto falta curar."""
    filas = []
    for documento in listar_documentos(db=db):
        conteo = curation.resumen_documento(db, documento.id_documento)
        filas.append({"documento": documento, "conteo": conteo})
    return filas


def _a_fila(fragmento) -> dict:
    """Un fragmento tal como lo necesita la plantilla de la bandeja."""
    texto = fragmento.contenido_texto or ""
    return {
        "id": fragmento.id_fragmento,
        "documento": fragmento.documento.titulo,
        "pagina_inicio": fragmento.pagina_inicio,
        "pagina_fin": fragmento.pagina_fin,
        "tipo": fragmento.tipo_fragmento,
        "texto": texto,
        "palabras": len(texto.split()),
        "estado": fragmento.estado_validacion,
        "id_objetivo": fragmento.id_objetivo,
    }


def _fila(
    request: Request, db: Session, id_fragmento: int, error: str | None = None
) -> HTMLResponse:
    fragmentos = curation.listar_fragmentos(db, limite=LIMITE_BANDEJA * 10)
    actual = next((f for f in fragmentos if f.id_fragmento == id_fragmento), None)
    if actual is None:
        return HTMLResponse("")
    return templates.TemplateResponse(
        request=request,
        name="teacher/_fila.html",
        context={
            "fragmento": _a_fila(actual),
            "objetivos": listar_objetivos(db=db),
            "error": error,
        },
    )


def _fila_con_error(
    request: Request, db: Session, id_fragmento: int, mensaje: str
) -> HTMLResponse:
    return _fila(request, db, id_fragmento, error=mensaje)


def _aviso(request: Request, estado: str, mensaje: str) -> HTMLResponse:
    """El texto se escapa vía plantilla: incluye el nombre del archivo subido."""
    return templates.TemplateResponse(
        request=request,
        name="teacher/_aviso.html",
        context={"estado": estado, "mensaje": mensaje},
    )


def _explicar_ingesta(exc: HTTPException) -> str:
    if exc.status_code == 409:
        return (
            f"{exc.detail} La deduplicación es por contenido, no por nombre: "
            f"subir el mismo archivo con otro nombre no lo duplica."
        )
    if exc.status_code == 415:
        return f"{exc.detail}"
    if exc.status_code == 422:
        return (
            f"{exc.detail} Suele pasar con PDF escaneados (imágenes sin capa de "
            f"texto): no sirven para un RAG textual."
        )
    return str(exc.detail)
