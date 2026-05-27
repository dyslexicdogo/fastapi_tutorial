from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.schemas.budget import RolloverRow
from app.crud.budget import get_rollover

router = APIRouter()


@router.get("/api/rollover", response_model=list[RolloverRow])
async def rollover_get(
    user: str = Depends(get_current_user),     # ← protected
):
    return get_rollover()