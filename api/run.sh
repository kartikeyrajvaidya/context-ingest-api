#!/bin/bash

set -e

if [ -f ".env" ]; then
    set -a
    . ./.env
    set +a
fi

if [ $# -eq 0 ]; then
    echo "Error: Missing parameter. Usage: $0 <api>"
    exit 1
fi

SERVICE_TYPE=$1

case $SERVICE_TYPE in
    "api")
        bash db/migrations/migrate.sh
        uvicorn api.server.run_api:app --reload --host 0.0.0.0 --port 8080
        ;;
    *)
        echo "wrong init param"
        exit 1
        ;;
esac
