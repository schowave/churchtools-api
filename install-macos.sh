#!/bin/bash

# Create a virtual environment if it doesn't exist yet
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Update pip
pip install --upgrade pip

echo "Installing reportlab without C extensions..."
pip install reportlab==3.5.68 --global-option="--without-c-extensions"

if [ $? -ne 0 ]; then
    echo "Installation of reportlab 3.5.68 failed, trying newer version..."
    pip install reportlab
fi

# Install the remaining dependencies
echo "Installing remaining dependencies..."
pip install -r requirements-macos.txt

echo "Installation completed!"
echo "Activate the virtual environment with 'source venv/bin/activate'"
echo "Run the tests with 'python -m pytest tests/'"