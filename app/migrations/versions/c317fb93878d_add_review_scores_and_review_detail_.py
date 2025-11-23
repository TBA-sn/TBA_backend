"""add review scores and review_detail table

Revision ID: 20251121_add_review_detail
Revises: <여기에_직전_리비전_ID_적기>
Create Date: 2025-11-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# 실제 환경에 맞게 수정
revision = "c317fb93878d"
down_revision = "9f32448ccd7e"
branch_labels = None
depends_on = None


def upgrade() -> None:

    with op.batch_alter_table("review") as batch_op:
        # 사용한 LLM 모델 이름 (예: "starcoder-15b")
        batch_op.add_column(sa.Column("model", sa.String(length=255), nullable=True))

        # 전체 품질 점수 (0~100)
        batch_op.add_column(sa.Column("quality_score", sa.Integer(), nullable=True))

        # 한 줄 요약(요약문)
        batch_op.add_column(sa.Column("summary", sa.Text(), nullable=True))

        # 카테고리별 점수
        batch_op.add_column(sa.Column("score_bug", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("score_maintainability", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("score_style", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("score_security", sa.Integer(), nullable=True))

    # 기존 row들에 기본값 채우고 싶으면 여기서 업데이트
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE review
            SET
              quality_score = COALESCE(quality_score, 0),
              summary = COALESCE(summary, ''),
              score_bug = COALESCE(score_bug, 0),
              score_maintainability = COALESCE(score_maintainability, 0),
              score_style = COALESCE(score_style, 0),
              score_security = COALESCE(score_security, 0)
            """
        )
    )

    # nullable=False로 바꾸고 싶으면 한 번 더 alter
    with op.batch_alter_table("review") as batch_op:
        batch_op.alter_column("quality_score", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("summary", existing_type=sa.Text(), nullable=False)
        batch_op.alter_column("score_bug", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("score_maintainability", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("score_style", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("score_security", existing_type=sa.Integer(), nullable=False)


    op.create_table(
        "review_detail",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "review_id",
            sa.BigInteger(),
            sa.ForeignKey("review.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
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

    op.create_index(
        "ix_review_detail_review_id",
        "review_detail",
        ["review_id"],
    )


def downgrade() -> None:
    # review_detail 먼저 제거
    op.drop_index("ix_review_detail_review_id", table_name="review_detail")
    op.drop_table("review_detail")

    # review 컬럼 롤백
    with op.batch_alter_table("review") as batch_op:
        batch_op.drop_column("score_security")
        batch_op.drop_column("score_style")
        batch_op.drop_column("score_maintainability")
        batch_op.drop_column("score_bug")
        batch_op.drop_column("summary")
        batch_op.drop_column("quality_score")
        batch_op.drop_column("model")
