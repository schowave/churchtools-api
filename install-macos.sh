#!/bin/bash

# Erstelle eine virtuelle Umgebung, falls noch nicht vorhanden
if [ ! -d "venv" ]; then
    echo "Erstelle virtuelle Umgebung..."
    python3 -m venv venv
fi

# Aktiviere die virtuelle Umgebung
source venv/bin/activate

# Aktualisiere pip
pip install --upgrade pip

# Installiere reportlab ohne C-Erweiterungen
echo "Installiere reportlab ohne C-Erweiterungen..."
pip install --no-binary=reportlab reportlab==3.5.68

# Installiere die restlichen Abhängigkeiten
echo "Installiere restliche Abhängigkeiten..."
pip install -r requirements-macos.txt

echo "Installation abgeschlossen!"
echo "Aktiviere die virtuelle Umgebung mit 'source venv/bin/activate'"
echo "Führe die Tests aus mit 'python -m pytest tests/'"