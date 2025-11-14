from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "7c067d8ff87d"
down_revision = "add_action_log_report_id"
branch_labels = None
depends_on = None


def upgrade():
    # 0) 기존 review 테이블 있으면 날리고 시작
    op.execute("DROP TABLE IF EXISTS review")

    # 1) 새 스펙대로 review 테이블 생성
    op.create_table(
        "review",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("code_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("aspects_json", sa.JSON(), nullable=False),
        sa.Column("total_steps", sa.Integer(), nullable=False),
        sa.Column("next_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("result_ref", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
            server_default=sa.text(
                "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ),
        ),
        sa.UniqueConstraint("request_hash", name="uq_review_request_hash"),
        mysql_charset="utf8mb4",
    )


def downgrade():
    op.drop_table("review")
