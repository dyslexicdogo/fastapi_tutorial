from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.schemas.budget import CategorySpendingTree
from app.crud.budget import get_avg_spent_by_category

router = APIRouter()


@router.get("/api/category-spending", response_model=CategorySpendingTree)
async def category_spending(
    user: str = Depends(get_current_user),
):
    return get_avg_spent_by_category()
