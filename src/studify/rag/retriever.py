"""Recuperación determinista sobre la base de conocimiento relacional.

Este módulo es la materialización del argumento central del cap. 13: **no hay
base vectorial ni embeddings**. La recuperación es una consulta SQL exacta sobre
identificadores curriculares, no una búsqueda de similitud espacial.

    «Las bases de datos vectoriales operan mediante búsquedas de similitud
    espacial, lo cual introduce un factor probabilístico que puede comprometer
    la precisión del material educativo. Un modelo relacional soluciona esta
    vulnerabilidad al mapear los fragmentos de conocimiento directamente a
    identificadores únicos asociados a los objetivos curriculares.» (cap. 13)

Consecuencia práctica: dos llamadas con los mismos argumentos devuelven siempre
los mismos fragmentos en el mismo orden. Por eso el `ORDER BY` termina con
claves únicas —sin un desempate total, Postgres puede devolver filas empatadas
en cualquier orden y la "recuperación determinista" dejaría de serlo.

El full-text search en español actúa **solo como filtro secundario** dentro de
un objetivo ya fijado. Nunca amplía el conjunto: no puede traer material de otro
objetivo por parecido textual, que es justamente lo que el proyecto descarta.
"""

from dataclasses import dataclass

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session, joinedload

from studify.db.models import DocumentoFuente, Fragmento

# Cuántos fragmentos se inyectan como contexto en el prompt maestro. Ocho
# fragmentos de ~180 palabras son ~1.400 palabras de contexto: suficiente para
# fundamentar una cápsula de 150–300 palabras sin diluir el foco temático.
LIMITE_POR_DEFECTO = 8

# Orden de preferencia de tipo de fragmento según el canal dominante del
# estudiante (tabla 11.1). No filtra: reordena. Un perfil visual ve primero las
# tablas y esquemas disponibles, pero si no hay ninguno recibe igual el texto —
# la alternativa sería devolver una cápsula vacía, que es peor.
PREFERENCIA_POR_CANAL: dict[str, tuple[str, ...]] = {
    "V": ("tabla", "esquema", "diagrama", "imagen"),
    "R": ("texto",),
    "A": ("texto",),
    "K": ("texto", "esquema"),
}

# La expresión debe coincidir **literalmente** con la del índice GIN definido en
# db/models.py (`ix_fragmento_contenido_fts`), o el planner no lo usa.
CONFIGURACION_FTS = "spanish"


@dataclass(frozen=True, slots=True)
class FragmentoRecuperado:
    """Un fragmento con la procedencia que la cápsula deberá citar.

    Lleva el documento y la página resueltos porque el contrato de la
    microcápsula (PLAN_DESARROLLO.md §3) exige que cada fuente citada indique
    `id_fragmento`, `documento` y `pagina`, y el validador de la Fase 3
    contrasta esas citas contra los fragmentos realmente inyectados.
    """

    id_fragmento: int
    texto: str
    tipo: str
    documento: str
    id_documento: int
    pagina_inicio: int | None
    pagina_fin: int | None
    etiqueta_tematica: str | None

    @property
    def cita(self) -> str:
        """Referencia legible para la trazabilidad del cap. 8.1."""
        if self.pagina_inicio is None:
            return self.documento
        if self.pagina_fin and self.pagina_fin != self.pagina_inicio:
            return f"{self.documento}, pp. {self.pagina_inicio}–{self.pagina_fin}"
        return f"{self.documento}, p. {self.pagina_inicio}"


def _base_validados(id_objetivo: int) -> Select:
    """Los dos filtros que ningún fragmento puede saltarse para llegar al prompt.

    1. `estado_validacion = 'validado'` — la barrera de curación del cap. 12.
    2. El documento de origen no está rechazado. Un documento se puede rechazar
       *después* de que sus fragmentos fueron validados (se descubre que estaba
       desactualizado, o que no era la versión oficial); sin esta condición,
       esos fragmentos seguirían alimentando cápsulas.

    Se filtra por estado del documento en negativo (`!= 'rechazado'`) y no en
    positivo (`== 'validado'`) a propósito: exigir el estado positivo haría que
    una curación fragmento a fragmento, sin marcar el documento completo,
    devolviera silenciosamente cero resultados.
    """
    return (
        select(Fragmento)
        .join(DocumentoFuente, Fragmento.id_documento == DocumentoFuente.id_documento)
        .where(Fragmento.id_objetivo == id_objetivo, *_filtros_recuperables())
    )


def _filtros_recuperables() -> tuple:
    """Las condiciones que hacen recuperable a un fragmento, en un solo lugar.

    Las comparte `inventario_por_objetivo`, que es lo que el panel del docente
    usa para decir si un tema tiene material. Si el panel las reescribiera por
    su cuenta, bastaría con que una de las dos se desincronizara para que la
    pantalla mostrara en verde un objetivo cuyo material el retriever ignora.
    """
    return (
        Fragmento.estado_validacion == "validado",
        DocumentoFuente.estado_curacion != "rechazado",
    )


