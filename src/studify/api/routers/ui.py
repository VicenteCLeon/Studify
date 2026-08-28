"""Lo que la interfaz necesita y solo existía dentro de los handlers Jinja.

Migración a React (27-ago-2026). Cada endpoint de acá corresponde a un pedazo de
`web/routers/student.py` que calculaba datos **dentro** de un handler que
devolvía HTML, de modo que no había forma de obtenerlos por HTTP.

Dos cosas se preservan al pie de la letra porque son decisiones de diseño del
informe, no detalles de implementación:

1. **La matriz de puntuación no se filtra al cliente** (cap. 17.1): el
   cuestionario viaja con letras `a|b|c|d`, nunca con canales V/A/R/K.
2. **La respuesta correcta del quiz no viaja al navegador**: la corrección se
   hace en el servidor contra `mini_quiz_json`. Si `indice_correcta` llegara al
   cliente, el quiz dejaría de medir nada.
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from studify.api.routers.capsules import diagnostico_vigente, registrar_quiz
from studify.api.schemas_capsulas import InteraccionQuizIn
from studify.api.schemas_ui import (
    ItemInstrumento,
    PerfilLegibleOut,
    RespuestaActividadIn,
    ResultadoActividadOut,
    SesionEstudianteOut,
    TextosUiOut,
)
from studify.db.models import Estudiante, MicrocapsulaGenerada
from studify.db.session import get_db
from studify.vark import instrumento
from studify.vark.rules import aplicar_reglas
from studify.vark.scoring import PerfilVark
from studify.web import sesion, textos

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["interfaz"])

LETRAS = ("a", "b", "c", "d")


# --- Instrumento y textos -----------------------------------------------------


@router.get(
    "/instrumento",
    response_model=list[ItemInstrumento],
    summary="Los 16 ítems del cuestionario VARK, con sus alternativas",
)
def obtener_instrumento() -> list[ItemInstrumento]:
    """Las alternativas se leen de `vark/instrumento.py`, la misma fuente que usa
    la calificación, para que la pantalla no pueda desalinearse de la matriz.

    **Viajan por letra, no por canal.** Es el servidor quien traduce la posición
    a V/A/R/K (`instrumento.canal_por_posicion`), tal como exige el cap. 17.1.
    """
    return [
        ItemInstrumento(
            numero=numero,
            enunciado=textos.ENUNCIADOS[numero - 1],
            alternativas=[
                {"letra": letra, "texto": texto}
                for letra, texto in zip(LETRAS, alternativas, strict=True)
            ],
        )
        for numero, alternativas in enumerate(instrumento.ITEMS, start=1)
    ]


@router.get(
    "/textos",
    response_model=TextosUiOut,
    summary="Nombres y colores de canal compartidos por las dos interfaces",
)
def obtener_textos() -> TextosUiOut:
    return TextosUiOut(
        nombre_canal=textos.NOMBRE_CANAL,
        color_canal=textos.COLOR_CANAL,
        nombre_tono=textos.NOMBRE_TONO,
    )


# --- Sesión del estudiante ----------------------------------------------------


@router.get(
    "/sesion",
    response_model=SesionEstudianteOut,
    summary="Qué estudiante está conectado, según la cookie firmada",
)
def sesion_actual(
    request: Request, db: Session = Depends(get_db)
) -> SesionEstudianteOut:
    """Sin sesión devuelve `id_estudiante: null` con 200, no un 401.

    No tener sesión es el estado normal de quien todavía no respondió el
    cuestionario, no un error: el cliente lo usa para decidir a qué pantalla
    mandarlo.
    """
    id_estudiante = sesion.estudiante_actual(request)
    if id_estudiante is None or db.get(Estudiante, id_estudiante) is None:
        return SesionEstudianteOut()

    return SesionEstudianteOut(
        id_estudiante=id_estudiante,
        tiene_diagnostico=diagnostico_vigente(db, id_estudiante) is not None,
    )


@router.post(
    "/sesion/{id_estudiante}",
    response_model=SesionEstudianteOut,
    summary="Deja al estudiante conectado tras responder el cuestionario",
)
def abrir_sesion(
    id_estudiante: int, response: Response, db: Session = Depends(get_db)
) -> SesionEstudianteOut:
    """Emite la cookie firmada. Es lo que `post_vark` hacía al final del flujo.

    Va como endpoint propio porque `POST /api/diagnosticos` es de la API pura
    —no sabe de cookies— y el cliente necesita quedar conectado justo después
    de crear el diagnóstico.
    """
    if db.get(Estudiante, id_estudiante) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado."
        )

    sesion.iniciar(response, id_estudiante)
    return SesionEstudianteOut(
        id_estudiante=id_estudiante,
        tiene_diagnostico=diagnostico_vigente(db, id_estudiante) is not None,
    )


@router.delete(
    "/sesion", status_code=status.HTTP_204_NO_CONTENT, summary="Cierra la sesión"
)
def cerrar_sesion(response: Response) -> Response:
    sesion.cerrar(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


# --- Perfil legible -----------------------------------------------------------


def _barras(perfil: PerfilVark) -> list[dict]:
    """Los cuatro canales ordenados de mayor a menor, listos para pintar."""
    valores: dict[str, Decimal] = perfil.como_dict()
    ordenados = sorted(valores.items(), key=lambda kv: (-kv[1], "VARK".index(kv[0])))
    return [
        {
            "canal": canal,
            "nombre": textos.NOMBRE_CANAL[canal],
            "color": textos.COLOR_CANAL[canal],
            "ancho": f"{porcentaje:.2f}",
            "texto": f"{porcentaje:.1f}".replace(".", ","),
        }
        for canal, porcentaje in ordenados
    ]


def _modalidad(jerarquia) -> str:
    if jerarquia.es_multimodal:
        return "Multimodal"
    if jerarquia.es_bimodal:
        return "Bimodal"
    return "Unimodal"


@router.get(
    "/perfil",
    response_model=PerfilLegibleOut,
    summary="Vector VARK y configuración de contenido del estudiante conectado",
)
def perfil_legible(
    request: Request, db: Session = Depends(get_db)
) -> PerfilLegibleOut:
    """El mismo cálculo que hacía `get_profile`, sin la plantilla.

    La fila persistida es la que la generación referencia por FK
    (`microcapsula_generada.id_config`); las reglas son función pura del vector,
    así que sus valores coinciden, pero se devuelve la guardada para que la
    pantalla no pueda diferir de lo que el motor va a usar.
    """
    id_estudiante = sesion.estudiante_actual(request)
    if id_estudiante is None or db.get(Estudiante, id_estudiante) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="No hay sesión abierta."
        )

    diagnostico = diagnostico_vigente(db, id_estudiante)
    if diagnostico is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Este estudiante todavía no tiene un diagnóstico.",
        )

    perfil = PerfilVark(
        v=diagnostico.porcentaje_v,
        a=diagnostico.porcentaje_a,
        r=diagnostico.porcentaje_r,
        k=diagnostico.porcentaje_k,
    )
    config = aplicar_reglas(perfil)
    jerarquia = config.jerarquia
    fila = diagnostico.configuracion

    explicacion = textos.EXPLICACION_CANAL[jerarquia.canal_primario]
    if jerarquia.es_multimodal:
        explicacion = f"{explicacion} {textos.EXPLICACION_MULTIMODAL}"

    return PerfilLegibleOut(
        id_diagnostico=diagnostico.id_diagnostico,
        canales=_barras(perfil),
        canal_principal=textos.NOMBRE_CANAL[jerarquia.canal_primario],
        canal_primario=jerarquia.canal_primario,
        canal_secundario=jerarquia.canal_secundario,
        modalidad=_modalidad(jerarquia),
        explicacion=explicacion,
        configuracion={
            "recursos_visuales": fila.recursos_visuales
            if fila
            else config.recursos_visuales,
            "palabras_texto": fila.palabras_texto if fila else config.palabras_texto,
            "componentes_practicos": fila.componentes_practicos
            if fila
            else config.componentes_practicos,
            "tono": textos.NOMBRE_TONO.get(
                config.tono_narrativo, config.tono_narrativo
            ),
            "pesos": {
                "texto": config.pesos.texto,
                "visual": config.pesos.visual,
                "narrativo": config.pesos.narrativo,
                "practico": config.pesos.practico,
            },
        },
        directivas=[textos.glosa_directiva(d) for d in config.directivas],
    )


# --- Actividad de cierre ------------------------------------------------------


@router.post(
    "/capsulas/{id_capsula}/responder",
    response_model=ResultadoActividadOut,
    summary="Corrige la actividad de cierre en el servidor",
)
def responder_actividad(
    id_capsula: int,
    payload: RespuestaActividadIn,
    request: Request,
    db: Session = Depends(get_db),
) -> ResultadoActividadOut:
    """Corrige contra el `mini_quiz_json` guardado, no contra nada del cliente.

    Es `submit_activity` de `web/routers/student.py`, sin el HTML. Mantiene sus
    dos guardias:

    - **Se comprueba el dueño de la cápsula**, para que la respuesta correcta no
      se pueda sondear con peticiones a ids ajenos.
    - **`indice_correcta` nunca sale de acá**: solo se devuelve el texto de la
      alternativa correcta, y únicamente cuando el estudiante ya falló.
    """
    id_estudiante = sesion.estudiante_actual(request)
    fila = db.get(MicrocapsulaGenerada, id_capsula)

    if fila is None or id_estudiante is None or fila.id_estudiante != id_estudiante:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta actividad no está disponible en tu sesión.",
        )

    quiz = fila.mini_quiz_json or {}

    if quiz.get("tipo") == "intentalo_tu":
        # No hay respuesta única que corregir: se muestra la esperada para que el
        # estudiante contraste lo que escribió. Se registra igual —sin acierto ni
        # alternativa— porque si no, los objetivos con actividad aplicada (los
        # perfiles K) no aparecerían nunca en el panel del docente, como si nadie
        # los hubiera trabajado.
        intento = _registrar_intento(db, fila, alternativa=None, acerto=None)
        return ResultadoActividadOut(
            estado="esperada",
            titulo="Respuesta esperada",
            retroalimentacion=quiz.get("retroalimentacion", ""),
            numero_intento=intento,
        )

    indice_correcta = quiz.get("indice_correcta")
    alternativas = quiz.get("alternativas") or []
    if indice_correcta is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Esta cápsula no tiene una actividad corregible.",
        )

    if payload.alternativa is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selecciona una alternativa antes de revisar.",
        )

    acerto = payload.alternativa == indice_correcta
    intento = _registrar_intento(db, fila, alternativa=payload.alternativa, acerto=acerto)

    correcta = (
        alternativas[indice_correcta]
        if 0 <= indice_correcta < len(alternativas)
        else ""
    )
    return ResultadoActividadOut(
        estado="ok" if acerto else "error",
        titulo="¡Correcto!" if acerto else "No es esa",
        retroalimentacion=quiz.get("retroalimentacion", ""),
        correcta=None if acerto else correcta,
        numero_intento=intento,
    )


def _registrar_intento(
    db: Session,
    fila: MicrocapsulaGenerada,
    *,
    alternativa: int | None,
    acerto: bool | None,
) -> int | None:
    """Deja el intento en la base para el panel del docente (Fase 5).

    Llama al mismo handler de `POST /api/capsulas/{id}/quiz`, que es quien numera
    el intento y comprueba el dueño de la cápsula.

    El 404 y el 403 de ese handler no pueden darse acá: el llamador ya verificó
    ambas cosas. Lo único que puede fallar es el 409 de dos peticiones
    simultáneas —el doble clic—, y en ese caso el intento que llegó primero ya
    quedó registrado. Perder el duplicado no vale interrumpirle la
    retroalimentación al estudiante.
    """
    try:
        interaccion = registrar_quiz(
            id_capsula=fila.id_capsula,
            payload=InteraccionQuizIn(
                id_estudiante=fila.id_estudiante,
                alternativa_seleccionada=alternativa,
                es_correcta=acerto,
            ),
            db=db,
        )
    except HTTPException:
        logger.warning(
            "no se pudo registrar el intento de la cápsula %s", fila.id_capsula
        )
        return None
    return interaccion.numero_intento
