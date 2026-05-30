from typing import List
from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.schemas.budget import ExpensesTimePoint
from app.crud.budget import get_expenses_over_time

router = APIRouter()


@router.get("/api/expenses-over-time", response_model=List[ExpensesTimePoint])
async def expenses_over_time(
    user: str = Depends(get_current_user),
):
    return get_expenses_over_time()
