from fastapi import APIRouter

from app.api.v1.routes import data_source_router, health_router

api_router = APIRouter()
api_router.include_router(health_router.router)
api_router.include_router(data_source_router.router)