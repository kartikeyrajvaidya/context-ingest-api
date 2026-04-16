"""Queries and feedback — applies db/migrations/sql/0002.sql verbatim."""

import inspect
import os

from alembic import op
from sqlalchemy import text

current_file_name = inspect.getfile(inspect.currentframe())
file_name_with_extension = current_file_name.split("/")[-1]
version = file_name_with_extension.split(".py")[0]

revision = version
down_revision = "0001"
branch_labels = None
depends_on = None

corresponding_sql_file = f"db/migrations/sql/{version}.sql"


def upgrade() -> None:
    if not os.path.exists(corresponding_sql_file):
        raise Exception(f"{corresponding_sql_file} migration SQL file does not exist")
    with open(corresponding_sql_file, encoding="utf8") as file_object:
        sql = file_object.read()
    connection = op.get_bind()
    connection.execute(text(sql), {"alembic_version": version})


def downgrade() -> None:
    pass
