"""FastAPI application entrypoint for the Heathrow taxi rank MVP."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import DEFAULT_TERMINALS
from app.models import ConflictError, NotFoundError
from app.routers import admin, driver, pages, rank_agent, screens
from app.store import get_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services import admin_service

    store = get_store()
    for terminal_id, name in DEFAULT_TERMINALS:
        if terminal_id not in store.terminals:
            admin_service.add_terminal(store, terminal_id, name)
    yield


app = FastAPI(
    title="Heathrow Taxi Rank System",
    description=(
        "MVP for managing the Heathrow Airport feeder park: queue wait "
        "estimation, terminal dispatch notifications, and the local / "
        "fares-fare return exemptions."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(NotFoundError)
def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ConflictError)
def handle_conflict(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


app.include_router(driver.router)
app.include_router(rank_agent.router)
app.include_router(admin.router)
app.include_router(screens.router)
app.include_router(pages.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
