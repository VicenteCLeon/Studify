"""Rol de estudiante para el grupo control del piloto.

Revision ID: f6b2c8d40e53
Revises: e5c1a7b39d42
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f6b2c8d40e53'
down_revision: str | None = 'e5c1a7b39d42'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('estudiante', sa.Column(
        'rol', sa.String(length=20), nullable=False, server_default='estudiante',
    ))
    op.create_check_constraint(
        'ck_estudiante_rol', 'estudiante', "rol IN ('estudiante', 'control')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_estudiante_rol', 'estudiante', type_='check')
    op.drop_column('estudiante', 'rol')
