"""Alembic environment configuration.

Builds the database URL from the same environment variables used by PostgresStorage,
so migrations run against the correct database without duplicating config.

When invoked programmatically (via PostgresStorage.initialize), an existing engine
is passed through config.attributes["engine"] to avoid creating a second pool.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

import sqlalchemy as sa
from alembic import context
from rossum_agent.postgres_storage import sa_metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = sa_metadata


def _get_url() -> sa.URL:
    """Build the database URL from environment variables (same defaults as PostgresStorage.__init__)."""
    return sa.URL.create(
        "postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "rossum"),
        password=os.getenv("POSTGRES_PASSWORD", "rossum"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "rossum_agent"),
    )


def _get_connect_args() -> dict[str, str]:
    """Build connect_args matching PostgresStorage (sslmode, timeout)."""
    args: dict[str, str] = {}
    sslmode = os.getenv("POSTGRES_SSLMODE")
    if sslmode:
        args["sslmode"] = sslmode
    return args


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode - emit SQL without a live connection."""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode - connect to the database."""
    # Reuse engine passed from PostgresStorage.initialize() if available
    connectable = config.attributes.get("engine") or sa.create_engine(_get_url(), connect_args=_get_connect_args())

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
