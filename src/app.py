from fastapi import FastAPI
from src.api.v1 import api_v1

app = FastAPI(title="WhatsApp Inbound Orchestrator", version="1.0.0")

app.include_router(api_v1, prefix="/api")