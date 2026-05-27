from fastapi import APIRouter
from app.api import auth

api_router = APIRouter()
api_router.include_router(auth.router)

# Phase 4 additions go here:
# from app.api import entry, view, rollover
# api_router.include_router(entry.router)
# api_router.include_router(view.router)
# api_router.include_router(rollover.router)