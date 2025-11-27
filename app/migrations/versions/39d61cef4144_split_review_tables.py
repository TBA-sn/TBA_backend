"""split review table into meta, main, category_result

Revision ID: 20251127_split_review
Revises: f7b588bfd1de
Create Date: 2025-11-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251127_split_review"
down_revision = "f7b588bfd1de" 
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) review_meta 테이블 생성 (Meta 클래스 전용)
    op.create_table(
        "review_meta",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("github_id", sa.String(length=32), nullable=True, index=True),
        sa.Column("version", sa.String(length=10), nullable=False, server_default="v1"),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default="legacy"),
        sa.Column("language", sa.String(length=50), nullable=False, server_default="python"),
        sa.Column("trigger", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("code_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("audit", sa.JSON(), nullable=True),
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

    # 2) review_category_result 테이블 생성 (카테고리별 점수/코멘트)
    op.create_table(
        "review_category_result",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "review_id",
            sa.Integer(),
            sa.ForeignKey("review.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("category", sa.String(length=50), nullable=False, index=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
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

    # 3) review 테이블에 meta_id 컬럼 추가 (일단 NULL 허용)
    op.add_column(
        "review",
        sa.Column("meta_id", sa.Integer(), nullable=True, index=True),
    )

    # 4) 기존 review 레코드 기반으로 review_meta 채우기
    #    - id를 그대로 review_meta.id로 사용해서 1:1 매핑
    #    - language / trigger / model 값도 같이 옮김
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            INSERT INTO review_meta (
                id,
                github_id,
                version,
                actor,
                language,
                `trigger`,
                code_fingerprint,
                model,
                result,
                audit,
                created_at,
                updated_at
            )
            SELECT
                r.id,
                NULL AS github_id,
                'v1' AS version,
                'legacy' AS actor,
                r.language,
                r.`trigger`,
                NULL AS code_fingerprint,
                r.model,
                NULL AS result,
                NULL AS audit,
                r.created_at,
                r.updated_at
            FROM review AS r
            """
        )
    )

    # 5) review.meta_id = review.id 로 세팅 (review_meta id와 1:1)
    conn.execute(sa.text("UPDATE review SET meta_id = id"))

    # 6) FK 추가 + NOT NULL 로 변경
    op.create_foreign_key(
        "fk_review_meta",
        "review",
        "review_meta",
        ["meta_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("review", "meta_id", existing_type=sa.Integer(), nullable=False)

    # 7) 기존 카테고리별 점수/코멘트 데이터를 review_category_result로 이사
    #    각 review 레코드당 4행 (bug / maintainability / style / security)
    conn.execute(
        sa.text(
            """
            INSERT INTO review_category_result (
                review_id, category, score, comment, created_at, updated_at
            )
            SELECT id, 'bug', score_bug, comment_bug, created_at, updated_at
            FROM review
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO review_category_result (
                review_id, category, score, comment, created_at, updated_at
            )
            SELECT id, 'maintainability', score_maintainability, comment_maintainability, created_at, updated_at
            FROM review
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO review_category_result (
                review_id, category, score, comment, created_at, updated_at
            )
            SELECT id, 'style', score_style, comment_style, created_at, updated_at
            FROM review
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO review_category_result (
                review_id, category, score, comment, created_at, updated_at
            )
            SELECT id, 'security', score_security, comment_security, created_at, updated_at
            FROM review
            """
        )
    )

    # 8) review 테이블에서 이제 필요 없는 컬럼들 제거
    #    - model, trigger, language
    #    - score_*, comment_*
    op.drop_column("review", "model")
    op.drop_column("review", "trigger")
    op.drop_column("review", "language")

    op.drop_column("review", "score_bug")
    op.drop_column("review", "score_maintainability")
    op.drop_column("review", "score_style")
    op.drop_column("review", "score_security")

    op.drop_column("review", "comment_bug")
    op.drop_column("review", "comment_maintainability")
    op.drop_column("review", "comment_style")
    op.drop_column("review", "comment_security")


def downgrade() -> None:
    """
    완벽한 데이터 복원은 어렵지만, 스키마는 대충 되돌릴 수 있게 만들어 둔다.
    (카테고리 테이블에 있는 값들을 다시 review.* 컬럼으로 합치려면
     여기서 추가 SQL을 더 써야 함)
    """

    conn = op.get_bind()

    # 1) review 테이블에 예전 컬럼들 다시 추가
    op.add_column(
        "review",
        sa.Column("model", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "review",
        sa.Column("trigger", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "review",
        sa.Column("language", sa.String(length=50), nullable=True),
    )

    op.add_column(
        "review",
        sa.Column("score_bug", sa.Integer(), nullable=True),
    )
    op.add_column(
        "review",
        sa.Column("score_maintainability", sa.Integer(), nullable=True),
    )
    op.add_column(
        "review",
        sa.Column("score_style", sa.Integer(), nullable=True),
    )
    op.add_column(
        "review",
        sa.Column("score_security", sa.Integer(), nullable=True),
    )

    op.add_column(
        "review",
        sa.Column("comment_bug", sa.Text(), nullable=True),
    )
    op.add_column(
        "review",
        sa.Column("comment_maintainability", sa.Text(), nullable=True),
    )
    op.add_column(
        "review",
        sa.Column("comment_style", sa.Text(), nullable=True),
    )
    op.add_column(
        "review",
        sa.Column("comment_security", sa.Text(), nullable=True),
    )

    # 2) review.meta_id → review_meta 값들 적당히 다시 복원 (간단 버전)
    #    여기서는 language / trigger / model 정도만 backfill
    conn.execute(
        sa.text(
            """
            UPDATE review r
            JOIN review_meta m ON r.meta_id = m.id
            SET
              r.language = m.language,
              r.`trigger` = m.`trigger`,
              r.model = m.model
            """
        )
    )

    # 3) 카테고리 점수/코멘트도 역으로 합치고 싶으면 여기서 더 구현 가능
    #   (지금은 스키마만 복구해두고 데이터까지 완벽 복원은 안 함)

    # 4) review 테이블에서 meta_id FK/컬럼 제거
    op.drop_constraint("fk_review_meta", "review", type_="foreignkey")
    op.drop_column("review", "meta_id")

    # 5) review_category_result, review_meta 테이블 드롭
    op.drop_table("review_category_result")
    op.drop_table("review_meta")
