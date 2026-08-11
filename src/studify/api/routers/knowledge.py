"""Endpoints de la base de conocimiento: ingesta, curación y catálogo (Fase 2).

Cubre el ciclo completo del material institucional: subir un documento oficial,
revisarlo fragmento a fragmento, y exponer al estudiante solo los temas sobre
los que efectivamente hay material validado.
"""

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from studify.api.schemas_knowledge import (
    AsignarObjetivoIn,
    AsignaturaDisponible,
    DocumentoOut,
    EditarFragmentoIn,
    FragmentoEnCuracion,
    FragmentoOut,
    FragmentoRecuperadoOut,
    IngestaOut,
    ObjetivoIn,
    ObjetivoOut,
    ResumenCuracionOut,
    TemaDisponible,
    UnidadDisponible,
    ValidarFragmentoIn,
)
from studify.db.models import (
    DocumentoFuente,
    Fragmento,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.db.session import get_db
from studify.knowledge import curation
from studify.knowledge.extract import FORMATOS_SOPORTADOS, FormatoNoSoportado
from studify.knowledge.ingest import (
    DocumentoDuplicado,
    DocumentoSinTexto,
    ingerir,
)
from studify.rag.retriever import contar_disponibles, recuperar

router = APIRouter(prefix="/api", tags=["base de conocimiento"])


# --- Catálogo curricular ------------------------------------------------------


@router.post(
    "/objetivos",
    response_model=ObjetivoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Da de alta un objetivo de aprendizaje",
)
def crear_objetivo(payload: ObjetivoIn, db: Session = Depends(get_db)) -> ObjetivoAprendizaje:
    """El catálogo se carga a mano: es información curricular, no se infiere."""
    duplicado = db.scalar(
        select(ObjetivoAprendizaje).where(
            ObjetivoAprendizaje.codigo_objetivo == payload.codigo_objetivo
        )
    )
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"ya existe un objetivo con código '{payload.codigo_objetivo}'",
        )

    objetivo = ObjetivoAprendizaje(**payload.model_dump(), estado="activo")
    db.add(objetivo)
    db.commit()
    return objetivo


@router.get(
    "/objetivos",
    response_model=list[ObjetivoOut],
    summary="Lista los objetivos del catálogo",
)
def listar_objetivos(
    asignatura: str | None = None,
    unidad: str | None = None,
    db: Session = Depends(get_db),
) -> list[ObjetivoAprendizaje]:
    stmt = select(ObjetivoAprendizaje).order_by(
        ObjetivoAprendizaje.asignatura,
        ObjetivoAprendizaje.unidad,
        ObjetivoAprendizaje.codigo_objetivo,
    )
    if asignatura:
        stmt = stmt.where(ObjetivoAprendizaje.asignatura == asignatura)
    if unidad:
        stmt = stmt.where(ObjetivoAprendizaje.unidad == unidad)
    return list(db.scalars(stmt).all())


@router.get(
    "/catalogo",
    response_model=list[AsignaturaDisponible],
    summary="Catálogo en cascada asignatura → unidad → tema, para el estudiante",
)
def catalogo(
    solo_con_material: bool = Query(
        default=True,
        description=(
            "Oculta los objetivos sin fragmentos validados. Un tema sin material "
            "no puede producir una cápsula fundamentada."
        ),
    ),
    db: Session = Depends(get_db),
) -> list[AsignaturaDisponible]:
    """Cierra la decisión pendiente n.º 4 del plan: cómo elige el tema el estudiante."""
    objetivos = db.scalars(
        select(ObjetivoAprendizaje)
        .where(ObjetivoAprendizaje.estado == "activo")
        .order_by(
            ObjetivoAprendizaje.asignatura,
            ObjetivoAprendizaje.unidad,
            ObjetivoAprendizaje.codigo_objetivo,
        )
    ).all()

    arbol: dict[str, dict[str, list[TemaDisponible]]] = {}
    for obj in objetivos:
        disponibles = contar_disponibles(db, obj.id_objetivo)
        if solo_con_material and disponibles == 0:
            continue
        arbol.setdefault(obj.asignatura, {}).setdefault(obj.unidad, []).append(
            TemaDisponible(
                id_objetivo=obj.id_objetivo,
                codigo_objetivo=obj.codigo_objetivo,
                tema=obj.tema,
                descripcion=obj.descripcion,
                fragmentos_disponibles=disponibles,
            )
        )

    return [
        AsignaturaDisponible(
            asignatura=asignatura,
            unidades=[
                UnidadDisponible(unidad=unidad, temas=temas)
                for unidad, temas in unidades.items()
            ],
        )
        for asignatura, unidades in arbol.items()
    ]


