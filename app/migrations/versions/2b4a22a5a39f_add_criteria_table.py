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

    # 0) 과거 잔재: case 테이블 있을 때만 정리
    conn.execute(text("DROP TABLE IF EXISTS `case`"))

    # 1) criteria_master 드랍 금지 (유지)
    # op.drop_index(op.f('name'), table_name='criteria_master')
    # op.drop_table('criteria_master')

    # 2) action_log: timestamp default(now)만 정리
    op.alter_column(
        "action_log",
        "timestamp",
        existing_type=mysql.DATETIME(),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )

    # 3) action_log: 과거 case FK/컬럼 정리 (존재할 때만)
    #    - fk_actionlog_case 드랍(있을 때만)
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

    #    - action_log.case_ref_id 컬럼 제거(있을 때만)
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

    # ⚠️ user_id NOT NULL / 인덱스 드랍은 건드리지 않는다
    # (FK/인덱스 충돌 및 1830/1553 방지)

    # 4) review: created_at default(now)
    op.alter_column(
        "review",
        "created_at",
        existing_type=mysql.DATETIME(),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )

    # 5) review: 과거 case FK/컬럼 정리 (존재할 때만)
    #    - fk_review_case 드랍(있을 때만)
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

    #    - review.criteria / review.case_ref_id 컬럼 제거(있을 때만)
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

    # 6) users: created_at default(now)
    op.alter_column(
        "users",
        "created_at",
        existing_type=mysql.DATETIME(),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )

    # ❌ 인덱스 드랍은 전부 생략 (특히 ix_action_user_id, ix_review_user_id)
    # ❌ criteria_master 드랍도 생략


def downgrade() -> None:
    """Best-effort downgrade (defaults back to CURRENT_TIMESTAMP; no case/idx recreation)."""
    # 기본 timestamp default만 원복
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
    # 나머지(과거 case 테이블/인덱스/구 FK/컬럼) 복구는 생략
