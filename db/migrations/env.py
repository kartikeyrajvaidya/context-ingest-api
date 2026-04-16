"""Alembic environment for ContextIngest API migrations."""

import logging
from logging.config import fileConfig

from alembic import context

from configs.db import DBConfig
from db import db

config = context.config
logger = logging.getLogger("alembic.env")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", DBConfig.DB_CONNECTION_URI)
schema_name = DBConfig.SCHEMA_NAME


def run_migrations_online():
    def process_revision_directives(context, revision, directives):  # noqa: ARG001
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("No changes in schema detected.")

    connection = db.get_sync_engine().connect()

    context.configure(
        connection=connection,
        process_revision_directives=process_revision_directives,
        version_table_schema=schema_name,
        transaction_per_migration=True,
    )

    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()


run_migrations_online()
