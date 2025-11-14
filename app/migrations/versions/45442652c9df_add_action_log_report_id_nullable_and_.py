from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "add_action_log_report_id"
down_revision = "7e3eafe47c1f"  # 바로 직전 리비전 ID로 바꿔줘. (너의 최신 head)

def upgrade():
    conn = op.get_bind()

    # 1) 컬럼 없으면 추가
    conn.execute(text("""
        SET @col_exists := (
          SELECT COUNT(*) FROM information_schema.columns
          WHERE table_schema = DATABASE()
            AND table_name = 'action_log'
            AND column_name = 'report_id'
        );
    """))
    conn.execute(text("""
        SET @sql := IF(@col_exists = 0,
          'ALTER TABLE `action_log` ADD COLUMN `report_id` INT NULL',
          'SELECT 1');
    """))
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))

    # 2) 인덱스 없으면 추가
    conn.execute(text("""
        SET @has_idx := (
          SELECT COUNT(*) FROM information_schema.statistics
          WHERE table_schema = DATABASE()
            AND table_name = 'action_log'
            AND index_name = 'ix_action_log_report_id'
        );
    """))
    conn.execute(text("""
        SET @sql := IF(@has_idx = 0,
          'CREATE INDEX `ix_action_log_report_id` ON `action_log`(`report_id`)',
          'SELECT 1');
    """))
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))

    # 3) FK 없으면 추가 (review_report.id 참조, 삭제 시 SET NULL)
    conn.execute(text("""
        SET @has_fk := (
          SELECT COUNT(*)
          FROM information_schema.referential_constraints
          WHERE constraint_schema = DATABASE()
            AND table_name = 'action_log'
            AND constraint_name = 'fk_action_log_report'
        );
    """))
    conn.execute(text("""
        SET @sql := IF(@has_fk = 0,
          'ALTER TABLE `action_log` ADD CONSTRAINT `fk_action_log_report` \
             FOREIGN KEY (`report_id`) REFERENCES `review_report`(`id`) \
             ON DELETE SET NULL ON UPDATE CASCADE',
          'SELECT 1');
    """))
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))

def downgrade():
    conn = op.get_bind()

    # FK 있으면 드랍
    conn.execute(text("""
        SET @has_fk := (
          SELECT COUNT(*)
          FROM information_schema.referential_constraints
          WHERE constraint_schema = DATABASE()
            AND table_name = 'action_log'
            AND constraint_name = 'fk_action_log_report'
        );
    """))
    conn.execute(text("""
        SET @sql := IF(@has_fk > 0,
          'ALTER TABLE `action_log` DROP FOREIGN KEY `fk_action_log_report`',
          'SELECT 1');
    """))
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))

    # 인덱스 있으면 드랍
    conn.execute(text("""
        SET @has_idx := (
          SELECT COUNT(*) FROM information_schema.statistics
          WHERE table_schema = DATABASE()
            AND table_name = 'action_log'
            AND index_name = 'ix_action_log_report_id'
        );
    """))
    conn.execute(text("""
        SET @sql := IF(@has_idx > 0,
          'DROP INDEX `ix_action_log_report_id` ON `action_log`',
          'SELECT 1');
    """))
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))

    # 컬럼 있으면 드랍
    conn.execute(text("""
        SET @col_exists := (
          SELECT COUNT(*) FROM information_schema.columns
          WHERE table_schema = DATABASE()
            AND table_name = 'action_log'
            AND column_name = 'report_id'
        );
    """))
    conn.execute(text("""
        SET @sql := IF(@col_exists > 0,
          'ALTER TABLE `action_log` DROP COLUMN `report_id`',
          'SELECT 1');
    """))
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))
