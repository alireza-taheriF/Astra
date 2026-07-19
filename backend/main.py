"""
Astra backend — FastAPI application entrypoint.

Wires the API routers into a single app. Kept minimal so cold starts stay fast;
heavy dependencies are imported lazily inside the routes/services that need them.
"""

from __future__ import annotations

from fastapi import FastAPI

from routers import badge

app = FastAPI(
    title="Astra API",
    version="1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.include_router(badge.router)


@app.get("/api/health", tags=["ops"])
def health() -> dict[str, str]:
    return {"status": "ok"}
