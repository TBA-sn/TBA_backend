"""drop review_report table

Revision ID: a30b543ed83f
Revises: 20251127_split_review
Create Date: 2025-11-27 16:36:39.657048

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a30b543ed83f'
down_revision: Union[str, Sequence[str], None] = '20251127_split_review'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # review_report 테이블이 있으면 날림
    op.drop_table("review_report")


def downgrade() -> None:
    # 되돌릴 때를 위해 구조만 복원
    op.create_table(
        "review_report",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("summary", sa.String(length=1024), nullable=True),
        sa.Column("global_score", sa.Integer(), nullable=True),
        sa.Column("model_score", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )