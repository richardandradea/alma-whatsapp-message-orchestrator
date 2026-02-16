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
    if hub_mode == "subscribe" and hub_verify_token == _settings.whatsapp_verify_token.get_secret_value():
        return PlainTextResponse(hub_challenge or "", status_code=200)
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/webhook", response_class=PlainTextResponse)
async def receive(request: Request):
    try:
        payload = await request.json()
        logger.info(f"Received WhatsApp webhook message: {json.dumps(payload)}")
        
        # Extraer número de teléfono y mensaje del payload
        phone_number, message_text = extract_whatsapp_message(payload)
        
        if phone_number and message_text:
            logger.info(f"Procesando mensaje de {phone_number}: {message_text}")
            
            # Enviar al agente y obtener respuesta
            try:
                agent_client = AgentClient()
                agent_response = await agent_client.send_message(phone_number, message_text)
                
                if agent_response:
                    logger.info(f"Mensaje enviado al agente exitosamente para {phone_number}")
                    
                    # Extraer texto de la respuesta del agente
                    response_text = agent_client.extract_agent_response_text(agent_response)
                    
                    if response_text:
                        logger.info(f"Respuesta del agente para {phone_number}: {response_text}")
                        
                        # Opcionalmente, enviar la respuesta de vuelta a WhatsApp
                        if _settings.whatsapp_api_url and _settings.whatsapp_access_token:
                            try:
                                whatsapp_client = WhatsAppClient()
                                sent = await whatsapp_client.send_message(phone_number, response_text)
                                if sent:
                                    logger.info(f"Respuesta enviada a WhatsApp para {phone_number}")
                                else:
                                    logger.warning(f"Error al enviar respuesta a WhatsApp para {phone_number}")
                            except ValueError as e:
                                logger.warning(f"No se puede enviar a WhatsApp: {e}")
                            except Exception as e:
                                logger.error(f"Error inesperado al enviar a WhatsApp: {e}")
                    else:
                        logger.warning(f"No se pudo extraer texto de la respuesta del agente: {agent_response}")
                else:
                    logger.warning(f"Error al enviar mensaje al agente para {phone_number}")
            except ValueError as e:
                logger.warning(f"No se puede enviar al agente: {e}. Continuando sin error.")
            except Exception as e:
                logger.error(f"Error inesperado al enviar al agente: {e}")
        else:
            logger.info("No se encontró mensaje de texto en el payload o el payload no es un mensaje")
        
        return PlainTextResponse("EVENT_RECEIVED", status_code=200)
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))