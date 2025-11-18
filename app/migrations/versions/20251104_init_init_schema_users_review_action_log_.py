from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "20251104_init"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("github_id", sa.String(32), nullable=False, unique=True),
        sa.Column("login", sa.String(100), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("avatar_url", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_users_github_id", "users", ["github_id"])

    op.create_table(
        "review",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("model_id", sa.String(64), nullable=False),
        sa.Column("language", sa.String(32), nullable=True),
        sa.Column("code", sa.Text, nullable=True),
        sa.Column("trigger", sa.String(32), nullable=True),
        sa.Column("result", mysql.JSON(), nullable=False),
        sa.Column("summary", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_review_user_id", "review", ["user_id"])
    op.create_index("ix_review_created_at", "review", ["created_at"])
    op.create_foreign_key(
        "fk_review_user", "review", "users",
        ["user_id"], ["id"], onupdate="CASCADE", ondelete="SET NULL"
    )

    op.create_table(
        "action_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("log_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("case_id", sa.String(64), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_action_user_id", "action_log", ["user_id"])
    op.create_index("ix_action_timestamp", "action_log", ["timestamp"])
    op.create_foreign_key(
        "fk_action_user", "action_log", "users",
        ["user_id"], ["id"], onupdate="CASCADE", ondelete="SET NULL"
    )

    op.execute("""
    CREATE OR REPLACE VIEW review_result AS
    SELECT
      r.id AS review_id,
      CAST(JSON_UNQUOTE(JSON_EXTRACT(r.result, '$.global_score')) AS DECIMAL(10,3)) AS global_score,
      CAST(JSON_UNQUOTE(JSON_EXTRACT(r.result, '$.model_score'))  AS DECIMAL(10,3)) AS model_score,
      JSON_EXTRACT(r.result, '$.categories') AS categories,
      COALESCE(r.summary, JSON_UNQUOTE(JSON_EXTRACT(r.result, '$.summary'))) AS summary
    FROM review r;
    """)

def downgrade():
    op.execute("DROP VIEW IF EXISTS review_result")
    op.drop_constraint("fk_action_user", "action_log", type_="foreignkey")
    op.drop_index("ix_action_timestamp", table_name="action_log")
    op.drop_index("ix_action_user_id", table_name="action_log")
    op.drop_table("action_log")

    op.drop_constraint("fk_review_user", "review", type_="foreignkey")
    op.drop_index("ix_review_created_at", table_name="review")
    op.drop_index("ix_review_user_id", table_name="review")
    op.drop_table("review")

    op.drop_index("ix_users_github_id", table_name="users")
    op.drop_table("users")
