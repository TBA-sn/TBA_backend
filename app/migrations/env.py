# app/migrations/env.py
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

this_dir = os.path.dirname(__file__)
proj_root = os.path.abspath(os.path.join(this_dir, os.pardir, os.pardir))
if proj_root not in sys.path:
    sys.path.append(proj_root)

from app.utils.database import Base
from app.models import user as user_models         
from app.models import review as review_models
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "tba_db")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "000000")

SQLALCHEMY_URL_SYNC = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)

config.set_main_option("sqlalchemy.url", SQLALCHEMY_URL_SYNC)

def run_migrations_offline() -> None:
    context.configure(
        url=SQLALCHEMY_URL_SYNC,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(SQLALCHEMY_URL_SYNC, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
