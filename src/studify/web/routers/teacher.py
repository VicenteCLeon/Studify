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

from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from studify.api.routers.capsules import ClienteLLM, get_cliente_llm
from studify.api.routers.knowledge import (
    crear_objetivo,
    listar_documentos,
    listar_objetivos,
    subir_documento,
)
from studify.api.schemas_knowledge import ObjetivoIn
from studify.config import get_settings
from studify.db.models import (
    DiagnosticoVark,
    Fragmento,
    InteraccionQuiz,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.db.session import get_db
from studify.generation.generator import ErrorGeneracion, generar
from studify.knowledge import curation
from studify.rag import orchestrator, retriever
from studify.vark.rules import aplicar_reglas
from studify.vark.scoring import CANALES, PerfilVark
from studify.web import textos
from studify.web.deps import templates
from studify.web.routers.student import _preparar_bloques

router = APIRouter(prefix="/teacher", tags=["web-teacher"])

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
    cobertura = _cobertura_curricular(db)

    # 2. Historial de Cápsulas (últimas 50)
    capsulas = db.scalars(
        select(MicrocapsulaGenerada)
        .order_by(MicrocapsulaGenerada.fecha_generacion.desc())
        .limit(50)
    ).all()

    # 3. Rendimiento en la actividad de cierre, por objetivo.
    quizzes = _rendimiento_actividades(db)

    # 5. Estadísticas VARK (Promedios generales)
    stmt_vark = select(
        func.avg(DiagnosticoVark.porcentaje_v).label("v"),
        func.avg(DiagnosticoVark.porcentaje_a).label("a"),
        func.avg(DiagnosticoVark.porcentaje_r).label("r"),
        func.avg(DiagnosticoVark.porcentaje_k).label("k"),
        func.count(DiagnosticoVark.id_diagnostico).label("total")
    )
    vark = db.execute(stmt_vark).first()

    return templates.TemplateResponse(
        request=request,
        name="teacher/analytics.html",
        context={
            "cobertura": cobertura,
            "sin_clasificar": _fragmentos_sin_clasificar(db),
            "capsulas": capsulas,
            "quizzes": quizzes,
            "vark_total": vark.total if vark else 0,
            "vark_barras": _barras_cohorte(vark),
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

    # Perfil simulado puro: 100% en el canal elegido, 0% en los otros tres.
    porcentajes = {c: Decimal(100 if c == canal_vark else 0) for c in CANALES}
    perfil = PerfilVark(
        v=porcentajes["V"], a=porcentajes["A"], r=porcentajes["R"], k=porcentajes["K"]
    )
    config = aplicar_reglas(perfil)


    fragmentos = retriever.recuperar(
        db,
        id_objetivo=id_objetivo,
        canal_primario=config.jerarquia.canal_primario,
    )
    
    try:
        prompt = orchestrator.construir(
            objetivo=objetivo,
            fragmentos=fragmentos,
            config=config,
            modelo=get_settings().llm_model,
        )
        resultado = generar(prompt, cliente=cliente)
    except orchestrator.ErrorPrompt as exc:
        return _aviso(request, "error", f"Error de material: {exc}")
    except ErrorGeneracion as exc:
        return _aviso(request, "error", f"Falló la generación: {exc}")

    capsula = resultado.capsula

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
            "bloques": _preparar_bloques(capsula.bloques_legibles()),
            "actividad": capsula.actividad,
            "es_simulacion": True,
            "perfil_simulado": textos.NOMBRE_CANAL[canal_vark],
        },
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


def _cobertura_curricular(db: Session) -> list[dict]:
    """Qué temas puede sostener el sistema hoy y con qué calidad de adaptación.

    Dos correcciones sobre la lectura ingenua de «tiene fragmentos aprobados»:

    1. **Cuenta lo que el retriever puede recuperar**, no lo que está validado.
       El inventario sale de `retriever.inventario_por_objetivo`, que aplica los
       mismos filtros que la recuperación real —incluido el del documento
       rechazado después de curar—, así que la pantalla no puede pintar de verde
       material que el motor ignora.

    2. **Un fragmento no es cobertura.** El retriever pide hasta
       `LIMITE_POR_DEFECTO` fragmentos para fundamentar una cápsula; con uno
       solo la genera igual, pero apoyada en una sola frase del apunte. Por eso
       hay un tramo intermedio explícito en vez de un sí/no.

    La columna por canal es el gap que el conteo total esconde: un objetivo con
    ocho fragmentos de texto está completo para los perfiles A y R, y deja al
    perfil V leyendo lo mismo que ellos.
    """
    inventario = retriever.inventario_por_objetivo(db)
    objetivos = db.scalars(
        select(ObjetivoAprendizaje).order_by(ObjetivoAprendizaje.codigo_objetivo)
    ).all()

    filas = []
    for objetivo in objetivos:
        tipos = inventario.get(objetivo.id_objetivo, {})
        total = sum(tipos.values())
        filas.append(
            {
                "objetivo": objetivo,
                "total": total,
                "tipos": sorted(tipos.items(), key=lambda kv: (-kv[1], kv[0])),
                "canales": [
                    {
                        "canal": canal,
                        "nombre": textos.NOMBRE_CANAL[canal],
                        "cantidad": cantidad,
                        # Con material, pero sin nada del tipo que ese canal
                        # aprovecha: la cápsula sale, la adaptación no.
                        "degradado": total > 0 and cantidad == 0,
                    }
                    for canal, cantidad in retriever.tipos_preferidos_disponibles(
                        tipos
                    ).items()
                ],
                "estado": (
                    "sin_material"
                    if total == 0
                    else "escaso"
                    if total < MINIMO_RECOMENDADO
                    else "cubierto"
                ),
            }
        )
    return filas


def _fragmentos_sin_clasificar(db: Session) -> int:
    """Fragmentos ingeridos que siguen esperando revisión.

    Se cuenta en global y no por objetivo a propósito: el objetivo se asigna
    **al validar** (`curation.validar`), así que un fragmento pendiente todavía
    no pertenece a ningún tema. Un conteo por objetivo daría cero en todas las
    filas y haría parecer que no queda trabajo de curación pendiente.
    """
    return db.scalar(
        select(func.count())
        .select_from(Fragmento)
        .where(Fragmento.estado_validacion == "pendiente")
    ) or 0


def _rendimiento_actividades(db: Session) -> list[dict]:
    """Cómo le fue al curso en la actividad de cierre, por objetivo.

    **El porcentaje se calcula solo sobre el primer intento.** El visor deja el
    formulario en pantalla después de la retroalimentación, así que quien falla
    puede cambiar la alternativa y reenviar; contando todos los intentos por
    igual, el curso mejoraría sus cifras a fuerza de insistir y el número
    dejaría de decir nada sobre lo que se entendió. Los reintentos se informan
    aparte porque son una señal por derecho propio: mucho reintento en un tema
    es material que no se está entendiendo a la primera.

    Las actividades `intentalo_tu` no tienen respuesta corregible (`es_correcta`
    nula) y quedan fuera del porcentaje, pero se cuentan igual: sin eso, un
    objetivo trabajado solo por perfiles K se vería idéntico a uno que nadie
    abrió nunca.

    Va en una función y no dentro del endpoint para poder comprobar la métrica
    contra la base sin levantar una plantilla de por medio.
    """
    primero = InteraccionQuiz.numero_intento == 1
    corregible = InteraccionQuiz.es_correcta.is_not(None)
    stmt = (
        select(
            ObjetivoAprendizaje.tema,
            func.count(func.distinct(MicrocapsulaGenerada.id_estudiante)).label(
                "alumnos"
            ),
            func.count().filter(primero & corregible).label("primeras"),
            func.count().filter(primero & InteraccionQuiz.es_correcta.is_(True)).label(
                "aciertos"
            ),
            func.count().filter(primero & ~corregible).label("abiertas"),
            func.count().filter(InteraccionQuiz.numero_intento > 1).label("reintentos"),
        )
        .select_from(InteraccionQuiz)
        .join(
            MicrocapsulaGenerada,
            InteraccionQuiz.id_capsula == MicrocapsulaGenerada.id_capsula,
        )
        .join(
            ObjetivoAprendizaje,
            MicrocapsulaGenerada.id_objetivo == ObjetivoAprendizaje.id_objetivo,
        )
        .group_by(ObjetivoAprendizaje.id_objetivo)
        .order_by(ObjetivoAprendizaje.codigo_objetivo)
    )
    return [
        {
            "tema": row.tema,
            "alumnos": row.alumnos,
            "primeras": row.primeras,
            "aciertos": row.aciertos,
            "abiertas": row.abiertas,
            "reintentos": row.reintentos,
            # None y 0 no son lo mismo: sin quiz corregible no hay porcentaje
            # que mostrar, y un 0% diría que todos fallaron.
            "porcentaje": (
                round(row.aciertos * 100 / row.primeras, 1) if row.primeras else None
            ),
        }
        for row in db.execute(stmt).all()
    ]


def _barras_cohorte(vark) -> list[dict]:
    """El promedio VARK del curso, listo para pintar con la misma escala que el
    perfil individual del estudiante.

    Se arma acá y no en la plantilla por la misma razón que `_barras` en
    `student.py`: el nombre y el color de cada canal ya existen en `textos`, y
    repetirlos en HTML hace que el gráfico del docente y el del estudiante
    deriven a colores distintos para el mismo canal.
    """
    if vark is None or not vark.total:
        return []
    valores = {"V": vark.v, "A": vark.a, "R": vark.r, "K": vark.k}
    ordenados = sorted(valores.items(), key=lambda kv: (-kv[1], "VARK".index(kv[0])))
    return [
        {
            "nombre": textos.NOMBRE_CANAL[canal],
            "color": textos.COLOR_CANAL[canal],
            "ancho": f"{porcentaje:.2f}",
            "texto": f"{porcentaje:.1f}".replace(".", ","),
        }
        for canal, porcentaje in ordenados
    ]


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
