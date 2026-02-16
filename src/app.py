from fastapi import FastAPI
from src.api.v1 import api_v1
from src.core.config import get_settings
from src.logger.logger_config import LoggerConfig

# Configurar logging antes de crear la app
LoggerConfig.configure()
logger = LoggerConfig.get_logger(__name__)
_settings = get_settings()

app = FastAPI(title="WhatsApp Inbound Orchestrator", version="1.0.0")

app.include_router(api_v1, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Evento de inicio de la aplicación"""
    logger.info("=" * 80)
    logger.info("🚀 INICIANDO WhatsApp Inbound Orchestrator")
    logger.info(f"   📦 Versión: 1.0.0")
    logger.info(f"   🌍 Entorno: {_settings.env}")
    logger.info(f"   🔧 Puerto: {_settings.port}")
    logger.info(f"   📊 Nivel de log: {_settings.log_level}")
    logger.info(f"   🤖 Agente URL: {_settings.agent_url if _settings.agent_url else 'No configurado'}")
    logger.info(f"   📱 WhatsApp API URL: {'Configurado' if _settings.whatsapp_api_url else 'No configurado'}")
    logger.info("=" * 80)


@app.on_event("shutdown")
async def shutdown_event():
    """Evento de cierre de la aplicación"""
    logger.info("=" * 80)
    logger.info("🛑 DETENIENDO WhatsApp Inbound Orchestrator")
    logger.info("=" * 80)