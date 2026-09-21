"""Serves the four role-based HTML pages (driver app, rank agent console,
admin console, feeder park information screen). All data on the pages is
fetched client-side from the JSON API in app/static/*.js.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "home.html", {"active": "home"})


@router.get("/driver", response_class=HTMLResponse)
def driver_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "driver.html", {"active": "driver"})


@router.get("/rank-agent", response_class=HTMLResponse)
def rank_agent_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "rank_agent.html", {"active": "rank-agent"})


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "admin.html", {"active": "admin"})


@router.get("/screen", response_class=HTMLResponse)
def screen_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "screen.html", {"active": "screen"})
