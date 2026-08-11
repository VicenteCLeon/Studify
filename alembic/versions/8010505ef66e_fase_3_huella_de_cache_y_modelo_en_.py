"""fase 3: huella de cache y modelo en microcapsula

Revision ID: 8010505ef66e
Revises: 8eb6f0399fee
Create Date: 2026-08-11 17:56:20.461727
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '8010505ef66e'
down_revision: str | None = '8eb6f0399fee'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# CORRECCIÓN MANUAL SOBRE EL AUTOGENERATE. Alembic emitió, además de las dos
# columnas nuevas, un `drop_index('ix_fragmento_contenido_fts')` en el upgrade y
# su `create_index` en el downgrade — o sea, borrar el índice GIN de full-text
# search en español al migrar hacia adelante y recrearlo al retroceder.
#
# No es un cambio real del modelo: es el mismo defecto ya documentado en
# AVANCE.md §5, autogenerate **no ve los índices definidos por expresión**
# (`db/models.py` lo declara con `text("to_tsvector('spanish', …)")`), así que
# cree que sobra en la base y propone eliminarlo.
#
# Aplicarlo tal cual habría dejado al retriever de la Fase 2 haciendo seq scan
# sobre `fragmento` sin ningún error visible. Ambas líneas se quitaron; si
# alguien regenera esta migración, hay que volver a quitarlas.


def upgrade() -> None:
    op.add_column('microcapsula_generada', sa.Column('huella_generacion', sa.String(length=64), nullable=True))
    op.add_column('microcapsula_generada', sa.Column('modelo_llm', sa.String(length=60), nullable=True))
    op.create_index(op.f('ix_microcapsula_generada_huella_generacion'), 'microcapsula_generada', ['huella_generacion'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_microcapsula_generada_huella_generacion'), table_name='microcapsula_generada')
    op.drop_column('microcapsula_generada', 'modelo_llm')
    op.drop_column('microcapsula_generada', 'huella_generacion')
