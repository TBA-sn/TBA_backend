"""add review_report and review.report_id

Revision ID: 4b8d8ba44037
Revises: 2b4a22a5a39f
Create Date: 2025-11-11 10:43:45.811707

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b8d8ba44037'
down_revision: Union[str, Sequence[str], None] = '2b4a22a5a39f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
