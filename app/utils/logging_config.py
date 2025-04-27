import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(log_dir="logs", log_level=logging.INFO):
    """
    Konfiguriert das Logging für die gesamte Anwendung.
    
    Args:
        log_dir: Verzeichnis für Logdateien
        log_level: Logging-Level (default: INFO)
    """
    # Stelle sicher, dass das Log-Verzeichnis existiert
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Konfiguriere Root-Logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Entferne bestehende Handler, um Duplizierung zu vermeiden
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Formatter für konsistentes Log-Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File Handler mit Rotation (max 10MB, 5 Backup-Dateien)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Spezifische Logger für verschiedene Komponenten
    loggers = {
        'api': logging.getLogger('app.api'),
        'database': logging.getLogger('app.database'),
        'services': logging.getLogger('app.services')
    }
    
    return loggers

# Hilfsfunktion für strukturierte Fehlerbehandlung
class APIError(Exception):
    """Basisklasse für API-bezogene Fehler"""
    def __init__(self, message, status_code=500, details=None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

def log_exception(logger, exc, context=None):
    """
    Protokolliert eine Ausnahme mit Kontext.
    
    Args:
        logger: Logger-Instanz
        exc: Die aufgetretene Ausnahme
        context: Zusätzlicher Kontext (dict)
    """
    context = context or {}
    error_msg = f"{type(exc).__name__}: {str(exc)}"
    
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        error_msg = f"{error_msg} - Context: {context_str}"
    
    logger.error(error_msg, exc_info=True)