from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.schemas.budget import SankeyData
from app.crud.budget import get_sankey_data

router = APIRouter()


@router.get("/api/sankey", response_model=SankeyData)
async def sankey(
    user: str = Depends(get_current_user),
):
    return get_sankey_data()
