from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.schemas.budget import (
    EntryRowResponse,
    SaveEntryRequest,
    AutofillRequest,
)
from app.crud.budget import (
    get_entries_for_month,
    save_entries,
    get_previous_month_allocated,
)

router = APIRouter()


@router.get("/api/entry", response_model=list[EntryRowResponse])
async def entry_get(
    year:  int,
    month: int,
    user:  str = Depends(get_current_user),    # ← protected
):
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="month must be 1–12")
    if year < 2000:
        raise HTTPException(status_code=400, detail="invalid year")

    return get_entries_for_month(year, month)


@router.post("/api/entry")
async def entry_post(
    body: SaveEntryRequest,
    user: str = Depends(get_current_user),     # ← protected
):
    if not (1 <= body.month <= 12):
        raise HTTPException(status_code=400, detail="month must be 1–12")
    if len(body.entries) != 14:
        raise HTTPException(status_code=400, detail="expected 14 entries")

    entries = [e.model_dump() for e in body.entries]
    saved   = save_entries(body.year, body.month, entries)
    return {"saved": saved}


@router.post("/api/entry/autofill", response_model=list[EntryRowResponse])
async def entry_autofill(
    body: AutofillRequest,
    user: str = Depends(get_current_user),     # ← protected
):
    return get_previous_month_allocated(body.year, body.month)