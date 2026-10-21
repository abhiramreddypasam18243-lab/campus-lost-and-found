#!/bin/sh
# Browser end-to-end tests in the official Playwright image, on the Compose network.
#
#   docker compose down -v && docker compose up -d --build     # fresh data: the journey expects it
#   docker compose exec -T backend python -m app.seed
#   sh e2e/run.sh
#
# NETWORK defaults to the network Compose creates for this folder; screenshots go to e2e/output.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
NETWORK="${NETWORK:-campuslostandfound_default}"
mkdir -p "$HERE/output"

docker run --rm --network "$NETWORK" \
  -e BASE=http://frontend -e OUT=/out \
  -v "$HERE:/e2e:ro" -v "$HERE/output:/out" \
  mcr.microsoft.com/playwright/python:v1.49.0-noble \
  sh -c "pip install -q --break-system-packages playwright==1.49.0 && python /e2e/journey.py && python /e2e/keyboard.py"
