"""Preferencia de voz del estudiante (narración del visor)

Revision ID: c3a91f5e7d20
Revises: aaf2d3de8b4e
Create Date: 2026-10-05 02:15:00.000000

Dos columnas nullable en `estudiante`: el género de la **voz** que prefiere oír
y el modo (calidad o rápida). NULL significa «sin preferencia» y se resuelve a
Dora (femenina, calidad) en `media/audio.py`, así que las filas existentes no
necesitan valor y no hay backfill.

Se llaman `voz_genero` y `voz_modo`, y no `genero`, porque `estudiante.genero`
ya existe y es el género sociodemográfico del estudiante, un dato sensible con
consentimiento expreso aparte (Ley 21.719). La preferencia de voz **no se
deduce** de ese dato ni lo toca.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'c3a91f5e7d20'
down_revision: str | None = 'aaf2d3de8b4e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('estudiante', sa.Column('voz_genero', sa.String(length=10), nullable=True))
    op.add_column('estudiante', sa.Column('voz_modo', sa.String(length=10), nullable=True))
    op.create_check_constraint(
        'ck_estudiante_voz_genero',
        'estudiante',
        "voz_genero IS NULL OR voz_genero IN ('femenina', 'masculina')",
    )
    op.create_check_constraint(
        'ck_estudiante_voz_modo',
        'estudiante',
        "voz_modo IS NULL OR voz_modo IN ('calidad', 'rapida')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_estudiante_voz_modo', 'estudiante', type_='check')
    op.drop_constraint('ck_estudiante_voz_genero', 'estudiante', type_='check')
    op.drop_column('estudiante', 'voz_modo')
    op.drop_column('estudiante', 'voz_genero')

# NOTA: igual que en las migraciones anteriores, si se regenera con
# --autogenerate hay que borrar a mano las líneas de 'ix_fragmento_contenido_fts'.
