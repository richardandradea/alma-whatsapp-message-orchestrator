import httpx
import json
from typing import Dict, Any, Optional, Union, List
from src.core.config import get_settings
from src.logger.logger_config import LoggerConfig

logger = LoggerConfig.get_logger(__name__)
_settings = get_settings()


class AgentClient:
    """Cliente para enviar mensajes al agente"""
    
    def __init__(self, agent_url: Optional[str] = None):
        self.agent_url = agent_url or _settings.agent_url
        if not self.agent_url:
            logger.error("❌ AGENT_URL no está configurado")
            raise ValueError("AGENT_URL no está configurado")
        logger.debug(f"🤖 AgentClient inicializado con URL: {self.agent_url}")
    
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
        payload = {
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
        logger.debug(f"📝 Mensaje formateado para el agente: appName={_settings.agent_app_name}, userId={phone_number}")
        return payload
    
    async def send_message(self, phone_number: str, message_text: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Envía un mensaje al agente y retorna la respuesta.
        
        Args:
            phone_number: Número de teléfono del usuario
            message_text: Texto del mensaje
            
        Returns:
            Dict o List con la respuesta del agente si es exitoso, None en caso contrario
        """
        try:
            payload = self.format_message(phone_number, message_text)
            logger.info(f"📤 Enviando mensaje al agente: {self.agent_url}")
            logger.debug(f"   📦 Payload completo: {json.dumps(payload, ensure_ascii=False)}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.debug(f"   ⏱️  Timeout configurado: 30.0s")
                response = await client.post(
                    self.agent_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                logger.debug(f"   📡 Respuesta HTTP recibida: Status {response.status_code}")
                response.raise_for_status()
                
                # Obtener la respuesta del agente
                agent_response = response.json()
                logger.info(f"✅ Mensaje enviado al agente exitosamente. Status: {response.status_code}")
                logger.debug(f"   📄 Tipo de respuesta: {type(agent_response).__name__}")
                if isinstance(agent_response, list):
                    logger.debug(f"   📊 Cantidad de elementos en array: {len(agent_response)}")
                logger.debug(f"   📦 Respuesta completa: {json.dumps(agent_response, ensure_ascii=False)}")
                
                return agent_response
                
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Error HTTP al enviar al agente: {e.response.status_code}")
            logger.error(f"   📄 Respuesta del servidor: {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"❌ Error de conexión al agente: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error inesperado al enviar al agente: {e}", exc_info=True)
            return None
    
    def extract_agent_response_text(self, agent_response: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Optional[str]:
        """
        Extrae el texto de la respuesta del agente.
        
        Soporta múltiples formatos:
        1. Array de objetos con content.parts (formato nuevo):
           [
             {
               "content": {
                 "parts": [{"text": "texto"}]
               }
             }
           ]
        2. agent_response["newMessage"]["parts"][0]["text"] (formato similar al enviado)
        3. agent_response["response"]["text"]
        4. agent_response["text"]
        5. agent_response["message"]
        
        Args:
            agent_response: Respuesta completa del agente (dict o list)
            
        Returns:
            Texto de la respuesta concatenado o None si no se encuentra
        """
        try:
            logger.debug(f"🔍 Extrayendo texto de respuesta del agente (tipo: {type(agent_response).__name__})")
            
            # Si es una lista (formato array de objetos)
            if isinstance(agent_response, list):
                logger.debug(f"   📋 Procesando array con {len(agent_response)} elementos")
                texts = []
                for idx, item in enumerate(agent_response):
                    if isinstance(item, dict):
                        # Buscar content.parts
                        content = item.get("content", {})
                        if isinstance(content, dict):
                            parts = content.get("parts", [])
                            logger.debug(f"   📦 Elemento {idx}: {len(parts)} partes encontradas")
                            if isinstance(parts, list):
                                for part_idx, part in enumerate(parts):
                                    if isinstance(part, dict) and "text" in part:
                                        text = part.get("text")
                                        if text and isinstance(text, str) and text.strip():
                                            texts.append(text.strip())
                                            logger.debug(f"      ✅ Texto {part_idx} extraído: {text[:50]}...")
                                    elif isinstance(part, dict):
                                        part_type = list(part.keys())[0] if part.keys() else "unknown"
                                        logger.debug(f"      ⏭️  Parte {part_idx} ignorada (tipo: {part_type})")
                
                if texts:
                    # Concatenar todos los textos con saltos de línea
                    result = "\n".join(texts)
                    logger.info(f"✅ Extraídos {len(texts)} textos del array de respuesta")
                    logger.debug(f"   📝 Texto final (longitud: {len(result)}): {result[:200]}{'...' if len(result) > 200 else ''}")
                    return result
                else:
                    logger.warning(f"⚠️  No se encontraron textos en el array de respuesta")
                    logger.debug(f"   📄 Respuesta completa: {json.dumps(agent_response, ensure_ascii=False)}")
            
            # Si es un diccionario, intentar formatos anteriores
            if isinstance(agent_response, dict):
                logger.debug("   📋 Procesando respuesta como diccionario")
                # Intentar diferentes formatos de respuesta
                if "newMessage" in agent_response:
                    logger.debug("   🔍 Formato detectado: newMessage")
                    parts = agent_response["newMessage"].get("parts", [])
                    if parts and len(parts) > 0:
                        text = parts[0].get("text")
                        logger.debug(f"   ✅ Texto extraído de newMessage.parts[0]")
                        return text
                
                if "response" in agent_response:
                    logger.debug("   🔍 Formato detectado: response")
                    if isinstance(agent_response["response"], str):
                        logger.debug("   ✅ Texto extraído de response (string)")
                        return agent_response["response"]
                    if isinstance(agent_response["response"], dict):
                        text = agent_response["response"].get("text")
                        logger.debug("   ✅ Texto extraído de response.text")
                        return text
                
                if "text" in agent_response:
                    logger.debug("   🔍 Formato detectado: text")
                    logger.debug("   ✅ Texto extraído de text")
                    return agent_response["text"]
                
                if "message" in agent_response:
                    logger.debug("   🔍 Formato detectado: message")
                    logger.debug("   ✅ Texto extraído de message")
                    return agent_response["message"]
            
            # Si no se encuentra en formato conocido, retornar el JSON completo como string
            logger.warning(f"⚠️  Formato de respuesta del agente no reconocido")
            logger.debug(f"   📄 Respuesta completa: {json.dumps(agent_response, ensure_ascii=False)}")
            return str(agent_response)
            
        except Exception as e:
            logger.error(f"Error extrayendo texto de la respuesta del agente: {e}", exc_info=True)
            return None
