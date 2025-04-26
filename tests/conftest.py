import pytest
import sys
import os

# Füge das Hauptverzeichnis zum Python-Pfad hinzu, damit die Module gefunden werden
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Aktiviere asyncio für pytest
pytest.importorskip("pytest_asyncio")

# Konfiguriere pytest-asyncio, um Warnungen zu vermeiden
pytest_plugins = ["pytest_asyncio"]

# Setze den default_fixture_loop_scope auf function
def pytest_addoption(parser):
    parser.addini("asyncio_default_fixture_loop_scope", default="function",
                 help="default scope for event loop fixtures")