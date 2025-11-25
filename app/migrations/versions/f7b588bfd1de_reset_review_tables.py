"""reset review tables

Revision ID: f7b588bfd1de
Revises: 3e7b4a8a9c01
Create Date: 2025-11-25 14:58:37.935128

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7b588bfd1de'
down_revision: Union[str, Sequence[str], None] = '3e7b4a8a9c01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ⚠️ 기존 review_detail 먼저 드랍 (FK 때문에 순서 중요)
    conn = op.get_bind()

    # 존재하면만 드랍 (MySQL 전용이라면 EXECUTE)
    # alembic에서 안전하게 가려면 그냥 try/except 대신 drop_table만 써도 됨.
    try:
        op.drop_table("review_detail")
    except Exception:
        pass

    try:
        op.drop_table("review")
    except Exception:
        pass

    # ─────────────────────────────────────────
    #  review 테이블 새로 생성
    # ─────────────────────────────────────────
    op.create_table(
        "review",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),

        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("trigger", sa.String(length=50), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=True),

        sa.Column("quality_score", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),

        sa.Column("score_bug", sa.Integer(), nullable=False),
        sa.Column("score_maintainability", sa.Integer(), nullable=False),
        sa.Column("score_style", sa.Integer(), nullable=False),
        sa.Column("score_security", sa.Integer(), nullable=False),

        sa.Column("comment_bug", sa.Text(), nullable=True),
        sa.Column("comment_maintainability", sa.Text(), nullable=True),
        sa.Column("comment_style", sa.Text(), nullable=True),
        sa.Column("comment_security", sa.Text(), nullable=True),

        sa.Column("status", sa.String(length=20), nullable=False, server_default="done"),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # 인덱스 (models에서 index=True였던 것들)
    op.create_index("ix_review_id", "review", ["id"])
    op.create_index("ix_review_user_id", "review", ["user_id"])

    # ─────────────────────────────────────────
    #  review_detail 테이블 새로 생성
    # ─────────────────────────────────────────
    op.create_table(
        "review_detail",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "review_id",
            sa.Integer(),
            sa.ForeignKey("review.id", ondelete="CASCADE"),
            nullable=False,
        ),

        sa.Column("issue_id", sa.String(length=50), nullable=True),
        sa.Column("issue_category", sa.String(length=100), nullable=False),
        sa.Column("issue_severity", sa.String(length=10), nullable=False),

        sa.Column("issue_summary", sa.String(length=255), nullable=False),
        sa.Column("issue_details", sa.Text(), nullable=True),

        sa.Column("issue_line_number", sa.Integer(), nullable=True),
        sa.Column("issue_column_number", sa.Integer(), nullable=True),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_review_detail_id", "review_detail", ["id"])
    op.create_index("ix_review_detail_review_id", "review_detail", ["review_id"])


def downgrade() -> None:
    # 되돌릴 때는 새 테이블만 드랍
    op.drop_index("ix_review_detail_review_id", table_name="review_detail")
    op.drop_index("ix_review_detail_id", table_name="review_detail")
    op.drop_table("review_detail")

    op.drop_index("ix_review_user_id", table_name="review")
    op.drop_index("ix_review_id", table_name="review")
    op.drop_table("review")