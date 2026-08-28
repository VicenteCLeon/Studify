"""Los cuatro cálculos del panel de analíticas del docente (Fase 5).

Movidos tal cual desde `web/routers/teacher.py` en la migración a React: los
docstrings originales se conservan porque explican *por qué* cada métrica se
calcula así, y esas razones no cambiaron al cambiar de transporte. Lo único que
se agregó es el `select()` del promedio de cohorte, que antes estaba suelto
dentro del handler de la vista.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from studify.db.models import (
    DiagnosticoVark,
    Fragmento,
    InteraccionQuiz,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.rag import retriever
from studify.web import textos

# Desde cuántos fragmentos recuperables se considera cubierto un objetivo. Es la
# mitad de lo que el retriever pide como contexto (`LIMITE_POR_DEFECTO`): por
# debajo de eso la cápsula se genera igual, pero apoyada en una porción del
# apunte demasiado chica como para fundamentar 150–300 palabras sin repetirse.
MINIMO_RECOMENDADO = retriever.LIMITE_POR_DEFECTO // 2


def cobertura_curricular(db: Session) -> list[dict]:
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


def fragmentos_sin_clasificar(db: Session) -> int:
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


def rendimiento_actividades(db: Session) -> list[dict]:
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


def promedio_vark_cohorte(db: Session):
    """Promedio del vector VARK sobre todos los diagnósticos, con el total.

    El `select` estaba suelto dentro del handler de la vista; se trae acá para
    que la cifra que ve el docente en el panel y la que devuelve la API salgan
    literalmente de la misma consulta.
    """
    return db.execute(
        select(
            func.avg(DiagnosticoVark.porcentaje_v).label("v"),
            func.avg(DiagnosticoVark.porcentaje_a).label("a"),
            func.avg(DiagnosticoVark.porcentaje_r).label("r"),
            func.avg(DiagnosticoVark.porcentaje_k).label("k"),
            func.count(DiagnosticoVark.id_diagnostico).label("total"),
        )
    ).first()


def barras_cohorte(vark) -> list[dict]:
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
            "canal": canal,
            "nombre": textos.NOMBRE_CANAL[canal],
            "color": textos.COLOR_CANAL[canal],
            "ancho": f"{porcentaje:.2f}",
            "texto": f"{porcentaje:.1f}".replace(".", ","),
        }
        for canal, porcentaje in ordenados
    ]
