import httpx
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
            raise ValueError("WHATSAPP_API_URL no está configurado")
        if not self.access_token:
            raise ValueError("WHATSAPP_ACCESS_TOKEN no está configurado")
    
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
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"Enviando mensaje a WhatsApp para {phone_number}")
            logger.debug(f"Payload: {payload}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.whatsapp_api_url,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                logger.info(f"Mensaje enviado a WhatsApp exitosamente. Status: {response.status_code}")
                return True
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP al enviar a WhatsApp: {e.response.status_code} - {e.response.text}")
            return False
        except httpx.RequestError as e:
            logger.error(f"Error de conexión a WhatsApp: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al enviar a WhatsApp: {e}")
            return False
