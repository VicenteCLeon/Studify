"""Perfil efectivo de contenido: individual o agregado fijo del grupo control.

La referencia es la media de los 43 vectores porcentuales del CSV original
(`data/data_cuestionarios_43.csv`), con el mismo peso por persona. Se redondeó
a centésimas por resto mayor, igual que en `scoring.py`. No se consulta la
cohorte viva: nuevos registros y reintentos no deben cambiar el grupo control.
No representa un diagnóstico individual ni se guarda como tal.
"""

from decimal import Decimal

from studify.db.models import DiagnosticoVark, Estudiante
from studify.vark.scoring import PerfilVark

VERSION_PERFIL_CONTROL = "control-cohorte43-v1"
PERFIL_CONTROL = PerfilVark(
    v=Decimal("19.12"), a=Decimal("27.11"),
    r=Decimal("25.56"), k=Decimal("28.21"),
)


def perfil_de_contenido(
    estudiante: Estudiante, diagnostico: DiagnosticoVark | None
) -> PerfilVark | None:
    """Resuelve el perfil en el servidor, sin aceptar decisiones del cliente."""
    if estudiante.rol == "control":
        return PERFIL_CONTROL
    if diagnostico is None:
        return None
    return PerfilVark(
        v=diagnostico.porcentaje_v, a=diagnostico.porcentaje_a,
        r=diagnostico.porcentaje_r, k=diagnostico.porcentaje_k,
    )
