"""Origen del registro del estudiante (R2, «No soy yo»)

Revision ID: e5c1a7b39d42
Revises: d7e2b9c41a58
Create Date: 2026-10-24 15:00:00.000000

Una columna nullable en `estudiante`: cómo llegó a registrarse desde la web
('nuevo', 'tras_salir', 'otra_persona' o 'sesion_vencida'). Sirve para filtrar
posibles duplicados en el A/B, ya que sin cuenta una misma persona puede quedar
registrada dos veces. Las filas existentes quedan en NULL («antes de esta
columna»): no hay forma de saber de dónde salieron, así que no hay backfill.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'e5c1a7b39d42'
down_revision: str | None = 'd7e2b9c41a58'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('estudiante', sa.Column('origen_registro', sa.String(length=20), nullable=True))
    op.create_check_constraint(
        'ck_estudiante_origen_registro',
        'estudiante',
        "origen_registro IS NULL OR origen_registro IN "
        "('nuevo', 'tras_salir', 'otra_persona', 'sesion_vencida')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_estudiante_origen_registro', 'estudiante', type_='check')
    op.drop_column('estudiante', 'origen_registro')

# NOTA: igual que en las migraciones anteriores, si se regenera con
# --autogenerate hay que borrar a mano las líneas de 'ix_fragmento_contenido_fts'.
