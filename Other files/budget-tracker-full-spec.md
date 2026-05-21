# Budget Tracker — Full Project Specification
**Version:** 3.0 — all 5 design steps complete and locked  
**Ready for:** coding session (Phase 1 onwards)

---

## Project Overview

A personal monthly budget tracking website for a single user. At the end of each month,
the user enters how much was allocated and spent per budget bucket. Two working pages:
a data entry page and a read-only data view page.

---

## User & Constraints

| Constraint | Decision |
|-----------|----------|
| User | Single person, London-based, full-stack developer |
| Backend | Python FastAPI |
| Frontend | HTML + CSS (Tailwind CDN) + vanilla JS. No React, no Vue. |
| Templating | Jinja2 — FastAPI serves HTML pages directly |
| Styling base | `base.html` already built — sidebar, header, footer, Inter font, Font Awesome |
| Database | SQLite — single `budget.db` file |
| Auth | JWT + username/password. Credentials in `.env` only. No users table. |
| Hosting | Render.com free tier + persistent disk (~£1/mo for SQLite) |
| Philosophy | Derived data is never stored — calculated on read |

---

## Step 1 — System Architecture (LOCKED)

### Architecture diagram

```
Browser (HTML + CSS + Vanilla JS)
  ├── /login    — username + password form → receives JWT
  ├── /entry    — data entry page
  └── /view     — read-only data view page
        ↕  HTTP (Jinja2 page renders + REST API calls with JWT)
FastAPI (Python) — single process, does everything
  ├── JWT middleware      — validates token on every protected request
  ├── REST API routes     — JSON in, JSON out
  └── Jinja2 templates   — serves the HTML pages
        ↕  SQL queries
SQLite (budget.db)
  ├── TABLE: buckets          — 14 rows, seeded once at startup, never changes
  ├── TABLE: monthly_entries  — all budget data the user enters
  └── VIEW:  v_rollover       — derived cumulative balance, never stored
```

### Key architectural decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Frontend/backend | Monolith — FastAPI does both | Single process, no CORS, simpler deployment |
| Auth | JWT + bcrypt password in `.env` | No Google Cloud, no OAuth, no users table |
| User storage | `.env` config only | Single user forever |
| ORM | None — raw `sqlite3` from stdlib | Dataset is tiny, SQL is straightforward, no ORM overhead |
| Hosting | Render free tier + persistent disk | Free, one-click deploy, disk survives redeploys |

---

## Step 2 — Data Model (LOCKED)

### Table: `buckets`

```sql
CREATE TABLE IF NOT EXISTS buckets (
  id            INTEGER PRIMARY KEY,
  display_name  TEXT    NOT NULL,
  category      TEXT    NOT NULL,
  category_sort INTEGER NOT NULL,
  sort_order    INTEGER NOT NULL
);
```

Seeded once at startup. Never modified at runtime. No `is_active` column — all 14
buckets are always visible. Mortgage and Prof. fee are zeroed via autofill when
no longer applicable, but never hidden.

---

### Table: `monthly_entries`

```sql
CREATE TABLE IF NOT EXISTS monthly_entries (
  id         INTEGER PRIMARY KEY,
  bucket_id  INTEGER NOT NULL REFERENCES buckets(id),
  year       INTEGER NOT NULL,
  month      INTEGER NOT NULL,   -- 1 to 12
  allocated  DECIMAL(10,2),
  spent      DECIMAL(10,2),      -- NULL = not yet entered (≠ 0 = entered, nothing spent)
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(bucket_id, year, month)
);
```

No `user_id` column — single user, no users table.

Critical rule: `spent = NULL` means the field was left blank (not entered yet).
`spent = 0` means the user entered it and spent nothing. These render differently in the UI.

---

### View: `v_rollover`

```sql
CREATE VIEW IF NOT EXISTS v_rollover AS
  SELECT
    bucket_id,
    SUM(allocated) - SUM(COALESCE(spent, 0)) AS cumulative_balance
  FROM monthly_entries
  GROUP BY bucket_id;
```

Recalculated fresh on every query. `COALESCE(spent, 0)` treats un-entered months as
zero-spent in the rollover — correct behaviour.

