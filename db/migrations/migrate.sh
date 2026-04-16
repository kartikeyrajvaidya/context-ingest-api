#!/bin/bash

set -e

if [ -f ".env" ]; then
    set -a
    . ./.env
    set +a
fi

migration_number="${1:-head}"

echo "Running migrations started ... ($(date "+%Y-%m-%d %H:%M:%S"))"
python -m alembic.config --config=db/migrations/alembic.ini upgrade $migration_number
echo "Running migrations ended ... ($(date "+%Y-%m-%d %H:%M:%S"))"
