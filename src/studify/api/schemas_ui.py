"""Contratos de lo que la interfaz necesita y la API todavía no exponía.

Los agrega la migración a React (27-ago-2026). Ninguno es una función nueva: son
datos que la capa Jinja ya calculaba dentro de sus handlers y que, al vivir solo
ahí, dejaban al cliente sin forma de obtenerlos.

- El **instrumento** (los 16 ítems y sus alternativas) lo armaba `get_vark`.
- El **perfil legible** (barras, glosas, modalidad) lo armaba `get_profile`.
- La **corrección del quiz** la hacía `submit_activity`, que decidía en el
  servidor si la respuesta era correcta sin que `indice_correcta` viajara nunca
  al navegador. Ese es el punto que hay que preservar sí o sí.
"""

from pydantic import BaseModel, ConfigDict, Field

# --- Instrumento VARK ---------------------------------------------------------


class AlternativaItem(BaseModel):
    """Una alternativa, identificada por su **letra** y no por su canal.

    El cap. 17.1 justifica así la tabla `respuesta_vark`: la matriz de puntuación
    no se filtra al cliente, de modo que los perfiles se pueden recalcular sin
    volver a aplicar el cuestionario. Si acá viajara el canal, cualquiera podría
    responder mirando el código fuente.
    """

    letra: str
    texto: str


class ItemInstrumento(BaseModel):
    numero: int
    enunciado: str
    alternativas: list[AlternativaItem]


# --- Sesión del estudiante ----------------------------------------------------


class SesionEstudianteOut(BaseModel):
    """Quién está usando la aplicación, según la cookie firmada.

    `id_estudiante` es `None` cuando no hay sesión, y eso **no es un error**: es
    el estado normal de quien todavía no ha respondido el cuestionario. El
    cliente lo usa para decidir si muestra el cuestionario o el catálogo.
    """

    id_estudiante: int | None = None
    tiene_diagnostico: bool = False


# --- Perfil legible -----------------------------------------------------------


class BarraPerfil(BaseModel):
    canal: str
    nombre: str
    color: str
    ancho: str
    texto: str


class PesosPerfil(BaseModel):
    texto: float
    visual: float
    narrativo: float
    practico: float


class ConfiguracionLegible(BaseModel):
    recursos_visuales: int
    palabras_texto: int
    componentes_practicos: int
    tono: str
    pesos: PesosPerfil


class PerfilLegibleOut(BaseModel):
    """El perfil del estudiante tal como se muestra en pantalla.

    Muestra las dos mitades del cap. 11: el **vector porcentual** persistido
    (tabla 17.2) y la **configuración de contenido** que las reglas derivaron de
    él (tabla 17.4). La segunda es la que condiciona la cápsula, así que se
    expone explícita: es lo que permite comprobar que la adaptación existe antes
    siquiera de generar contenido.

    La jerarquía se **recalcula** desde el vector en vez de leerse de una
    columna, porque el cap. 17.2 prohíbe persistir la etiqueta del perfil.
    """

    id_diagnostico: int
    canales: list[BarraPerfil]
    canal_principal: str
    canal_primario: str
    canal_secundario: str
    modalidad: str
    explicacion: str
    configuracion: ConfiguracionLegible
    directivas: list[str]


# --- Actividad de cierre ------------------------------------------------------


class RespuestaActividadIn(BaseModel):
    """Lo que el estudiante contesta.

    `alternativa` es opcional porque las actividades `intentalo_tu` no tienen
    respuesta única que corregir.
    """

    alternativa: int | None = None


class ResultadoActividadOut(BaseModel):
    """El veredicto, calculado **en el servidor**.

    `estado` distingue tres situaciones que la pantalla muestra distinto:
    `ok` (acertó), `error` (falló) y `esperada` (actividad abierta, no hay nada
    que corregir; se muestra la respuesta esperada para contrastar).

    `correcta` solo viaja cuando el estudiante ya falló: mandarla siempre
    pondría la respuesta al alcance de quien mire la red antes de contestar.
    """

    estado: str = Field(description="ok | error | esperada")
    titulo: str
    retroalimentacion: str
    correcta: str | None = None
    numero_intento: int | None = None


# --- Catálogo y textos compartidos --------------------------------------------


class TextosUiOut(BaseModel):
    """Nombres y colores de canal, para que las dos interfaces no diverjan.

    Se expone en vez de copiarse al cliente porque ya pasó una vez: el gráfico
    del docente y el del estudiante tienen que usar el mismo color para el mismo
    canal, y duplicar el mapa en TypeScript garantiza que en algún momento
    dejen de coincidir.
    """

    model_config = ConfigDict(from_attributes=True)

    nombre_canal: dict[str, str]
    color_canal: dict[str, str]
    nombre_tono: dict[str, str]