---

### Derived values — never stored

| Value | Formula | Where shown |
|-------|---------|-------------|
| Monthly sum | `SUM(allocated - spent)` across all 14 buckets for one month | Rightmost column, /view |
| Rollover balance | `SUM(allocated) - SUM(COALESCE(spent, 0))` per bucket, all-time | Pinned bottom row, /view |

---

### Bucket seed data (14 rows)

```python
BUCKET_SEED = [
    (1,  "Mortgage",              "Fixed commitments",  1, 1),
    (2,  "Prof. fee",             "Fixed commitments",  1, 2),
    (3,  "Monthly essentials",    "Monthly",            2, 3),
    (4,  "Monthly discretionary", "Monthly",            2, 4),
    (5,  "Car (annual)",          "Annual essentials",  3, 5),
    (6,  "Home (annual)",         "Annual essentials",  3, 6),
    (7,  "Health & dental",       "Annual essentials",  3, 7),
    (8,  "Essential travel",      "Annual essentials",  3, 8),
    (9,  "Tech & admin",          "Annual essentials",  3, 9),
    (10, "Car replace (5yr)",     "Expected irregulars",4, 10),
    (11, "Heat pump (10yr)",      "Expected irregulars",4, 11),
    (12, "Unknown unexpected",    "Unknown unexpected", 5, 12),
    (13, "Yolo monthly",          "Yolo",               6, 13),
    (14, "Yolo annual",           "Yolo",               6, 14),
]
# INSERT OR IGNORE INTO buckets VALUES (?,?,?,?,?)
```

---

## Step 3 — API Design (LOCKED)

All endpoints are protected by JWT except `POST /api/auth/login`.
JWT is passed as `Authorization: Bearer <token>` header on every request.

---

### 1. `POST /api/auth/login`

**Purpose:** Validate credentials, return JWT.

Request body:
```json
{
  "username": "admin",
  "password": "yourpassword"
}
```

Response 200:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

Errors: `401 Unauthorized` — wrong username or password.

---

### 2. `GET /api/entry?year=&month=`

**Purpose:** Fetch one month's entries to populate the data entry form.

Query params: `year` (int), `month` (int, 1–12)

Response 200 — array of 14 items, one per bucket in `sort_order`:
```json
[
  {
    "bucket_id":    1,
    "display_name": "Mortgage",
    "sort_order":   1,
    "allocated":    1200.00,
    "spent":        null
  }
]
```

Buckets with no saved entry for that month return `allocated: null, spent: null`.

---

### 3. `POST /api/entry`

**Purpose:** Upsert all 14 rows for a month (the Save button).

Request body:
```json
{
  "year":  2025,
  "month": 5,
  "entries": [
    { "bucket_id": 1, "allocated": 1200.00, "spent": null },
    { "bucket_id": 2, "allocated": 850.00,  "spent": 850.00 }
  ]
}
```

Response 200:
```json
{ "saved": 14 }
```

Uses `INSERT OR REPLACE` — safe to re-save the same month.
A blank `spent` field in the form sends `null`, not `0`.

Errors: `400` invalid year/month, `422` non-numeric values.

---

### 4. `POST /api/entry/autofill`

**Purpose:** Return previous month's allocated values to populate the form.
Does NOT write anything to the database — returns suggested values only.
The user reviews them and clicks Save to persist.

Request body:
```json
{
  "year":  2025,
  "month": 5
}
```

Response 200 — same shape as `GET /api/entry`.
If there is no previous month, returns 14 rows with `allocated: null` — no error.

---

### 5. `GET /api/view?offset=`

**Purpose:** Fetch the history table data, 12 months per page.

Query params: `offset` (int, default 0)
- `offset=0` → most recent 12 months
- `offset=1` → months 13–24 ago
- `offset=2` → months 25–36 ago

Response 200:
```json
{
  "months": [
    {
      "year":  2025,
      "month": 4,
      "entries": [
        { "bucket_id": 1, "allocated": 1200.00, "spent": 1200.00 }
      ],
      "monthly_sum": 4160.00
    }
  ],
  "has_more": true
}
```

