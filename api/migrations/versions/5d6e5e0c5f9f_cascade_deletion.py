"""cascade deletion

Revision ID: 5d6e5e0c5f9f
Revises: 4ac31b3764d5
Create Date: 2024-11-01 15:55:14.528365

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d6e5e0c5f9f'
down_revision: Union[str, None] = '4ac31b3764d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('task_segments_task_id_fkey', 'task_segments', type_='foreignkey')

    op.create_foreign_key(
        'task_segments_task_id_fkey',
        'task_segments',
        'tasks',
        ['task_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('task_segments_task_id_fkey', 'task_segments', type_='foreignkey')

    op.create_foreign_key(
        'task_segments_task_id_fkey',
        'task_segments',
        'tasks',
        ['task_id'],
        ['id']
    )