from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.schemas.budget import ViewResponse
from app.crud.budget import get_view_data

router = APIRouter()


@router.get("/api/view", response_model=ViewResponse)
async def view_get(
    offset: int = 0,
    user:   str = Depends(get_current_user),   # ← protected
):
    return get_view_data(offset)