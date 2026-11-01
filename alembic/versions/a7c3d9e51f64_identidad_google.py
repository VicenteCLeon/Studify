"""Identidad Google opcional y transacciones OAuth de un solo uso.

Revision ID: a7c3d9e51f64
Revises: f6b2c8d40e53
"""

import sqlalchemy as sa
from alembic import op

revision = 'a7c3d9e51f64'
down_revision = 'f6b2c8d40e53'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('estudiante', sa.Column('google_sub', sa.String(255), nullable=True))
    op.add_column('estudiante', sa.Column('google_email', sa.String(320), nullable=True))
    op.add_column('estudiante', sa.Column('google_nombre', sa.String(200), nullable=True))
    op.create_unique_constraint('uq_estudiante_google_sub', 'estudiante', ['google_sub'])
    op.create_table(
        'intento_google',
        sa.Column('estado_hash', sa.String(64), primary_key=True),
        sa.Column('nonce', sa.String(128), nullable=False),
        sa.Column('verificador', sa.String(128), nullable=False),
        sa.Column('expira', sa.DateTime(timezone=True), nullable=False),
        sa.Column('rol', sa.String(20), nullable=False),
        sa.Column('id_estudiante', sa.Integer(), sa.ForeignKey(
            'estudiante.id_estudiante', ondelete='CASCADE'
        ), nullable=True),
        sa.CheckConstraint("rol IN ('estudiante', 'control')", name='ck_intento_google_rol'),
    )
    op.create_index('ix_intento_google_expira', 'intento_google', ['expira'])


def downgrade():
    op.drop_table('intento_google')
    op.drop_constraint('uq_estudiante_google_sub', 'estudiante', type_='unique')
    op.drop_column('estudiante', 'google_nombre')
    op.drop_column('estudiante', 'google_email')
    op.drop_column('estudiante', 'google_sub')
