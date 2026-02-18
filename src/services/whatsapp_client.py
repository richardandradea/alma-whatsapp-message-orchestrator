import httpx
import json
from typing import Optional
from src.core.config import get_settings
from src.logger.logger_config import LoggerConfig

logger = LoggerConfig.get_logger(__name__)
_settings = get_settings()


class WhatsAppClient:
    """Cliente para enviar mensajes de vuelta a WhatsApp Business API"""
    
    def __init__(self, whatsapp_api_url: Optional[str] = None, access_token: Optional[str] = None):
        self.whatsapp_api_url = whatsapp_api_url or _settings.whatsapp_api_url
        self.access_token = access_token or _settings.whatsapp_access_token.get_secret_value() if _settings.whatsapp_access_token else None
        
        if not self.whatsapp_api_url:
            logger.error("❌ WHATSAPP_API_URL no está configurado")
            raise ValueError("WHATSAPP_API_URL no está configurado")
        if not self.access_token:
            logger.error("❌ WHATSAPP_ACCESS_TOKEN no está configurado")
            raise ValueError("WHATSAPP_ACCESS_TOKEN no está configurado")
        
        logger.debug(f"📱 WhatsAppClient inicializado con URL: {self.whatsapp_api_url}")
    
    async def send_message(self, phone_number: str, message_text: str) -> bool:
        """
        Envía un mensaje de texto a WhatsApp.
        
        Args:
            phone_number: Número de teléfono del destinatario (con código de país, sin +)
            message_text: Texto del mensaje a enviar
            
        Returns:
            True si se envió correctamente, False en caso contrario
        """
        try:
            # Formato para WhatsApp Business API
            payload = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "text",
                "text": {
                    "body": message_text
                }
            }
            
            headers = {
                "Authorization": f"Bearer {self.access_token[:20]}...",  # Solo primeros caracteres por seguridad
                "Content-Type": "application/json"
            }
            
            logger.info(f"📤 Enviando mensaje a WhatsApp para {phone_number}")
            logger.debug(f"   🔗 URL: {self.whatsapp_api_url}")
            logger.debug(f"   📦 Payload: {json.dumps(payload, ensure_ascii=False)}")
            logger.debug(f"   📝 Mensaje (longitud: {len(message_text)}): {message_text[:100]}{'...' if len(message_text) > 100 else ''}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.debug(f"   ⏱️  Timeout configurado: 30.0s")
                response = await client.post(
                    self.whatsapp_api_url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
                )
                logger.debug(f"   📡 Respuesta HTTP recibida: Status {response.status_code}")
                response.raise_for_status()
                
                response_data = response.json() if response.content else {}
                logger.info(f"✅ Mensaje enviado a WhatsApp exitosamente. Status: {response.status_code}")
                logger.debug(f"   📄 Respuesta de WhatsApp: {json.dumps(response_data, ensure_ascii=False)}")
                return True
                
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Error HTTP al enviar a WhatsApp: {e.response.status_code}")
            logger.error(f"   📄 Respuesta del servidor: {e.response.text}")
            return False
        except httpx.RequestError as e:
            logger.error(f"❌ Error de conexión a WhatsApp: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error inesperado al enviar a WhatsApp: {e}", exc_info=True)
            return False
    
    async def send_interactive_message(
        self, 
        phone_number: str, 
        body: str, 
        footer: str | None = None,
        buttons: list[dict] | None = None
    ) -> bool:
        """
        Envía un mensaje interactivo con botones a WhatsApp.
        
        Args:
            phone_number: Número de teléfono del destinatario (con código de país, sin +)
            body: Texto principal del mensaje
            footer: Texto del footer (opcional)
            buttons: Lista de botones con formato [{"id": "button_id", "title": "Button Title"}]
            
        Returns:
            True si se envió correctamente, False en caso contrario
        """
        try:
            # Validar que haya botones
            if not buttons or len(buttons) == 0:
                logger.error("❌ No se proporcionaron botones para el mensaje interactivo")
                return False
            
            # Validar cantidad de botones (WhatsApp permite máximo 3)
            if len(buttons) > 3:
                logger.error(f"❌ Demasiados botones: {len(buttons)}. WhatsApp permite máximo 3 botones")
                return False
            
            # Formatear botones al formato de WhatsApp
            formatted_buttons = []
            for button in buttons:
                if "id" not in button or "title" not in button:
                    logger.warning(f"⚠️  Botón inválido ignorado: {button}")
                    continue
                formatted_buttons.append({
                    "type": "reply",
                    "reply": {
                        "id": button["id"],
                        "title": button["title"]
                    }
                })
            
            if len(formatted_buttons) == 0:
                logger.error("❌ No se pudo formatear ningún botón válido")
                return False
            
            # Formato para WhatsApp Business API - Mensaje interactivo con botones
            payload = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {
                        "text": body
                    },
                    "action": {
                        "buttons": formatted_buttons
                    }
                }
            }
            
            # Agregar footer si está presente
            if footer:
                payload["interactive"]["footer"] = {
                    "text": footer
                }
            
            logger.info(f"📤 Enviando mensaje interactivo a WhatsApp para {phone_number}")
            logger.info(f"   📦 Payload enviado: {json.dumps(payload, ensure_ascii=False, indent=2)}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.debug(f"   ⏱️  Timeout configurado: 30.0s")
                response = await client.post(
                    self.whatsapp_api_url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
                )
                logger.debug(f"   📡 Respuesta HTTP recibida: Status {response.status_code}")
                response.raise_for_status()
                
                response_data = response.json() if response.content else {}
                logger.info(f"✅ Mensaje interactivo enviado a WhatsApp exitosamente. Status: {response.status_code}")
                logger.debug(f"   📄 Respuesta de WhatsApp: {json.dumps(response_data, ensure_ascii=False)}")
                return True
                
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Error HTTP al enviar mensaje interactivo a WhatsApp: {e.response.status_code}")
            logger.error(f"   📄 Respuesta del servidor: {e.response.text}")
            return False
        except httpx.RequestError as e:
            logger.error(f"❌ Error de conexión a WhatsApp: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error inesperado al enviar mensaje interactivo a WhatsApp: {e}", exc_info=True)
            return False
    
    async def send_typing_indicator(self, phone_number: str, message_id: str | None = None, is_typing: bool = True) -> bool:
        """
        Envía un indicador de typing (escribiendo) a WhatsApp.
        
        Formato según documentación oficial:
        {
          "messaging_product": "whatsapp",
          "status": "read",
          "message_id": "<WHATSAPP_MESSAGE_ID>",
          "typing_indicator": {
            "type": "text"
          }
        }
        
        Args:
            phone_number: Número de teléfono del destinatario (con código de país, sin +)
            message_id: ID del mensaje al que se responde (opcional, pero recomendado)
            is_typing: True para mostrar "escribiendo...", False para ocultarlo
            
        Returns:
            True si se envió correctamente, False en caso contrario
        """
        try:
            if not is_typing:
                # Para desactivar el typing, no necesitamos enviar nada especial
                # El typing se desactiva automáticamente cuando enviamos un mensaje
                logger.debug(f"⌨️  Typing se desactivará automáticamente al enviar el siguiente mensaje")
                return True
            
            # Si no tenemos message_id, no podemos enviar el typing indicator
            # ya que el formato requiere message_id
            if not message_id:
                logger.debug(f"⌨️  No se puede enviar typing indicator sin message_id")
                return False
            
            # Formato correcto según documentación oficial de WhatsApp Business API
            payload = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
                "typing_indicator": {
                    "type": "text"
                }
            }
            
            logger.info(f"⌨️  Enviando indicador de typing a WhatsApp para {phone_number}")
            logger.debug(f"   📦 Payload: {json.dumps(payload, ensure_ascii=False)}")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.whatsapp_api_url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
                )
                response.raise_for_status()
                
                response_data = response.json() if response.content else {}
                logger.info(f"✅ Indicador de typing enviado exitosamente. Status: {response.status_code}")
                logger.debug(f"   📄 Respuesta de WhatsApp: {json.dumps(response_data, ensure_ascii=False)}")
                return True
                
        except httpx.HTTPStatusError as e:
            logger.warning(f"⚠️  Error HTTP al enviar indicador de typing: {e.response.status_code}")
            logger.warning(f"   📄 Respuesta del servidor: {e.response.text}")
            return False
        except httpx.RequestError as e:
            logger.warning(f"⚠️  Error de conexión al enviar indicador de typing: {e}")
            return False
        except Exception as e:
            logger.warning(f"⚠️  Error inesperado al enviar indicador de typing: {e}", exc_info=True)
            return False
