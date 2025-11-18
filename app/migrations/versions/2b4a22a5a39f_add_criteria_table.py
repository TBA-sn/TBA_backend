"""add criteria table (safe)

Revision ID: 2b4a22a5a39f
Revises: cd418cf91f90
Create Date: 2025-11-10 17:51:16.913907
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = "2b4a22a5a39f"
down_revision: Union[str, Sequence[str], None] = "cd418cf91f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema (safe: only-if-exists)."""
    from sqlalchemy import text

    conn = op.get_bind()

    conn.execute(text("DROP TABLE IF EXISTS `case`"))

    op.alter_column(
        "action_log",
        "timestamp",
        existing_type=mysql.DATETIME(),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )

    conn.execute(
        text(
            """
        SET @has_fk := (
          SELECT COUNT(*) FROM information_schema.referential_constraints
          WHERE constraint_schema = DATABASE()
            AND constraint_name = :fk
        );
    """
        ),
        {"fk": op.f("fk_actionlog_case")},
    )
    conn.execute(
        text(
            """
        SET @sql := IF(@has_fk > 0,
          CONCAT('ALTER TABLE `action_log` DROP FOREIGN KEY ', :fkname),
          'SELECT 1');
    """
        ),
        {"fkname": op.f("fk_actionlog_case")},
    )
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))

    conn.execute(
        text(
            """
        SET @col_exists := (
          SELECT COUNT(*) FROM information_schema.columns
          WHERE table_schema = DATABASE()
            AND table_name = 'action_log'
            AND column_name = 'case_ref_id'
        );
    """
        )
    )
    conn.execute(
        text(
            """
        SET @sql := IF(@col_exists > 0,
          'ALTER TABLE `action_log` DROP COLUMN `case_ref_id`',
          'SELECT 1');
    """
        )
    )
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))

    op.alter_column(
        "review",
        "created_at",
        existing_type=mysql.DATETIME(),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )

    conn.execute(
        text(
            """
        SET @has_fk := (
          SELECT COUNT(*) FROM information_schema.referential_constraints
          WHERE constraint_schema = DATABASE()
            AND constraint_name = :fk
        );
    """
        ),
        {"fk": op.f("fk_review_case")},
    )
    conn.execute(
        text(
            """
        SET @sql := IF(@has_fk > 0,
          CONCAT('ALTER TABLE `review` DROP FOREIGN KEY ', :fkname),
          'SELECT 1');
    """
        ),
        {"fkname": op.f("fk_review_case")},
    )
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))

    for col in ("criteria", "case_ref_id"):
        conn.execute(
            text(
                """
            SET @col_exists := (
              SELECT COUNT(*) FROM information_schema.columns
              WHERE table_schema = DATABASE()
                AND table_name = 'review'
                AND column_name = :col
            );
        """
            ),
            {"col": col},
        )
        conn.execute(
            text(
                """
            SET @sql := IF(@col_exists > 0,
              CONCAT('ALTER TABLE `review` DROP COLUMN `', :col, '`'),
              'SELECT 1');
        """
            ),
            {"col": col},
        )
        conn.execute(text("PREPARE stmt FROM @sql"))
        conn.execute(text("EXECUTE stmt"))
        conn.execute(text("DEALLOCATE PREPARE stmt"))

    op.alter_column(
        "users",
        "created_at",
        existing_type=mysql.DATETIME(),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )

def downgrade() -> None:
    """Best-effort downgrade (defaults back to CURRENT_TIMESTAMP; no case/idx recreation)."""
    op.alter_column(
        "users",
        "created_at",
        existing_type=mysql.DATETIME(),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        existing_nullable=False,
    )
    op.alter_column(
        "review",
        "created_at",
        existing_type=mysql.DATETIME(),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        existing_nullable=False,
    )
    op.alter_column(
        "action_log",
        "timestamp",
        existing_type=mysql.DATETIME(),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        existing_nullable=False,
    )
