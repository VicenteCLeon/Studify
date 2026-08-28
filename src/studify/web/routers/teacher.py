"""Panel de curación del docente (Fase 4).

Es la única puerta por la que el material institucional entra al sistema: se
sube un PDF/PPTX, la ingesta lo fragmenta y el docente decide fragmento a
fragmento qué queda disponible para el retriever. Ningún fragmento sin validar
llega jamás al prompt (cap. 12/13), así que esta pantalla no es administrativa:
es la barrera de seguridad del proyecto.

Por eso mismo todo este router exige sesión de docente (`web/routers/auth.py`):
la dependencia está declarada en el `APIRouter`, de modo que cubre también las
vistas que se agreguen más adelante.

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
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from studify.analytics import panel, simulador
from studify.api.routers.capsules import ClienteLLM, get_cliente_llm
from studify.api.routers.knowledge import (
    crear_objetivo,
    listar_documentos,
    listar_objetivos,
    subir_documento,
)
from studify.api.schemas_knowledge import ObjetivoIn
from studify.db.models import (
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.db.session import get_db
from studify.knowledge import curation, tagger
from studify.rag import retriever
from studify.vark.scoring import CANALES
from studify.web import textos
from studify.web.deps import templates
from studify.web.routers import auth
from studify.web.routers.student import _preparar_bloques

# El guardián va acá, en el router, y no en cada handler: cualquier vista que se
# agregue después al panel queda cerrada por el solo hecho de colgar de este
# router, sin depender de que alguien se acuerde de repetir la dependencia. El
# login vive en `web/routers/auth.py`, que es el único `/teacher/*` abierto.
router = APIRouter(
    prefix="/teacher",
    tags=["web-teacher"],
    dependencies=[Depends(auth.requiere_docente)],
)

# Cuántos fragmentos muestra la bandeja de una vez. La curación es trabajo
# humano y el techo del plan es de 40–60 fragmentos por unidad, así que una
# página basta para revisar un documento completo sin paginar.
LIMITE_BANDEJA = 60

# Desde cuántos fragmentos recuperables se considera cubierto un objetivo. Es la
# mitad de lo que el retriever pide como contexto (`LIMITE_POR_DEFECTO`): por
# debajo de eso la cápsula se genera igual, pero apoyada en una porción del
# apunte demasiado chica como para fundamentar 150–300 palabras sin repetirse.
MINIMO_RECOMENDADO = retriever.LIMITE_POR_DEFECTO // 2


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


@router.post("/curation/objetivos", response_class=HTMLResponse)
def crear_objetivo_web(
    request: Request,
    codigo_objetivo: str = Form(...),
    asignatura: str = Form(...),
    unidad: str = Form(...),
    tema: str = Form(...),
    descripcion: str = Form(default=""),
    nivel_taxonomico: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Alta de un objetivo del catálogo desde el panel, sin pasar por consola.

    `scripts/cargar_objetivos.py` sigue existiendo y es la vía correcta para
    sembrar un plan de estudios completo de una vez —nadie escribe 60 objetivos
    en un formulario—, pero obligar al docente a abrir una terminal para agregar
    **un** tema convertía una tarea de treinta segundos en un trámite técnico.
    Ambas vías escriben por el mismo camino: `crear_objetivo`, el handler de
    `POST /api/objetivos`, con su control de código duplicado incluido.
    """
    try:
        payload = ObjetivoIn(
            codigo_objetivo=codigo_objetivo.strip(),
            asignatura=asignatura.strip(),
            unidad=unidad.strip(),
            tema=tema.strip(),
            descripcion=descripcion.strip() or None,
            nivel_taxonomico=nivel_taxonomico.strip() or None,
        )
    except ValidationError as exc:
        # Los largos de la tabla 17.5 los valida el propio contrato Pydantic.
        # Sus mensajes vienen en inglés y esta pantalla es del docente, así que
        # se traducen igual que en `generation/validator.py`. Es una ruta
        # defensiva —el formulario ya trae `maxlength` y `required`—, pero se
        # alcanza desde `curl` o si alguien quita un atributo de la plantilla.
        return _aviso(request, "error", f"Datos inválidos — {_explicar_campos(exc)}")

    try:
        objetivo = crear_objetivo(payload=payload, db=db)
    except HTTPException as exc:
        return _aviso(request, "error", str(exc.detail))

    respuesta = _aviso(
        request,
        "ok",
        f"Objetivo «{objetivo.codigo_objetivo} — {objetivo.tema}» creado. "
        f"Ya puedes asignarle fragmentos en la bandeja de revisión.",
    )
    # La bandeja recarga sus selectores para que el objetivo recién creado
    # aparezca sin tener que refrescar la página a mano.
    respuesta.headers["HX-Trigger"] = "fragmentos-actualizados"
    return respuesta


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


