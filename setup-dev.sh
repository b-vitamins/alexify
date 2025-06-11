#!/bin/bash
set -euo pipefail

# setup-dev.sh - Prepare isolated development environment for alexify
# This script installs system packages, creates a Python virtual environment,
# downloads all Python dependencies, installs them, and runs a basic test to
# verify the setup. Run once while online.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE_DIR="$ROOT/.cache/pip"

# Ensure apt packages are installed
need_pkg() {
    dpkg -s "$1" &>/dev/null || return 0
}

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-dev build-essential git

# Create virtual environment if missing
if [ ! -d "$ROOT/.venv" ]; then
    python3 -m venv "$ROOT/.venv"
fi

source "$ROOT/.venv/bin/activate"

# Upgrade pip and ensure wheel
pip install --upgrade pip wheel

mkdir -p "$CACHE_DIR"

# Download dependencies for offline use
pip download -d "$CACHE_DIR" -r "$ROOT/requirements-dev.txt"

# Install requirements online now (packages are also cached for offline reuse)
pip install -r "$ROOT/requirements-dev.txt"

# Install poetry for convenience
if ! command -v poetry >/dev/null 2>&1; then
    pip install poetry
fi

# Install pre-commit hooks if configuration present
if [ -f "$ROOT/.pre-commit-config.yaml" ]; then
    pre-commit install
fi

# Run tests to confirm everything works
pytest -q

echo "Development environment setup complete."
