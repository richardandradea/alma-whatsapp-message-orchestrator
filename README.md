# WhatsApp Inbound Orchestrator

A **FastAPI-based microservice** that receives WhatsApp Business API webhook messages, extracts message content, and forwards them to an agent service in a standardized format.

---

## 🚀 Features

* **Versioned API (`/api/v1/...`)** for scalable evolution
* **Webhook Receiver**: Handles WhatsApp Business API webhook verification and message reception
* **Agent Integration**: Formats and forwards messages to an agent service
* **Structured Logging**: Centralized and detailed logs for observability
* **Docker Support**: Ready-to-deploy container setup
* **Health Checks**: Built-in endpoint for liveness and readiness
* **Error Handling**: Robust exception management with contextual logs
* **Backward Compatibility**: Temporary support for legacy `/webhook` endpoints

---

## 📋 Prerequisites

* Python **3.11+**
* **WhatsApp Business API** webhook access
* **Docker** (optional for containerized deployments)

---

## 🛠️ Installation

### Local Development

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd orchestrator-whatsapp-inbound
   ```

2. **Create virtual environment**

   ```bash
   make venv
   ```

3. **Install dependencies**

   ```bash
   make install
   ```

4. **Configure environment variables**
   Create a `.env` file in the project root:

   ```env
   WHATSAPP_VERIFY_TOKEN=your_whatsapp_verify_token
   AGENT_APP_NAME=alma
   AGENT_URL=http://localhost:3000/api/agent
   # Opcional: para enviar respuestas de vuelta a WhatsApp
   WHATSAPP_API_URL=https://graph.facebook.com/v18.0/YOUR_PHONE_NUMBER_ID/messages
   WHATSAPP_ACCESS_TOKEN=your_whatsapp_access_token
   ENV=dev
   LOG_LEVEL=INFO
   PORT=8080
   ```

5. **Run the application**

   ```bash
   make run-local
   ```

---

### Docker Deployment

1. **Build image**

   ```bash
   make build
   ```

2. **Run container**

   ```bash
   make run
   ```

3. **Run in detached mode**

   ```bash
   make run-d
   ```

---

## 🔧 Configuration

### Environment Variables

| Variable                | Description                           | Required | Default |
| ----------------------- | ------------------------------------- | -------- | ------- |
| `WHATSAPP_VERIFY_TOKEN` | WhatsApp webhook verification token   | ✅        | —       |
| `AGENT_APP_NAME`        | Nombre de la aplicación del agente    | ❌        | alma    |
| `AGENT_URL`             | URL del endpoint del agente           | ❌        | —       |
| `WHATSAPP_API_URL`      | URL de la API de WhatsApp para enviar mensajes | ❌ | — |
| `WHATSAPP_ACCESS_TOKEN` | Token de acceso de WhatsApp Business API | ❌ | — |
| `ENV`                   | Application environment (dev/qa/prod) | ❌        | dev     |
| `LOG_LEVEL`             | Logging level                         | ❌        | INFO    |
| `PORT`                  | Application port                      | ❌        | 8080    |

---

## 📤 Payload para la API del Agente

### Payload que recibirá tu API

Cuando se recibe un mensaje de WhatsApp, este servicio envía un **POST** a tu `AGENT_URL` con el siguiente payload:

**Endpoint:** `POST {AGENT_URL}`  
**Headers:** `Content-Type: application/json`

**Payload:**
```json
{
  "appName": "alma",
  "userId": "56994962184",
  "sessionId": "56994962184",
  "newMessage": {
    "role": "user",
    "parts": [{
      "text": "Hola, necesito ayuda"
    }]
  }
}
```

**Campos:**
- `appName`: Valor de `AGENT_APP_NAME` (default: "alma")
- `userId`: Número de teléfono del usuario (sin prefijo +)
- `sessionId`: Mismo que `userId` (número de teléfono)
- `newMessage.role`: Siempre "user" para mensajes entrantes
- `newMessage.parts[0].text`: Texto del mensaje recibido

### Respuesta esperada de tu API

Tu API debe responder con **HTTP 200 OK** y un JSON. Formatos soportados:

**Formato recomendado:**
```json
{
  "newMessage": {
    "role": "assistant",
    "parts": [{
      "text": "Hola, ¿cómo puedo ayudarte?"
    }]
  }
}
```

**Otros formatos aceptados:**
- `{"response": "texto"}` 
- `{"text": "texto"}`
- `{"message": "texto"}`

El servicio extraerá automáticamente el texto de la respuesta y, si está configurado, lo enviará de vuelta a WhatsApp.

---

## 📡 API Endpoints

### 🟢 Primary (Versioned)

| Method | Endpoint                   | Description                   |
| ------ | -------------------------- | ----------------------------- |
| `GET`  | `/api/v1/whatsapp/health`  | Health check                  |
| `GET`  | `/api/v1/whatsapp/webhook` | WhatsApp webhook verification |
| `POST` | `/api/v1/whatsapp/webhook` | WhatsApp message receiver     |

#### **Webhook Verification**

**GET** `/api/v1/whatsapp/webhook`

Query parameters:

| Name               | Description                     |
| ------------------ | ------------------------------- |
| `hub.mode`         | Verification mode (`subscribe`) |
| `hub.verify_token` | Token configured in Meta        |
| `hub.challenge`    | Challenge string to echo back   |

Response:

```
200 OK - Returns the hub.challenge string
403 Forbidden - Invalid token or mode
```

#### **Message Reception**

**POST** `/api/v1/whatsapp/webhook`

Payload: WhatsApp webhook JSON

El endpoint:
1. Recibe el webhook de WhatsApp
2. Extrae el número de teléfono y el texto del mensaje
3. Formatea el mensaje según el formato del agente
4. Envía el mensaje al agente (si `AGENT_URL` está configurado)
5. **Obtiene la respuesta del agente**
6. **Opcionalmente, envía la respuesta de vuelta a WhatsApp** (si `WHATSAPP_API_URL` y `WHATSAPP_ACCESS_TOKEN` están configurados)

**Payload enviado al agente (POST a `AGENT_URL`):**

**Método:** `POST`  
**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "appName": "alma",
  "userId": "56994962184",
  "sessionId": "56994962184",
  "newMessage": {
    "role": "user",
    "parts": [{
      "text": "Hola"
    }]
  }
}
```

