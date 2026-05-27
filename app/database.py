import sqlite3
from app.config import DATABASE_URL


# ── Seed data ──────────────────────────────────────────────────────────────
# 14 budget buckets. Inserted once at startup, never changed at runtime.
# (id, display_name, category, category_sort, sort_order)

BUCKET_SEED = [
    (1,  "Mortgage",              "Fixed commitments",   1,  1),
    (2,  "Prof. fee",             "Fixed commitments",   1,  2),
    (3,  "Monthly essentials",    "Monthly",             2,  3),
    (4,  "Monthly discretionary", "Monthly",             2,  4),
    (5,  "Car (annual)",          "Annual essentials",   3,  5),
    (6,  "Home (annual)",         "Annual essentials",   3,  6),
    (7,  "Health & dental",       "Annual essentials",   3,  7),
    (8,  "Essential travel",      "Annual essentials",   3,  8),
    (9,  "Tech & admin",          "Annual essentials",   3,  9),
    (10, "Car replace (5yr)",     "Expected irregulars", 4, 10),
    (11, "Heat pump (10yr)",      "Expected irregulars", 4, 11),
    (12, "Unknown unexpected",    "Unknown unexpected",  5, 12),
    (13, "Yolo monthly",          "Yolo",                6, 13),
    (14, "Yolo annual",           "Yolo",                6, 14),
]


# ── Connection ─────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """
    Open and return a SQLite connection.
    Called once per request in the API route handlers (Phase 4).

    row_factory = sqlite3.Row makes rows behave like dicts:
      row["bucket_id"]  instead of  row[0]
    This matters a lot when you start building API responses.

    check_same_thread=False is required for FastAPI — SQLite's default
    rejects connections used across threads, but FastAPI's async context
    needs this relaxed.
    """
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ── Init ───────────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Create all tables, the v_rollover view, and seed the 14 buckets.
    Safe to call on every startup — IF NOT EXISTS and INSERT OR IGNORE
    mean nothing breaks or duplicates if this has already run before.
    """
    conn = get_connection()
    cur  = conn.cursor()

    # ── Table: buckets ──────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS buckets (
            id            INTEGER PRIMARY KEY,
            display_name  TEXT    NOT NULL,
            category      TEXT    NOT NULL,
            category_sort INTEGER NOT NULL,
            sort_order    INTEGER NOT NULL
        )
    """)

    # ── Table: monthly_entries ──────────────────────────────────────────
    # spent = NULL means not yet entered (different from spent = 0)
    # UNIQUE(bucket_id, year, month) enforces one row per bucket per month
    cur.execute("""
        CREATE TABLE IF NOT EXISTS monthly_entries (
            id         INTEGER PRIMARY KEY,
            bucket_id  INTEGER NOT NULL REFERENCES buckets(id),
            year       INTEGER NOT NULL,
            month      INTEGER NOT NULL,
            allocated  DECIMAL(10,2),
            spent      DECIMAL(10,2),
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(bucket_id, year, month)
        )
    """)

    # ── View: v_rollover ────────────────────────────────────────────────
    # A VIEW is a saved query — queried like a table but never stores data.
    # COALESCE(spent, 0) treats NULL (not entered) as 0 in the sum,
    # so un-entered months don't inflate the rollover balance.
    cur.execute("""
        CREATE VIEW IF NOT EXISTS v_rollover AS
            SELECT
                bucket_id,
                SUM(allocated) - SUM(COALESCE(spent, 0)) AS cumulative_balance
            FROM monthly_entries
            GROUP BY bucket_id
    """)

    # ── Seed buckets ────────────────────────────────────────────────────
    # INSERT OR IGNORE skips any row whose PRIMARY KEY already exists.
    # executemany runs one INSERT per tuple in the list — more efficient
    # than calling execute() 14 times in a loop.
    cur.executemany(
        """
        INSERT OR IGNORE INTO buckets
            (id, display_name, category, category_sort, sort_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        BUCKET_SEED
    )

    conn.commit()   # write everything to disk
    conn.close()    # release the file lock

    print("✓ Database ready")