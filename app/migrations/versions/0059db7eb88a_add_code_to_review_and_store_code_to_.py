"""add code to review and store_code to users

Revision ID: 0059db7eb88a
Revises: 4420d44692a9
Create Date: 2025-12-08 14:36:32.300374

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0059db7eb88a'
down_revision: Union[str, Sequence[str], None] = '4420d44692a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # review.code 추가
    op.add_column(
        "review",
        sa.Column("code", sa.Text(), nullable=True),
    )

    # users.store_code 추가
    op.add_column(
        "users",
        sa.Column(
            "store_code",
            sa.Boolean(),
            nullable=False,
            server_default="0",  # 또는 text("0")
        ),
    )


def downgrade() -> None:
    op.drop_column("review", "code")
    op.drop_column("users", "store_code")
