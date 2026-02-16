import logging
import sys
from pathlib import Path

from src.core.config import get_settings

class LoggerConfig:
    _configured = False   # evita configuraciones duplicadas

    @classmethod
    def configure(cls, level: str = "INFO", log_file: str | None = None):
        """
        Configures global logging for the entire application.

        Args:
            level (str): Log level ("DEBUG", "INFO", "WARNING", "ERROR")
            log_file (str | None): Path to the log file, or None to not use a file
        """
        settings = get_settings()
        
        if cls._configured:
            return  # ya configurado, evita duplicados

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        cls._configured = True
        root_logger.info("Global logger configured successfully!")

    @staticmethod
    def get_logger(name: str):
        """Returns a logger by name (modular)."""
        return logging.getLogger(name)