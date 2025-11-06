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
    """
    - review.user_id: NULL 허용 + FK 재정의 (ON DELETE SET NULL, ON UPDATE CASCADE)
    - action_log.user_id: NULL 허용 유지 + FK 재정의 (동일 정책)
    - action_log.log_id: NULL 값 채우고 NOT NULL + UNIQUE 보장
    * 위험한 DROP INDEX / DROP TABLE 일절 금지
    """
    conn = op.get_bind()

    # ─────────────────────────────────────────────────────────
    # review.user_id → nullable + FK 재정의
    # ─────────────────────────────────────────────────────────
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
        nullable=True,           # ← NULL 허용
        existing_nullable=True   # 안전을 위해 True로 둠 (기존이 NOT NULL이어도 문제 없음)
    )

    op.create_foreign_key(
        "fk_review_user",
        "review", "users",
        ["user_id"], ["id"],
        ondelete="SET NULL",
        onupdate="CASCADE",
    )

    # ─────────────────────────────────────────────────────────
    # action_log.user_id → nullable 유지 + FK 재정의
    #   (SET NULL 정책이므로 절대 NOT NULL로 바꾸지 말 것)
    # ─────────────────────────────────────────────────────────
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

    # nullable 보정 (이미 nullable이면 no-op)
    op.alter_column(
        "action_log", "user_id",
        existing_type=sa.Integer(),
        nullable=True,           # ← 반드시 nullable
        existing_nullable=True
    )

    op.create_foreign_key(
        "fk_action_user",
        "action_log", "users",
        ["user_id"], ["id"],
        ondelete="SET NULL",
        onupdate="CASCADE",
    )

    # ─────────────────────────────────────────────────────────
    # action_log.log_id → NULL 채우고 NOT NULL + UNIQUE
    # ─────────────────────────────────────────────────────────
    # MySQL UUID()는 36자 문자열이므로 VARCHAR(64)에 안전
    op.execute("UPDATE action_log SET log_id = CONCAT('lg-', UUID()) WHERE log_id IS NULL")

    op.alter_column(
        "action_log", "log_id",
        existing_type=sa.String(length=64),
        nullable=False
    )

    # 유니크 제약 추가 (이미 있으면 예외 무시)
    try:
        op.create_unique_constraint("uq_action_log_log_id", "action_log", ["log_id"])
    except Exception:
        pass

    # ⚠️ 그 외 자동 생성됐던 컬럼 타입/디폴트 변경, 인덱스 드랍/생성 등은
    #    안전을 위해 여기서 수행하지 않음. 실제로 필요하면 별도 리비전에서 개별 적용해.


def downgrade() -> None:
    """
    최소 롤백:
    - action_log.log_id UNIQUE 제거, nullable 복원
    - action_log.user_id FK 제거, (원복을 원한다면) NOT NULL 복원
    - review.user_id FK 제거, NOT NULL 복원
    """
    # UNIQUE 제거 (있으면)
    try:
        op.drop_constraint("uq_action_log_log_id", "action_log", type_="unique")
    except Exception:
        pass

    op.alter_column(
        "action_log", "log_id",
        existing_type=sa.String(length=64),
        nullable=True
    )

    # action_log.user_id FK 제거 후 NOT NULL 복원(이전 스키마를 따른다고 가정)
    try:
        op.drop_constraint("fk_action_user", "action_log", type_="foreignkey")
    except Exception:
        pass

    op.alter_column(
        "action_log", "user_id",
        existing_type=sa.Integer(),
        nullable=False
    )

    # review.user_id FK 제거 후 NOT NULL 복원
    try:
        op.drop_constraint("fk_review_user", "review", type_="foreignkey")
    except Exception:
        pass

    op.alter_column(
        "review", "user_id",
        existing_type=sa.Integer(),
        nullable=False
    )
