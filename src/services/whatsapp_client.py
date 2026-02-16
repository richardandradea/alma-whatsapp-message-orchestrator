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