@router.get("/analytics", response_class=HTMLResponse)
def get_analytics(request: Request, db: Session = Depends(get_db)):
    """Panel de analíticas del curso (Fase 5)."""
    
    # 1. Cobertura Curricular
    cobertura = panel.cobertura_curricular(db)

    # 2. Historial de Cápsulas (últimas 50)
    capsulas = db.scalars(
        select(MicrocapsulaGenerada)
        .order_by(MicrocapsulaGenerada.fecha_generacion.desc())
        .limit(50)
    ).all()

    # 3. Rendimiento en la actividad de cierre, por objetivo.
    quizzes = panel.rendimiento_actividades(db)

    # 5. Estadísticas VARK (Promedios generales)
    vark = panel.promedio_vark_cohorte(db)

    return templates.TemplateResponse(
        request=request,
        name="teacher/analytics.html",
        context={
            "cobertura": cobertura,
            "sin_clasificar": panel.fragmentos_sin_clasificar(db),
            "capsulas": capsulas,
            "quizzes": quizzes,
            "vark_total": vark.total if vark else 0,
            "vark_barras": panel.barras_cohorte(vark),
        }
    )


@router.get("/simulator", response_class=HTMLResponse)
def get_simulator(request: Request, db: Session = Depends(get_db)):
    """Vista del simulador: elegir un tema y un perfil VARK."""
    return templates.TemplateResponse(
        request=request,
        name="teacher/simulator.html",
        context={
            "objetivos": listar_objetivos(db=db),
        }
    )


@router.post("/simulator/generate", response_class=HTMLResponse)
def post_simulator_generate(
    request: Request,
    id_objetivo: int = Form(...),
    canal: str = Form(...),
    db: Session = Depends(get_db),
    cliente: ClienteLLM | None = Depends(get_cliente_llm),
):
    """Genera una cápsula al vuelo para el perfil simulado."""
    if not cliente:
        return _aviso(request, "error", "Falta LLM_API_KEY para simular.")

    objetivo = db.get(ObjetivoAprendizaje, id_objetivo)
    if not objetivo:
        return _aviso(request, "error", "Objetivo no encontrado.")

    # Un canal desconocido dejaría el vector en 0/0/0/0, que rompe el invariante
    # de `PerfilVark` (suma 100) y que `derivar()` interpreta como multimodal con
    # primario V: se generaría una cápsula para un perfil que no existe, sin
    # error visible. Se corta acá.
    canal_vark = canal.strip().upper()
    if canal_vark not in CANALES:
        return _aviso(
            request,
            "error",
            f"«{canal}» no es un canal VARK: elige Visual, Auditivo, "
            f"Lectura/Escritura o Kinestésico.",
        )

    columna = _generar_capsula_pura(db, objetivo, canal_vark, cliente)
    if columna["error"]:
        return _aviso(request, "error", columna["error"])

    capsula = columna["capsula"]

    # El mismo partial que ve el estudiante, no la página completa: HTMX lo
    # inyecta dentro del simulador, que ya tiene cabecera y `<head>` propios.
    #
    # Acá la actividad viaja **entera**, con `indice_correcta` y
    # `retroalimentacion`. Es lo contrario de lo que hace `student.py` a
    # propósito: el estudiante no puede ver la clave en el código fuente, y el
    # docente vino justamente a revisarla. La cápsula simulada además no se
    # persiste, así que no hay nada que responder ni que corregir.
    return templates.TemplateResponse(
        request=request,
        name="student/_capsula.html",
        context={
            "objetivo": objetivo,
            "capsula": capsula,
            "bloques": columna["bloques"],
            "actividad": capsula.actividad,
            "es_simulacion": True,
            "perfil_simulado": textos.NOMBRE_CANAL[canal_vark],
        },
    )


