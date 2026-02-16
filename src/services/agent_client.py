import httpx
from typing import Dict, Any, Optional
from src.core.config import get_settings
from src.logger.logger_config import LoggerConfig

logger = LoggerConfig.get_logger(__name__)
_settings = get_settings()


class AgentClient:
    """Cliente para enviar mensajes al agente"""
    
    def __init__(self, agent_url: Optional[str] = None):
        self.agent_url = agent_url or _settings.agent_url
        if not self.agent_url:
            raise ValueError("AGENT_URL no está configurado")
    
    def format_message(self, phone_number: str, message_text: str) -> Dict[str, Any]:
        """
        Formatea un mensaje de WhatsApp al formato requerido por el agente.
        
        Mapeo de datos:
        - appName: De AGENT_APP_NAME (variable de entorno, default: "alma")
        - userId: phone_number extraído de entry[0].changes[0].value.messages[0].from
        - sessionId: Mismo que userId (número de teléfono)
        - newMessage.role: Valor fijo "user" para mensajes entrantes
        - newMessage.parts[0].text: message_text extraído de entry[0].changes[0].value.messages[0].text.body
        
        Args:
            phone_number: Número de teléfono del usuario extraído de messages[0].from
            message_text: Texto del mensaje extraído de messages[0].text.body
            
        Returns:
            Dict con el formato requerido por el agente:
            {
                "appName": "alma",
                "userId": "569XXXXXXXX",
                "sessionId": "569XXXXXXXX",
                "newMessage": {
                    "role": "user",
                    "parts": [{"text": "Hola"}]
                }
            }
        """
        return {
            "appName": _settings.agent_app_name,
            "userId": phone_number,
            "sessionId": phone_number,
            "newMessage": {
                "role": "user",
                "parts": [{
                    "text": message_text
                }]
            }
        }
    
    async def send_message(self, phone_number: str, message_text: str) -> Optional[Dict[str, Any]]:
        """
        Envía un mensaje al agente y retorna la respuesta.
        
        Args:
            phone_number: Número de teléfono del usuario
            message_text: Texto del mensaje
            
        Returns:
            Dict con la respuesta del agente si es exitoso, None en caso contrario
        """
        try:
            payload = self.format_message(phone_number, message_text)
            logger.info(f"Enviando mensaje al agente: {self.agent_url}")
            logger.debug(f"Payload: {payload}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.agent_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                
                # Obtener la respuesta del agente
                agent_response = response.json()
                logger.info(f"Mensaje enviado al agente exitosamente. Status: {response.status_code}")
                logger.debug(f"Respuesta del agente: {agent_response}")
                
                return agent_response
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP al enviar al agente: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Error de conexión al agente: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado al enviar al agente: {e}")
            return None
    
    def extract_agent_response_text(self, agent_response: Dict[str, Any]) -> Optional[str]:
        """
        Extrae el texto de la respuesta del agente.
        
        El formato esperado puede variar, pero intenta extraer de:
        - agent_response["newMessage"]["parts"][0]["text"] (formato similar al enviado)
        - agent_response["response"]["text"]
        - agent_response["text"]
        - agent_response["message"]
        
        Args:
            agent_response: Respuesta completa del agente
            
        Returns:
            Texto de la respuesta o None si no se encuentra
        """
        try:
            # Intentar diferentes formatos de respuesta
            if "newMessage" in agent_response:
                parts = agent_response["newMessage"].get("parts", [])
                if parts and len(parts) > 0:
                    return parts[0].get("text")
            
            if "response" in agent_response:
                if isinstance(agent_response["response"], str):
                    return agent_response["response"]
                if isinstance(agent_response["response"], dict):
                    return agent_response["response"].get("text")
            
            if "text" in agent_response:
                return agent_response["text"]
            
            if "message" in agent_response:
                return agent_response["message"]
            
            # Si no se encuentra en formato conocido, retornar el JSON completo como string
            logger.warning(f"Formato de respuesta del agente no reconocido: {agent_response}")
            return str(agent_response)
            
        except Exception as e:
            logger.error(f"Error extrayendo texto de la respuesta del agente: {e}")
            return None
