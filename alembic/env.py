import os
from logging.config import fileConfig
from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
import backend.db.models
from backend.db.models.base import Base
from backend.db.runtime_roles import validate_migration_database_url, validate_runtime_roles

_initial_env = os.getenv("MANGARECON_ENV", "").lower().strip()

if _initial_env == "test":
    load_dotenv(".env.test", override=True)
else:
    load_dotenv(".env", override=False)

_ENV = os.getenv("MANGARECON_ENV", "prod").lower().strip()
if _ENV not in {"dev", "test", "prod"}:
    raise RuntimeError("MANGARECON_ENV must be one of: dev, test, prod.")

config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url_sync = os.getenv("DATABASE_URL_SYNC")
if not database_url_sync:
    env_file = ".env.test" if _ENV == "test" else ".env"
    raise RuntimeError(f"DATABASE_URL_SYNC is not set. Check {env_file}.")

validate_migration_database_url(
    database_url_sync,
    environment=_ENV,
)
config.set_main_option("sqlalchemy.url", database_url_sync.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate migration SQL without opening a database connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the configured database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            validate_runtime_roles(connection)
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
