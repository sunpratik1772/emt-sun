"""Report downloads — CSV and Excel exports from workflow runs.

Files are written under `OUTPUT_DIR` by ``csv_output`` / ``excel_output`` nodes.
The frontend receives a URL with only the basename (`/report/foo.csv`).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..deps import OUTPUT_DIR

router = APIRouter(tags=["reports"])

_MEDIA: dict[str, str] = {
    ".csv": "text/csv; charset=utf-8",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
}


def _media_type(name: str) -> str:
    return _MEDIA.get(Path(name).suffix.lower(), "application/octet-stream")


@router.get("/report/{filename}")
def download_report(filename: str) -> FileResponse:
    """Download a generated export (.csv, .xlsx) by basename."""
    safe = Path(filename).name
    if safe != filename:
        raise HTTPException(status_code=400, detail="filename must be a bare filename")
    path = OUTPUT_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Report '{safe}' not found")
    return FileResponse(
        str(path),
        filename=safe,
        media_type=_media_type(safe),
        headers={
            "Content-Disposition": f'attachment; filename="{safe}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