`monthly_sum` is calculated server-side. `has_more: true` means show the Older button.
Months with no entries at all are omitted from the array.

---

### 6. `GET /api/rollover`

**Purpose:** Fetch cumulative all-time rollover balance per bucket.
No params — always all-time. Queries `v_rollover` view directly.

Response 200 — array of 14 items:
```json
[
  {
    "bucket_id":          1,
    "display_name":       "Mortgage",
    "cumulative_balance": 2400.00
  }
]
```

---

## Step 4 — UI/UX Design (LOCKED)

### Page 1 — `/entry` (data entry)

**Layout:**
```
[ May ▼ ] [ 2025 ▼ ]  [ Autofill ]          [ Save ]
─────────────────────────────────────────────────────
Bucket                  Allocated £    Spent £
─────────────────────────────────────────────────────
Mortgage                [ 1200     ]   [ 1200  ]
Prof. fee               [ 850      ]   [ 850   ]
Monthly essentials      [ 600      ]   [ 542   ]
Monthly discretionary   [ 400      ]   [       ]   ← blank = NULL
...14 rows total
─────────────────────────────────────────────────────
Monthly total           £ 4,160        partial
```

**JS behaviour — `static/js/entry.js`:**

| Trigger | Action |
|---------|--------|
| Page load | Read `?year=&month=` from URL; default to current month. Call `GET /api/entry`, populate form. |
| Month/year selector change | If unsaved changes exist, warn user. Call `GET /api/entry` for new month. |
| Autofill clicked | Call `POST /api/entry/autofill`. Populate allocated inputs only. Leave spent untouched. |
| Save clicked | Gather all 14 rows. Blank `spent` → send `null`. Call `POST /api/entry`. Show green toast on success. |
| Any allocated input changes | Recalculate and update monthly total live (pure JS, no API call). |
| Non-numeric input | Prevent. Only allow numbers, decimal point, and blank. |

---

### Page 2 — `/view` (data view — read-only)

**Layout:**
```
[ ← Older ]    May 2024 – Apr 2025    [ Newer → ]  (disabled at offset=0)
┌──────────┬──────────┬──────────┬─────────────────────────────┬────────┐
│ Month    │ Mortgage │ Prof.fee │ ... (14 buckets total) ...  │ Sum £  │
├──────────┼──────────┼──────────┼─────────────────────────────┼────────┤
│ Apr 2025 │  1,200   │   850    │            ...              │ 4,160  │
│ Mar 2025 │  1,200   │   850    │            ...              │ 4,160  │
│ Feb 2025 │  1,200   │    —     │            ...              │partial │
│ ...      │          │          │                             │        │
├──────────┼──────────┼──────────┼─────────────────────────────┼────────┤
│ ROLLOVER │  2,400   │  1,700   │            ...              │ 8,240  │  ← pinned
└──────────┴──────────┴──────────┴─────────────────────────────┴────────┘
```

Table must be wrapped in `<div class="overflow-x-auto">` — 16 columns require horizontal scrolling.

**JS behaviour — `static/js/view.js`:**

| Trigger | Action |
|---------|--------|
| Page load | Call `GET /api/view?offset=0` and `GET /api/rollover` in parallel. Render table + rollover row. |
| Older clicked | `offset += 1`. Call `GET /api/view?offset=N`. Re-render table. |
| Newer clicked | `offset -= 1`. Call `GET /api/view?offset=N`. Re-render table. |
| `has_more: false` | Hide Older button. |
| `offset === 0` | Disable Newer button. |
| Click a month row | Navigate to `/entry?year=Y&month=M` for that month. |
| `spent = null` in response | Render as `—`, never as `0`. |

---

### Shared UX rules

- All API calls include `Authorization: Bearer <token>` header.
- On any 401 response, redirect to `/login`.
- Currency formatted as `£X,XXX` (no pence needed for budget amounts).
- Toast messages: green for success, red for error, auto-dismiss after 3 seconds.

---

## Step 5 — Implementation Plan (LOCKED)

Build in this order. Never start a phase until the previous phase is verified.

### Phase 1 — Project skeleton

