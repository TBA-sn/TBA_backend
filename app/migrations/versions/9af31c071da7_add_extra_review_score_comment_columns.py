"""add extra review score/comment columns

Revision ID: 3e7b4a8a9c01
Revises: 2d0552dcc021
Create Date: 2025-11-22 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "3e7b4a8a9c01"
down_revision: Union[str, Sequence[str], None] = "2d0552dcc021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add new score/comment columns to review table."""

    # 이미 있는 컬럼은 다시 만들지 않고, 새로 추가된 애들만 만든다.
    # 점수 4개 (NOT NULL, 기본값 0)
    op.add_column(
        "review",
        sa.Column("score_performance", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "review",
        sa.Column("score_docs", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "review",
        sa.Column("score_dependency", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "review",
        sa.Column("score_testing", sa.Integer(), nullable=False, server_default="0"),
    )

    # 코멘트 4개 (NULL 허용)
    op.add_column("review", sa.Column("comment_performance", sa.Text(), nullable=True))
    op.add_column("review", sa.Column("comment_docs", sa.Text(), nullable=True))
    op.add_column("review", sa.Column("comment_dependency", sa.Text(), nullable=True))
    op.add_column("review", sa.Column("comment_testing", sa.Text(), nullable=True))

    # server_default 제거하고 싶으면 여기서 한 번 더 alter 해도 됨 (지금은 그냥 둬도 상관 없음)


def downgrade() -> None:
    """Downgrade schema: drop newly added columns."""
    op.drop_column("review", "comment_testing")
    op.drop_column("review", "comment_dependency")
    op.drop_column("review", "comment_docs")
    op.drop_column("review", "comment_performance")

    op.drop_column("review", "score_testing")
    op.drop_column("review", "score_dependency")
    op.drop_column("review", "score_docs")
    op.drop_column("review", "score_performance")
