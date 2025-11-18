"""fix: review.user_id nullable + action_log.log_id unique

Revision ID: cd418cf91f90
Revises: 2993ec8ed3a4
Create Date: 2025-11-06 10:27:08.264401
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "cd418cf91f90"
down_revision: Union[str, Sequence[str], None] = "2993ec8ed3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    fk_name_review = conn.execute(text("""
        SELECT CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'review'
          AND COLUMN_NAME = 'user_id'
          AND REFERENCED_TABLE_NAME = 'users'
        LIMIT 1
    """)).scalar()

    if fk_name_review:
        op.drop_constraint(fk_name_review, "review", type_="foreignkey")

    op.alter_column(
        "review", "user_id",
        existing_type=sa.Integer(),
        nullable=True,
        existing_nullable=True
    )

    op.create_foreign_key(
        "fk_review_user",
        "review", "users",
        ["user_id"], ["id"],
        ondelete="SET NULL",
        onupdate="CASCADE",
    )

    fk_name_action = conn.execute(text("""
        SELECT CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'action_log'
          AND COLUMN_NAME = 'user_id'
          AND REFERENCED_TABLE_NAME = 'users'
        LIMIT 1
    """)).scalar()

    if fk_name_action:
        op.drop_constraint(fk_name_action, "action_log", type_="foreignkey")

    op.alter_column(
        "action_log", "user_id",
        existing_type=sa.Integer(),
        nullable=True,
        existing_nullable=True
    )

    op.create_foreign_key(
        "fk_action_user",
        "action_log", "users",
        ["user_id"], ["id"],
        ondelete="SET NULL",
        onupdate="CASCADE",
    )


    op.execute("UPDATE action_log SET log_id = CONCAT('lg-', UUID()) WHERE log_id IS NULL")

    op.alter_column(
        "action_log", "log_id",
        existing_type=sa.String(length=64),
        nullable=False
    )

    try:
        op.create_unique_constraint("uq_action_log_log_id", "action_log", ["log_id"])
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_constraint("uq_action_log_log_id", "action_log", type_="unique")
    except Exception:
        pass

    op.alter_column(
        "action_log", "log_id",
        existing_type=sa.String(length=64),
        nullable=True
    )

    
    try:
        op.drop_constraint("fk_action_user", "action_log", type_="foreignkey")
    except Exception:
        pass

    op.alter_column(
        "action_log", "user_id",
        existing_type=sa.Integer(),
        nullable=False
    )

    try:
        op.drop_constraint("fk_review_user", "review", type_="foreignkey")
    except Exception:
        pass

    op.alter_column(
        "review", "user_id",
        existing_type=sa.Integer(),
        nullable=False
    )
