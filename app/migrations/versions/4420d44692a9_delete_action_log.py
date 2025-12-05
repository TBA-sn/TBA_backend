"""delete action-log

Revision ID: 4420d44692a9
Revises: 9a2093da1d6c
Create Date: 2025-12-05 14:52:07.771255

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4420d44692a9'
down_revision: Union[str, Sequence[str], None] = '9a2093da1d6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # action_log 이 없을 수도 있으니까 안전하게 IF EXISTS 사용
    op.execute("DROP TABLE IF EXISTS action_log")

    op.create_table(
        "action_log",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("event_name", sa.String(length=255), nullable=True),
        sa.Column("properties", sa.JSON(), nullable=True),
        # FK 필요 없게 해놨으면 여기 없음
        # sa.ForeignKeyConstraint(
        #     ["user_id"],
        #     ["user.id"],
        #     name="fk_action_user",
        #     ondelete="SET NULL",
        # ),
    )

    op.create_index("ix_action_log_user_id", "action_log", ["user_id"])
    op.create_index("ix_action_log_timestamp", "action_log", ["timestamp"])

def downgrade() -> None:
    # 되돌릴 때는 그냥 action_log 제거 (필요하면 옛 스키마로 다시 생성)
    op.drop_index("ix_action_log_timestamp", table_name="action_log")
    op.drop_index("ix_action_log_user_id", table_name="action_log")
    op.drop_table("action_log")