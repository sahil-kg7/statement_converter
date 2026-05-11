from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

app = FastAPI(title="Statement Converter", version="0.1.0")
app.include_router(router, prefix="/api")

app_dir = Path(__file__).resolve().parent
workspace_root = app_dir.parents[1]
legacy_static_dir = app_dir / "static"
frontend_dist_dir = workspace_root / "frontend" / "dist"
frontend_dir = frontend_dist_dir if frontend_dist_dir.exists() else legacy_static_dir
assets_dir = (
    frontend_dir / "assets" if frontend_dir == frontend_dist_dir else legacy_static_dir
)

if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


@app.get("/{full_path:path}", include_in_schema=False)
def spa_entry(full_path: str) -> FileResponse:
    candidate = frontend_dir / full_path
    if full_path and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(frontend_dir / "index.html")
