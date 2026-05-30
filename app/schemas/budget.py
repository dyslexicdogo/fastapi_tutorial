from pydantic import BaseModel
from typing import List, Optional


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
    entries: List[EntryRow]


class AutofillRequest(BaseModel):
    """Request body for POST /api/entry/autofill."""
    year:  int
    month: int


# ── View schemas ───────────────────────────────────────────────────────────

class MonthRow(BaseModel):
    """One month's data as it appears in the view table."""
    year:         int
    month:        int
    entries:      List[EntryRow]
    monthly_sum:  Optional[float] #= None   # None if any spent values are missing


class ViewResponse(BaseModel):
    """Response for GET /api/view."""
    months:   List[MonthRow]
    has_more: bool


# ── Rollover schemas ───────────────────────────────────────────────────────

class RolloverRow(BaseModel):
    """One bucket's all-time totals."""
    bucket_id:       int
    display_name:    str
    total_allocated: float
    total_spent:     float


class BucketAvgSpent(BaseModel):
    name:  str
    value: float


class CategoryAvgSpent(BaseModel):
    name:     str
    children: List[BucketAvgSpent]


class CategorySpendingTree(BaseModel):
    name:     str
    children: List[CategoryAvgSpent]


class ExpensesTimePoint(BaseModel):
    """Total expenses at a given month."""
    year:        int
    month:       int
    total_spent: float


class SankeyNode(BaseModel):
    name: str


class SankeyLink(BaseModel):
    source: int
    target: int
    value: float


class SankeyData(BaseModel):
    nodes: List[SankeyNode]
    links: List[SankeyLink]


class RolloverTimePoint(BaseModel):
    """Cumulative rollover balance at a given month."""
    year:              int
    month:             int
    cumulative_balance: float