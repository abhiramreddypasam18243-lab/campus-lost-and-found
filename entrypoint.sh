#!/bin/sh
set -e

echo "=== Smart Campus Lost and Found ==="
echo "Running database migrations..."
alembic upgrade head || echo "Migration notice: continuing..."

echo "Seeding synthetic campus tree and demo users (AC-145)..."
python -m app.seed || echo "Seed notice: continuing..."

PORT="${PORT:-8000}"
echo "Starting unified service on port ${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
