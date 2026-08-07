"""Jerarquía de canales derivada del vector porcentual (cap. 17.2).

El sistema **no persiste** la clasificación del perfil: canal primario, canal
secundario y condición de multimodalidad se calculan en tiempo de consulta a
partir de los porcentajes, que son la única fuente de verdad. Así no puede
existir inconsistencia entre el vector guardado y su interpretación categórica
(principio rector del cap. 17).

---

**Nota sobre una ambigüedad del informe.** Dos capítulos definen la
multimodalidad de manera distinta:

- Cap. 10: «en caso de **empates o diferencias mínimas**» → bimodal. No
  cuantifica "mínima", y razona sobre los puntajes crudos.
- Cap. 11.1: «dos dimensiones con diferencia **≤ 10 puntos porcentuales**» →
  bimodal; «tres o más dimensiones **sobre el 20%**» → multimodal. Cuantificado,
  y sobre el vector porcentual.

Ambos criterios no son equivalentes: 10 puntos porcentuales sobre un total de
~16 selecciones equivalen a ~1,6 selecciones de diferencia, mientras que
"empate" exige diferencia 0. Este módulo implementa el criterio **cuantificado
del cap. 11.1** por ser el único reproducible, y deja el umbral como parámetro
para poder contrastar ambas lecturas contra los 43 diagnósticos reales cuando
se cargue el CSV. Si la tabla 16.2 no se reproduce, esta es la primera
discrepancia a revisar.
"""

from dataclasses import dataclass
from decimal import Decimal

from studify.vark.scoring import CANALES, PerfilVark

# Umbrales del cap. 11.1.
UMBRAL_BIMODAL = Decimal("10")  # diferencia máxima respecto del canal dominante
UMBRAL_MULTIMODAL = Decimal("20")  # piso de la fila 7, usado solo para contenido
MIN_CANALES_MULTIMODAL = 3

# **Criterio de activación de canales.** Un canal está activo si empata con el
# máximo o queda a una diferencia mínima de él (≤ UMBRAL_BIMODAL). Si quedan dos
# activos el perfil es bimodal; si quedan tres o más, multimodal. Es la fila 6 de
# la tabla 11.1 generalizada a más de dos canales, y coincide con el cap. 10:
# «el sistema define el perfil identificando el valor máximo […]; en caso de
# empates o diferencias mínimas, lo clasifica como multimodal (bimodal)».
#
# Se descartó usar la fila 7 («tres o más dimensiones sobre el 20%») para
# etiquetar, que era la implementación anterior. Ese umbral es absoluto y no
# relativo al máximo, de modo que un perfil como {0V, 21A, 21R, 58K} —dominado
# con claridad por K— quedaba marcado multimodal solo porque otros dos canales
# pasaban el 20%, pese a estar a 37 puntos del dominante. La fila 7 se conserva,
# pero como regla de **contenido** (qué bloques incluir en la cápsula), que es
# donde el informe la usa; ver `vark/rules.py`.

NOMBRES_CANAL = {
    "V": "visual",
    "A": "auditivo",
    "R": "lector_escritor",
    "K": "kinestesico",
}


@dataclass(frozen=True, slots=True)
class JerarquiaCanales:
    """Interpretación categórica derivada del vector porcentual.

    `etiqueta` usa orden alfabético (A+K, K+R, …) para poder contrastar
    directamente contra la tabla 16.2 del informe, que está tabulada así.
    `jerarquia` usa orden por puntaje descendente (K→A), que es como el cap.
    16.4 describe el perfil predominante y el orden en que el prompt debe
    priorizar los elementos instruccionales.
    """

    canal_primario: str
    canal_secundario: str
    canales_activos: tuple[str, ...]
    es_bimodal: bool
    es_multimodal: bool
    etiqueta: str
    jerarquia: str

    @property
    def es_unimodal(self) -> bool:
        return not (self.es_bimodal or self.es_multimodal)


def _ordenar_canales(perfil: PerfilVark) -> list[tuple[str, Decimal]]:
    """Canales de mayor a menor porcentaje.

    Desempata por el orden canónico V, A, R, K para que dos vectores idénticos
    produzcan siempre la misma jerarquía; sin esto el resultado dependería del
    orden de iteración y los tests serían intermitentes.
    """
    valores = perfil.como_dict()
    return sorted(valores.items(), key=lambda kv: (-kv[1], CANALES.index(kv[0])))


def derivar(
    perfil: PerfilVark,
    umbral_bimodal: Decimal = UMBRAL_BIMODAL,
    umbral_multimodal: Decimal = UMBRAL_MULTIMODAL,
) -> JerarquiaCanales:
    """Deriva la jerarquía de canales del cap. 17.2 aplicando las reglas 11.1.

    `umbral_multimodal` no interviene en la clasificación: se conserva en la
    firma porque la fila 7 de la tabla 11.1 sigue rigiendo el **contenido** de
    la cápsula (ver `vark/rules.py`) y para poder contrastar la lectura
    alternativa contra los 43 diagnósticos reales.
    """
    ordenados = _ordenar_canales(perfil)
    primario, pct_primario = ordenados[0]
    secundario = ordenados[1][0]

    # Activos: los que empatan con el máximo o quedan a una diferencia mínima.
    activos = tuple(
        c for c, pct in ordenados if (pct_primario - pct) <= umbral_bimodal
    )
    es_multimodal = len(activos) >= MIN_CANALES_MULTIMODAL
    es_bimodal = len(activos) == 2

    # Etiqueta en orden alfabético → comparable con la tabla 16.2.
    etiqueta = "+".join(sorted(activos))
    # Jerarquía en orden de peso → refleja la prioridad instruccional (cap. 16.4).
    jerarquia = "→".join(c for c, _ in ordenados if c in activos)

    return JerarquiaCanales(
        canal_primario=primario,
        canal_secundario=secundario,
        canales_activos=activos,
        es_bimodal=es_bimodal,
        es_multimodal=es_multimodal,
        etiqueta=etiqueta,
        jerarquia=jerarquia,
    )
