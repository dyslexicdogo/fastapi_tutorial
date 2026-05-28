from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import init_db
from app.api.router import api_router

app = FastAPI(title="Budget Tracker")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Register all API routes
app.include_router(api_router)


@app.on_event("startup")
async def startup_event():
    init_db()


# ── Page routes ────────────────────────────────────────────────────────────
# These serve the HTML pages. More page routes added in Phase 5.

@app.get("/")
async def root():
    # Redirect bare "/" to the login page
    return RedirectResponse(url="/login")


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request})


@app.get("/entry")
async def entry_page(request: Request):
    return templates.TemplateResponse(request, "entry.html", {"request": request, "title": "Budget Entry"})


@app.get("/view")
async def view_page(request: Request):
    return templates.TemplateResponse(request, "view.html", {"request": request, "title": "Budget View"})

@app.get("/logout")
async def logout():
    # JWT lives in the browser's localStorage — the client clears it.
    # This route just redirects to login; the JS on login.html clears the token.
    return RedirectResponse(url="/login")