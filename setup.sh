#!/bin/bash

# Exit on error
set -e

# Create venv if missing, or rebuild it if a Python upgrade broke it
if ! quantenv/bin/python -c "import sys" >/dev/null 2>&1; then
    rm -rf quantenv
    python -m venv quantenv
    echo "Virtual environment 'quantenv' created."
fi

# Activate venv
source quantenv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

echo "Setup complete. To activate later: source quantenv/bin/activate"
