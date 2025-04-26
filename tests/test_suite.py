import pytest
import sys
import os

# Füge das Hauptverzeichnis zum Python-Pfad hinzu, damit die Module gefunden werden
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Wir verwenden pytest statt unittest für die Test-Suite, da es besser mit asyncio umgehen kann
if __name__ == '__main__':
    # Führe alle Tests mit pytest aus
    sys.exit(pytest.main(["-v", "tests/"]))