def recuperar(
    db: Session,
    *,
    id_objetivo: int,
    canal_primario: str | None = None,
    consulta: str | None = None,
    limite: int = LIMITE_POR_DEFECTO,
) -> list[FragmentoRecuperado]:
    """Devuelve los fragmentos validados de un objetivo de aprendizaje.

    `canal_primario` reordena por tipo de recurso según el perfil VARK;
    `consulta` restringe por full-text search en español dentro del objetivo.
    Ninguno de los dos puede introducir material de otro objetivo.
    """
    stmt = _base_validados(id_objetivo).options(
        joinedload(Fragmento.documento)
    )

    if consulta and consulta.strip():
        vector = func.to_tsvector(CONFIGURACION_FTS, Fragmento.contenido_texto)
        pregunta = func.plainto_tsquery(CONFIGURACION_FTS, consulta)
        stmt = stmt.where(vector.op("@@")(pregunta))

    orden = []
    if canal_primario:
        preferidos = PREFERENCIA_POR_CANAL.get(canal_primario.upper(), ())
        if preferidos:
            # CASE que asigna 0 a los tipos preferidos (en su orden) y un valor
            # alto al resto, para que suban sin excluir a nadie.
            orden.append(
                case(
                    {tipo: i for i, tipo in enumerate(preferidos)},
                    value=Fragmento.tipo_fragmento,
                    else_=len(preferidos),
                )
            )

    # Desempate total y estable: sin estas dos claves, dos fragmentos con la
    # misma prioridad podrían salir en cualquier orden entre llamadas y la
    # recuperación dejaría de ser determinista.
    orden += [Fragmento.id_documento, Fragmento.numero_fragmento]

    filas = db.scalars(stmt.order_by(*orden).limit(limite)).unique().all()

    return [
        FragmentoRecuperado(
            id_fragmento=f.id_fragmento,
            texto=f.contenido_texto or "",
            tipo=f.tipo_fragmento,
            documento=f.documento.titulo,
            id_documento=f.id_documento,
            pagina_inicio=f.pagina_inicio,
            pagina_fin=f.pagina_fin,
            etiqueta_tematica=f.etiqueta_tematica,
        )
        for f in filas
    ]


def inventario_por_objetivo(db: Session) -> dict[int, dict[str, int]]:
    """Qué material recuperable tiene cada objetivo, desglosado por tipo.

    Una sola consulta para todos los objetivos: el panel del docente los recorre
    completos y preguntar objetivo por objetivo sería una consulta por fila.

    Aplica **los mismos filtros que `recuperar`**, incluido el del documento
    rechazado. Contar solo por `estado_validacion` —que es lo intuitivo— daría
    por cubierto un objetivo cuyos fragmentos vienen de un apunte retirado
    después de la curación: material aprobado que el retriever ya no mira.
    """
    stmt = (
        select(
            Fragmento.id_objetivo,
            Fragmento.tipo_fragmento,
            func.count().label("cantidad"),
        )
        .join(DocumentoFuente, Fragmento.id_documento == DocumentoFuente.id_documento)
        .where(Fragmento.id_objetivo.is_not(None), *_filtros_recuperables())
        .group_by(Fragmento.id_objetivo, Fragmento.tipo_fragmento)
    )
    inventario: dict[int, dict[str, int]] = {}
    for id_objetivo, tipo, cantidad in db.execute(stmt):
        inventario.setdefault(id_objetivo, {})[tipo] = cantidad
    return inventario


def tipos_preferidos_disponibles(tipos: dict[str, int]) -> dict[str, int]:
    """Cuántos fragmentos del tipo que prefiere cada canal hay en un objetivo.

    Ojo con la lectura: `PREFERENCIA_POR_CANAL` **reordena, no filtra**. Un cero
    acá no significa que ese perfil se quede sin cápsula —recibe el texto
    disponible—, sino que la adaptación se degrada: un estudiante visual sin
    tablas ni esquemas lee exactamente lo mismo que uno lecto-escritor, y la
    diferenciación que el proyecto quiere demostrar no se produce en ese tema.
    """
    return {
        canal: sum(tipos.get(tipo, 0) for tipo in preferidos)
        for canal, preferidos in PREFERENCIA_POR_CANAL.items()
    }


def contar_disponibles(db: Session, id_objetivo: int) -> int:
    """Cuántos fragmentos validados tiene un objetivo.

    Lo usa el catálogo para no ofrecerle al estudiante temas sobre los que el
    sistema todavía no puede generar nada: un objetivo con cero fragmentos
    validados produciría una cápsula sin fundamento o un error, y ambas cosas
    son peores que no mostrarlo.
    """
    return db.scalar(
        select(func.count()).select_from(_base_validados(id_objetivo).subquery())
    ) or 0
