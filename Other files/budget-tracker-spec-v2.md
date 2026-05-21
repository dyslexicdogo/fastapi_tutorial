# Budget Tracker — Full Project Specification
**Version:** 2.0 (clean restart)  
**Status:** Design steps 1 & 2 locked. Ready to continue from Step 3: API Design.

---

## What This Document Is

This is a full handover for a personal budget tracking web app. The software design
process is being followed in 5 steps. Steps 1 and 2 are complete and locked.
Pick up from Step 3: API Design.

---

## Project Overview

A personal monthly budget tracking website for a single user. At the end of each month,
the user enters how much was allocated and spent per budget bucket. The app has two main
working pages: a data entry page and a read-only data view page. Simple, no frills,
self-hosted on a free cloud tier.

---

## User & Constraints

- **User:** Single person, London-based, full-stack developer
- **Stack:** Python FastAPI (backend) + HTML/CSS/vanilla JS (frontend). No React, no Vue.
- **Templating:** Jinja2 (FastAPI serves HTML pages directly — no separate frontend deployment)
- **Styling:** Tailwind CSS (CDN), Font Awesome icons, Inter font (Google Fonts)
- **Database:** SQLite — single `.db` file on the server
- **Auth:** JWT + username/password. Credentials stored in `.env` only. No users table.
- **Hosting:** Render.com free tier (one Python process, one deployment)
- **Philosophy:** Keep it simple. Derived data is never stored — calculated on read.

---

## The 5-Step Design Process

| Step | Topic | Status |
|------|-------|--------|
| 1 | System Architecture | ✅ Locked |
| 2 | Data Model | ✅ Locked |
| 3 | API Design | ⬜ Next |
| 4 | UI/UX Design | ⬜ Todo |
| 5 | Implementation Plan | ⬜ Todo |

---

## Step 1 — System Architecture (LOCKED)

### How the pieces connect

```
Browser (HTML + CSS + Vanilla JS)
  ├── /login    — username + password form → receives JWT
  ├── /entry    — data entry page (month selector + 14-row form)
  └── /view     — read-only data view page (historical table)
        ↕  HTTP (Jinja2 page renders + REST API calls with JWT)
FastAPI (Python) — single process, does everything
  ├── JWT middleware      — validates token on every protected request
  ├── REST API routes     — JSON in, JSON out
  └── Jinja2 templates   — serves the HTML pages
        ↕  SQL queries
SQLite (budget.db)
  ├── TABLE: buckets          — 14 rows, seeded once at startup
  ├── TABLE: monthly_entries  — all budget data the user enters
  └── VIEW:  v_rollover       — derived cumulative balance, never stored
```

### Key architectural decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Frontend/backend split | Monolith — FastAPI does both | Single process, simpler deployment, no CORS |
| Auth mechanism | JWT + username/password | No Google Cloud project needed, no OAuth redirect |
| User storage | `.env` config only — no users table | Single user forever, simplest possible |
| Hosting | Render free tier | Free, supports Python, one-click deploy |
| SQLite persistence | Render persistent disk (~$1/mo) needed | Free tier has ephemeral storage — file wiped on redeploy |

---

## Step 2 — Data Model (LOCKED)

### Table: `buckets`

Stores the 14 budget bucket definitions. Seeded once at app startup. Never modified at runtime.

```sql
CREATE TABLE buckets (
  id            INTEGER PRIMARY KEY,
  display_name  TEXT    NOT NULL,
  category      TEXT    NOT NULL,
  category_sort INTEGER NOT NULL,   -- controls category grouping order
  sort_order    INTEGER NOT NULL    -- controls row order in the UI
);
```

**No `is_active` column** — explicitly rejected. All 14 buckets are always visible.
Two buckets (Mortgage, Prof. fee) may eventually be zeroed out via autofill, but are
never hidden or deactivated. Full history is always preserved.

---

### Table: `monthly_entries`

The only table that grows over time. One row per bucket per month. 14 rows written
on every Save action.