# --- Documentos ---------------------------------------------------------------


@router.post(
    "/documentos",
    response_model=IngestaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Sube un documento oficial y lo fragmenta",
)
def subir_documento(
    archivo: UploadFile = File(...),
    titulo: str | None = None,
    asignatura: str | None = None,
    tipo_documento: str | None = None,
    origen: str | None = None,
    version: str | None = None,
    db: Session = Depends(get_db),
) -> IngestaOut:
    """Ingiere un PDF/PPTX. Todo queda pendiente de curación (cap. 12)."""
    nombre = archivo.filename or "documento"
    sufijo = Path(nombre).suffix.lower()
    if sufijo not in FORMATOS_SOPORTADOS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"formato '{sufijo or 'desconocido'}' no soportado. "
                f"Formatos válidos: {', '.join(FORMATOS_SOPORTADOS)}"
            ),
        )

    # El archivo subido llega como stream; se materializa en un temporal porque
    # los extractores trabajan sobre rutas. `ingerir` deja después su propia
    # copia estable en el almacén.
    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp) / Path(nombre).name
        with destino.open("wb") as fh:
            shutil.copyfileobj(archivo.file, fh)

        try:
            resultado = ingerir(
                db,
                destino,
                titulo=titulo or Path(nombre).stem,
                asignatura=asignatura,
                tipo_documento=tipo_documento,
                origen=origen,
                version=version,
            )
        except DocumentoDuplicado as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except DocumentoSinTexto as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        except FormatoNoSoportado as exc:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
            ) from exc

    return IngestaOut(
        id_documento=resultado.id_documento,
        titulo=resultado.titulo,
        total_fragmentos=resultado.total_fragmentos,
        pagina_maxima=resultado.pagina_maxima,
        palabras_totales=resultado.palabras_totales,
    )


@router.get("/documentos", response_model=list[DocumentoOut], summary="Lista los documentos")
def listar_documentos(db: Session = Depends(get_db)) -> list[DocumentoFuente]:
    return list(
        db.scalars(
            select(DocumentoFuente).order_by(DocumentoFuente.fecha_carga.desc())
        ).all()
    )


@router.delete(
    "/documentos/{id_documento}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina un documento y sus fragmentos",
)
def eliminar_documento(id_documento: int, db: Session = Depends(get_db)) -> None:
    """Deshace una carga equivocada, salvo que ya haya fundamentado una cápsula.

    Se rechaza el borrado si algún fragmento del documento figura como fuente de
    una microcápsula ya generada. La FK de `microcapsula_generada` es
    `ON DELETE SET NULL`, así que borrar igual no daría error: dejaría cápsulas
    con la fuente en blanco, rompiendo en silencio la auditabilidad que exige el
    cap. 13. Para retirar material ya usado está `estado_curacion = 'rechazado'`,
    que lo saca del retriever conservando la trazabilidad histórica.
    """
    documento = db.get(DocumentoFuente, id_documento)
    if documento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no existe el documento {id_documento}",
        )

    capsulas = db.scalar(
        select(func.count())
        .select_from(MicrocapsulaGenerada)
        .join(
            Fragmento,
            MicrocapsulaGenerada.id_fragmento_fuente == Fragmento.id_fragmento,
        )
        .where(Fragmento.id_documento == id_documento)
    )
    if capsulas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"el documento {id_documento} fundamenta {capsulas} microcápsula(s) "
                f"ya generada(s); borrarlo dejaría esas cápsulas sin fuente. "
                f"Use estado_curacion='rechazado' para retirarlo del retriever."
            ),
        )

    db.delete(documento)
    db.commit()


@router.get(
    "/documentos/{id_documento}/resumen",
    response_model=ResumenCuracionOut,
    summary="Avance de la curación de un documento",
)
def resumen_curacion(id_documento: int, db: Session = Depends(get_db)) -> ResumenCuracionOut:
    if db.get(DocumentoFuente, id_documento) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no existe el documento {id_documento}",
        )
    conteo = curation.resumen_documento(db, id_documento)
    return ResumenCuracionOut(id_documento=id_documento, **conteo)


# --- Curación de fragmentos ---------------------------------------------------


