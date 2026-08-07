"""Ampliar estudiante.genero a VARCHAR(50)

Revision ID: 8eb6f0399fee
Revises: ec6446cc3c52
Create Date: 2026-08-06 21:59:25.890568
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '8eb6f0399fee'
down_revision: str | None = 'ec6446cc3c52'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # La tabla 17.1 del informe declara genero VARCHAR(20), pero el propio
    # instrumento ofrece "No Binario / otra identidad" (27 caracteres).
    op.alter_column('estudiante', 'genero',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=50),
               existing_nullable=True)


def downgrade() -> None:
    # Ojo: revertir a VARCHAR(20) trunca —y por lo tanto falla— si ya hay
    # registros con la opción "No Binario / otra identidad".
    op.alter_column('estudiante', 'genero',
               existing_type=sa.String(length=50),
               type_=sa.VARCHAR(length=20),
               existing_nullable=True)

# NOTA: el autogenerate propuso además borrar 'ix_fragmento_contenido_fts' y
# recrearlo en el downgrade. Se eliminaron ambas líneas a mano: ese índice está
# definido por expresión en models.py y Alembic no lo detecta, así que lo lee
# como "sobra en la base de datos". Cualquier migración futura generada con
# --autogenerate va a proponer lo mismo; hay que borrar esas líneas cada vez.
