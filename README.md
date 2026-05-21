# Budget Tracker

A personal monthly budget tracking web app built with FastAPI, SQLite, and vanilla JavaScript. Designed for a single-user workflow with JWT authentication, monthly budget entry, autofill from previous months, rollover balance tracking, and a read-only historical dashboard.

## Features

* Monthly budget allocation and spending tracking
* Autofill previous month allocations
* Read-only history view with rollover balances
* JWT authentication with credentials stored in `.env`
* FastAPI + Jinja2 monolith architecture
* SQLite database with derived SQL views
* Lightweight frontend using Tailwind CDN and vanilla JS
* Ready for deployment on Render

## Tech Stack

* Backend: Python + FastAPI
* Frontend: HTML, Tailwind CSS, Vanilla JavaScript
* Database: SQLite
* Auth: JWT + bcrypt
* Deployment: Render.com + persistent disk storage
