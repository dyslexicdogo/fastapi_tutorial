from typing import List
from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.schemas.budget import RolloverTimePoint
from app.crud.budget import get_rollover_over_time

router = APIRouter()


@router.get("/api/rollover-over-time", response_model=List[RolloverTimePoint])
async def rollover_over_time(
    user: str = Depends(get_current_user),
):
    return get_rollover_over_time()
