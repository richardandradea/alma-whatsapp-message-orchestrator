from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from src.core.config import get_settings
from src.logger.logger_config import LoggerConfig
from src.services.agent_client import AgentClient
from src.services.whatsapp_client import WhatsAppClient
import json

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
logger = LoggerConfig.get_logger(__name__)
_settings = get_settings()


def extract_whatsapp_message(payload: dict) -> tuple[str | None, str | None]:
    """
    Extrae el número de teléfono y el texto del mensaje del payload de WhatsApp.
    
    Estructura esperada del payload:
    {
      "object": "whatsapp_business_account",
      "entry": [{
        "changes": [{
          "value": {
            "messages": [{
              "from": "569XXXXXXXX",
              "type": "text",
              "text": {"body": "Hola"}
            }],
            "contacts": [{
              "wa_id": "569XXXXXXXX"
            }]
          }
        }]
      }]
    }
    
    Args:
        payload: Payload completo del webhook de WhatsApp
        
    Returns:
        Tupla (phone_number, message_text) o (None, None) si no se encuentra
    """
    try:
        # Validar que el objeto sea de WhatsApp Business Account
        if payload.get("object") != "whatsapp_business_account":
            logger.warning(f"Payload no es de WhatsApp Business Account: {payload.get('object')}")
        
        entries = payload.get("entry", [])
        if not entries:
            logger.warning("No se encontraron 'entry' en el payload")
            return None, None
        
        for entry in entries:
            changes = entry.get("changes", [])
            if not changes:
                logger.warning("No se encontraron 'changes' en el entry")
                continue
            
            for change in changes:
                # Verificar que el campo sea "messages"
                if change.get("field") != "messages":
                    logger.debug(f"Ignorando change con field: {change.get('field')}")
                    continue
                
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                if not messages:
                    logger.debug("No se encontraron mensajes en el value")
                    continue
                
                for message in messages:
                    # Obtener número de teléfono del remitente
                    phone_number = message.get("from")
                    message_type = message.get("type")
                    
                    # Solo procesar mensajes de texto
                    if message_type == "text" and phone_number:
                        text_obj = message.get("text", {})
                        message_text = text_obj.get("body", "")
                        
                        if message_text:
                            logger.debug(f"Extraído: phone={phone_number}, text={message_text}")
                            return phone_number, message_text
                        else:
                            logger.warning(f"Mensaje de texto sin body: {message}")
                    else:
                        logger.debug(f"Ignorando mensaje tipo: {message_type}, from: {phone_number}")
                            
    except KeyError as e:
        logger.error(f"Campo faltante en el payload de WhatsApp: {e}")
    except Exception as e:
        logger.error(f"Error extrayendo mensaje del payload: {e}", exc_info=True)
    
    return None, None


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "whatsapp-inbound-orchestrator", "env": _settings.env}

@router.get("/webhook", response_class=PlainTextResponse)
async def verify(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge")
):
    logger.info("🔐 Verificación de webhook de WhatsApp")
    logger.debug(f"   Mode: {hub_mode}, Token recibido: {hub_verify_token is not None}, Challenge: {hub_challenge is not None}")
    
    if hub_mode == "subscribe" and hub_verify_token == _settings.whatsapp_verify_token.get_secret_value():
        logger.info("✅ Verificación exitosa")
        return PlainTextResponse(hub_challenge or "", status_code=200)
    
    logger.warning("❌ Verificación fallida")
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/webhook", response_class=PlainTextResponse)
async def receive(request: Request):
    logger.info("=" * 80)
    logger.info("📥 INICIO: Recepción de webhook de WhatsApp")
    try:
        payload = await request.json()
        logger.info(f"📦 Payload recibido: {json.dumps(payload, ensure_ascii=False)}")
        
        # Extraer número de teléfono y mensaje del payload
        logger.debug("🔍 Extrayendo número de teléfono y mensaje del payload...")
        phone_number, message_text = extract_whatsapp_message(payload)
        
        if phone_number and message_text:
            logger.info(f"✅ Mensaje extraído exitosamente")
            logger.info(f"   📱 Teléfono: {phone_number}")
            logger.info(f"   💬 Mensaje: {message_text}")
            
            # Enviar al agente y obtener respuesta
            try:
                logger.info("🤖 Iniciando comunicación con el agente...")
                agent_client = AgentClient()
                logger.debug(f"   🔗 URL del agente: {agent_client.agent_url}")
                
                agent_response = await agent_client.send_message(phone_number, message_text)
                
                if agent_response:
                    logger.info(f"✅ Respuesta recibida del agente para {phone_number}")
                    logger.debug(f"   📄 Tipo de respuesta: {type(agent_response).__name__}")
                    
                    # Extraer texto de la respuesta del agente
                    logger.debug("🔍 Extrayendo texto de la respuesta del agente...")
                    response_text = agent_client.extract_agent_response_text(agent_response)
                    
                    if response_text:
                        logger.info(f"✅ Texto extraído de la respuesta del agente")
                        logger.info(f"   📝 Respuesta: {response_text[:200]}{'...' if len(response_text) > 200 else ''}")
                        
                        # Opcionalmente, enviar la respuesta de vuelta a WhatsApp
                        if _settings.whatsapp_api_url and _settings.whatsapp_access_token:
                            logger.info("📤 Enviando respuesta a WhatsApp...")
                            try:
                                whatsapp_client = WhatsAppClient()
                                logger.debug(f"   🔗 URL de WhatsApp API: {_settings.whatsapp_api_url}")
                                
                                sent = await whatsapp_client.send_message(phone_number, response_text)
                                if sent:
                                    logger.info(f"✅ Respuesta enviada a WhatsApp exitosamente para {phone_number}")
                                else:
                                    logger.warning(f"⚠️  Error al enviar respuesta a WhatsApp para {phone_number}")
                            except ValueError as e:
                                logger.warning(f"⚠️  No se puede enviar a WhatsApp: {e}")
                            except Exception as e:
                                logger.error(f"❌ Error inesperado al enviar a WhatsApp: {e}", exc_info=True)
                        else:
                            logger.info("ℹ️  WhatsApp API no configurado, omitiendo envío de respuesta")
                    else:
                        logger.warning(f"⚠️  No se pudo extraer texto de la respuesta del agente")
                        logger.debug(f"   📄 Respuesta completa: {json.dumps(agent_response, ensure_ascii=False)}")
                else:
                    logger.warning(f"⚠️  No se recibió respuesta del agente para {phone_number}")
            except ValueError as e:
                logger.warning(f"⚠️  No se puede enviar al agente: {e}. Continuando sin error.")
            except Exception as e:
                logger.error(f"❌ Error inesperado al enviar al agente: {e}", exc_info=True)
        else:
            logger.info("ℹ️  No se encontró mensaje de texto en el payload o el payload no es un mensaje")
            if not phone_number:
                logger.debug("   ⚠️  No se pudo extraer el número de teléfono")
            if not message_text:
                logger.debug("   ⚠️  No se pudo extraer el texto del mensaje")
        
        logger.info("✅ FIN: Webhook procesado exitosamente")
        logger.info("=" * 80)
        return PlainTextResponse("EVENT_RECEIVED", status_code=200)
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ ERROR CRÍTICO procesando webhook: {e}", exc_info=True)
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=str(e))