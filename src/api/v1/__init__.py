from fastapi import APIRouter
from src.api.v1.whatsapp.webhook import router as whatsapp_router

api_v1 = APIRouter(prefix="/v1")
api_v1.include_router(whatsapp_router)