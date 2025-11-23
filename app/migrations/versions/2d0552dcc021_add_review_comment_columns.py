"""add review comment columns

Revision ID: 2d0552dcc021
Revises: c317fb93878d
Create Date: 2025-11-22 17:18:32.595849

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '2d0552dcc021'
down_revision: Union[str, Sequence[str], None] = 'c317fb93878d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add comment columns, drop legacy score fields."""

    # 1) 리뷰 코멘트 컬럼 4개 추가
    op.add_column('review', sa.Column('comment_bug', sa.Text(), nullable=True))
    op.add_column('review', sa.Column('comment_maintainability', sa.Text(), nullable=True))
    op.add_column('review', sa.Column('comment_style', sa.Text(), nullable=True))
    op.add_column('review', sa.Column('comment_security', sa.Text(), nullable=True))

    # 2) 옛 필드들 정리
    #   - code, file_path, scores(JSON), categories(JSON), global/model score 등
    op.drop_index(op.f('ix_review_code_fingerprint'), table_name='review')

    op.drop_column('review', 'file_path')
    op.drop_column('review', 'categories')
    op.drop_column('review', 'global_score')
    op.drop_column('review', 'code_fingerprint')
    op.drop_column('review', 'scores')
    op.drop_column('review', 'model_score')
    op.drop_column('review', 'code')
    op.drop_column('review', 'efficiency_index')


def downgrade() -> None:
    """Downgrade schema: restore legacy fields, drop comment columns."""

    # 1) 옛 필드들 복구
    op.add_column('review', sa.Column('efficiency_index', mysql.FLOAT(), nullable=True))
    op.add_column('review', sa.Column('code', mysql.TEXT(), nullable=False))
    op.add_column('review', sa.Column('model_score', mysql.INTEGER(), nullable=True))
    op.add_column('review', sa.Column('scores', mysql.JSON(), nullable=True))
    op.add_column('review', sa.Column('code_fingerprint', mysql.VARCHAR(length=128), nullable=True))
    op.add_column('review', sa.Column('global_score', mysql.INTEGER(), nullable=True))
    op.add_column('review', sa.Column('categories', mysql.JSON(), nullable=True))
    op.add_column('review', sa.Column('file_path', mysql.VARCHAR(length=255), nullable=False))

    op.create_index(op.f('ix_review_code_fingerprint'), 'review', ['code_fingerprint'], unique=False)

    # 2) 새 코멘트 컬럼 제거
    op.drop_column('review', 'comment_security')
    op.drop_column('review', 'comment_style')
    op.drop_column('review', 'comment_maintainability')
    op.drop_column('review', 'comment_bug')
