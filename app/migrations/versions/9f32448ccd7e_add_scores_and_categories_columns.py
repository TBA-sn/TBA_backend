"""add scores and categories columns

Revision ID: 9f32448ccd7e
Revises: 8dff0767a35b
Create Date: 2025-11-16 17:26:15.229690

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '9f32448ccd7e'
down_revision: Union[str, Sequence[str], None] = '8dff0767a35b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('action_log', 'timestamp',
               existing_type=mysql.DATETIME(),
               server_default=sa.text('now()'),
               existing_nullable=True)
    op.add_column('review', sa.Column('scores', sa.JSON(), nullable=True))
    op.add_column('review', sa.Column('categories', sa.JSON(), nullable=True))
    op.alter_column('review', 'created_at',
               existing_type=mysql.DATETIME(),
               server_default=sa.text('now()'),
               existing_nullable=False)
    op.alter_column('review', 'updated_at',
               existing_type=mysql.DATETIME(),
               server_default=sa.text('now()'),
               existing_nullable=False)
    op.alter_column('review_report', 'user_id',
               existing_type=mysql.INTEGER(),
               nullable=False)
    op.alter_column('review_report', 'created_at',
               existing_type=mysql.DATETIME(),
               server_default=sa.text('now()'),
               existing_nullable=False)
    op.alter_column('review_report', 'updated_at',
               existing_type=mysql.DATETIME(),
               server_default=sa.text('now()'),
               existing_nullable=False)
    op.alter_column('users', 'created_at',
               existing_type=mysql.DATETIME(),
               server_default=sa.text('now()'),
               existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('users', 'created_at',
               existing_type=mysql.DATETIME(),
               server_default=sa.text('CURRENT_TIMESTAMP'),
               existing_nullable=False)
    op.alter_column('review_report', 'updated_at',
               existing_type=mysql.DATETIME(),
               server_default=sa.text('CURRENT_TIMESTAMP'),
               existing_nullable=False)
    op.alter_column('review_report', 'created_at',
               existing_type=mysql.DATETIME(),
               server_default=sa.text('CURRENT_TIMESTAMP'),
               existing_nullable=False)
    op.alter_column('review_report', 'user_id',
               existing_type=mysql.INTEGER(),
               nullable=True)
    op.alter_column('review', 'updated_at',
               existing_type=mysql.DATETIME(),
               server_default=sa.text('CURRENT_TIMESTAMP'),
               existing_nullable=False)
    op.alter_column('review', 'created_at',
               existing_type=mysql.DATETIME(),
               server_default=sa.text('CURRENT_TIMESTAMP'),
               existing_nullable=False)
    op.drop_column('review', 'categories')
    op.drop_column('review', 'scores')
    op.alter_column('action_log', 'timestamp',
               existing_type=mysql.DATETIME(),
               server_default=sa.text('CURRENT_TIMESTAMP'),
               existing_nullable=True)