def _a_curacion(fragmento: Fragmento) -> FragmentoEnCuracion:
    texto = fragmento.contenido_texto or ""
    return FragmentoEnCuracion(
        id_fragmento=fragmento.id_fragmento,
        id_documento=fragmento.id_documento,
        id_objetivo=fragmento.id_objetivo,
        numero_fragmento=fragmento.numero_fragmento,
        tipo_fragmento=fragmento.tipo_fragmento,
        contenido_texto=texto,
        pagina_inicio=fragmento.pagina_inicio,
        pagina_fin=fragmento.pagina_fin,
        etiqueta_tematica=fragmento.etiqueta_tematica,
        estado_validacion=fragmento.estado_validacion,
        documento_titulo=fragmento.documento.titulo,
        objetivo_codigo=fragmento.objetivo.codigo_objetivo if fragmento.objetivo else None,
        palabras=len(texto.split()),
    )


@router.get(
    "/fragmentos",
    response_model=list[FragmentoEnCuracion],
    summary="Bandeja de curación",
)
def listar_fragmentos(
    id_documento: int | None = None,
    estado: str | None = Query(default=None, pattern="^(pendiente|validado|descartado)$"),
    id_objetivo: int | None = None,
    limite: int = Query(default=50, ge=1, le=200),
    desplazamiento: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[FragmentoEnCuracion]:
    fragmentos = curation.listar_fragmentos(
        db,
        id_documento=id_documento,
        estado=estado,
        id_objetivo=id_objetivo,
        limite=limite,
        desplazamiento=desplazamiento,
    )
    return [_a_curacion(f) for f in fragmentos]


def _ejecutar(operacion) -> Fragmento:
    """Traduce los errores de curación a 4xx con el mensaje del servicio."""
    try:
        return operacion()
    except curation.ErrorCuracion as exc:
        mensaje = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if mensaje.startswith("no existe")
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=codigo, detail=mensaje) from exc


@router.post(
    "/fragmentos/{id_fragmento}/validar",
    response_model=FragmentoOut,
    summary="Habilita un fragmento para el retriever",
)
def validar_fragmento(
    id_fragmento: int,
    payload: ValidarFragmentoIn | None = None,
    db: Session = Depends(get_db),
) -> Fragmento:
    id_objetivo = payload.id_objetivo if payload else None
    return _ejecutar(lambda: curation.validar(db, id_fragmento, id_objetivo=id_objetivo))


@router.post(
    "/fragmentos/{id_fragmento}/descartar",
    response_model=FragmentoOut,
    summary="Marca un fragmento como no utilizable",
)
def descartar_fragmento(id_fragmento: int, db: Session = Depends(get_db)) -> Fragmento:
    return _ejecutar(lambda: curation.descartar(db, id_fragmento))


@router.patch(
    "/fragmentos/{id_fragmento}/objetivo",
    response_model=FragmentoOut,
    summary="Asigna el objetivo de aprendizaje de un fragmento",
)
def asignar_objetivo(
    id_fragmento: int, payload: AsignarObjetivoIn, db: Session = Depends(get_db)
) -> Fragmento:
    return _ejecutar(
        lambda: curation.asignar_objetivo(db, id_fragmento, payload.id_objetivo)
    )


@router.patch(
    "/fragmentos/{id_fragmento}/texto",
    response_model=FragmentoOut,
    summary="Corrige el texto extraído antes de validarlo",
)
def editar_fragmento(
    id_fragmento: int, payload: EditarFragmentoIn, db: Session = Depends(get_db)
) -> Fragmento:
    return _ejecutar(lambda: curation.editar_texto(db, id_fragmento, payload.contenido_texto))


# --- Recuperación (previa a la Fase 3) ---------------------------------------


@router.get(
    "/recuperar",
    response_model=list[FragmentoRecuperadoOut],
    summary="Fragmentos validados de un objetivo (RAG estructurado)",
)
def recuperar_fragmentos(
    id_objetivo: int,
    canal_primario: str | None = Query(default=None, pattern="^[VARKvark]$"),
    consulta: str | None = None,
    limite: int = Query(default=8, ge=1, le=30),
    db: Session = Depends(get_db),
) -> list[FragmentoRecuperadoOut]:
    """Expone el retriever para poder auditarlo antes de conectarle el LLM.

    Es lo que la Fase 3 inyectará en el prompt maestro: verlo por separado
    permite comprobar la trazabilidad sin depender de una API de LLM.
    """
    fragmentos = recuperar(
        db,
        id_objetivo=id_objetivo,
        canal_primario=canal_primario,
        consulta=consulta,
        limite=limite,
    )
    return [
        FragmentoRecuperadoOut(
            id_fragmento=f.id_fragmento,
            texto=f.texto,
            tipo=f.tipo,
            documento=f.documento,
            pagina_inicio=f.pagina_inicio,
            pagina_fin=f.pagina_fin,
            etiqueta_tematica=f.etiqueta_tematica,
            cita=f.cita,
        )
        for f in fragmentos
    ]
