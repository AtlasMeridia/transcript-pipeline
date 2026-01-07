#!/bin/bash
# Start the Transcript Pipeline backend locally (for MLX Whisper on Apple Silicon)
#
# Usage: ./start-local.sh
#
# This script:
# 1. Creates a Python virtual environment if needed
# 2. Installs dependencies including mlx-whisper
# 3. Starts the FastAPI server on port 8000

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
REQUIREMENTS="requirements-local.txt"

echo "=== Transcript Pipeline - Local Backend ==="
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Python version: $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "Virtual environment created at $VENV_DIR"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Install/update dependencies
echo ""
echo "Installing dependencies from $REQUIREMENTS..."
pip install -q --upgrade pip
pip install -q -r "$REQUIREMENTS"

# Check for .env file
if [ ! -f ".env" ]; then
    echo ""
    echo "Warning: No .env file found."
    echo "Copy .env.example to .env and add your API keys:"
    echo "  cp .env.example .env"
    echo ""
fi

# Start the server
echo ""
echo "Starting server on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""
echo "-------------------------------------------"
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
