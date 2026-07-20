from fastapi import APIRouter

from app.api.v1.routes import (
    agent_router,
    auth_router,
    data_cleaning_router,
    data_source_router,
    export_router,
    health_router,
    superadmin_router,
    users_router,
)

api_router = APIRouter()
api_router.include_router(health_router.router)
api_router.include_router(auth_router.router)
api_router.include_router(users_router.router)
api_router.include_router(superadmin_router.router)
api_router.include_router(data_source_router.router)
api_router.include_router(data_cleaning_router.router)
api_router.include_router(agent_router.router)
api_router.include_router(export_router.router)