**Build:** Create folder structure. Set up virtual environment. Write `requirements.txt`.
Write minimal `main.py` that starts FastAPI and returns `{"status": "ok"}` on `GET /`.
Mount static folder. Create `.env` and `.gitignore` (add `.env` and `budget.db` to gitignore
immediately, before writing any secrets).

**Verify:**
```bash
uvicorn app.main:app --reload
# browser: http://localhost:8000 → {"status": "ok"}
```

---

### Phase 2 — Database

**Build:** Write `app/database.py`. On startup: create all tables, create `v_rollover` view,
seed 14 buckets (`INSERT OR IGNORE`). Call `init_db()` from `main.py` startup event.

**Verify:**
```bash
sqlite3 budget.db ".tables"
# expect: buckets  monthly_entries  v_rollover
sqlite3 budget.db "SELECT count(*) FROM buckets;"
# expect: 14
```

---

### Phase 3 — Auth

**Build:** Write `app/auth.py`: bcrypt password verify, JWT encode/decode.
Write `app/api/auth.py`: `POST /api/auth/login`.
Write `get_current_user` FastAPI dependency — reads JWT from Authorization header,
raises `401` if missing or invalid. Write `templates/login.html`.

**Verify:** Open `http://localhost:8000/docs`.
```
POST /api/auth/login  correct creds → 200 + token
POST /api/auth/login  wrong creds  → 401
GET  /api/entry  no token → 401
```

---

### Phase 4 — API routes

**Build:** Write Pydantic schemas in `app/schemas/budget.py` first.
Write raw SQL functions in `app/crud/budget.py`.
Wire into route handlers: `app/api/entry.py`, `app/api/view.py`, `app/api/rollover.py`.
Register all routes in `app/api/router.py`, include router in `main.py`.

**Verify:** All 6 endpoints visible and testable in `/docs`.
Test each with a valid JWT from Phase 3.

---

### Phase 5 — HTML templates

**Build:** Apply fixes to `base.html`:
1. Add `{% block extra_head %}{% endblock %}` before `</head>`
2. Add `{% block extra_scripts %}{% endblock %}` before `</body>`
3. Change `fa-bars-staggered` to `fa-bars`
4. Update sidebar nav links to `/entry`, `/view`, `/logout`

Build `templates/entry.html` and `templates/view.html` as Jinja2 child templates
extending `base.html`. HTML structure only — no JS yet.
Add FastAPI page routes in `main.py` that render the templates.

**Verify:**
```
http://localhost:8000/entry  → page renders, no Jinja2 errors
http://localhost:8000/view   → page renders, no Jinja2 errors
```

---

### Phase 6 — Frontend JavaScript

**Build:** `static/js/entry.js` — on load fetch entries, populate form, wire Autofill +
Save buttons, live monthly total calculation.
`static/js/view.js` — on load fetch view + rollover in parallel, render table,
wire Older/Newer buttons and month-row click navigation.

Load each script in its template via `{% block extra_scripts %}`.

**Verify — full end-to-end flow:**
```
Login → /entry loads the form
→ Autofill populates allocated values
→ Save shows green toast
→ /view shows the saved row
→ Older button paginates correctly
→ Click a month row → /entry opens for that month
→ Rollover row shows cumulative balances
```

---

### Phase 7 — Deploy to Render

**Build:**
1. Push repo to GitHub (confirm `.env` and `budget.db` are in `.gitignore`)
2. Create a Render Web Service, connect the GitHub repo
3. Set build and start commands (see below)
4. Add all `.env` variables in the Render dashboard
5. Add a Render Persistent Disk, mount at `/data`
6. Update `DATABASE_URL=/data/budget.db` in Render environment variables

