"""intentos de quiz numerados y actividades abiertas

Revision ID: 2fbc7391c0a3
Revises: 5e11a9cf4a0b
Create Date: 2026-08-12 17:41:46.206714

Deja `interaccion_quiz` en condiciones de sostener la métrica que el panel del
docente dice mostrar (Fase 5):

- `numero_intento` permite calcular el acierto **al primer intento**. Sin él,
  como el visor deja el formulario en pantalla tras la retroalimentación, quien
  reenvía hasta acertar sumaba un acierto igual que quien acertó de una.
- `es_correcta` y `alternativa_seleccionada` pasan a admitir NULL para poder
  registrar las actividades `intentalo_tu`, que no tienen respuesta corregible.
- La restricción única sobre (cápsula, intento) evita que dos peticiones
  simultáneas —un doble clic— dupliquen el mismo intento.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '2fbc7391c0a3'
down_revision: str | None = '5e11a9cf4a0b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# CORRECCIÓN MANUAL SOBRE EL AUTOGENERATE, la misma de `8010505ef66e` y
# `8eb6f0399fee`: alembic volvió a emitir un `drop_index` de
# `ix_fragmento_contenido_fts` en el upgrade y su `create_index` en el
# downgrade. No es un cambio del modelo — autogenerate no ve los índices
# definidos por expresión— y aplicarlo dejaría al retriever de la Fase 2
# haciendo seq scan sobre `fragmento` sin ningún error visible. Ambas líneas se
# quitaron; si alguien regenera esta migración, hay que volver a quitarlas.
#
# El `server_default` de `numero_intento` tampoco lo puso autogenerate: sin él,
# un `ADD COLUMN NOT NULL` falla en cualquier base que ya tenga respuestas
# registradas. Se aplica para las filas existentes —todas son un primer
# intento— y se retira enseguida, porque el valor lo pone el servidor al
# insertar y el modelo no declara default de base de datos.


def upgrade() -> None:
    op.add_column(
        'interaccion_quiz',
        sa.Column(
            'numero_intento', sa.SmallInteger(), nullable=False, server_default='1'
        ),
    )
    op.alter_column('interaccion_quiz', 'numero_intento', server_default=None)
    op.alter_column('interaccion_quiz', 'alternativa_seleccionada',
               existing_type=sa.SMALLINT(),
               nullable=True)
    op.alter_column('interaccion_quiz', 'es_correcta',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.create_unique_constraint('uq_interaccion_capsula_intento', 'interaccion_quiz', ['id_capsula', 'numero_intento'])
    op.create_check_constraint('ck_interaccion_numero_intento', 'interaccion_quiz', 'numero_intento >= 1')


def downgrade() -> None:
    # Deliberadamente no borra nada: si hay respuestas de actividades abiertas
    # (`es_correcta` nulo), el ALTER falla y hay que decidir a mano qué hacer
    # con esas filas. Perderlas en silencio sería peor que un downgrade roto.
    op.drop_constraint('ck_interaccion_numero_intento', 'interaccion_quiz', type_='check')
    op.drop_constraint('uq_interaccion_capsula_intento', 'interaccion_quiz', type_='unique')
    op.alter_column('interaccion_quiz', 'es_correcta',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.alter_column('interaccion_quiz', 'alternativa_seleccionada',
               existing_type=sa.SMALLINT(),
               nullable=False)
    op.drop_column('interaccion_quiz', 'numero_intento')
