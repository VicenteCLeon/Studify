"""Contratos del panel del docente: analíticas y simulador (migración a React).

Estos esquemas no inventan datos: describen exactamente lo que
`studify.analytics` ya calculaba para las plantillas Jinja. Se escriben como
Pydantic —en vez de devolver los `dict` crudos— porque son el contrato que el
cliente TypeScript va a tipar, y un `dict` sin forma declarada convierte
cualquier cambio del backend en un error silencioso en el navegador.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from studify.generation.schemas import Actividad, BloqueContenido, Fuente

EstadoCobertura = Literal["sin_material", "escaso", "cubierto"]


# --- Analíticas ---------------------------------------------------------------


class ObjetivoResumen(BaseModel):
    """El objetivo dentro de una fila de cobertura, sin sus campos de gestión."""

    model_config = ConfigDict(from_attributes=True)

    id_objetivo: int
    codigo_objetivo: str
    asignatura: str
    unidad: str
    tema: str


class CanalCobertura(BaseModel):
    canal: str
    nombre: str
    cantidad: int
    # Hay material, pero nada del tipo que este canal aprovecha: la cápsula sale,
    # la adaptación no. Es el gap que el total esconde.
    degradado: bool


class TipoFragmentoConteo(BaseModel):
    tipo: str
    cantidad: int


class FilaCobertura(BaseModel):
    objetivo: ObjetivoResumen
    total: int
    tipos: list[TipoFragmentoConteo]
    canales: list[CanalCobertura]
    estado: EstadoCobertura


class FilaRendimiento(BaseModel):
    tema: str
    alumnos: int
    primeras: int
    aciertos: int
    abiertas: int
    reintentos: int
    # `None` y `0` no son lo mismo: sin quiz corregible no hay porcentaje que
    # mostrar, y un 0% diría que todos fallaron.
    porcentaje: float | None = None


class BarraCanal(BaseModel):
    canal: str
    nombre: str
    color: str
    ancho: str
    texto: str


class CapsulaHistorial(BaseModel):
    """Fila del historial de cápsulas del panel."""

    model_config = ConfigDict(from_attributes=True)

    id_capsula: int
    id_estudiante: int
    id_objetivo: int
    titulo: str
    estado_validacion: str
    modelo_llm: str | None = None
    fecha_generacion: datetime


class AnaliticasOut(BaseModel):
    """Todo lo que la pantalla de analíticas necesita, en una sola petición.

    Va junto y no en cuatro endpoints porque la pantalla los muestra siempre a
    la vez: separarlos obligaría al cliente a orquestar cuatro llamadas para
    pintar una sola vista, y a manejar el estado intermedio en que unas
    respondieron y otras no.
    """

    cobertura: list[FilaCobertura]
    sin_clasificar: int
    rendimiento: list[FilaRendimiento]
    vark_total: int
    vark_barras: list[BarraCanal]
    capsulas: list[CapsulaHistorial]


# --- Simulador ----------------------------------------------------------------


class SimulacionIn(BaseModel):
    id_objetivo: int
    # Solo para la generación de un canal suelto; la comparación recorre los
    # cuatro y no lo recibe.
    canal: str | None = None


class CapsulaSimulada(BaseModel):
    """La cápsula generada al vuelo. No se persiste: no tiene `id_capsula`.

    A diferencia de lo que ve el estudiante, acá la actividad viaja **entera**,
    con `indice_correcta` y `retroalimentacion`: el docente vino justamente a
    revisar la calidad de la pregunta, y no hay nada que responder porque la
    cápsula simulada no existe en la base.
    """

    # El simulador entrega una `Microcapsula` (el contrato de `generation/`), no
    # un dict: `from_attributes` deja convertirla sin volver a serializarla a
    # mano campo por campo, que es donde se colaría una diferencia entre lo que
    # valida el generador y lo que expone la API.
    model_config = ConfigDict(from_attributes=True)

    titulo: str
    objetivo_aprendizaje: str
    activacion: str
    concepto_central: str
    representacion_adaptativa: list[BloqueContenido]
    ejemplo: BloqueContenido
    actividad: Actividad
    fuentes: list[Fuente]


class ColumnaSimulacion(BaseModel):
    """Una columna del simulador: la cápsula de un canal, o el motivo del fallo.

    Misma forma en éxito y en error —solo cambia `error`— para que el cliente no
    tenga que distinguir dos estructuras. Cada canal falla por separado: si uno
    revienta, los otros tres se siguen mostrando.
    """

    model_config = ConfigDict(from_attributes=True)

    canal: str
    nombre_canal: str
    color_canal: str
    capsula: CapsulaSimulada | None = None
    palabras: int | None = None
    error: str | None = None