**Descripción de campos:**
- `appName` (string): Nombre de la aplicación, obtenido de `AGENT_APP_NAME` (default: "alma")
- `userId` (string): Número de teléfono del usuario que envió el mensaje (sin prefijo +)
- `sessionId` (string): ID de sesión, actualmente igual al `userId` (número de teléfono)
- `newMessage` (object): Objeto que contiene el mensaje del usuario
  - `role` (string): Rol del mensaje, siempre "user" para mensajes entrantes
  - `parts` (array): Array de partes del mensaje
    - `text` (string): Texto del mensaje recibido de WhatsApp

**Ejemplo completo:**
```bash
curl -X POST http://localhost:3000/api/agent \
  -H "Content-Type: application/json" \
  -d '{
    "appName": "alma",
    "userId": "56994962184",
    "sessionId": "56994962184",
    "newMessage": {
      "role": "user",
      "parts": [{
        "text": "Hola, necesito ayuda"
      }]
    }
  }'
```

**Formato de respuesta esperado del agente:**

Tu API del agente debe responder con un JSON. El servicio intenta extraer el texto de la respuesta de varios formatos posibles:

**Formato recomendado (similar al enviado):**
```json
{
  "newMessage": {
    "role": "assistant",
    "parts": [{
      "text": "Hola, ¿cómo puedo ayudarte?"
    }]
  }
}
```

**Otros formatos soportados:**

1. **Respuesta simple:**
```json
{
  "response": "Hola, ¿cómo puedo ayudarte?"
}
```

2. **Respuesta con objeto:**
```json
{
  "response": {
    "text": "Hola, ¿cómo puedo ayudarte?"
  }
}
```