@router.post("/simulator/compare", response_class=HTMLResponse)
def post_simulator_compare(
    request: Request,
    id_objetivo: int = Form(...),
    db: Session = Depends(get_db),
    cliente: ClienteLLM | None = Depends(get_cliente_llm),
):
    """Genera las cuatro cápsulas puras (V, A, R, K) del mismo objetivo, lado a lado.

    Cierra el pendiente n.º 10 de AVANCE.md §6, que es literalmente el criterio
    de término de la Fase 3 en PLAN_DESARROLLO.md §4: «comparar visualmente
    cuatro cápsulas del mismo objetivo generadas para V, A, R y K: si no se
    distinguen entre sí, la adaptación no está funcionando». Antes solo se
    podía generar una cápsula a la vez (`/simulator/generate`) y compararlas de
    memoria entre pestañas.

    **Cada canal se resuelve por separado y un fallo no aborta a los otros
    tres.** Cuatro llamadas al LLM son cuatro oportunidades de que una falle
    (timeout, cápsula que no pasa el validador en los reintentos); si una
    columna revienta, las otras tres igual sirven para juzgar la adaptación —
    y son exactamente las que ya se pagaron.
    """
    if not cliente:
        return _aviso(request, "error", "Falta LLM_API_KEY para simular.")

    objetivo = db.get(ObjetivoAprendizaje, id_objetivo)
    if not objetivo:
        return _aviso(request, "error", "Objetivo no encontrado.")

    columnas = [_generar_capsula_pura(db, objetivo, canal, cliente) for canal in CANALES]

    return templates.TemplateResponse(
        request=request,
        name="teacher/_comparacion.html",
        context={"objetivo": objetivo, "columnas": columnas},
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


@router.post("/curation/tag", response_class=HTMLResponse)
def tag_pending_fragments(
    request: Request,
    id_documento: int | None = Form(default=None),
    db: Session = Depends(get_db),
    cliente: ClienteLLM | None = Depends(get_cliente_llm),
):
    """Sugiere objetivo y etiqueta temática para los fragmentos pendientes sin objetivo.

    No valida nada por sí solo (`knowledge.tagger` no toca `id_objetivo` ni
    `estado_validacion`): deja la propuesta en `metadatos_json`, y es
    `_a_fila`/`_fila.html` quien la usa para preseleccionar el selector de
    objetivo en la bandeja. El curador sigue teniendo que pulsar «Validar».
    """
    if not cliente:
        return _aviso(request, "error", "Falta LLM_API_KEY para sugerir con IA.")

    sugerencias = tagger.etiquetar_pendientes(
        db, cliente=cliente, id_documento=id_documento, limite=LIMITE_BANDEJA
    )

    if not sugerencias:
        respuesta = _aviso(
            request,
            "ok",
            "No hay fragmentos pendientes sin objetivo para sugerir"
            + (" en este documento." if id_documento else "."),
        )
    else:
        exitosas = [s for s in sugerencias if s.ok and s.id_objetivo is not None]
        sin_propuesta = [s for s in sugerencias if s.ok and s.id_objetivo is None]
        fallidas = [s for s in sugerencias if not s.ok]
        partes = [f"{len(exitosas)} de {len(sugerencias)} fragmentos con objetivo sugerido"]
        if sin_propuesta:
            partes.append(f"{len(sin_propuesta)} sin un objetivo claro (revísalos a mano)")
        if fallidas:
            partes.append(f"{len(fallidas)} fallaron: {fallidas[0].error}")
        respuesta = _aviso(
            request,
            "ok" if exitosas else "error",
            "; ".join(partes)
            + ". Revisa la bandeja: los campos ya vienen prellenados, pero cada "
            "fragmento se sigue validando a mano.",
        )

    # Misma recarga que tras una ingesta: la bandeja se refresca sola con las
    # sugerencias nuevas, sin pedirle al docente que recargue la página.
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


# `_perfil_puro`, `_generar_capsula_pura`, `_columna_error`,
# `_cobertura_curricular`, `_fragmentos_sin_clasificar`, `_rendimiento_actividades`
# y `_barras_cohorte` se movieron a `studify.analytics` en la migración a React
# (27-ago-2026): eran ~240 líneas de cálculo que solo se podían alcanzar
# renderizando una plantilla. Ahora las consume tanto esta vista como
# `api/routers/analytics.py`, que es lo único que garantiza que el panel Jinja y
# el de React no se contradigan mientras convivan.


def _generar_capsula_pura(
    db: Session,
    objetivo: ObjetivoAprendizaje,
    canal_vark: str,
    cliente: ClienteLLM,
) -> dict:
    """Adapta la columna del dominio a lo que espera la plantilla.

    El dominio devuelve la `Microcapsula` cruda; acá se le agregan los bloques
    ya normalizados, que es una decisión de presentación y por eso no vive allá.
    """
    columna = simulador.generar_capsula_pura(db, objetivo, canal_vark, cliente)
    columna["bloques"] = (
        _preparar_bloques(columna["capsula"].bloques_legibles())
        if columna["capsula"] is not None
        else None
    )
    return columna


def _columna_error(canal_vark: str, mensaje: str) -> dict:
    columna = simulador.columna_error(canal_vark, mensaje)
    columna["bloques"] = None
    return columna


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
    """Un fragmento tal como lo necesita la plantilla de la bandeja.

    La sugerencia del tagger solo se expone mientras el fragmento sigue sin
    objetivo asignado: una vez que alguien lo valida, `id_objetivo` deja de
    ser `None` y esta función ya no la incluye — no hace falta, la plantilla
    solo la usa para preseleccionar un `<select>` que a esa altura ni se
    muestra.
    """
    texto = fragmento.contenido_texto or ""
    sugerencia = (
        (fragmento.metadatos_json or {}).get("sugerencia_llm")
        if fragmento.id_objetivo is None
        else None
    ) or {}
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
        "sugerido_id_objetivo": sugerencia.get("id_objetivo"),
        "sugerido_etiqueta": sugerencia.get("etiqueta_tematica"),
        "sugerido_motivo": sugerencia.get("motivo"),
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


def _explicar_campos(exc: ValidationError) -> str:
    """Errores de Pydantic → una frase en español, campo por campo."""
    partes: list[str] = []
    for error in exc.errors():
        campo = ".".join(str(p) for p in error["loc"]) or "(formulario)"
        tipo = error["type"]
        if tipo == "string_too_long":
            limite = error.get("ctx", {}).get("max_length", "?")
            detalle = f"supera el máximo de {limite} caracteres"
        elif tipo in ("string_too_short", "missing"):
            detalle = "es obligatorio"
        elif tipo == "value_error":
            detalle = error["msg"].removeprefix("Value error, ")
        else:
            detalle = error["msg"]
        partes.append(f"{campo}: {detalle}")
    return "; ".join(partes)


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
