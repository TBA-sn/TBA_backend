"""baseline (no-op)

Revision ID: 2993ec8ed3a4
Revises: 20251104_init
Create Date: 2025-11-06 10:17:08.795986

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2993ec8ed3a4'
down_revision: Union[str, Sequence[str], None] = '20251104_init'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
