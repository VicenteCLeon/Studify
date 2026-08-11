"""Curación humana de la base de conocimiento (cap. 12).

La ingesta deja material *candidato*; este módulo es el que lo habilita. Es la
única puerta por la que un fragmento pasa de `pendiente` a `validado`, y por lo
tanto la única forma de que llegue al prompt.

**La regla que más errores evita: no se puede validar sin objetivo asignado.**
El retriever recupera por `id_objetivo` (cap. 15, «consulta SQL exacta usando
identificadores únicos vinculados al objetivo de aprendizaje»). Un fragmento
validado con `id_objetivo = NULL` es inalcanzable para siempre: aprobado, sin
error visible y sin llegar nunca a una cápsula. Es el fallo silencioso más fácil
de cometer revisando decenas de fragmentos seguidos, así que se bloquea.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from studify.db.models import DocumentoFuente, Fragmento, ObjetivoAprendizaje


class ErrorCuracion(Exception):
    """Operación de curación inválida."""


def listar_fragmentos(
    db: Session,
    *,
    id_documento: int | None = None,
    estado: str | None = None,
    id_objetivo: int | None = None,
    limite: int = 50,
    desplazamiento: int = 0,
) -> list[Fragmento]:
    """Bandeja de revisión, en orden de lectura del documento.

    El orden por (documento, número de fragmento) no es cosmético: revisar un
    apunte salteado obliga al curador a reconstruir mentalmente el hilo del
    texto, y así es como se asignan objetivos equivocados.
    """
    stmt = (
        select(Fragmento)
        .options(joinedload(Fragmento.documento), joinedload(Fragmento.objetivo))
        .order_by(Fragmento.id_documento, Fragmento.numero_fragmento)
    )
    if id_documento is not None:
        stmt = stmt.where(Fragmento.id_documento == id_documento)
    if estado is not None:
        stmt = stmt.where(Fragmento.estado_validacion == estado)
    if id_objetivo is not None:
        stmt = stmt.where(Fragmento.id_objetivo == id_objetivo)

    return list(db.scalars(stmt.limit(limite).offset(desplazamiento)).unique().all())


def _obtener(db: Session, id_fragmento: int) -> Fragmento:
    fragmento = db.get(Fragmento, id_fragmento)
    if fragmento is None:
        raise ErrorCuracion(f"no existe el fragmento {id_fragmento}")
    return fragmento


def asignar_objetivo(db: Session, id_fragmento: int, id_objetivo: int) -> Fragmento:
    """Vincula un fragmento con el objetivo de aprendizaje que le corresponde."""
    fragmento = _obtener(db, id_fragmento)

    objetivo = db.get(ObjetivoAprendizaje, id_objetivo)
    if objetivo is None:
        raise ErrorCuracion(f"no existe el objetivo de aprendizaje {id_objetivo}")
    if objetivo.estado != "activo":
        raise ErrorCuracion(
            f"el objetivo '{objetivo.codigo_objetivo}' está en estado "
            f"'{objetivo.estado}': no se le puede asociar material"
        )

    fragmento.id_objetivo = id_objetivo
    db.commit()
    return fragmento


def editar_texto(db: Session, id_fragmento: int, texto: str) -> Fragmento:
    """Corrige el contenido de un fragmento antes de validarlo.

    Hace falta porque la extracción automática arrastra ruido —encabezados de
    página, numeración, notas al pie que se cuelan a mitad de párrafo— y el
    cap. 12 pide material curado, no material crudo.
    """
    texto = texto.strip()
    if not texto:
        raise ErrorCuracion(
            "el texto no puede quedar vacío; para eliminar el fragmento use 'descartar'"
        )

    fragmento = _obtener(db, id_fragmento)
    fragmento.contenido_texto = texto
    metadatos = dict(fragmento.metadatos_json or {})
    metadatos["palabras"] = len(texto.split())
    metadatos["editado_por_curador"] = True
    fragmento.metadatos_json = metadatos
    db.commit()
    return fragmento


def validar(db: Session, id_fragmento: int, *, id_objetivo: int | None = None) -> Fragmento:
    """Habilita un fragmento para el retriever.

    Si se pasa `id_objetivo`, lo asigna en el mismo acto: revisar y clasificar
    son una sola decisión del curador, y separarlas en dos llamadas invita a
    dejar fragmentos aprobados sin objetivo.
    """
    fragmento = _obtener(db, id_fragmento)

    if id_objetivo is not None:
        asignar_objetivo(db, id_fragmento, id_objetivo)

    if fragmento.id_objetivo is None:
        raise ErrorCuracion(
            f"el fragmento {id_fragmento} no tiene objetivo de aprendizaje "
            f"asignado. Validarlo así lo dejaría inalcanzable: el retriever "
            f"recupera por objetivo, de modo que nunca llegaría a una cápsula."
        )

    if not (fragmento.contenido_texto or "").strip():
        raise ErrorCuracion(
            f"el fragmento {id_fragmento} no tiene texto: no puede fundamentar nada"
        )

    fragmento.estado_validacion = "validado"

    # Un documento con material aprobado ya pasó por revisión. Sin esto, el
    # documento quedaría "pendiente" para siempre y el panel de curación
    # mostraría trabajo terminado como si estuviera por hacer.
    documento = db.get(DocumentoFuente, fragmento.id_documento)
    if documento is not None and documento.estado_curacion == "pendiente":
        documento.estado_curacion = "validado"

    db.commit()
    return fragmento


def descartar(db: Session, id_fragmento: int) -> Fragmento:
    """Marca un fragmento como no utilizable.

    No se borra: el cap. 12 exige trazabilidad del proceso de curación, y saber
    qué se descartó (y que se revisó) es parte de eso. Un fragmento descartado
    simplemente nunca cumple el filtro del retriever.
    """
    fragmento = _obtener(db, id_fragmento)
    fragmento.estado_validacion = "descartado"
    db.commit()
    return fragmento


def resumen_documento(db: Session, id_documento: int) -> dict[str, int]:
    """Cuántos fragmentos hay en cada estado, para medir el avance de la curación."""
    filas = db.execute(
        select(Fragmento.estado_validacion, func.count())
        .where(Fragmento.id_documento == id_documento)
        .group_by(Fragmento.estado_validacion)
    ).all()
    conteo = {"pendiente": 0, "validado": 0, "descartado": 0}
    for estado, total in filas:
        conteo[estado] = total
    conteo["total"] = sum(conteo.values())
    return conteo
