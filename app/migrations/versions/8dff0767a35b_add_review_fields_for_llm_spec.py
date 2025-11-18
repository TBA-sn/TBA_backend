"""add review fields for llm spec

Revision ID: 8dff0767a35b
Revises: 4180ef382170
Create Date: 2025-11-14 16:51:34.578688

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = '8dff0767a35b'
down_revision: Union[str, Sequence[str], None] = '4180ef382170'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'review',
        'code_fingerprint',
        existing_type=mysql.VARCHAR(length=64),
        type_=sa.String(length=128),
        nullable=True,
    )
    op.alter_column(
        'review',
        'trigger',
        existing_type=mysql.VARCHAR(length=32),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.alter_column(
        'review',
        'status',
        existing_type=mysql.VARCHAR(length=32),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.alter_column(
        'review',
        'summary',
        existing_type=mysql.TEXT(),
        nullable=True,
    )
    op.alter_column(
        'review',
        'created_at',
        existing_type=mysql.DATETIME(),
        server_default=sa.text('now()'),
        existing_nullable=False,
    )
    op.alter_column(
        'review',
        'updated_at',
        existing_type=mysql.DATETIME(),
        server_default=sa.text('now()'),
        existing_nullable=False,
    )

    op.alter_column(
        'review_report',
        'created_at',
        existing_type=mysql.DATETIME(),
        server_default=sa.text('now()'),
        existing_nullable=False,
    )
    op.alter_column(
        'review_report',
        'updated_at',
        existing_type=mysql.DATETIME(),
        server_default=sa.text('now()'),
        existing_nullable=False,
    )

    op.drop_constraint(op.f('fk_review_report_user'), 'review_report', type_='foreignkey')
    op.create_foreign_key(None, 'review_report', 'users', ['user_id'], ['id'])

    op.alter_column(
        'users',
        'created_at',
        existing_type=mysql.DATETIME(),
        server_default=sa.text('now()'),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'users',
        'created_at',
        existing_type=mysql.DATETIME(),
        server_default=sa.text('CURRENT_TIMESTAMP'),
        existing_nullable=False,
    )

    op.drop_constraint(None, 'review_report', type_='foreignkey')
    op.create_foreign_key(
        op.f('fk_review_report_user'),
        'review_report',
        'users',
        ['user_id'],
        ['id'],
        onupdate='CASCADE',
        ondelete='SET NULL',
    )
    op.alter_column(
        'review_report',
        'updated_at',
        existing_type=mysql.DATETIME(),
        server_default=sa.text('CURRENT_TIMESTAMP'),
        existing_nullable=False,
    )
    op.alter_column(
        'review_report',
        'created_at',
        existing_type=mysql.DATETIME(),
        server_default=sa.text('CURRENT_TIMESTAMP'),
        existing_nullable=False,
    )


    op.alter_column(
        'review',
        'updated_at',
        existing_type=mysql.DATETIME(),
        server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        existing_nullable=False,
    )
    op.alter_column(
        'review',
        'created_at',
        existing_type=mysql.DATETIME(),
        server_default=sa.text('CURRENT_TIMESTAMP'),
        existing_nullable=False,
    )
    op.alter_column(
        'review',
        'summary',
        existing_type=mysql.TEXT(),
        nullable=False,
    )
    op.alter_column(
        'review',
        'status',
        existing_type=sa.String(length=20),
        type_=mysql.VARCHAR(length=32),
        existing_nullable=False,
    )
    op.alter_column(
        'review',
        'trigger',
        existing_type=sa.String(length=20),
        type_=mysql.VARCHAR(length=32),
        existing_nullable=False,
    )
    op.alter_column(
        'review',
        'code_fingerprint',
        existing_type=sa.String(length=128),
        type_=mysql.VARCHAR(length=64),
        nullable=False,
    )
