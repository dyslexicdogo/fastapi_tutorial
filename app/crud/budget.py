import sqlite3
from typing import List, Optional
from app.database import get_connection


# ── Entry CRUD ─────────────────────────────────────────────────────────────

def get_entries_for_month(year: int, month: int) -> List[dict]:
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


def save_entries(year: int, month: int, entries: List[dict]) -> int:
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


def get_previous_month_allocated(year: int, month: int) -> List[dict]:
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
    Fetch 10 months of entry data for the view table.
    offset=0 → most recent 10 months
    offset=1 → months 11-20 ago, etc.

    has_more is True if there are entries older than the current page.
    """
    conn = get_connection()
    cur  = conn.cursor()

    # Step 1: find which months have data, paginated
    # We fetch 11 rows but only return 10 — the 11th tells us has_more
    cur.execute("""
        SELECT DISTINCT year, month
        FROM monthly_entries
        ORDER BY year DESC, month DESC
        LIMIT 11 OFFSET ?
    """, (offset * 10,))

    month_keys = cur.fetchall()
    has_more   = len(month_keys) == 11
    month_keys = month_keys[:10]   # trim back to 10

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

def get_rollover() -> List[dict]:
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


def get_avg_spent_by_category() -> dict:
    """
    Fetch average spent per bucket grouped by category,
    structured as a hierarchy for D3 treemap.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            b.category,
            b.category_sort,
            b.display_name,
            b.sort_order,
            AVG(COALESCE(me.spent, 0)) AS avg_spent
        FROM buckets b
        LEFT JOIN monthly_entries me ON me.bucket_id = b.id
        GROUP BY b.id, b.category, b.category_sort, b.display_name, b.sort_order
        ORDER BY b.category_sort, b.sort_order
    """)

    rows = cur.fetchall()
    conn.close()

    categories: dict = {}
    for row in rows:
        cat = row["category"]
        if cat not in categories:
            categories[cat] = {"name": cat, "children": []}
        categories[cat]["children"].append({
            "name":  row["display_name"],
            "value": round(row["avg_spent"], 2),
        })

    children = sorted(categories.values(),
                      key=lambda c: -max(ch["value"] for ch in c["children"]))

    return {"name": "root", "children": children}


def get_expenses_over_time() -> List[dict]:
    """
    Fetch total spent per month over time.
    Returns one row per month with the sum of spent amounts.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            year,
            month,
            SUM(COALESCE(spent, 0)) AS total_spent
        FROM monthly_entries
        GROUP BY year, month
        ORDER BY year, month
    """)

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_sankey_data() -> dict:
    """
    Fetch data for a sankey diagram showing the flow from total allocated
    through total spent (per category) and rollover.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            SUM(allocated)            AS total_allocated,
            SUM(COALESCE(spent, 0))   AS total_spent
        FROM monthly_entries
    """)
    totals   = cur.fetchone()
    total_allocated = round(totals["total_allocated"] or 0, 2)
    total_spent     = round(totals["total_spent"] or 0, 2)
    rollover        = round(total_allocated - total_spent, 2)

    cur.execute("""
        SELECT
            b.category,
            b.category_sort,
            SUM(COALESCE(me.spent, 0)) AS total_spent
        FROM monthly_entries me
        JOIN buckets b ON b.id = me.bucket_id
        GROUP BY b.category, b.category_sort
        ORDER BY b.category_sort
    """)
    cat_rows = cur.fetchall()
    conn.close()

    nodes = [
        {"name": "Total allocated"},
        {"name": "Total spent"},
        {"name": "Rollover"},
    ]

    links = [
        {"source": 0, "target": 1, "value": total_spent},
        {"source": 0, "target": 2, "value": rollover},
    ]

    for row in cat_rows:
        idx = len(nodes)
        nodes.append({"name": row["category"]})
        links.append({"source": 1, "target": idx, "value": round(row["total_spent"], 2)})

    return {"nodes": nodes, "links": links}


def get_rollover_over_time() -> List[dict]:
    """
    Fetch cumulative rollover balance over time.
    Returns one row per month with the running total of (allocated - spent).
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            year,
            month,
            SUM(SUM(allocated - COALESCE(spent, 0)))
                OVER (ORDER BY year, month) AS cumulative_balance
        FROM monthly_entries
        GROUP BY year, month
        ORDER BY year, month
    """)

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows