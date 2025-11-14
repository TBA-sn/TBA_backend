"""merge heads

Revision ID: 1809653bcfa9
Revises: 4b8d8ba44037, drop_case_table
Create Date: 2025-11-11 11:02:07.848386

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1809653bcfa9'
down_revision: Union[str, Sequence[str], None] = ('4b8d8ba44037', 'drop_case_table')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
