"""Reglas de decisión de la tabla 11.1 → `configuracion_contenido` (tabla 17.4).

Este módulo cierra la **decisión pendiente n.º 1** de `PLAN_DESARROLLO.md` §6:
las fórmulas del cap. 11.2 producen valores continuos, pero la tabla 17.4
persiste enteros (`recursos_visuales`, `palabras_texto`,
`componentes_practicos`). Faltaban los cortes.

**Criterio adoptado y por qué.** El plan proponía cortar sobre los C_*
(`recursos_visuales = 0 si C_visual < 15, 1 si < 25, 2 si ≥ 25`). Se descarta:
la tabla 11.1 del informe está escrita sobre los **porcentajes VARK crudos**
(«p_V ≥ 40% → al menos dos recursos visuales»), no sobre los C_*. Cortar sobre
C_visual daría resultados distintos a los que el informe especifica —un perfil
con p_V = 40% exacto produce C_visual = 24,5, que con el corte propuesto daría
1 recurso visual y no los 2 que exige la tabla 11.1.

Por lo tanto:

- Las **cantidades discretas** (`recursos_visuales`, `componentes_practicos`)
  salen directamente de los umbrales sobre p_V y p_K de la tabla 11.1. Es
  transcripción del informe, no una decisión nueva.
- Los **pesos continuos** (`peso_*`) se guardan tal cual salen del cap. 11.2.
- `palabras_texto` sí necesita un corte inventado, porque el informe solo fija
  el rango global 150–300 (cap. 11.1) sin decir cómo repartirlo. Se interpola
  linealmente sobre la posición de C_texto dentro de su rango alcanzable
  [40, 75]: un perfil puramente lector/escritor pide las 300 palabras, uno
  puramente visual las 150, y el resto queda en proporción. Es el único
  parámetro de este módulo que no está determinado por el informe; aprobado
  por el equipo el 06-ago-2026 (ver AVANCE.md §2 bis).
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from studify.vark.hierarchy import JerarquiaCanales, derivar
from studify.vark.scoring import PerfilVark
from studify.vark.weighting import (
    PesosContenido,
    calcular_pesos,
    posicion_en_rango,
)

# Umbrales de la tabla 11.1.
UMBRAL_ALTO = Decimal("40")  # "p_X ≥ 40%"
UMBRAL_VISUAL_MEDIO = Decimal("25")  # "25% ≤ p_V < 40%"

# Rango de extensión textual del cap. 11.1.
PALABRAS_MIN = 150
PALABRAS_MAX = 300

# Tonos instruccionales de la tabla 17.4 (`tono_narrativo`, VARCHAR(20)).
TONO_ORAL = "oral"
TONO_FORMAL = "formal"
TONO_PRACTICO = "practico"
TONO_ESPACIAL = "espacial"
TONO_MIXTO = "mixto"

# Tono asociado a cada canal según los perfiles descritos en el cap. 11.2.
TONO_POR_CANAL = {
    "A": TONO_ORAL,
    "R": TONO_FORMAL,
    "K": TONO_PRACTICO,
    "V": TONO_ESPACIAL,
}


@dataclass(frozen=True, slots=True)
class ConfiguracionGenerada:
    """Salida de las reglas: los campos de la tabla 17.4.

    Es un objeto puro, sin dependencia de la base de datos: se calcula desde el
    vector porcentual y recién después se persiste. Eso permite testear las
    reglas sin Postgres y recalcular configuraciones sin tocar la BD.
    """

    pesos: PesosContenido
    recursos_visuales: int
    palabras_texto: int
    componentes_practicos: int
    audio_activo: bool
    tono_narrativo: str
    canales_activos: str
    jerarquia: JerarquiaCanales

    # Directivas estructurales para el prompt maestro de la Fase 3. No se
    # persisten: se derivan de las mismas reglas al construir el prompt. Son
    # instrucciones sobre *qué bloques incluir*, no adjetivos de tono, que es
    # la mitigación acordada para el riesgo de que las cuatro cápsulas VARK
    # salgan indistinguibles (PLAN_DESARROLLO.md §5).
    directivas: tuple[str, ...]


def _cantidad_recursos_visuales(p_v: Decimal) -> int:
    """Tabla 11.1, filas 1 y 2 (sobre p_V, no sobre C_visual)."""
    if p_v >= UMBRAL_ALTO:
        return 2
    if p_v >= UMBRAL_VISUAL_MEDIO:
        return 1
    return 0


def _cantidad_componentes_practicos(p_k: Decimal) -> int:
    """Tabla 11.1, fila 5.

    Con p_K ≥ 40% el informe exige tres elementos concretos: ejemplo aplicado,
    secuencia paso a paso y actividad "inténtalo tú". Bajo ese umbral se
    conserva un componente práctico mínimo mientras el canal siga presente,
    porque el cap. 11.2 describe el kinestésico como aporte gradual y no como
    un interruptor.
    """
    if p_k >= UMBRAL_ALTO:
        return 3
    if p_k >= UMBRAL_VISUAL_MEDIO:
        return 2
    if p_k > 0:
        return 1
    return 0


def _palabras_objetivo(pesos: PesosContenido) -> int:
    """Interpola C_texto sobre el rango 150–300 del cap. 11.1.

    Único corte no especificado por el informe (ver docstring del módulo).
    """
    posicion = posicion_en_rango("texto", pesos.texto)
    bruto = Decimal(PALABRAS_MIN) + posicion * Decimal(PALABRAS_MAX - PALABRAS_MIN)
    return int(bruto.to_integral_value(rounding=ROUND_HALF_UP))


def _tono(perfil: PerfilVark, jerarquia: JerarquiaCanales) -> str:
    """Tono instruccional según el cap. 11.2.

    El cap. 11.2 asigna un tono a cada perfil (V→espacial, A→conversacional,
    R→formal, K→práctico) y la tabla 17.4 admite además "mixto".

    La regla de asignación tiene un orden deliberado, porque las reglas 1–5 y
    la 7 de la tabla 11.1 **se solapan**: un perfil como {0V, 21A, 21R, 58K}
    tiene tres canales sobre 20% (regla 7 → multimodal) y a la vez un canal
    sobre 40% (regla 5 → práctico). Tratarlo como "mixto" borraría el hecho de
    que K domina con 58%.

    Por eso: si algún canal alcanza el umbral alto, su tono manda; "mixto"
    queda reservado para los perfiles genuinamente planos, donde ningún canal
    llega a 40% y hay tres o más activos. Esto no contradice la regla 7 —el
    equilibrio de contenidos que ella pide se expresa en las directivas, que
    sí integran los cuatro registros.
    """
    p = perfil.como_dict()
    dominante = max(("V", "A", "R", "K"), key=lambda c: (p[c], -"VARK".index(c)))

    if p[dominante] >= UMBRAL_ALTO:
        return TONO_POR_CANAL[dominante]
    if jerarquia.es_multimodal:
        return TONO_MIXTO
    return TONO_POR_CANAL[jerarquia.canal_primario]


def _directivas(perfil: PerfilVark, jerarquia: JerarquiaCanales) -> tuple[str, ...]:
    """Traduce la tabla 11.1 en instrucciones estructurales para el prompt."""
    p = perfil.como_dict()
    directivas: list[str] = []

    if p["V"] >= UMBRAL_ALTO:
        directivas += ["incluir_mapa_conceptual", "tabla_comparativa", "estructura_jerarquica"]
    elif p["V"] >= UMBRAL_VISUAL_MEDIO:
        directivas.append("recurso_visual_complementario")

    if p["R"] >= UMBRAL_ALTO:
        directivas += ["encabezados_jerarquicos", "definiciones_exactas", "glosario"]

    if p["A"] >= UMBRAL_ALTO:
        directivas += ["tono_oral", "analogias_cotidianas", "preguntas_reflexivas"]

    if p["K"] >= UMBRAL_ALTO:
        directivas += ["ejemplo_resuelto", "paso_a_paso", "actividad_aplicada"]

    # Regla 7: un perfil multimodal pide una cápsula equilibrada «integrando
    # texto, apoyo visual, explicación narrativa y actividad práctica». Se
    # aplica siempre que el perfil sea multimodal, no solo cuando ninguna otra
    # regla disparó: un perfil como {33V, 33A, 0R, 33K} activa la regla 2 por
    # p_V ≥ 25% y se quedaría con un único recurso visual como toda directiva,
    # que es justamente lo contrario de una cápsula equilibrada.
    if jerarquia.es_multimodal:
        directivas += [
            "estructura_jerarquica",
            "analogias_cotidianas",
            "definiciones_exactas",
            "ejemplo_resuelto",
        ]

    # Red de seguridad: ningún perfil puede quedar sin directivas, porque el
    # prompt maestro quedaría sin instrucciones estructurales y el LLM
    # produciría una cápsula genérica. Se cae al canal primario.
    if not directivas:
        directivas += _DIRECTIVAS_POR_CANAL[jerarquia.canal_primario]

    # dict.fromkeys deduplica conservando el orden de aparición: las directivas
    # específicas del perfil quedan antes que las de equilibrio multimodal, y
    # ese orden es el que refleja la prioridad instruccional del cap. 16.4.
    return tuple(dict.fromkeys(directivas))


_DIRECTIVAS_POR_CANAL = {
    "V": ("incluir_mapa_conceptual", "tabla_comparativa", "estructura_jerarquica"),
    "A": ("tono_oral", "analogias_cotidianas", "preguntas_reflexivas"),
    "R": ("encabezados_jerarquicos", "definiciones_exactas", "glosario"),
    "K": ("ejemplo_resuelto", "paso_a_paso", "actividad_aplicada"),
}


def aplicar_reglas(perfil: PerfilVark) -> ConfiguracionGenerada:
    """Vector porcentual → configuración de contenido (tabla 11.1 → tabla 17.4)."""
    pesos = calcular_pesos(perfil)
    jerarquia = derivar(perfil)
    p = perfil.como_dict()

    return ConfiguracionGenerada(
        pesos=pesos,
        recursos_visuales=_cantidad_recursos_visuales(p["V"]),
        palabras_texto=_palabras_objetivo(pesos),
        componentes_practicos=_cantidad_componentes_practicos(p["K"]),
        # Fuera de alcance del prototipo: no hay TTS en el stack del cap. 14.
        # El canal auditivo se atiende con redacción conversacional (tono oral).
        # Decisión 2 de PLAN_DESARROLLO.md §6.
        audio_activo=False,
        tono_narrativo=_tono(perfil, jerarquia),
        canales_activos="".join(jerarquia.canales_activos),
        jerarquia=jerarquia,
        directivas=_directivas(perfil, jerarquia),
    )
