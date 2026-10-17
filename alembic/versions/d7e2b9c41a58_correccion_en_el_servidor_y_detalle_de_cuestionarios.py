"""corrección en el servidor y detalle de los cuestionarios

Revision ID: d7e2b9c41a58
Revises: c3a91f5e7d20
Create Date: 2026-10-17 12:00:00.000000

Tres cambios en `interaccion_quiz`, para que la métrica del panel mida lo que
dice medir (punto 3 de la revisión del 16-oct-2026):

- Columnas nuevas `aciertos`, `total_preguntas` y `detalle_json`: los
  cuestionarios (`quiz_multi`, `flashcards_y_quiz`) se guardan pregunta por
  pregunta. Antes solo quedaba «todas correctas».
- Los `flashcards` ya registrados pasan a «sin corrección» (`es_correcta`
  NULL): se guardaban como acierto por apretar «Terminé el repaso».
- Los `quiz_mc` ya registrados se recalculan contra `indice_correcta`: los que
  entraron por la API traían el `es_correcta` que declaraba el cliente. Sin
  alternativa guardada no hay cómo verificarlo, así que quedan en NULL.

Los cuestionarios ya registrados no tienen detalle por pregunta y quedan con
`aciertos` en NULL: el panel no los promedia.

El recálculo de datos no se deshace en el downgrade: los valores anteriores
eran los incorrectos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'd7e2b9c41a58'
down_revision: str | None = 'c3a91f5e7d20'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('interaccion_quiz', sa.Column('aciertos', sa.SmallInteger(), nullable=True))
    op.add_column(
        'interaccion_quiz', sa.Column('total_preguntas', sa.SmallInteger(), nullable=True)
    )
    op.add_column(
        'interaccion_quiz',
        sa.Column('detalle_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_check_constraint(
        'ck_interaccion_aciertos',
        'interaccion_quiz',
        'aciertos IS NULL OR (total_preguntas >= 1 AND aciertos BETWEEN 0 AND total_preguntas)',
    )

    op.execute(
        """
        UPDATE interaccion_quiz AS i
        SET es_correcta = NULL
        FROM microcapsula_generada AS m
        WHERE m.id_capsula = i.id_capsula
          AND m.mini_quiz_json ->> 'tipo' = 'flashcards'
        """
    )
    op.execute(
        """
        UPDATE interaccion_quiz AS i
        SET es_correcta = CASE
            WHEN i.alternativa_seleccionada IS NULL
              OR m.mini_quiz_json ->> 'indice_correcta' IS NULL THEN NULL
            ELSE i.alternativa_seleccionada = (m.mini_quiz_json ->> 'indice_correcta')::int
        END
        FROM microcapsula_generada AS m
        WHERE m.id_capsula = i.id_capsula
          AND m.mini_quiz_json ->> 'tipo' = 'quiz_mc'
        """
    )


def downgrade() -> None:
    op.drop_constraint('ck_interaccion_aciertos', 'interaccion_quiz', type_='check')
    op.drop_column('interaccion_quiz', 'detalle_json')
    op.drop_column('interaccion_quiz', 'total_preguntas')
    op.drop_column('interaccion_quiz', 'aciertos')

# NOTA: igual que en las migraciones anteriores, si se regenera con
# --autogenerate hay que borrar a mano las líneas de 'ix_fragmento_contenido_fts'.
