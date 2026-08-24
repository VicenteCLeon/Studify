"""Etiquetado asistido por LLM de fragmentos pendientes (cap. 12, Fase 2).

`PLAN_DESARROLLO.md` §2 lo describe así: «el LLM propone objetivo asociado,
etiqueta temática y tipo de fragmento; queda en `estado_validacion =
'pendiente'»». Este módulo cubre las dos primeras — el tipo de fragmento
("texto", "tabla", …) ya lo resuelve `knowledge/chunker.py` a partir de la
estructura del documento, y no hay nada que un LLM pueda inferir ahí que no
sepa ya el extractor con más certeza.

**Propone, nunca decide — literal, no solo declarado.** A diferencia de
`curation.py`, este módulo **no escribe `Fragmento.id_objetivo` ni
`estado_validacion`**. Deja la sugerencia en `metadatos_json['sugerencia_llm']`
y es la UI (`web/routers/teacher.py`) la que la usa para **preseleccionar** el
selector de objetivo en la bandeja de revisión: el curador sigue teniendo que
pulsar «Validar» para que la asignación real ocurra, por el único camino que ya
existía (`curation.validar` → `curation.asignar_objetivo`). Si el modelo se
equivoca, no pasa nada irreversible: la sugerencia es un valor por defecto en
un `<select>`, no una escritura en la base.

**Por qué el motivo de no implementarlo antes ya no aplica.** Quedó fuera de la
Fase 2 porque entonces no había credencial de LLM (AVANCE.md §6, pendiente
n.º 3); desde el 13-ago-2026 sí la hay, así que el único bloqueo real ya se
cerró.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from studify.db.models import DocumentoFuente, Fragmento, ObjetivoAprendizaje
from studify.generation.generator import ClienteLLM, Mensaje
from studify.generation.validator import ErrorFormatoJSON, extraer_json

logger = logging.getLogger(__name__)

# Cuántos objetivos como máximo se listan en el prompt. Acota el costo y, sobre
# todo, evita que el modelo tenga que elegir entre un catálogo completo de
# varias asignaturas a la vez — más opciones irrelevantes es más superficie
# para que proponga algo que no corresponde.
MAX_CANDIDATOS = 40

SISTEMA = (
    "Eres un asistente que ayuda a un docente a clasificar fragmentos de "
    "material de clase dentro de un catálogo curricular ya existente. Tu "
    "tarea es PROPONER, nunca decidir: el docente revisa y confirma cada "
    "sugerencia antes de que se use en algo. No inventes objetivos que no "
    "estén en la lista que se te entrega. Responde únicamente con un objeto "
    "JSON, en español, sin texto fuera del JSON."
)


class ErrorEtiquetado(Exception):
    """El fragmento no existe o no tiene texto: no hay nada que clasificar.

    No se usa para "el modelo no supo elegir" ni "el JSON llegó roto" — esos
    son resultados esperables de una sugerencia y quedan en
    `Sugerencia.error`, igual que `ResultadoValidacion.errores` no lanza
    excepción por una cápsula rechazada.
    """


@dataclass(slots=True)
class Sugerencia:
    """El resultado de pedirle al modelo una propuesta para un fragmento."""

    id_fragmento: int
    id_objetivo: int | None = None
    codigo_objetivo: str | None = None
    etiqueta_tematica: str | None = None
    motivo: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _candidatos(db: Session, documento: DocumentoFuente) -> list[ObjetivoAprendizaje]:
    """Objetivos activos, acotados a la asignatura del documento cuando se conoce.

    `DocumentoFuente.asignatura` es opcional (se completa al subir el archivo,
    no siempre se llena): si falta, se listan todos los objetivos activos —
    peor que nada, sigue siendo mejor que negarse a sugerir.
    """
    stmt = select(ObjetivoAprendizaje).where(ObjetivoAprendizaje.estado == "activo")
    if documento.asignatura:
        stmt = stmt.where(ObjetivoAprendizaje.asignatura == documento.asignatura)
    stmt = stmt.order_by(ObjetivoAprendizaje.unidad, ObjetivoAprendizaje.codigo_objetivo)
    return list(db.scalars(stmt.limit(MAX_CANDIDATOS)).all())


def _prompt_usuario(fragmento: Fragmento, candidatos: list[ObjetivoAprendizaje]) -> str:
    listado = "\n".join(
        f"- id {o.id_objetivo}: [{o.codigo_objetivo}] {o.unidad} — {o.tema}"
        + (f" ({o.descripcion})" if o.descripcion else "")
        for o in candidatos
    )
    return (
        "Catálogo de objetivos de aprendizaje disponibles:\n"
        f"{listado}\n\n"
        f"Fragmento a clasificar (documento «{fragmento.documento.titulo}», "
        f"página {fragmento.pagina_inicio}):\n"
        f'"""\n{fragmento.contenido_texto}\n"""\n\n'
        "Responde con exactamente este JSON, sin texto adicional:\n"
        '{"id_objetivo": <el id del catálogo de arriba que mejor corresponda al '
        'fragmento, o null si ninguno encaja>, "etiqueta_tematica": <3 a 6 '
        'palabras que resuman el tema del fragmento>, "motivo": <una oración '
        "explicando por qué ese objetivo, o por qué ninguno>}"
    )


def etiquetar_fragmento(db: Session, id_fragmento: int, *, cliente: ClienteLLM) -> Sugerencia:
    """Pide al modelo una sugerencia de objetivo y etiqueta para un fragmento.

    No hace `commit` de nada que no sea la propia sugerencia guardada en
    `metadatos_json`; ver el docstring del módulo sobre por qué eso no cuenta
    como "decidir".
    """
    fragmento = db.get(Fragmento, id_fragmento)
    if fragmento is None:
        raise ErrorEtiquetado(f"no existe el fragmento {id_fragmento}")
    if not (fragmento.contenido_texto or "").strip():
        raise ErrorEtiquetado(f"el fragmento {id_fragmento} no tiene texto que clasificar")

    candidatos = _candidatos(db, fragmento.documento)
    if not candidatos:
        motivo_sin_candidatos = (
            f"no hay objetivos activos en «{fragmento.documento.asignatura}» para "
            f"sugerir"
            if fragmento.documento.asignatura
            else "no hay objetivos de aprendizaje activos para sugerir"
        )
        return Sugerencia(id_fragmento=id_fragmento, error=motivo_sin_candidatos)

    mensajes = [
        Mensaje("system", SISTEMA),
        Mensaje("user", _prompt_usuario(fragmento, candidatos)),
    ]

    try:
        crudo = cliente.responder(mensajes)
        datos = extraer_json(crudo)
    except ErrorFormatoJSON as exc:
        return Sugerencia(
            id_fragmento=id_fragmento,
            error=f"el modelo no devolvió un JSON utilizable: {exc}",
        )

    disponibles = {o.id_objetivo: o for o in candidatos}
    objetivo_propuesto = None
    id_propuesto = datos.get("id_objetivo")
    if id_propuesto is not None:
        try:
            id_propuesto = int(id_propuesto)
        except (TypeError, ValueError):
            id_propuesto = None
        else:
            objetivo_propuesto = disponibles.get(id_propuesto)
            if objetivo_propuesto is None:
                # El modelo propuso un id fuera de la lista que se le dio: es el
                # mismo riesgo de "cita alucinada" que la regla 5 de
                # `generation/validator.py`, aplicado acá al catálogo
                # curricular en vez de a los fragmentos. Se descarta solo la
                # propuesta de objetivo — la etiqueta temática puede seguir
                # siendo útil aunque el modelo no haya sabido a qué objetivo
                # del catálogo asociarla.
                logger.warning(
                    "tagger: id_objetivo=%r propuesto para el fragmento %d no "
                    "está en el catálogo entregado (%d candidatos)",
                    datos.get("id_objetivo"),
                    id_fragmento,
                    len(candidatos),
                )

    etiqueta = datos.get("etiqueta_tematica")
    etiqueta = etiqueta.strip() if isinstance(etiqueta, str) else None
    motivo = datos.get("motivo")
    motivo = motivo.strip() if isinstance(motivo, str) else ""

    sugerencia = Sugerencia(
        id_fragmento=id_fragmento,
        id_objetivo=objetivo_propuesto.id_objetivo if objetivo_propuesto else None,
        codigo_objetivo=objetivo_propuesto.codigo_objetivo if objetivo_propuesto else None,
        etiqueta_tematica=etiqueta or None,
        motivo=motivo,
    )

    metadatos = dict(fragmento.metadatos_json or {})
    metadatos["sugerencia_llm"] = {
        "id_objetivo": sugerencia.id_objetivo,
        "codigo_objetivo": sugerencia.codigo_objetivo,
        "etiqueta_tematica": sugerencia.etiqueta_tematica,
        "motivo": sugerencia.motivo,
        "modelo": cliente.modelo,
    }
    fragmento.metadatos_json = metadatos
    db.commit()

    return sugerencia


def etiquetar_pendientes(
    db: Session,
    *,
    cliente: ClienteLLM,
    id_documento: int | None = None,
    limite: int = 20,
) -> list[Sugerencia]:
    """Etiqueta en lote los fragmentos pendientes que todavía no tienen objetivo.

    Se acota a `id_objetivo IS NULL`: uno ya asignado no necesita sugerencia,
    lo asignó una persona. Y a `estado_validacion = 'pendiente'`: lo ya
    validado o descartado quedó fuera del flujo de curación. `limite` existe
    por la misma razón que `LIMITE_BANDEJA` en el panel — cada fragmento cuesta
    una llamada real al modelo, y un lote sin techo sobre un documento grande
    puede tardar minutos y no es gratis.

    Un fragmento que falla (sin candidatos, JSON inservible) no interrumpe el
    lote: se recoge el error en su propia `Sugerencia` y se sigue con el
    resto, igual que hace `_generar_capsula_pura` en el simulador con cada
    columna del comparador V/A/R/K.

    Vuelve a pedir sugerencia para un fragmento ya sugerido antes si sigue sin
    objetivo asignado: es una decisión deliberada — el curador puede haber
    corregido el texto (`curation.editar_texto`) desde la última corrida y
    volver a etiquetar entrega una propuesta consistente con el texto actual,
    a costa de una llamada de más si simplemente se repite el clic.
    """
    stmt = (
        select(Fragmento)
        .where(Fragmento.id_objetivo.is_(None))
        .where(Fragmento.estado_validacion == "pendiente")
        .order_by(Fragmento.id_documento, Fragmento.numero_fragmento)
        .limit(limite)
    )
    if id_documento is not None:
        stmt = stmt.where(Fragmento.id_documento == id_documento)

    resultados: list[Sugerencia] = []
    for fragmento in db.scalars(stmt).all():
        try:
            resultados.append(
                etiquetar_fragmento(db, fragmento.id_fragmento, cliente=cliente)
            )
        except ErrorEtiquetado as exc:
            resultados.append(Sugerencia(id_fragmento=fragmento.id_fragmento, error=str(exc)))
    return resultados
