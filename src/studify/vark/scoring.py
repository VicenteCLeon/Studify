"""Calificación del instrumento VARK: 16 ítems → puntajes crudos → vector porcentual.

Implementa la "Fase de Mapeo Algorítmico y Calificación Individual" del cap. 10:

1. Cada alternativa marcada se mapea a su canal sensorial (V, A, R o K).
2. Se acumula la **frecuencia absoluta** por canal → P_usuario = {P_V, P_A, P_R, P_K}.
3. Los puntajes crudos se normalizan a porcentajes que suman 100 (cap. 11.2).

Dos particularidades del instrumento, explícitas en el cap. 10, que condicionan
el diseño de este módulo:

- **Selección múltiple por ítem:** el estudiante puede marcar más de una
  alternativa, así que el total de selecciones no es 16 sino ≥ 0 y sin cota
  superior fija. Por eso la normalización divide por el total de selecciones y
  no por 16.
- **Ítems en blanco permitidos:** un estudiante puede no responder. El caso
  límite —ninguna selección en todo el instrumento— no tiene vector porcentual
  definido (sería 0/0) y se trata como error explícito, no como un vector de
  ceros que luego rompería las reglas de mapeo aguas abajo.
"""

from collections import Counter
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CANALES = ("V", "A", "R", "K")

# Escala de los porcentajes: DECIMAL(5,2) en la tabla 17.2.
_CENTESIMA = Decimal("0.01")
_CIEN = Decimal("100")


class ErrorDiagnosticoVacio(ValueError):
    """No hay ninguna selección: el perfil porcentual sería indeterminado (0/0)."""


@dataclass(frozen=True, slots=True)
class Seleccion:
    """Una alternativa marcada por el estudiante en un ítem del instrumento."""

    num_pregunta: int
    alternativa: str
    canal: str

    def __post_init__(self) -> None:
        if not 1 <= self.num_pregunta <= 16:
            raise ValueError(
                f"num_pregunta debe estar entre 1 y 16, se recibió {self.num_pregunta}"
            )
        if self.canal not in CANALES:
            raise ValueError(
                f"canal debe ser uno de {CANALES}, se recibió {self.canal!r}"
            )


@dataclass(frozen=True, slots=True)
class PuntajesVark:
    """Frecuencia absoluta de selecciones por canal (tabla 17.2, `puntaje_*`)."""

    v: int
    a: int
    r: int
    k: int

    @property
    def total(self) -> int:
        return self.v + self.a + self.r + self.k


@dataclass(frozen=True, slots=True)
class PerfilVark:
    """Vector porcentual normalizado (tabla 17.2, `porcentaje_*`).

    Es el **único** registro del perfil de aprendizaje: el sistema no persiste
    etiquetas como "visual" o "bimodal" (principio rector del cap. 17). Las
    interpretaciones categóricas se derivan en `studify.vark.hierarchy`.

    Invariante: v + a + r + k == 100 exactamente.
    """

    v: Decimal
    a: Decimal
    r: Decimal
    k: Decimal

    @property
    def total(self) -> Decimal:
        return self.v + self.a + self.r + self.k

    def como_dict(self) -> dict[str, Decimal]:
        return {"V": self.v, "A": self.a, "R": self.r, "K": self.k}


def acumular_puntajes(selecciones: list[Seleccion]) -> PuntajesVark:
    """Paso 2 del cap. 10: frecuencia absoluta de selecciones por canal."""
    conteo = Counter(s.canal for s in selecciones)
    return PuntajesVark(
        v=conteo["V"], a=conteo["A"], r=conteo["R"], k=conteo["K"]
    )


def normalizar_a_porcentajes(puntajes: PuntajesVark) -> PerfilVark:
    """Convierte los puntajes crudos en el vector porcentual del cap. 11.2.

    El informe exige `p_V + p_A + p_R + p_K = 100` como igualdad estricta, pero
    redondear cada canal por separado no lo garantiza: {1, 1, 1, 0} da tres
    veces 33.33 y suma 99.99.

    Se resuelve con el **método del resto mayor**: se reparte la diferencia
    residual (en centésimas) entre los canales cuya parte fraccionaria fue
    truncada, de mayor a menor. Así la suma da 100 exacto y el ajuste recae en
    los canales que más "perdieron" al redondear, en vez de cargarse siempre al
    mismo. Con eso el CHECK de la tabla `diagnostico_vark` nunca se dispara por
    un artefacto de redondeo.
    """
    if puntajes.total == 0:
        raise ErrorDiagnosticoVacio(
            "El diagnóstico no tiene ninguna selección: el vector porcentual "
            "es indeterminado. Revisar que el estudiante haya respondido al "
            "menos un ítem del instrumento."
        )

    total = Decimal(puntajes.total)
    crudos = {
        "V": Decimal(puntajes.v) / total * _CIEN,
        "A": Decimal(puntajes.a) / total * _CIEN,
        "R": Decimal(puntajes.r) / total * _CIEN,
        "K": Decimal(puntajes.k) / total * _CIEN,
    }

    # Truncar hacia abajo y medir cuánto se perdió en cada canal.
    truncados = {c: v.quantize(_CENTESIMA, rounding="ROUND_DOWN") for c, v in crudos.items()}
    residuo = _CIEN - sum(truncados.values())

    # Repartir el residuo de a una centésima, priorizando restos mayores.
    # Se desempata por el orden canónico V, A, R, K para que el resultado sea
    # determinista y reproducible entre corridas.
    faltan = int((residuo / _CENTESIMA).to_integral_value(rounding=ROUND_HALF_UP))
    orden = sorted(
        CANALES,
        key=lambda c: (-(crudos[c] - truncados[c]), CANALES.index(c)),
    )
    for i in range(faltan):
        truncados[orden[i % len(orden)]] += _CENTESIMA

    return PerfilVark(
        v=truncados["V"], a=truncados["A"], r=truncados["R"], k=truncados["K"]
    )


def calificar(selecciones: list[Seleccion]) -> tuple[PuntajesVark, PerfilVark]:
    """Flujo completo de calificación individual del cap. 10.

    Devuelve ambas representaciones porque la tabla 17.2 persiste las dos: los
    puntajes crudos permiten reproducir las tablas 16.2/16.3 del informe (que
    están expresadas en promedios de puntaje, no de porcentaje), y el vector
    porcentual es lo que consume el orquestador para armar el prompt.
    """
    puntajes = acumular_puntajes(selecciones)
    return puntajes, normalizar_a_porcentajes(puntajes)
