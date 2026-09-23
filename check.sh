#!/usr/bin/env bash
# Verificación rápida: sintaxis, importaciones y tests. Antes de cualquier commit.
set -e
cd "$(dirname "$0")"
python3 -m compileall -q seedscout tests
python3 -c "import seedscout.web, seedscout.cli, seedscout.pipeline"
python3 -m pytest tests/ -q
echo "check.sh OK"
