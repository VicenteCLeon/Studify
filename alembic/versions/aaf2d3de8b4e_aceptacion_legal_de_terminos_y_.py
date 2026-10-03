"""aceptacion legal de terminos y privacidad

Revision ID: aaf2d3de8b4e
Revises: 2fbc7391c0a3
Create Date: 2026-10-02 23:38:04.241170

Agrega `aceptacion_legal`, la trazabilidad del consentimiento del marco legal
(02-oct-2026): qué versión de los Términos y de la Política de Privacidad
aceptó cada estudiante y cuándo (UTC), más el consentimiento expreso y
separado para el dato sensible de género. Es lo que permite demostrar el
consentimiento y volver a pedirlo cuando cambia la versión (`web/legal.py`).

Los estudiantes que ya existen quedan sin filas: no aceptaron nada todavía, así
que se les pide la aceptación la próxima vez que entren.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'aaf2d3de8b4e'
down_revision: str | None = '2fbc7391c0a3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# CORRECCIÓN MANUAL SOBRE EL AUTOGENERATE, la misma de `8010505ef66e`,
# `8eb6f0399fee` y `2fbc7391c0a3`: alembic volvió a emitir un `drop_index` de
# `ix_fragmento_contenido_fts` en el upgrade y su `create_index` en el
# downgrade. No es un cambio del modelo —autogenerate no ve los índices
# definidos por expresión— y aplicarlo dejaría al retriever haciendo seq scan
# sobre `fragmento`. Ambas líneas se quitaron; si alguien regenera esta
# migración, hay que volver a quitarlas.


def upgrade() -> None:
    op.create_table('aceptacion_legal',
    sa.Column('id_aceptacion', sa.Integer(), nullable=False),
    sa.Column('id_estudiante', sa.Integer(), nullable=False),
    sa.Column('documento', sa.String(length=20), nullable=False),
    sa.Column('version', sa.String(length=20), nullable=False),
    sa.Column('aceptado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("documento IN ('terminos', 'privacidad', 'genero')", name='ck_aceptacion_documento'),
    sa.ForeignKeyConstraint(['id_estudiante'], ['estudiante.id_estudiante'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id_aceptacion'),
    sa.UniqueConstraint('id_estudiante', 'documento', 'version', name='uq_aceptacion_estudiante_version')
    )
    op.create_index(op.f('ix_aceptacion_legal_id_estudiante'), 'aceptacion_legal', ['id_estudiante'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_aceptacion_legal_id_estudiante'), table_name='aceptacion_legal')
    op.drop_table('aceptacion_legal')
