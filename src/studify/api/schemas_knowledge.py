"""Contratos Pydantic de la base de conocimiento (Fase 2).

En archivo aparte de `schemas.py` porque son dos dominios distintos: aquel
modela el perfilamiento del estudiante, este el material institucional. Nada
los relaciona hasta la Fase 3, cuando el generador cruza perfil y fragmentos.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EstadoFragmento = Literal["pendiente", "validado", "descartado"]
EstadoCuracion = Literal["pendiente", "validado", "rechazado"]


# --- Objetivos de aprendizaje ------------------------------------------------


class ObjetivoIn(BaseModel):
    """Alta de un objetivo del catálogo curricular (tabla 17.5)."""

    codigo_objetivo: str = Field(max_length=30)
    asignatura: str = Field(max_length=100)
    unidad: str = Field(max_length=100)
    tema: str = Field(max_length=150)
    descripcion: str | None = None
    nivel_taxonomico: str | None = Field(default=None, max_length=50)


class ObjetivoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_objetivo: int
    codigo_objetivo: str
    asignatura: str
    unidad: str
    tema: str
    descripcion: str | None = None
    nivel_taxonomico: str | None = None
    estado: str


class TemaDisponible(BaseModel):
    """Un objetivo tal como lo ve el estudiante en el catálogo.

    Incluye `fragmentos_disponibles` porque un objetivo sin material validado
    no puede generar una cápsula fundamentada: mostrarlo llevaría al estudiante
    a un error o —peor— a contenido inventado.
    """

    id_objetivo: int
    codigo_objetivo: str
    tema: str
    descripcion: str | None = None
    fragmentos_disponibles: int


class UnidadDisponible(BaseModel):
    unidad: str
    temas: list[TemaDisponible]


class AsignaturaDisponible(BaseModel):
    asignatura: str
    unidades: list[UnidadDisponible]


# --- Documentos ---------------------------------------------------------------


class DocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_documento: int
    titulo: str
    tipo_documento: str | None = None
    formato: str | None = None
    origen: str | None = None
    asignatura: str | None = None
    version: str | None = None
    estado_curacion: str
    fecha_carga: datetime


class IngestaOut(BaseModel):
    """Resultado de subir un documento a la base de conocimiento."""

    id_documento: int
    titulo: str
    total_fragmentos: int
    pagina_maxima: int
    palabras_totales: int
    mensaje: str = Field(
        default=(
            "Documento ingerido. Los fragmentos quedan en estado 'pendiente' "
            "hasta que se revisen y se les asigne un objetivo de aprendizaje."
        )
    )


# --- Fragmentos ---------------------------------------------------------------


class FragmentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_fragmento: int
    id_documento: int
    id_objetivo: int | None = None
    numero_fragmento: int
    tipo_fragmento: str
    contenido_texto: str | None = None
    pagina_inicio: int | None = None
    pagina_fin: int | None = None
    etiqueta_tematica: str | None = None
    estado_validacion: str


class FragmentoEnCuracion(FragmentoOut):
    """Fragmento con el contexto que el curador necesita para decidir."""

    documento_titulo: str
    objetivo_codigo: str | None = None
    palabras: int


class ValidarFragmentoIn(BaseModel):
    """Aprobación de un fragmento, opcionalmente asignando su objetivo."""

    id_objetivo: int | None = None


class EditarFragmentoIn(BaseModel):
    contenido_texto: str = Field(min_length=1)


class AsignarObjetivoIn(BaseModel):
    id_objetivo: int


class ResumenCuracionOut(BaseModel):
    id_documento: int
    pendiente: int
    validado: int
    descartado: int
    total: int


# --- Recuperación -------------------------------------------------------------


class FragmentoRecuperadoOut(BaseModel):
    """Lo que el retriever entrega al generador de la Fase 3."""

    id_fragmento: int
    texto: str
    tipo: str
    documento: str
    pagina_inicio: int | None = None
    pagina_fin: int | None = None
    etiqueta_tematica: str | None = None
    cita: str = Field(description="Referencia legible para la trazabilidad del cap. 8.1")
