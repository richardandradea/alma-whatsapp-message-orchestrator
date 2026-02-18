from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from src.core.config import get_settings
from src.logger.logger_config import LoggerConfig
from src.services.agent_client import AgentClient
from src.services.whatsapp_client import WhatsAppClient
import json

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
logger = LoggerConfig.get_logger(__name__)
_settings = get_settings()


# Modelos Pydantic para validación de payloads
class TaskAction(BaseModel):
    """Modelo para acciones/botones de la tarea"""
    id: str = Field(..., description="ID único del botón")
    title: str = Field(..., description="Título del botón")


class TaskNotificationRequest(BaseModel):
    """Modelo para el payload de notificación de tarea"""
    task_id: str = Field(..., description="ID único de la tarea")
    notification_type: str = Field(..., description="Tipo de notificación (ej: 'reminder')")
    to: int = Field(..., description="Número de teléfono del destinatario (sin prefijo +)")
    body: str = Field(..., description="Cuerpo del mensaje")
    footer: Optional[str] = Field(None, description="Texto del footer (opcional)")
    actions: List[TaskAction] = Field(..., description="Lista de botones/acciones (máximo 3)")


def extract_whatsapp_message(payload: dict) -> tuple[str | None, str | None]:
    """
    Extrae el número de teléfono y el texto del mensaje del payload de WhatsApp.
    
    Soporta dos tipos de mensajes:
    1. Mensajes de texto: extrae el texto del campo text.body
    2. Mensajes interactivos (botones): extrae el ID del botón desde interactive.button_reply.id
    
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
    
    O para mensajes interactivos:
    {
      "object": "whatsapp_business_account",
      "entry": [{
        "changes": [{
          "value": {
            "messages": [{
              "from": "569XXXXXXXX",
              "type": "interactive",
              "interactive": {
                "type": "button_reply",
                "button_reply": {
                  "id": "complete",
                  "title": "Entendido"
                }
              }
            }]
          }
        }]
      }]
    }
    
    Args:
        payload: Payload completo del webhook de WhatsApp
        
    Returns:
        Tupla (phone_number, message_text) o (None, None) si no se encuentra
        Para mensajes interactivos, message_text será el ID del botón
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
                    
                    if not phone_number:
                        logger.debug("Mensaje sin número de teléfono")
                        continue
                    
                    # Procesar mensajes de texto
                    if message_type == "text":
                        text_obj = message.get("text", {})
                        message_text = text_obj.get("body", "")
                        
                        if message_text:
                            logger.debug(f"Extraído mensaje de texto: phone={phone_number}, text={message_text}")
                            return phone_number, message_text
                        else:
                            logger.warning(f"Mensaje de texto sin body: {message}")
                    
                    # Procesar mensajes interactivos (botones)
                    elif message_type == "interactive":
                        interactive = message.get("interactive", {})
                        interactive_type = interactive.get("type")
                        
                        if interactive_type == "button_reply":
                            button_reply = interactive.get("button_reply", {})
                            button_id = button_reply.get("id")
                            button_title = button_reply.get("title", "")
                            
                            if button_id:
                                logger.info(f"Extraído mensaje interactivo: phone={phone_number}, button_id={button_id}, button_title={button_title}")
                                # Enviar el ID del botón como mensaje al agente
                                return phone_number, button_id
                            else:
                                logger.warning(f"Mensaje interactivo sin button_reply.id: {message}")
                        else:
                            logger.debug(f"Ignorando mensaje interactivo tipo: {interactive_type}")
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
            
            # Enviar indicador de typing para mejorar UX
            if _settings.whatsapp_api_url and _settings.whatsapp_access_token:
                try:
                    whatsapp_client = WhatsAppClient()
                    await whatsapp_client.send_typing_indicator(phone_number, is_typing=True)
                    logger.debug("⌨️  Indicador de typing activado")
                except Exception as e:
                    logger.debug(f"⚠️  No se pudo enviar indicador de typing: {e}")
            
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
                                
                                # El typing se desactiva automáticamente al enviar el mensaje
                                # No es necesario enviar typing_off explícitamente
                                
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


@router.post("/tasksnotification")
async def task_notification(request: TaskNotificationRequest):
    """
    Endpoint para enviar notificaciones de tareas con botones interactivos a WhatsApp.
    
    Recibe un payload con información de la tarea y envía un mensaje interactivo
    con botones al usuario de WhatsApp.
    """
    logger.info("=" * 80)
    logger.info("📋 INICIO: Notificación de tarea")
    logger.info(f"   📦 Payload recibido: {json.dumps(request.model_dump(), ensure_ascii=False, indent=2)}")
    
    try:
        # Validar que WhatsApp API esté configurado
        if not _settings.whatsapp_api_url or not _settings.whatsapp_access_token:
            logger.error("❌ WhatsApp API no está configurado")
            raise HTTPException(
                status_code=500, 
                detail="WhatsApp API no está configurado. Configure WHATSAPP_API_URL y WHATSAPP_ACCESS_TOKEN"
            )
        
        # Validar cantidad de botones (WhatsApp permite máximo 3)
        if len(request.actions) > 3:
            logger.error(f"❌ Demasiados botones: {len(request.actions)}. WhatsApp permite máximo 3")
            raise HTTPException(
                status_code=400,
                detail=f"Demasiados botones: {len(request.actions)}. WhatsApp permite máximo 3 botones"
            )
        
        if len(request.actions) == 0:
            logger.error("❌ No se proporcionaron botones")
            raise HTTPException(
                status_code=400,
                detail="Se requiere al menos un botón en 'actions'"
            )
        
        # Convertir número de teléfono a string
        phone_number = str(request.to)
        logger.info(f"   📱 Teléfono destino: {phone_number}")
        logger.info(f"   📝 Cuerpo del mensaje: {request.body}")
        if request.footer:
            logger.info(f"   📄 Footer: {request.footer}")
        logger.info(f"   🔘 Botones: {len(request.actions)}")
        
        # Formatear botones para WhatsAppClient
        buttons = [{"id": action.id, "title": action.title} for action in request.actions]
        
        # Enviar mensaje interactivo a WhatsApp
        try:
            whatsapp_client = WhatsAppClient()
            logger.info("📤 Enviando notificación de tarea a WhatsApp...")
            
            sent = await whatsapp_client.send_interactive_message(
                phone_number=phone_number,
                body=request.body,
                footer=request.footer,
                buttons=buttons
            )
            
            if sent:
                logger.info(f"✅ Notificación de tarea enviada exitosamente a {phone_number}")
                logger.info("=" * 80)
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "Notificación de tarea enviada exitosamente",
                        "task_id": request.task_id,
                        "phone_number": phone_number
                    }
                )
            else:
                logger.error(f"❌ Error al enviar notificación de tarea a {phone_number}")
                raise HTTPException(
                    status_code=500,
                    detail="Error al enviar notificación de tarea a WhatsApp"
                )
                
        except ValueError as e:
            logger.error(f"❌ Error de configuración: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.error(f"❌ Error inesperado al enviar notificación: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error al enviar notificación: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ ERROR CRÍTICO procesando notificación de tarea: {e}", exc_info=True)
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=str(e))