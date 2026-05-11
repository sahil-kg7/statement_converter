from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.schemas import ConversionPreviewResponse, HealthResponse
from app.output.csv_writer import build_output_csv
from app.output.download_cache import DownloadCache
from app.pipeline.errors import UnsupportedStatementError
from app.pipeline.orchestrator import ConversionOrchestrator

router = APIRouter()
orchestrator = ConversionOrchestrator()
download_cache = DownloadCache()


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post(
    "/convert",
    response_model=None,
    responses={422: {"description": "The uploaded statement could not be parsed"}},
)
async def convert(
    file: Annotated[UploadFile, File(...)],
) -> PlainTextResponse | JSONResponse:
    payload = await file.read()
    try:
        result = orchestrator.convert(file.filename or "statement", payload)
    except UnsupportedStatementError as error:
        return JSONResponse(
            status_code=422, content=error.to_payload().model_dump(mode="json")
        )
    except ValueError as error:
        return JSONResponse(
            status_code=422,
            content={"error": "unprocessable_statement", "detail": str(error)},
        )

    output = build_output_csv(result.transactions)
    return PlainTextResponse(
        content=output,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="normalized-statement.csv"',
        },
    )


@router.post(
    "/convert/preview",
    response_model=ConversionPreviewResponse,
    responses={422: {"description": "The uploaded statement could not be parsed"}},
)
async def convert_preview(
    file: Annotated[UploadFile, File(...)],
) -> ConversionPreviewResponse:
    source_name = file.filename or "statement"
    payload = await file.read()
    try:
        result = orchestrator.convert(source_name, payload)
    except UnsupportedStatementError as error:
        return JSONResponse(
            status_code=422, content=error.to_payload().model_dump(mode="json")
        )
    except ValueError as error:
        return JSONResponse(
            status_code=422,
            content={"error": "unprocessable_statement", "detail": str(error)},
        )

    csv_text = build_output_csv(result.transactions)
    token = download_cache.store(csv_text, source_name=source_name)
    return ConversionPreviewResponse(
        detected_bank=result.detected_bank,
        statement_kind=result.statement_kind,
        conversion_source=result.conversion_source,
        total_rows=len(result.transactions),
        preview_rows=result.transactions[:20],
        download_token=token,
        download_url=f"/api/download/{token}",
    )


@router.get(
    "/download/{token}",
    response_model=None,
    responses={404: {"description": "Download not found or expired"}},
)
def download(token: str) -> PlainTextResponse:
    cached = download_cache.get(token)
    if cached is None:
        raise HTTPException(status_code=404, detail="Download not found or expired")

    return PlainTextResponse(
        content=cached.csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{cached.download_name}"',
        },
    )
