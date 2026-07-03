from fastapi import APIRouter

from app.api.v1 import analyses, auth, chat, health, incidents, knowledge, reports, uploads

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(uploads.router)
api_router.include_router(analyses.router)
api_router.include_router(incidents.router)
api_router.include_router(reports.router)
api_router.include_router(knowledge.router)