```sql
CREATE TABLE monthly_entries (
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

**No `user_id` column** — intentionally absent. Single user, no users table needed.

**Critical rule on `spent`:**
- `NULL` = the user has not entered this field yet → shown as blank / `—` in the UI
- `0` = the user entered it and spent nothing → shown as `0`

---

### View: `v_rollover`

Calculates the cumulative all-time balance per bucket. Not stored — recalculated on every query.
For ~1,680 rows (14 buckets × 12 months × 10 years) SQLite runs this in under 1ms.

```sql
CREATE VIEW v_rollover AS
  SELECT
    bucket_id,
    SUM(allocated) - SUM(COALESCE(spent, 0)) AS cumulative_balance
  FROM monthly_entries
  GROUP BY bucket_id;
```

`COALESCE(spent, 0)` treats unset months as zero-spent in the rollover calculation,
which is the correct behaviour — an un-entered month doesn't inflate the balance.

---

### Derived values (never stored)

| Value | Formula | Where shown |
|-------|---------|-------------|
| Monthly sum | `SUM(allocated - spent)` across all 14 buckets for one month | Rightmost column on /view |
| Rollover balance | `SUM(allocated) - SUM(COALESCE(spent, 0))` per bucket, all-time | Pinned bottom row on /view |

---

### Bucket seed data (14 rows)

These are inserted at app startup via a seed function. If they already exist, skip.

| id | display_name | category | category_sort | sort_order |
|----|-------------|----------|--------------|-----------|
| 1  | Mortgage | Fixed commitments | 1 | 1 |
| 2  | Prof. fee | Fixed commitments | 1 | 2 |
| 3  | Monthly essentials | Monthly | 2 | 3 |
| 4  | Monthly discretionary | Monthly | 2 | 4 |
| 5  | Car (annual) | Annual essentials | 3 | 5 |
| 6  | Home (annual) | Annual essentials | 3 | 6 |
| 7  | Health & dental | Annual essentials | 3 | 7 |
| 8  | Essential travel | Annual essentials | 3 | 8 |
| 9  | Tech & admin | Annual essentials | 3 | 9 |
| 10 | Car replace (5yr) | Expected irregulars | 4 | 10 |
| 11 | Heat pump (10yr) | Expected irregulars | 4 | 11 |
| 12 | Unknown unexpected | Unknown unexpected | 5 | 12 |
| 13 | Yolo monthly | Yolo | 6 | 13 |
| 14 | Yolo annual | Yolo | 6 | 14 |

---

## The Two Working Pages

### Page 1 — `/entry` (Data Entry)

**Purpose:** Enter or update figures for a single chosen month.

**Layout (top to bottom):**
1. Month + year selector — defaults to current month on load
2. Flat list of all 14 buckets in `sort_order` sequence (no category grouping)
3. Each row: `bucket display_name` | `allocated` input | `spent` input
4. Two action buttons: **Autofill** and **Save**

**Behaviour rules:**
- Loading a month that has existing entries → populate form with those values
- Loading a month with no entries → blank form
- `spent` inputs left blank → saved as `NULL` (not entered)
- `spent` inputs set to `0` → saved as `0` (entered, nothing spent)
- **Autofill:** copies the previous month's `allocated` values into the allocated column only. `spent` is always entered manually. If there is no previous month (first ever use), autofill does nothing — no error shown.
- **Save:** upserts all 14 rows at once using `INSERT OR REPLACE`. Safe to re-save the same month repeatedly.

---

### Page 2 — `/view` (Data View)

**Purpose:** Read-only historical overview of all entered data.

**Layout:**
- Table where **rows = months** (newest at top), **columns = 14 buckets + 1 monthly sum column**
- Cells where `spent` is `NULL` display as `—` (not entered), not `0`
- **Monthly sum column** (rightmost): `SUM(allocated - spent)` for that month across all 14 buckets
- **Rollover row** (pinned at bottom): cumulative `SUM(allocated) - SUM(COALESCE(spent, 0))` per bucket, all-time (from `v_rollover` view)
- **No editing on this page** — read-only

**Open question (to decide at Step 3):**
Does `/view` always show a fixed trailing 12 months, or can the user page back further?
This affects the API endpoint design.

---

## Environment Variables (`.env`)

```
APP_USERNAME=admin
APP_PASSWORD_HASH=<bcrypt hash — generate with command below>
JWT_SECRET=<random 32-byte hex string>
JWT_EXPIRE_MINUTES=1440
DATABASE_URL=./budget.db
```

**Generate password hash:**
```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

**Never commit `.env` to git.** Add to `.gitignore` before writing any secrets.

---

## Project File Structure