3. **Texto directo:**
```json
{
  "text": "Hola, ¿cómo puedo ayudarte?"
}
```

4. **Mensaje:**
```json
{
  "message": "Hola, ¿cómo puedo ayudarte?"
}
```

**Nota:** Si tu API retorna un formato diferente, el servicio registrará la respuesta completa en los logs pero intentará extraer el texto automáticamente.

**Ejemplo de respuesta completa del agente:**
```bash
# Tu API debe responder con status 200 OK y un JSON
HTTP/1.1 200 OK
Content-Type: application/json

{
  "newMessage": {
    "role": "assistant",
    "parts": [{
      "text": "Hola, ¿cómo puedo ayudarte?"
    }]
  }
}
```

**Envío automático de respuesta a WhatsApp:**

Si configuras `WHATSAPP_API_URL` y `WHATSAPP_ACCESS_TOKEN`, el servicio automáticamente enviará la respuesta del agente de vuelta al usuario de WhatsApp.

**Ejemplo de URL de WhatsApp API:**
```
https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages
```

Response:

```
200 OK - EVENT_RECEIVED
```

---

### 🕘 Legacy (Deprecated)

For backward compatibility (temporary):

| Method | Endpoint   | Status        |
| ------ | ---------- | ------------- |
| `GET`  | `/webhook` | 🟡 Deprecated |
| `POST` | `/webhook` | 🟡 Deprecated |
| `GET`  | `/health`  | 🟡 Deprecated |

Use `/api/v1/whatsapp/...` instead.

---

## 🐳 Docker Commands

| Command      | Description                 |
| ------------ | --------------------------- |
| `make build` | Build Docker image          |
| `make run`   | Run container (with `.env`) |
| `make run-d` | Run container detached      |
| `make stop`  | Stop running container      |
| `make logs`  | View logs                   |
| `make shell` | Enter container shell       |
| `make ps`    | List containers             |
| `make clean` | Remove virtual environment  |

---

## 📊 Logging

* Application startup and shutdown events
* HTTP requests and response times
* Webhook verification (success/failure)
* Message payloads (truncated or sanitized if necessary)
* Exceptions with stack traces

🗂 Logs are written to:

* Console (stdout)
* `logs/app.log`

---

## 🔍 Monitoring

* **Health check**: `/api/v1/whatsapp/health`
* **Log monitoring**: via file or external logging systems (CloudWatch/ELK)

---

## 🚨 Troubleshooting

| Issue                      | Possible Cause               | Fix                                   |
| -------------------------- | ---------------------------- | ------------------------------------- |
| Webhook verification fails | Wrong token or URL not HTTPS | Check `WHATSAPP_VERIFY_TOKEN` and Meta app config |
| App doesn't start          | Missing `.env` vars or port conflict | Recheck environment and logs          |

Enable verbose logs:

```env
LOG_LEVEL=DEBUG
```

---

## 🏗️ Architecture

```
WhatsApp Business API
        │
        ▼
 FastAPI App (/api/v1/whatsapp/webhook)
        │
        ├──► Logging
        │
        └──► Agent Service (if AGENT_URL configured)
```

1. WhatsApp sends webhook events
2. FastAPI validates and logs incoming messages
3. Messages are extracted (phone number and text)
4. Messages are formatted and sent to the agent service (if configured)

---

## 🔒 Security

* Token-based webhook verification
* Input validation for all incoming payloads
* `.env`-based secrets (no hardcoding)
* Optional HTTPS enforcement (reverse proxy or API Gateway)

---

## ⚙️ Performance

* Async I/O for non-blocking processing
* Lightweight dependencies
* Containerized for portability
* Minimal startup time

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`feat/add-telegram-support`)
3. Make your changes
4. Add or update tests
5. Submit a pull request

---

## 📄 License

TBD

---

## 📞 Support

* 🐞 Report issues in the repository's issue tracker
* 📘 Check logs in `logs/app.log`
* 📬 Contact the maintainers via GitHub Issues