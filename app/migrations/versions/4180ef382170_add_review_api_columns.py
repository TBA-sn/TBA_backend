"""add review api columns

Revision ID: 4180ef382170
Revises: 7c067d8ff87d
Create Date: 2025-11-14 13:25:00.367583

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4180ef382170'
down_revision: Union[str, Sequence[str], None] = '7c067d8ff87d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