```
budget-tracker/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app, mounts routes, seeds DB
│   ├── config.py         # Reads .env settings
│   ├── database.py       # SQLite connection, table creation, seed
│   ├── auth.py           # JWT encode/decode, password verify
│   ├── models/
│   │   └── budget.py     # SQLAlchemy or raw SQL row models
│   ├── schemas/
│   │   └── budget.py     # Pydantic request/response schemas
│   ├── api/
│   │   ├── auth.py       # POST /api/auth/login
│   │   ├── entry.py      # GET+POST /api/entry, POST /api/entry/autofill
│   │   ├── view.py       # GET /api/view
│   │   ├── rollover.py   # GET /api/rollover
│   │   └── router.py     # Combines all API routes
│   └── crud/
│       └── budget.py     # All DB query functions
├── static/
│   ├── css/style.css
│   └── js/
│       ├── entry.js      # JS for /entry page
│       └── view.js       # JS for /view page
├── templates/
│   ├── base.html         # Base layout (sidebar, header, footer — already built)
│   ├── login.html
│   ├── entry.html
│   └── view.html
├── .env                  # Secrets — never commit
├── .gitignore            # Must include .env and budget.db
├── requirements.txt
└── run.py
```

---

## What Is Already Built

- `base.html` — complete base layout with collapsible sidebar, sticky header, Tailwind CSS,
  Font Awesome, Inter font, hamburger menu JS. Child templates extend it using
  `{% block content %}{% endblock %}`.

---

## All Key Decisions (Reference)

| Decision | Choice | Reason |
|----------|--------|--------|
| Auth | JWT + bcrypt password in `.env` | No Google Cloud needed, no OAuth, simplest for single user |
| Users table | None | Single user forever |
| `user_id` on entries | Not present | Redundant without a users table |
| UI model | Two pages: /entry and /view | Clean separation; avoids complex inline-edit JS |
| Data entry layout | Flat list of all 14 buckets | User preference — no category grouping on the form |
| Save behaviour | Upsert all 14 rows at once | Natural fit for monthly review; simpler than per-cell saves |
| Autofill | Copy prev month's `allocated` verbatim | Reads from `monthly_entries`, no separate presets table |
| First-month autofill | No-op, no error | Graceful degradation |
| `spent = NULL` vs `0` | NULL = not entered; 0 = entered zero | Allows UI to distinguish blank from zero |
| Rollover storage | Never stored — SQL VIEW | Dataset is tiny; SQLite handles it in <1ms |
| Sum total storage | Never stored — calculated on read | Same reasoning as rollover |
| `is_active` on buckets | Rejected | Not needed; zero via autofill is sufficient |
| Bucket count | 14 rows across 7 categories | Final confirmed structure |
| Table orientation | Months = rows, buckets = columns | User's explicit preference |
| Rollover display | Pinned bottom row on /view | Cumulative per bucket, all-time |

---

## Open Questions (Resolve at Step 3)

1. **Month navigation on /view:** Does the table show a fixed trailing 12 months,
   or can the user page back to see older months? Affects the `GET /api/view` endpoint design.

2. **SQLite on Render:** Render free tier has ephemeral disk — the `.db` file is wiped
   on each redeploy. Render's persistent disk (~$1/mo) solves this. Needs a decision
   before the deployment step.

---

## Prompt to Continue in a New Chat

Paste this entire document, then add:

> We are designing a personal budget tracker web app. Steps 1 (System Architecture) and
> 2 (Data Model) are complete and locked — all decisions are in the document above.
>
> Please continue from **Step 3: API Design**.
>
> For Step 3, define every FastAPI REST endpoint needed for this app:
> - `POST /api/auth/login` — validate credentials, return JWT
> - `GET  /api/entry?year=&month=` — fetch one month's 14 entries for the form
> - `POST /api/entry` — upsert all 14 rows for a month (Save)
> - `POST /api/entry/autofill` — copy prev month's allocated into a new month
> - `GET  /api/view` — fetch N months of entries for the table
> - `GET  /api/rollover` — fetch cumulative rollover per bucket
>
> For each endpoint specify: URL, HTTP method, request body or query params shape,
> and response JSON shape. Also resolve the open question about month navigation
> on /view before designing that endpoint.
>
> After Step 3 is locked, continue to Step 4 (UI/UX Design) and Step 5
> (Implementation Plan) in sequence.