**Render settings:**
```
Build command:  pip install -r requirements.txt
Start command:  uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Verify:**
```
App loads at your Render URL
Login works
Save an entry
Trigger a redeploy
Entry still there  ← confirms persistent disk is working
```

---

## File Structure

```
budget-tracker/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI app, startup, mounts routes, serves pages
│   ├── config.py             # Reads .env via python-dotenv
│   ├── database.py           # SQLite connect, create tables, seed buckets
│   ├── auth.py               # JWT encode/decode, bcrypt verify, dependency
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py           # POST /api/auth/login
│   │   ├── entry.py          # GET+POST /api/entry, POST /api/entry/autofill
│   │   ├── view.py           # GET /api/view
│   │   ├── rollover.py       # GET /api/rollover
│   │   └── router.py         # Combines all API routes
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── budget.py         # Pydantic request/response models
│   └── crud/
│       ├── __init__.py
│       └── budget.py         # All raw SQL query functions
├── static/
│   ├── css/
│   │   └── style.css         # Custom overrides (minimal)
│   └── js/
│       ├── entry.js          # JS for /entry page
│       └── view.js           # JS for /view page
├── templates/
│   ├── base.html             # Base layout — already built, apply 4 fixes from Step 4
│   ├── login.html            # Login form page
│   ├── entry.html            # Data entry page
│   └── view.html             # Data view page
├── .env                      # Secrets — NEVER commit
├── .gitignore                # Must include .env and budget.db
├── requirements.txt
└── run.py                    # Optional: python run.py to start
```

---

## `requirements.txt`

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
python-multipart==0.0.9
jinja2==3.1.4
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-dotenv==1.0.1
pydantic==2.7.1
```

No SQLAlchemy — raw `sqlite3` from the Python standard library is sufficient.

---

## `.env` Template

```
APP_USERNAME=admin
APP_PASSWORD_HASH=<generate with command below>
JWT_SECRET=<generate with command below>
JWT_EXPIRE_MINUTES=1440
DATABASE_URL=./budget.db
```

---

## Key Commands

```bash
# 1. Create and activate virtual environment
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate bcrypt password hash (paste into .env as APP_PASSWORD_HASH)
python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('yourpassword'))"

# 4. Generate JWT secret (paste into .env as JWT_SECRET)
python -c "import secrets; print(secrets.token_hex(32))"

# 5. Run development server
uvicorn app.main:app --reload

# 6. Inspect database
sqlite3 budget.db ".tables"
sqlite3 budget.db "SELECT * FROM buckets;"

# 7. Open API docs (test all endpoints interactively)
open http://localhost:8000/docs
```

---

## All Key Decisions (Reference)

| Decision | Choice | Reason |
|----------|--------|--------|
| Auth | JWT + bcrypt in `.env` | No Google Cloud, no OAuth, simplest for single user |
| Users table | None | Single user forever |
| `user_id` on entries | Not present | Redundant without a users table |
| ORM | None — raw sqlite3 | Tiny dataset, clean SQL, no overhead |
| UI model | Two pages: /entry and /view | Clean separation, avoids complex inline-edit JS |
| Data entry layout | Flat list, all 14 buckets | User preference — no category grouping on form |
| Save behaviour | Upsert all 14 rows at once | One round-trip, one transaction, safe to repeat |
| Autofill | Returns data only — does not save | User reviews before committing |
| First-month autofill | No-op, no error | Graceful degradation |
| `spent = NULL` vs `0` | NULL = not entered; 0 = entered zero | Allows UI to distinguish blank from zero |
| Rollover storage | Never stored — SQL VIEW | <1ms query, no staleness risk |
| Derived data | Never stored | Calculated on read throughout |
| `is_active` on buckets | Rejected | Zero via autofill is sufficient |
| Table orientation | Months = rows, buckets = columns | User's explicit preference |
| Month navigation | Default 12, pageable with offset | User wants history accessible |
| Monthly sum | Calculated server-side in API response | Business logic stays in Python |
| `has_more` vs page count | Boolean only | Simpler, no extra COUNT(*) query |
| Chart.js loading | Per-page only via `extra_scripts` block | Don't load on every page |

---

## Prompt to Start Coding

Paste this entire document into a new chat, then add:

> All 5 design steps are complete. Please start the implementation from Phase 1.
>
> Work through each phase in order, producing the actual code for each file.
> After each phase, show the verify step so I can confirm it works before
> we move to the next phase.
>
> Start with Phase 1: project skeleton.
> Create the folder structure, `requirements.txt`, a minimal `app/main.py`,
> `.env` template, and `.gitignore`.
