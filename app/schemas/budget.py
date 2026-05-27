from pydantic import BaseModel
from typing import Optional


# ── Entry schemas ──────────────────────────────────────────────────────────

class EntryRow(BaseModel):
    """One bucket's data for a single month — used in both request and response."""
    bucket_id:    int
    allocated:    Optional[float] = None
    spent:        Optional[float] = None   # None = not entered (≠ 0 = entered, nothing spent)


class EntryRowResponse(EntryRow):
    """Response shape — adds display_name and sort_order for the frontend."""
    display_name: str
    sort_order:   int


class SaveEntryRequest(BaseModel):
    """Request body for POST /api/entry — saves all 14 rows at once."""
    year:    int
    month:   int
    entries: list[EntryRow]


class AutofillRequest(BaseModel):
    """Request body for POST /api/entry/autofill."""
    year:  int
    month: int


# ── View schemas ───────────────────────────────────────────────────────────

class MonthRow(BaseModel):
    """One month's data as it appears in the view table."""
    year:         int
    month:        int
    entries:      list[EntryRow]
    monthly_sum:  Optional[float] #= None   # None if any spent values are missing


class ViewResponse(BaseModel):
    """Response for GET /api/view."""
    months:   list[MonthRow]
    has_more: bool


# ── Rollover schemas ───────────────────────────────────────────────────────

class RolloverRow(BaseModel):
    """One bucket's cumulative all-time balance."""
    bucket_id:          int
    display_name:       str
    cumulative_balance: float