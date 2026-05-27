from fastapi import APIRouter
from app.api import auth, entry, view, rollover

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(entry.router)
api_router.include_router(view.router)
api_router.include_router(rollover.router)