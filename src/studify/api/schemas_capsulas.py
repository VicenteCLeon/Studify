"""Contratos Pydantic de la generación de microcápsulas (Fase 3).

Reutiliza los tipos de `generation/schemas.py` en vez de redefinirlos: el
contrato que valida la salida del LLM y el que la API expone tienen que ser el
mismo objeto, o la UI terminaría renderizando una forma que el validador nunca
comprobó.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studify.generation.schemas import Actividad, BloqueContenido, Fuente

# De dónde salió la cápsula que se devuelve. Se expone porque cambia lo que el
# número significa: una latencia de 40 ms es un acierto de caché, no un modelo
# rapidísimo, y el bake-off de la Fase 3 tiene que poder separar ambas cosas.
OrigenCapsula = Literal["generada", "cache", "cache_compartido"]


class CapsulaIn(BaseModel):
    """Cuerpo de POST /api/capsulas."""

    id_estudiante: int
    id_objetivo: int


class CapsulaOut(BaseModel):
    """La microcápsula tal como la recibe la UI."""

    model_config = ConfigDict(from_attributes=True)

    id_capsula: int
    id_estudiante: int
    id_objetivo: int
    fecha_generacion: datetime
    estado_validacion: str

    titulo: str
    objetivo_aprendizaje: str
    contenido: list[BloqueContenido]
    actividad: Actividad
    fuentes: list[Fuente]

    origen: OrigenCapsula
    modelo_llm: str | None = None
    intentos: int | None = Field(
        default=None,
        description=(
            "Llamadas al modelo que costó esta cápsula. Solo viene cuando "
            "`origen` es 'generada'; es la métrica del criterio de término de "
            "la Fase 3."
        ),
    )
    segundos: float | None = None


class ResumenCapsulaOut(BaseModel):
    """Fila del historial, sin el contenido completo."""

    model_config = ConfigDict(from_attributes=True)

    id_capsula: int
    id_estudiante: int
    id_objetivo: int
    titulo: str
    estado_validacion: str
    modelo_llm: str | None = None
    fecha_generacion: datetime
