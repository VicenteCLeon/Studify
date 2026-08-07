"""Contratos Pydantic de la API.

Separados de los modelos SQLAlchemy a propósito: lo que la API acepta y devuelve
no tiene por qué coincidir con cómo se guarda. El caso más claro es la jerarquía
de canales, que se **devuelve** al cliente pero no se persiste (cap. 17.2).
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LetraAlternativa = Literal["a", "b", "c", "d"]


# --- Entrada -----------------------------------------------------------------


class EstudianteIn(BaseModel):
    """Variables sociodemográficas del cap. 9 (tabla 17.1).

    Todas opcionales: el cuestionario VARK puede responderse sin identificarse,
    y el perfil se calcula igual. Solo `carrera` se usa para segmentar en el
    análisis de resultados, nunca para decidir cómo se genera una cápsula.
    """

    rango_etario: str | None = Field(default=None, max_length=20)
    genero: str | None = Field(default=None, max_length=50)
    carrera: str | None = Field(default=None, max_length=80)
    ano_ingreso: int | None = Field(default=None, ge=1950, le=2100)


class RespuestaItemIn(BaseModel):
    """Las alternativas marcadas en un ítem del instrumento.

    `alternativas` puede venir vacía: el cap. 10 permite dejar ítems en blanco
    cuando ninguna opción describe al estudiante. Y puede traer más de una: la
    selección múltiple es parte del diseño del instrumento, no una anomalía.
    """

    num_pregunta: int = Field(ge=1, le=16)
    alternativas: list[LetraAlternativa] = Field(default_factory=list)

    @model_validator(mode="after")
    def sin_alternativas_repetidas(self) -> "RespuestaItemIn":
        if len(set(self.alternativas)) != len(self.alternativas):
            raise ValueError(
                f"el ítem {self.num_pregunta} trae alternativas repetidas: "
                f"{self.alternativas}"
            )
        return self


class DiagnosticoIn(BaseModel):
    """Cuerpo de POST /api/diagnosticos.

    Se puede diagnosticar a un estudiante nuevo (enviando `estudiante`) o a uno
    ya registrado (enviando `id_estudiante`), pero no ambos: son dos formas
    excluyentes de decir a quién pertenece el diagnóstico.
    """

    id_estudiante: int | None = None
    estudiante: EstudianteIn | None = None
    respuestas: list[RespuestaItemIn] = Field(min_length=1)

    @model_validator(mode="after")
    def estudiante_nuevo_o_existente(self) -> "DiagnosticoIn":
        if self.id_estudiante is None and self.estudiante is None:
            raise ValueError(
                "hay que indicar 'id_estudiante' (estudiante ya registrado) o "
                "'estudiante' (datos para crear uno nuevo)"
            )
        if self.id_estudiante is not None and self.estudiante is not None:
            raise ValueError(
                "'id_estudiante' y 'estudiante' son excluyentes: el diagnóstico "
                "pertenece a un estudiante existente o a uno nuevo, no a ambos"
            )
        return self

    @model_validator(mode="after")
    def sin_items_duplicados(self) -> "DiagnosticoIn":
        vistos = [r.num_pregunta for r in self.respuestas]
        repetidos = {n for n in vistos if vistos.count(n) > 1}
        if repetidos:
            raise ValueError(
                f"los ítems {sorted(repetidos)} vienen más de una vez; las "
                f"selecciones múltiples van juntas en 'alternativas'"
            )
        return self


# --- Salida ------------------------------------------------------------------


class PuntajesOut(BaseModel):
    """Frecuencia absoluta por canal (tabla 17.2, `puntaje_*`)."""

    v: int
    a: int
    r: int
    k: int
    total: int


class PerfilOut(BaseModel):
    """Vector porcentual normalizado (tabla 17.2, `porcentaje_*`). Suma 100."""

    v: Decimal
    a: Decimal
    r: Decimal
    k: Decimal


class JerarquiaOut(BaseModel):
    """Derivada en tiempo de consulta, nunca persistida (cap. 17.2)."""

    canal_primario: str
    canal_secundario: str
    canales_activos: list[str]
    es_unimodal: bool
    es_bimodal: bool
    es_multimodal: bool
    etiqueta: str = Field(description="Orden alfabético, comparable con la tabla 16.2")
    jerarquia: str = Field(description="Orden por peso, como el cap. 16.4 (p. ej. K→A)")


class ConfiguracionOut(BaseModel):
    """Salida de las reglas del cap. 11.1 (tabla 17.4)."""

    model_config = ConfigDict(from_attributes=True)

    id_config: int | None = None

    peso_texto: Decimal
    peso_visual: Decimal
    peso_narrativo: Decimal
    peso_practico: Decimal

    recursos_visuales: int
    palabras_texto: int
    componentes_practicos: int
    audio_activo: bool
    tono_narrativo: str
    canales_activos: str

    directivas: list[str] = Field(
        description=(
            "Instrucciones estructurales para el prompt maestro de la Fase 3. "
            "No se persisten: se derivan de las mismas reglas."
        )
    )


class DiagnosticoOut(BaseModel):
    """Respuesta de POST /api/diagnosticos."""

    id_diagnostico: int
    id_estudiante: int
    puntajes: PuntajesOut
    perfil: PerfilOut
    jerarquia: JerarquiaOut
    configuracion: ConfiguracionOut
