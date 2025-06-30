#!/bin/bash

# Exit on error
set -e

# Create venv if it doesn't exist
if [ ! -d "quantenv" ]; then
    python -m venv quantenv
    echo "Virtual environment 'quantenv' created."
fi

# Activate venv
source quantenv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

echo "Setup complete. To activate later: source quantenv/bin/activate"
