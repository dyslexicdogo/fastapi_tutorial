from fastapi import APIRouter
from app.api import auth, entry, view, rollover, rollover_time, expenses_time, category_spending, sankey

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(entry.router)
api_router.include_router(view.router)
api_router.include_router(rollover.router)
api_router.include_router(rollover_time.router)
api_router.include_router(expenses_time.router)
api_router.include_router(category_spending.router)
api_router.include_router(sankey.router)