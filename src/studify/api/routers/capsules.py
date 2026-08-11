"""Generación de microcápsulas — `POST /api/capsulas` (Fase 3).

Es el endpoint donde se juntan las tres fases anteriores: el perfil VARK de la
Fase 1, el material curado de la Fase 2 y el motor de generación de esta. El
flujo completo por petición:

    diagnóstico del estudiante → configuracion_contenido (vark/rules)
    objetivo + canal primario  → fragmentos validados (rag/retriever)
    ambos                      → prompt maestro (rag/orchestrator)
    prompt                     → cápsula validada (generation/generator)

**Política de caché y regeneración** (decisión 5 de AVANCE §7, cerrada el
11-ago-2026). Por defecto el endpoint devuelve la cápsula ya generada para la
misma huella; con `?regenerar=true` produce una versión nueva y conserva la
anterior. Se eligió sobre "sobrescribir" porque el bake-off de la Fase 3 y la
validación docente de la Fase 5 comparan varias cápsulas del mismo objetivo, y
sobrescribir las haría desaparecer.

El caché tiene dos niveles, y el segundo es el que de verdad ahorra: si **otro**
estudiante con el mismo tramo de perfil ya pidió este objetivo, se copia su
cápsula en una fila nueva para este estudiante en vez de volver a pagarle al
modelo. Se copia y no se comparte la fila porque la tabla 17.8 vincula cada
cápsula a un estudiante, y el A/B de la Fase 5 necesita saber qué vio cada uno.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from studify.api.schemas_capsulas import CapsulaIn, CapsulaOut, ResumenCapsulaOut
from studify.config import get_settings
from studify.db.models import (
    DiagnosticoVark,
    Estudiante,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.db.session import get_db
from studify.generation.generator import (
    ClienteLLM,
    ClienteOpenAILike,
    ErrorGeneracion,
    ResultadoGeneracion,
    generar,
)
from studify.generation.schemas import Microcapsula
from studify.rag import orchestrator
from studify.rag.orchestrator import ErrorPrompt
from studify.rag.retriever import recuperar
from studify.vark.rules import aplicar_reglas
from studify.vark.scoring import PerfilVark

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/capsulas", tags=["cápsulas"])

# Longitud de `microcapsula_generada.titulo` (tabla 17.8). El contrato ya limita
# el título a 10 palabras, pero diez palabras largas caben igual sobre 150
# caracteres y el INSERT fallaría con un error de base de datos en vez de
# entregar la cápsula.
MAX_TITULO = 150


def get_cliente_llm() -> ClienteLLM | None:
    """El cliente del modelo, como dependencia inyectable.

    Va por `Depends` y no construido dentro del handler para que los tests
    puedan sustituirlo por un cliente falso con `dependency_overrides`, igual
    que `get_db` permite apuntar a otra base. Sin eso, probar el caché o la
    política de regeneración exigiría credenciales y una llamada real a
    DeepSeek en cada test.

    Devuelve `None` en vez de levantar 503 cuando falta la credencial, porque
    las dependencias se resuelven **antes** del handler: abortar acá dejaría sin
    servir también las cápsulas que estaban en caché y no necesitan al modelo
    para nada. El 503 se levanta más adelante, justo cuando se comprueba que
    hay que generar de verdad.
    """
    try:
        return ClienteOpenAILike()
    except ErrorGeneracion:
        return None


# --- Desglose entre las dos columnas JSONB de la tabla 17.8 ------------------


def _desglosar(capsula: Microcapsula) -> tuple[dict, dict]:
    """Separa la cápsula en `contenido_json` y `mini_quiz_json`.

    La tabla 17.8 declara las dos columnas por separado, así que se usan por
    separado: dejar `mini_quiz_json` en NULL y meter todo en `contenido_json`
    funcionaría, pero apartaría el modelo físico del diccionario de datos del
    informe sin ninguna ganancia.
    """
    completa = capsula.model_dump()
    actividad = completa.pop("actividad")
    return completa, actividad


def _recomponer(fila: MicrocapsulaGenerada) -> dict:
    return {**fila.contenido_json, "actividad": fila.mini_quiz_json}


def _a_salida(
    fila: MicrocapsulaGenerada,
    *,
    origen: str,
    resultado: ResultadoGeneracion | None = None,
) -> CapsulaOut:
    return CapsulaOut(
        id_capsula=fila.id_capsula,
        id_estudiante=fila.id_estudiante,
        id_objetivo=fila.id_objetivo,
        fecha_generacion=fila.fecha_generacion,
        estado_validacion=fila.estado_validacion,
        origen=origen,
        modelo_llm=fila.modelo_llm,
        intentos=resultado.intentos if resultado else None,
        segundos=round(resultado.segundos, 3) if resultado else None,
        **_recomponer(fila),
    )


# --- Caché --------------------------------------------------------------------


def _mas_reciente(db: Session, condiciones) -> MicrocapsulaGenerada | None:
    """La última cápsula que cumple las condiciones.

    Se desempata por `id_capsula` además de la fecha: `fecha_generacion` viene
    de `now()`, que en Postgres es constante dentro de una transacción, así que
    dos cápsulas creadas juntas comparten marca de tiempo y sin el desempate el
    "más reciente" sería arbitrario.
    """
    return db.scalars(
        select(MicrocapsulaGenerada)
        .where(*condiciones)
        .order_by(
            MicrocapsulaGenerada.fecha_generacion.desc(),
            MicrocapsulaGenerada.id_capsula.desc(),
        )
        .limit(1)
    ).first()


def _buscar_en_cache(
    db: Session, *, id_estudiante: int, id_objetivo: int, huella: str
) -> tuple[MicrocapsulaGenerada | None, str | None]:
    propia = _mas_reciente(
        db,
        (
            MicrocapsulaGenerada.id_estudiante == id_estudiante,
            MicrocapsulaGenerada.id_objetivo == id_objetivo,
            MicrocapsulaGenerada.huella_generacion == huella,
        ),
    )
    if propia is not None:
        return propia, "cache"

    ajena = _mas_reciente(
        db,
        (
            MicrocapsulaGenerada.id_objetivo == id_objetivo,
            MicrocapsulaGenerada.huella_generacion == huella,
        ),
    )
    if ajena is not None:
        return ajena, "cache_compartido"

    return None, None


# --- Endpoint -----------------------------------------------------------------


@router.post(
    "",
    response_model=CapsulaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Genera (o recupera del caché) la microcápsula de un objetivo",
)
def crear_capsula(
    payload: CapsulaIn,
    regenerar: bool = Query(
        False,
        description=(
            "Fuerza una generación nueva ignorando el caché. La cápsula "
            "anterior se conserva: no se sobrescribe, se versiona."
        ),
    ),
    db: Session = Depends(get_db),
    cliente: ClienteLLM | None = Depends(get_cliente_llm),
) -> CapsulaOut:
    estudiante = db.get(Estudiante, payload.id_estudiante)
    if estudiante is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no existe el estudiante {payload.id_estudiante}",
        )

    objetivo = db.get(ObjetivoAprendizaje, payload.id_objetivo)
    if objetivo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no existe el objetivo de aprendizaje {payload.id_objetivo}",
        )

    diagnostico = diagnostico_vigente(db, payload.id_estudiante)
    if diagnostico is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"el estudiante {payload.id_estudiante} no tiene diagnóstico "
                f"VARK. Sin perfil no hay nada que adaptar: primero hay que "
                f"responder el cuestionario en POST /api/diagnosticos"
            ),
        )

    perfil = PerfilVark(
        v=diagnostico.porcentaje_v,
        a=diagnostico.porcentaje_a,
        r=diagnostico.porcentaje_r,
        k=diagnostico.porcentaje_k,
    )
    config = aplicar_reglas(perfil)

    # El canal primario reordena los fragmentos por tipo, no los filtra: un
    # perfil visual ve primero las tablas disponibles, pero si el apunte no
    # tiene ninguna recibe igual el texto (ver rag/retriever.py).
    fragmentos = recuperar(
        db,
        id_objetivo=payload.id_objetivo,
        canal_primario=config.jerarquia.canal_primario,
    )

    ajustes = get_settings()
    try:
        prompt = orchestrator.construir(
            objetivo=objetivo,
            fragmentos=fragmentos,
            config=config,
            modelo=ajustes.llm_model,
        )
    except ErrorPrompt as exc:
        # El caso típico es un objetivo sin material validado. Es un 422 y no un
        # 500: el sistema está bien, falta curar (cap. 12).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    if not regenerar:
        cacheada, origen = _buscar_en_cache(
            db,
            id_estudiante=payload.id_estudiante,
            id_objetivo=payload.id_objetivo,
            huella=prompt.huella,
        )
        if cacheada is not None and origen == "cache":
            return _a_salida(cacheada, origen=origen)
        if cacheada is not None:
            copia = _persistir(
                db,
                capsula=None,
                fila_origen=cacheada,
                id_estudiante=payload.id_estudiante,
                id_objetivo=payload.id_objetivo,
                id_config=diagnostico.configuracion.id_config
                if diagnostico.configuracion
                else None,
                huella=prompt.huella,
                modelo=cacheada.modelo_llm,
            )
            return _a_salida(copia, origen="cache_compartido")

    if cliente is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "falta LLM_API_KEY en el .env: no se puede generar una cápsula "
                "nueva. Las que ya estén en caché sí se siguen sirviendo."
            ),
        )

    try:
        resultado = generar(prompt, cliente=cliente)
    except ErrorGeneracion as exc:
        # El plan §3: agotados los reintentos «se registra y se devuelve 502».
        # Esa tasa de fallo es un dato de resultados para el informe.
        logger.error(
            "generación agotada para estudiante=%s objetivo=%s: %s",
            payload.id_estudiante,
            payload.id_objetivo,
            exc.errores_por_intento,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    fila = _persistir(
        db,
        capsula=resultado.capsula,
        fila_origen=None,
        id_estudiante=payload.id_estudiante,
        id_objetivo=payload.id_objetivo,
        id_config=diagnostico.configuracion.id_config if diagnostico.configuracion else None,
        huella=prompt.huella,
        modelo=resultado.modelo,
    )
    return _a_salida(fila, origen="generada", resultado=resultado)


@router.get(
    "",
    response_model=list[ResumenCapsulaOut],
    summary="Historial de cápsulas, filtrable por estudiante y objetivo",
)
def listar_capsulas(
    id_estudiante: int | None = None,
    id_objetivo: int | None = None,
    limite: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[MicrocapsulaGenerada]:
    """Las versiones quedan todas: es lo que permite comparar entre modelos."""
    stmt = select(MicrocapsulaGenerada).order_by(
        MicrocapsulaGenerada.fecha_generacion.desc(),
        MicrocapsulaGenerada.id_capsula.desc(),
    )
    if id_estudiante is not None:
        stmt = stmt.where(MicrocapsulaGenerada.id_estudiante == id_estudiante)
    if id_objetivo is not None:
        stmt = stmt.where(MicrocapsulaGenerada.id_objetivo == id_objetivo)

    return list(db.scalars(stmt.limit(limite)).all())


@router.get(
    "/{id_capsula}",
    response_model=CapsulaOut,
    summary="Recupera una cápsula ya generada",
)
def obtener_capsula(id_capsula: int, db: Session = Depends(get_db)) -> CapsulaOut:
    fila = db.get(MicrocapsulaGenerada, id_capsula)
    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no existe la cápsula {id_capsula}",
        )
    return _a_salida(fila, origen="cache")


# --- Auxiliares ---------------------------------------------------------------


def diagnostico_vigente(db: Session, id_estudiante: int) -> DiagnosticoVark | None:
    """El diagnóstico vigente del estudiante.

    Se toma el más reciente y no "el" diagnóstico porque un estudiante puede
    responder el cuestionario más de una vez (la tabla 17.2 no lo impide), y la
    cápsula tiene que reflejar su perfil actual.

    Es público porque la UI de la Fase 4 necesita exactamente el mismo criterio:
    si la pantalla de perfil mostrara un diagnóstico distinto del que usa la
    generación, el estudiante vería un vector y recibiría cápsulas de otro.
    """
    return db.scalars(
        select(DiagnosticoVark)
        .where(DiagnosticoVark.id_estudiante == id_estudiante)
        .order_by(
            DiagnosticoVark.fecha_diagnostico.desc(),
            DiagnosticoVark.id_diagnostico.desc(),
        )
        .limit(1)
    ).first()


def _persistir(
    db: Session,
    *,
    capsula: Microcapsula | None,
    fila_origen: MicrocapsulaGenerada | None,
    id_estudiante: int,
    id_objetivo: int,
    id_config: int | None,
    huella: str,
    modelo: str | None,
) -> MicrocapsulaGenerada:
    """Guarda una cápsula recién generada o la copia de una del caché."""
    if capsula is not None:
        contenido, actividad = _desglosar(capsula)
        titulo = capsula.titulo
        id_fragmento = capsula.fuentes[0].id_fragmento if capsula.fuentes else None
    else:
        assert fila_origen is not None
        contenido = fila_origen.contenido_json
        actividad = fila_origen.mini_quiz_json
        titulo = fila_origen.titulo
        id_fragmento = fila_origen.id_fragmento_fuente

    fila = MicrocapsulaGenerada(
        id_estudiante=id_estudiante,
        id_objetivo=id_objetivo,
        id_config=id_config,
        id_fragmento_fuente=id_fragmento,
        titulo=titulo[:MAX_TITULO],
        contenido_json=contenido,
        mini_quiz_json=actividad,
        huella_generacion=huella,
        modelo_llm=modelo,
    )
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila
