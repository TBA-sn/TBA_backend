from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "drop_case_table"
down_revision = "2b4a22a5a39f"   # 바로 직전 리비전 ID로 바꿔!

def upgrade():
    # 안전하게 존재할 때만 드랍 (MySQL은 IF EXISTS 필요)
    op.execute("DROP TABLE IF EXISTS `case`")

def downgrade():
    # 필요시 복구 스켈레톤(진짜 되돌릴 일 없으면 비워도 됨)
    op.create_table(
        'case',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        # 최소 컬럼만 (원래 스키마 몰라도 복구용 스텁)
    )
