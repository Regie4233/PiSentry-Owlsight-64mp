#!/bin/bash

# PiSentry Camera UI Launch Script
# This script sets up the virtual environment and starts the Flask server.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Check if venv exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/Update dependencies
echo "Checking dependencies..."
pip install -r requirements.txt --quiet

# Check if config.txt is likely configured (basic check for ov64a40)
if ! grep -q "ov64a40" /boot/firmware/config.txt 2>/dev/null && ! grep -q "ov64a40" /boot/config.txt 2>/dev/null; then
    echo "WARNING: Arducam ov64a40 overlay not found in config.txt."
    echo "You may need to run 'sudo python3 setup_pi.py' and reboot first."
fi

echo "Starting PiSentry Camera UI on http://0.0.0.0:5000"
python3 app.py
