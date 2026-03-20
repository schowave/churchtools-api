import unittest


class TestLoggingConfig(unittest.TestCase):
    def test_configure_logging_console(self):
        from app.logging_config import configure_logging

        configure_logging("console")
        import structlog

        logger = structlog.get_logger()
        assert logger is not None

    def test_configure_logging_json(self):
        from app.logging_config import configure_logging

        configure_logging("json")
        import structlog

        logger = structlog.get_logger()
        assert logger is not None
