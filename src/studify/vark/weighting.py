"""Fórmulas de ponderación C_* del cap. 11.2.

Traducen el vector porcentual VARK en cuatro pesos continuos que describen el
énfasis instruccional de la microcápsula:

    C_texto     = 0.40·p_V + 0.55·p_A + 0.75·p_R + 0.50·p_K
    C_visual    = 0.45·p_V + 0.10·p_A + 0.15·p_R + 0.15·p_K
    C_narrativo = 0.05·p_V + 0.30·p_A + 0.05·p_R + 0.10·p_K
    C_practico  = 0.10·p_V + 0.05·p_A + 0.05·p_R + 0.25·p_K

Nota sobre la escala: los coeficientes de cada *fila* no suman 1, y los de cada
*columna* tampoco (V: 1.00, A: 1.00, R: 1.00, K: 1.00 — estos sí). En
consecuencia C_texto + C_visual + C_narrativo + C_practico = 100 para cualquier
vector de entrada válido, pero cada C_* por separado se mueve en un rango
acotado y **no** recorre 0–100. Por ejemplo C_visual solo alcanza 45 en el
extremo p_V=100, y C_narrativo nunca pasa de 30.

Esto importa para los cortes de `rules.py`: interpretar un C_* como si fuera un
porcentaje de 0 a 100 llevaría a umbrales mal calibrados. Los rangos reales,
calculados sobre los vértices del símplex (un canal al 100%), son:

    C_texto     ∈ [40, 75]
    C_visual    ∈ [10, 45]
    C_narrativo ∈ [ 5, 30]
    C_practico  ∈ [ 5, 25]
"""

from dataclasses import dataclass
from decimal import Decimal

from studify.vark.scoring import PerfilVark

# Matriz de coeficientes del cap. 11.2, indexada [componente][canal].
# Se declara explícita en vez de incrustada en las fórmulas para que quede
# contrastable línea a línea contra el informe.
COEFICIENTES: dict[str, dict[str, Decimal]] = {
    "texto": {
        "V": Decimal("0.40"),
        "A": Decimal("0.55"),
        "R": Decimal("0.75"),
        "K": Decimal("0.50"),
    },
    "visual": {
        "V": Decimal("0.45"),
        "A": Decimal("0.10"),
        "R": Decimal("0.15"),
        "K": Decimal("0.15"),
    },
    "narrativo": {
        "V": Decimal("0.05"),
        "A": Decimal("0.30"),
        "R": Decimal("0.05"),
        "K": Decimal("0.10"),
    },
    "practico": {
        "V": Decimal("0.10"),
        "A": Decimal("0.05"),
        "R": Decimal("0.05"),
        "K": Decimal("0.25"),
    },
}

# Rangos alcanzables por cada componente (mínimo y máximo sobre los vértices
# del símplex). Los usa `rules.py` para normalizar antes de aplicar cortes.
RANGOS: dict[str, tuple[Decimal, Decimal]] = {
    componente: (min(coefs.values()) * 100, max(coefs.values()) * 100)
    for componente, coefs in COEFICIENTES.items()
}

_CENTESIMA = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class PesosContenido:
    """Los cuatro C_* continuos (tabla 17.4, columnas `peso_*`)."""

    texto: Decimal
    visual: Decimal
    narrativo: Decimal
    practico: Decimal

    @property
    def total(self) -> Decimal:
        return self.texto + self.visual + self.narrativo + self.practico

    def como_dict(self) -> dict[str, Decimal]:
        return {
            "texto": self.texto,
            "visual": self.visual,
            "narrativo": self.narrativo,
            "practico": self.practico,
        }


def calcular_pesos(perfil: PerfilVark) -> PesosContenido:
    """Aplica las cuatro fórmulas del cap. 11.2 al vector porcentual."""
    p = perfil.como_dict()

    def componente(nombre: str) -> Decimal:
        coefs = COEFICIENTES[nombre]
        bruto = sum((coefs[canal] * p[canal] for canal in ("V", "A", "R", "K")), Decimal(0))
        return bruto.quantize(_CENTESIMA)

    return PesosContenido(
        texto=componente("texto"),
        visual=componente("visual"),
        narrativo=componente("narrativo"),
        practico=componente("practico"),
    )


def posicion_en_rango(componente: str, valor: Decimal) -> Decimal:
    """Normaliza un C_* a 0–1 dentro de su rango alcanzable.

    Sirve para razonar sobre "qué tan alto está este componente para lo que
    puede llegar a estar", que es lo que necesitan los cortes de `rules.py`.
    Un C_visual de 25 no es "un cuarto de énfasis visual": es 0.43 del rango
    [10, 45], o sea prácticamente la mitad de lo que el modelo permite.
    """
    minimo, maximo = RANGOS[componente]
    if valor <= minimo:
        return Decimal(0)
    if valor >= maximo:
        return Decimal(1)
    return (valor - minimo) / (maximo - minimo)
