import sqlite3
from typing import Optional
from app.database import get_connection


# ── Entry CRUD ─────────────────────────────────────────────────────────────

def get_entries_for_month(year: int, month: int) -> list[dict]:
    """
    Fetch all 14 buckets for a given month.
    Buckets with no saved entry return allocated=None, spent=None.
    Uses a LEFT JOIN so all buckets appear even with no monthly_entries row.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            b.id           AS bucket_id,
            b.display_name,
            b.sort_order,
            me.allocated,
            me.spent
        FROM buckets b
        LEFT JOIN monthly_entries me
            ON me.bucket_id = b.id
            AND me.year     = ?
            AND me.month    = ?
        ORDER BY b.sort_order
    """, (year, month))

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def save_entries(year: int, month: int, entries: list[dict]) -> int:
    """
    Upsert all 14 rows for a month in a single transaction.
    INSERT OR REPLACE handles both new entries and updates to existing ones.
    Returns the number of rows saved.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.executemany("""
        INSERT OR REPLACE INTO monthly_entries
            (bucket_id, year, month, allocated, spent, updated_at)
        VALUES
            (:bucket_id, :year, :month, :allocated, :spent, CURRENT_TIMESTAMP)
    """, [
        {
            "bucket_id": e["bucket_id"],
            "year":      year,
            "month":     month,
            "allocated": e["allocated"],
            "spent":     e["spent"],
        }
        for e in entries
    ])

    saved = cur.rowcount
    conn.commit()
    conn.close()
    return saved


def get_previous_month_allocated(year: int, month: int) -> list[dict]:
    """
    Fetch the previous month's allocated values for autofill.
    Returns the same shape as get_entries_for_month but with spent=None always.
    If there is no previous month, all allocated values will be None.
    """
    # Calculate previous month — handles January → December rollback
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    rows = get_entries_for_month(prev_year, prev_month)

    # Autofill only touches allocated — clear spent from the response
    for row in rows:
        row["spent"] = None

    return rows


# ── View CRUD ──────────────────────────────────────────────────────────────

def get_view_data(offset: int = 0) -> dict:
    """
    Fetch 12 months of entry data for the view table.
    offset=0 → most recent 12 months
    offset=1 → months 13-24 ago, etc.

    monthly_sum is None if any bucket's spent is NULL for that month
    (can't calculate a complete sum from incomplete data).

    has_more is True if there are entries older than the current page.
    """
    conn = get_connection()
    cur  = conn.cursor()

    # Step 1: find which months have data, paginated
    # We fetch 13 rows but only return 12 — the 13th tells us has_more
    cur.execute("""
        SELECT DISTINCT year, month
        FROM monthly_entries
        ORDER BY year DESC, month DESC
        LIMIT 13 OFFSET ?
    """, (offset * 12,))

    month_keys = cur.fetchall()
    has_more   = len(month_keys) == 13
    month_keys = month_keys[:12]   # trim back to 12

    if not month_keys:
        conn.close()
        return {"months": [], "has_more": False}

    # Step 2: fetch all entries for those months
    # Build a WHERE clause for the exact year/month pairs
    placeholders = ",".join(["(?,?)"] * len(month_keys))
    params       = [val for mk in month_keys for val in (mk["year"], mk["month"])]

    cur.execute(f"""
        SELECT
            me.year,
            me.month,
            me.bucket_id,
            me.allocated,
            me.spent
        FROM monthly_entries me
        WHERE (me.year, me.month) IN ({placeholders})
        ORDER BY me.year DESC, me.month DESC, me.bucket_id
    """, params)

    all_entries = cur.fetchall()
    conn.close()

    # Step 3: group entries by month
    months_dict: dict = {}
    for row in all_entries:
        key = (row["year"], row["month"])
        if key not in months_dict:
            months_dict[key] = {
                "year":    row["year"],
                "month":   row["month"],
                "entries": [],
            }
        months_dict[key]["entries"].append({
            "bucket_id": row["bucket_id"],
            "allocated": row["allocated"],
            "spent":     row["spent"],
        })

    # Step 4: calculate monthly_sum per month
    # None if any spent value is NULL (partial month)
    months = []
    for key in sorted(months_dict, reverse=True):
        m       = months_dict[key]
        entries = m["entries"]

        monthly_sum  = sum((e["allocated"] or 0) - (e["spent"] or 0) for e in entries)

        months.append({
            "year":        m["year"],
            "month":       m["month"],
            "entries":     entries,
            "monthly_sum": monthly_sum,
        })

    return {"months": months, "has_more": has_more}


# ── Rollover CRUD ──────────────────────────────────────────────────────────

def get_rollover() -> list[dict]:
    """
    Fetch cumulative all-time balance per bucket from the v_rollover view.
    Joins with buckets to include display_name in the response.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            b.id           AS bucket_id,
            b.display_name,
            COALESCE(vr.cumulative_balance, 0) AS cumulative_balance
        FROM buckets b
        LEFT JOIN v_rollover vr ON vr.bucket_id = b.id
        ORDER BY b.sort_order
    """)

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows