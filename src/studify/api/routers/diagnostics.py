"""Endpoints de diagnóstico VARK.

Es el flujo completo del cap. 10 expuesto por HTTP: el estudiante responde los
16 ítems y recibe de vuelta su vector porcentual junto con la configuración de
contenido que se usará para generar sus cápsulas.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from studify.api.schemas import (
    ConfiguracionOut,
    DiagnosticoIn,
    DiagnosticoOut,
    JerarquiaOut,
    PerfilOut,
    PuntajesOut,
)
from studify.db.models import (
    ConfiguracionContenido,
    DiagnosticoVark,
    Estudiante,
    RespuestaVark,
)
from studify.db.session import get_db
from studify.vark.instrumento import canal_por_posicion
from studify.vark.rules import ConfiguracionGenerada, aplicar_reglas
from studify.vark.scoring import (
    ErrorDiagnosticoVacio,
    PerfilVark,
    PuntajesVark,
    Seleccion,
    calificar,
)

router = APIRouter(prefix="/api/diagnosticos", tags=["diagnósticos"])


def _armar_respuesta(
    id_diagnostico: int,
    id_estudiante: int,
    puntajes: PuntajesVark,
    perfil: PerfilVark,
    config: ConfiguracionGenerada,
    id_config: int | None = None,
) -> DiagnosticoOut:
    j = config.jerarquia
    return DiagnosticoOut(
        id_diagnostico=id_diagnostico,
        id_estudiante=id_estudiante,
        puntajes=PuntajesOut(
            v=puntajes.v, a=puntajes.a, r=puntajes.r, k=puntajes.k, total=puntajes.total
        ),
        perfil=PerfilOut(v=perfil.v, a=perfil.a, r=perfil.r, k=perfil.k),
        jerarquia=JerarquiaOut(
            canal_primario=j.canal_primario,
            canal_secundario=j.canal_secundario,
            canales_activos=list(j.canales_activos),
            es_unimodal=j.es_unimodal,
            es_bimodal=j.es_bimodal,
            es_multimodal=j.es_multimodal,
            etiqueta=j.etiqueta,
            jerarquia=j.jerarquia,
        ),
        configuracion=ConfiguracionOut(
            id_config=id_config,
            peso_texto=config.pesos.texto,
            peso_visual=config.pesos.visual,
            peso_narrativo=config.pesos.narrativo,
            peso_practico=config.pesos.practico,
            recursos_visuales=config.recursos_visuales,
            palabras_texto=config.palabras_texto,
            componentes_practicos=config.componentes_practicos,
            audio_activo=config.audio_activo,
            tono_narrativo=config.tono_narrativo,
            canales_activos=config.canales_activos,
            directivas=list(config.directivas),
        ),
    )


@router.post(
    "",
    response_model=DiagnosticoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Califica el cuestionario VARK y devuelve la configuración de contenido",
)
def crear_diagnostico(payload: DiagnosticoIn, db: Session = Depends(get_db)) -> DiagnosticoOut:
    """Flujo del cap. 10: 16 ítems → puntajes → vector porcentual → configuración.

    Persiste en las cuatro entidades del módulo de perfilamiento. Las respuestas
    individuales se guardan (tabla 17.3) para poder recalcular los perfiles si
    cambia la matriz de puntuación, sin volver a aplicar el cuestionario.
    """
    # Las letras se traducen a canales acá y no en el cliente: la matriz de
    # puntuación es del servidor (ver studify.vark.instrumento).
    selecciones: list[Seleccion] = []
    for item in payload.respuestas:
        for letra in item.alternativas:
            canal = canal_por_posicion(item.num_pregunta, letra)
            if canal is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"el ítem {item.num_pregunta} no tiene alternativa "
                        f"'{letra}' en el instrumento"
                    ),
                )
            selecciones.append(Seleccion(item.num_pregunta, letra, canal))

    try:
        puntajes, perfil = calificar(selecciones)
    except ErrorDiagnosticoVacio as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    config = aplicar_reglas(perfil)

    if payload.id_estudiante is not None:
        estudiante = db.get(Estudiante, payload.id_estudiante)
        if estudiante is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no existe el estudiante {payload.id_estudiante}",
            )
    else:
        estudiante = Estudiante(**payload.estudiante.model_dump())
        db.add(estudiante)
        db.flush()

    diagnostico = DiagnosticoVark(
        id_estudiante=estudiante.id_estudiante,
        puntaje_v=puntajes.v,
        puntaje_a=puntajes.a,
        puntaje_r=puntajes.r,
        puntaje_k=puntajes.k,
        porcentaje_v=perfil.v,
        porcentaje_a=perfil.a,
        porcentaje_r=perfil.r,
        porcentaje_k=perfil.k,
    )
    db.add(diagnostico)
    db.flush()

    db.add_all(
        RespuestaVark(
            id_diagnostico=diagnostico.id_diagnostico,
            num_pregunta=s.num_pregunta,
            alternativa=s.alternativa,
            canal_mapeado=s.canal,
        )
        for s in selecciones
    )

    fila_config = ConfiguracionContenido(
        id_diagnostico=diagnostico.id_diagnostico,
        peso_texto=config.pesos.texto,
        peso_visual=config.pesos.visual,
        peso_narrativo=config.pesos.narrativo,
        peso_practico=config.pesos.practico,
        recursos_visuales=config.recursos_visuales,
        palabras_texto=config.palabras_texto,
        componentes_practicos=config.componentes_practicos,
        audio_activo=config.audio_activo,
        tono_narrativo=config.tono_narrativo,
        canales_activos=config.canales_activos,
    )
    db.add(fila_config)
    db.commit()

    return _armar_respuesta(
        id_diagnostico=diagnostico.id_diagnostico,
        id_estudiante=estudiante.id_estudiante,
        puntajes=puntajes,
        perfil=perfil,
        config=config,
        id_config=fila_config.id_config,
    )


@router.get(
    "/{id_diagnostico}",
    response_model=DiagnosticoOut,
    summary="Recupera un diagnóstico ya calculado",
)
def obtener_diagnostico(id_diagnostico: int, db: Session = Depends(get_db)) -> DiagnosticoOut:
    """Devuelve el diagnóstico persistido con su jerarquía recalculada.

    La jerarquía se deriva del vector guardado en vez de leerse de una columna,
    porque el cap. 17.2 exige que la interpretación categórica no se persista:
    así no puede quedar desincronizada respecto de los porcentajes.
    """
    diagnostico = db.get(DiagnosticoVark, id_diagnostico)
    if diagnostico is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no existe el diagnóstico {id_diagnostico}",
        )

    perfil = PerfilVark(
        v=diagnostico.porcentaje_v,
        a=diagnostico.porcentaje_a,
        r=diagnostico.porcentaje_r,
        k=diagnostico.porcentaje_k,
    )
    puntajes = PuntajesVark(
        v=diagnostico.puntaje_v,
        a=diagnostico.puntaje_a,
        r=diagnostico.puntaje_r,
        k=diagnostico.puntaje_k,
    )
    config = aplicar_reglas(perfil)

    return _armar_respuesta(
        id_diagnostico=diagnostico.id_diagnostico,
        id_estudiante=diagnostico.id_estudiante,
        puntajes=puntajes,
        perfil=perfil,
        config=config,
        id_config=diagnostico.configuracion.id_config if diagnostico.configuracion else None,
    )
