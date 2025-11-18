from alembic import op
import sqlalchemy as sa

revision = "drop_case_table"
down_revision = "2b4a22a5a39f"

def upgrade():
    op.execute("DROP TABLE IF EXISTS `case`")

def downgrade():
    op.create_table(
        'case',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
    )
