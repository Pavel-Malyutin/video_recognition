"""add ondelete

Revision ID: 05a26dd30e00
Revises: 5d6e5e0c5f9f
Create Date: 2024-11-02 14:57:10.325522

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05a26dd30e00'
down_revision: Union[str, None] = '5d6e5e0c5f9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('recognition_results_segment_id_fkey', 'recognition_results', type_='foreignkey')
    op.create_foreign_key(None, 'recognition_results', 'task_segments', ['segment_id'], ['id'], ondelete='CASCADE')

def downgrade() -> None:
    op.drop_constraint(None, 'recognition_results', type_='foreignkey')
    op.create_foreign_key('recognition_results_segment_id_fkey', 'recognition_results', 'task_segments', ['segment_id'], ['id'])
