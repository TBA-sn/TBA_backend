from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy import text

revision = "7e3eafe47c1f"
down_revision = "1809653bcfa9"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS `review_report` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `user_id` INT NULL,
            `model_id` VARCHAR(128) NOT NULL,
            `summary` VARCHAR(1024),
            `global_score` INT,
            `model_score` INT,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            CONSTRAINT `fk_review_report_user`
                FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
                ON DELETE SET NULL ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """))

    conn.execute(text("""
        SET @col_exists := (
          SELECT COUNT(*) FROM information_schema.columns
          WHERE table_schema = DATABASE()
            AND table_name = 'review'
            AND column_name = 'report_id'
        );
    """))
    conn.execute(text("""
        SET @sql := IF(@col_exists = 0,
          'ALTER TABLE `review` ADD COLUMN `report_id` INT NULL',
          'SELECT 1');
    """))
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))

    conn.execute(text("""
        SET @has_idx := (
          SELECT COUNT(*) FROM information_schema.statistics
          WHERE table_schema = DATABASE()
            AND table_name = 'review'
            AND index_name = 'ix_review_report_id'
        );
    """))
    conn.execute(text("""
        SET @sql := IF(@has_idx = 0,
          'CREATE INDEX `ix_review_report_id` ON `review`(`report_id`)',
          'SELECT 1');
    """))
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))

    conn.execute(text("""
        SET @has_fk := (
          SELECT COUNT(*)
          FROM information_schema.referential_constraints
          WHERE constraint_schema = DATABASE()
            AND table_name = 'review'
            AND constraint_name = 'fk_review_report'
        );
    """))
    conn.execute(text("""
        SET @sql := IF(@has_fk = 0,
          'ALTER TABLE `review` ADD CONSTRAINT `fk_review_report` \
             FOREIGN KEY (`report_id`) REFERENCES `review_report`(`id`) \
             ON DELETE SET NULL ON UPDATE CASCADE',
          'SELECT 1');
    """))
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))


def downgrade():
    conn = op.get_bind()

    conn.execute(text("""
        SET @has_fk := (
          SELECT COUNT(*)
          FROM information_schema.referential_constraints
          WHERE constraint_schema = DATABASE()
            AND table_name = 'review'
            AND constraint_name = 'fk_review_report'
        );
    """))
    conn.execute(text("""
        SET @sql := IF(@has_fk > 0,
          'ALTER TABLE `review` DROP FOREIGN KEY `fk_review_report`',
          'SELECT 1');
    """))
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))

    conn.execute(text("""
        SET @has_idx := (
          SELECT COUNT(*) FROM information_schema.statistics
          WHERE table_schema = DATABASE()
            AND table_name = 'review'
            AND index_name = 'ix_review_report_id'
        );
    """))
    conn.execute(text("""
        SET @sql := IF(@has_idx > 0,
          'DROP INDEX `ix_review_report_id` ON `review`',
          'SELECT 1');
    """))
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))

    conn.execute(text("""
        SET @col_exists := (
          SELECT COUNT(*) FROM information_schema.columns
          WHERE table_schema = DATABASE()
            AND table_name = 'review'
            AND column_name = 'report_id'
        );
    """))
    conn.execute(text("""
        SET @sql := IF(@col_exists > 0,
          'ALTER TABLE `review` DROP COLUMN `report_id`',
          'SELECT 1');
    """))
    conn.execute(text("PREPARE stmt FROM @sql"))
    conn.execute(text("EXECUTE stmt"))
    conn.execute(text("DEALLOCATE PREPARE stmt"))

    conn.execute(text("DROP TABLE IF EXISTS `review_report`;"))
