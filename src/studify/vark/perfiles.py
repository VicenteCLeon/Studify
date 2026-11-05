"""Perfil efectivo de contenido del grupo experimental.

La referencia es la media de los 43 vectores porcentuales del CSV original
(`data/data_cuestionarios_43.csv`), con el mismo peso por persona. Se redondeó
a centésimas por resto mayor, igual que en `scoring.py`. No se consulta la
cohorte viva: nuevos registros y reintentos no deben cambiar el grupo control.
No representa un diagnóstico individual ni se guarda como tal.

**Desde el 04-nov-2026 el control ya no usa este perfil.** Recibe una
cápsula básica sin adaptación VARK (`orchestrator.construir(config=None)`), en
la variante de caché `VARIANTE_CONTROL`, y desde el punto 2c (05-nov) tampoco
tiene perfil de contenido: `perfil_de_contenido` devuelve None para él. Cada
llamador ramifica por rol antes de pedirlo (generación, visor y perfil).
`PERFIL_CONTROL` queda solo como referencia de los tests que reproducen el
promedio desde el CSV.
"""

from decimal import Decimal

from studify.db.models import DiagnosticoVark, Estudiante
from studify.vark.scoring import PerfilVark

# Variante de caché de la cápsula básica del grupo control.
VARIANTE_CONTROL = "control-neutro-v1"

# Variante anterior (01-nov-2026), cuando el control generaba con PERFIL_CONTROL.
# Ya no se usa para generar; queda para identificar esas cápsulas antiguas, que
# siguen en la base pero no se reutilizan porque su huella es otra.
VERSION_PERFIL_CONTROL = "control-cohorte43-v1"
PERFIL_CONTROL = PerfilVark(
    v=Decimal("19.12"), a=Decimal("27.11"),
    r=Decimal("25.56"), k=Decimal("28.21"),
)


def perfil_de_contenido(
    estudiante: Estudiante, diagnostico: DiagnosticoVark | None
) -> PerfilVark | None:
    """Resuelve el perfil en el servidor, sin aceptar decisiones del cliente.

    El grupo control no tiene perfil (None), aunque tuviera un diagnóstico
    agregado por un proceso externo.
    """
    if estudiante.rol == "control":
        return None
    if diagnostico is None:
        return None
    return PerfilVark(
        v=diagnostico.porcentaje_v, a=diagnostico.porcentaje_a,
        r=diagnostico.porcentaje_r, k=diagnostico.porcentaje_k,
    )
