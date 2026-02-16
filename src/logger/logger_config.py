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
        
        # Limpiar handlers existentes para evitar duplicados
        if root_logger.handlers:
            root_logger.handlers.clear()
        
        # Configurar nivel del root logger
        log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
        root_logger.setLevel(log_level)
        
        # Permitir propagación para que los loggers hijos también funcionen
        root_logger.propagate = True

        # Handler para consola (stdout) - usar stderr para evitar buffering
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)

        # Handler para archivo (opcional)
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            root_logger.addHandler(file_handler)

        # Configurar loggers específicos para reducir ruido de librerías externas
        logging.getLogger("uvicorn").setLevel(logging.WARNING)  # Reducir logs de uvicorn
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # Reducir logs de acceso
        logging.getLogger("fastapi").setLevel(logging.WARNING)  # Reducir logs de fastapi
        logging.getLogger("httpx").setLevel(logging.WARNING)  # Reducir logs de httpx
        
        # Asegurar que nuestros loggers de la aplicación usen el nivel INFO o superior
        # Esto garantiza que todos los logs INFO, WARNING, ERROR se muestren
        for logger_name in ["src", "__main__"]:
            app_logger = logging.getLogger(logger_name)
            app_logger.setLevel(log_level)
            app_logger.propagate = True  # Permitir propagación al root logger
            # No agregar handlers duplicados, usar los del root logger
        
        # Configurar loggers específicos de nuestros módulos para asegurar nivel INFO
        for module_name in ["src.api", "src.services", "src.core", "src.logger"]:
            module_logger = logging.getLogger(module_name)
            module_logger.setLevel(log_level)
            module_logger.propagate = True

        cls._configured = True
        root_logger.info("=" * 80)
        root_logger.info(f"✅ Logger configurado exitosamente - Nivel: {settings.log_level.upper()}")
        root_logger.info(f"   📊 Los logs desde {settings.log_level.upper()} se mostrarán en consola")
        root_logger.info("=" * 80)

    @staticmethod
    def get_logger(name: str):
        """Returns a logger by name (modular)."""
        return logging.getLogger(name)