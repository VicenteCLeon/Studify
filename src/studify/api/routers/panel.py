"""Analíticas y simulador del docente por HTTP (migración a React, 27-ago-2026).

Estos endpoints no calculan nada: llaman a `studify.analytics`, que es la misma
función que usa el panel Jinja. Existen porque hasta ahora esa lógica **solo era
alcanzable renderizando una plantilla**, y sin ellos el panel del docente no se
podía migrar a un cliente que consume JSON.

Todo cuelga de un router con `auth.requiere_docente_api`, igual que el resto de
la curación (pendiente n.º 17): la cobertura del curso, el rendimiento de los
quizzes y el simulador —que gasta créditos del LLM en cada llamada— no son datos
del estudiante.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from studify.analytics import panel, simulador
from studify.api.routers.capsules import ClienteLLM, get_cliente_llm
from studify.api.schemas_panel import AnaliticasOut, ColumnaSimulacion, SimulacionIn
from studify.db.models import MicrocapsulaGenerada, ObjetivoAprendizaje
from studify.db.session import get_db
from studify.vark.scoring import CANALES
from studify.web.routers import auth

router = APIRouter(
    prefix="/api",
    tags=["panel del docente"],
    dependencies=[Depends(auth.requiere_docente_api)],
)

# Cuántas cápsulas muestra el historial del panel. El mismo número que usaba la
# vista Jinja, para que ambas pantallas muestren lo mismo mientras convivan.
LIMITE_HISTORIAL = 50


@router.get(
    "/analiticas",
    response_model=AnaliticasOut,
    summary="Cobertura curricular, rendimiento de quizzes y perfil de la cohorte",
)
def analiticas(db: Session = Depends(get_db)) -> AnaliticasOut:
    """Las cinco métricas del panel en una sola respuesta.

    Van juntas y no en cinco endpoints porque la pantalla las muestra siempre a
    la vez: separarlas obligaría al cliente a orquestar cinco llamadas para
    pintar una vista y a manejar el estado intermedio en que unas respondieron
    y otras no.
    """
    vark = panel.promedio_vark_cohorte(db)
    capsulas = db.scalars(
        select(MicrocapsulaGenerada)
        .order_by(MicrocapsulaGenerada.fecha_generacion.desc())
        .limit(LIMITE_HISTORIAL)
    ).all()

    return AnaliticasOut.model_validate(
        {
            "cobertura": [
                # `tipos` viene como lista de tuplas (el orden importa: ya está
                # ordenado por cantidad) y se nombra acá para que el cliente no
                # dependa de posiciones dentro de un array.
                {**fila, "tipos": [{"tipo": t, "cantidad": c} for t, c in fila["tipos"]]}
                for fila in panel.cobertura_curricular(db)
            ],
            "sin_clasificar": panel.fragmentos_sin_clasificar(db),
            "rendimiento": panel.rendimiento_actividades(db),
            "vark_total": vark.total if vark else 0,
            "vark_barras": panel.barras_cohorte(vark),
            "capsulas": capsulas,
        }
    )


def _objetivo_o_404(db: Session, id_objetivo: int) -> ObjetivoAprendizaje:
    objetivo = db.get(ObjetivoAprendizaje, id_objetivo)
    if objetivo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Objetivo no encontrado."
        )
    return objetivo


def _cliente_o_503(cliente: ClienteLLM | None) -> ClienteLLM:
    if cliente is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Falta LLM_API_KEY para simular.",
        )
    return cliente


@router.post(
    "/simulador/generar",
    response_model=ColumnaSimulacion,
    summary="Genera la cápsula de un perfil VARK puro, sin persistirla",
)
def simular_canal(
    payload: SimulacionIn,
    db: Session = Depends(get_db),
    cliente: ClienteLLM | None = Depends(get_cliente_llm),
) -> ColumnaSimulacion:
    """Un canal suelto. La cápsula **no se guarda**: es una prueba del docente.

    Un canal desconocido dejaría el vector en 0/0/0/0, que rompe el invariante
    de `PerfilVark` (suma 100) y que `derivar()` interpreta como multimodal con
    primario V: se generaría una cápsula para un perfil que no existe, sin error
    visible. Se corta acá, igual que en la vista Jinja.
    """
    canal_vark = (payload.canal or "").strip().upper()
    if canal_vark not in CANALES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"«{payload.canal}» no es un canal VARK: elige Visual, Auditivo, "
                f"Lectura/Escritura o Kinestésico."
            ),
        )

    objetivo = _objetivo_o_404(db, payload.id_objetivo)
    columna = simulador.generar_capsula_pura(
        db, objetivo, canal_vark, _cliente_o_503(cliente)
    )
    return ColumnaSimulacion.model_validate(columna)


@router.post(
    "/simulador/comparar",
    response_model=list[ColumnaSimulacion],
    summary="Genera las cuatro cápsulas puras (V, A, R, K) del mismo objetivo",
)
def comparar_canales(
    payload: SimulacionIn,
    db: Session = Depends(get_db),
    cliente: ClienteLLM | None = Depends(get_cliente_llm),
) -> list[ColumnaSimulacion]:
    """El criterio de término de la Fase 3: ver si los cuatro perfiles se distinguen.

    **Cada canal se resuelve por separado y un fallo no aborta a los otros
    tres.** Cuatro llamadas al LLM son cuatro oportunidades de que una falle; si
    una columna revienta, las otras tres igual sirven para juzgar la adaptación
    — y son exactamente las que ya se pagaron.
    """
    objetivo = _objetivo_o_404(db, payload.id_objetivo)
    real = _cliente_o_503(cliente)
    return [
        ColumnaSimulacion.model_validate(
            simulador.generar_capsula_pura(db, objetivo, canal, real)
        )
        for canal in CANALES
    ]
