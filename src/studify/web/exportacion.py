"""Todos los datos de un estudiante, tal como están en la base (`/mis-datos`).

Es el derecho de acceso y de portabilidad: la misma estructura se muestra
resumida en la página y se descarga completa como JSON. Lee las relaciones del
modelo y no copia nada, así que si se agrega una tabla con datos del
estudiante hay que sumarla acá: es la lista de lo que se declara en la
sección 2 de la Política de Privacidad.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from studify.db.models import AceptacionLegal, Estudiante, InteraccionQuiz, MicrocapsulaGenerada


def datos_de(db: Session, estudiante: Estudiante) -> dict:
    diagnosticos = sorted(estudiante.diagnosticos, key=lambda d: d.fecha_diagnostico)
    capsulas = sorted(estudiante.capsulas, key=lambda c: c.fecha_generacion)
    ids_capsulas = [c.id_capsula for c in capsulas]
    intentos = (
        db.scalars(
            select(InteraccionQuiz)
            .where(InteraccionQuiz.id_capsula.in_(ids_capsulas))
            .order_by(InteraccionQuiz.fecha_respuesta)
        ).all()
        if ids_capsulas
        else []
    )
    aceptaciones = db.scalars(
        select(AceptacionLegal)
        .where(AceptacionLegal.id_estudiante == estudiante.id_estudiante)
        .order_by(AceptacionLegal.aceptado_en)
    ).all()

    return {
        "estudiante": {
            "id_estudiante": estudiante.id_estudiante,
            "fecha_registro": estudiante.fecha_registro,
            "rango_etario": estudiante.rango_etario,
            "genero": estudiante.genero,
            "carrera": estudiante.carrera,
            "ano_ingreso": estudiante.ano_ingreso,
        },
        "diagnosticos_vark": [
            {
                "id_diagnostico": d.id_diagnostico,
                "fecha": d.fecha_diagnostico,
                "puntajes": {
                    "V": d.puntaje_v,
                    "A": d.puntaje_a,
                    "R": d.puntaje_r,
                    "K": d.puntaje_k,
                },
                "porcentajes": {
                    "V": d.porcentaje_v,
                    "A": d.porcentaje_a,
                    "R": d.porcentaje_r,
                    "K": d.porcentaje_k,
                },
                "respuestas": [
                    {"pregunta": r.num_pregunta, "alternativa": r.alternativa}
                    for r in sorted(d.respuestas, key=lambda r: (r.num_pregunta, r.alternativa))
                ],
                "configuracion_contenido": _configuracion(d.configuracion),
            }
            for d in diagnosticos
        ],
        "capsulas": [_capsula(c) for c in capsulas],
        "intentos_en_actividades": [
            {
                "id_capsula": i.id_capsula,
                "numero_intento": i.numero_intento,
                "alternativa_seleccionada": i.alternativa_seleccionada,
                "es_correcta": i.es_correcta,
                "fecha": i.fecha_respuesta,
            }
            for i in intentos
        ],
        "aceptaciones": [
            {"documento": a.documento, "version": a.version, "aceptado_en": a.aceptado_en}
            for a in aceptaciones
        ],
    }


def _configuracion(config) -> dict | None:
    if config is None:
        return None
    return {
        "peso_texto": config.peso_texto,
        "peso_visual": config.peso_visual,
        "peso_narrativo": config.peso_narrativo,
        "peso_practico": config.peso_practico,
        "recursos_visuales": config.recursos_visuales,
        "palabras_texto": config.palabras_texto,
        "componentes_practicos": config.componentes_practicos,
        "tono_narrativo": config.tono_narrativo,
        "canales_activos": config.canales_activos,
    }


def _capsula(c: MicrocapsulaGenerada) -> dict:
    return {
        "id_capsula": c.id_capsula,
        "fecha": c.fecha_generacion,
        "tema": c.objetivo.tema if c.objetivo else None,
        "titulo": c.titulo,
        "modelo_llm": c.modelo_llm,
        "contenido": c.contenido_json,
        "actividad": c.mini_quiz_json,
    }
