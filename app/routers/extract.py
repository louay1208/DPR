"""Extraction, correction, and export endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from app.config import EXPORT_DIR, get_runtime_config
from app.models.schemas import (
    BulkDeleteRequest,
    ExtractionRequest,
    ExtractionResult,
    ProcessingStatus,
    RecordUpdate,
    ReportType,
)
from app.services.corrector import CorrectorService
from app.services.exporter import ExporterService
from app.services.logger import LogService
from app.services import extraction_store

from app.services.parser import ParserService

router = APIRouter(prefix="/api", tags=["extract"])

# In-memory cache for active extraction results (lazy-loaded from DB)
_extraction_store: dict[str, ExtractionResult] = {}


DATA_TYPE_FIELDS = {
    "dc": "dc_data",
    "dw": "dw_data",
    "mc": "mc_data",
    "wt": "wt_data",
}


def _get_data_list(
    result: ExtractionResult, data_type: str
) -> list[dict]:
    """Return the mutable data list for a given type."""
    field = DATA_TYPE_FIELDS.get(data_type)
    if not field:
        raise HTTPException(400, f"Invalid data_type: {data_type}")
    return getattr(result, field)


def _sync_combined(result: ExtractionResult) -> None:
    """Re-build result.data, record_count, and column lists from typed lists."""
    result.data = result.dc_data + result.dw_data + result.mc_data + result.wt_data
    result.record_count = len(result.data)
    # Rebuild columns as union of ALL rows' keys (different concessions may map different fields)
    if result.dc_data:
        result.dc_columns = sorted({k for row in result.dc_data for k in row})
    if result.dw_data:
        result.dw_columns = sorted({k for row in result.dw_data for k in row})
    if result.mc_data:
        result.mc_columns = sorted({k for row in result.mc_data for k in row})
    if result.wt_data:
        result.wt_columns = sorted({k for row in result.wt_data for k in row})
    result.columns = (
        result.dc_columns or result.dw_columns
        or result.mc_columns or result.wt_columns
    )


def get_extraction_store() -> dict[str, ExtractionResult]:
    return _extraction_store


def _resolve_extraction(extraction_id: str) -> ExtractionResult | None:
    """Look up extraction: in-memory cache first, then DB fallback.

    Caches the result in memory for subsequent requests in the same
    server lifecycle.
    """
    result = _extraction_store.get(extraction_id)
    if result:
        return result
    result = extraction_store.load_extraction(extraction_id)
    if result:
        _extraction_store[extraction_id] = result
    return result


@router.get("/attribute-map")
async def get_attribute_map() -> JSONResponse:
    """Return a mapping from attribute codes to human-readable names.

    Built from the union of all concession mappings in the DB.
    Response: { "DC001": "Nom Concession", "DC002": "Date", ... }
    """
    from app.services import config_store

    attr_map: dict[str, str] = {}
    concessions = config_store.list_concessions()

    for conc in concessions:
        detail = config_store.get_concession(conc.id)
        if not detail:
            continue
        # DC mappings
        for m in detail.mappings.dc:
            if m.attribute_code and m.attribute and m.attribute_code not in attr_map:
                attr_map[m.attribute_code] = m.attribute
        # MC mappings
        for m in detail.mappings.mc:
            if m.attribute_code and m.attribute and m.attribute_code not in attr_map:
                attr_map[m.attribute_code] = m.attribute
        # DW mappings (from wells)
        for well in detail.mappings.dw:
            for m in well.fields:
                if m.attribute_code and m.attribute and m.attribute_code not in attr_map:
                    attr_map[m.attribute_code] = m.attribute
        # WT mappings (from wells)
        for well in detail.mappings.wt:
            for m in well.fields:
                if m.attribute_code and m.attribute and m.attribute_code not in attr_map:
                    attr_map[m.attribute_code] = m.attribute

    return JSONResponse(attr_map)

@router.post("/extract", response_model=ExtractionResult)
async def extract_data(request: ExtractionRequest) -> ExtractionResult:
    """Extract data from DPR files.

    Supports two modes:
    - folder: reads DPR files from a local folder path
    - upload: uses previously uploaded files from /api/files
    """
    logger = LogService.get()
    runtime = get_runtime_config()

    # Resolve DPR folder from request or uploaded files
    dpr_folder = ""
    if request.dpr_source == "upload":
        from app.config import UPLOAD_DIR
        if request.uploaded_file_ids:
            dpr_folder = str(UPLOAD_DIR)
            await logger.info(
                f"Using {len(request.uploaded_file_ids)} uploaded file(s)",
                source="extract",
            )
        elif UPLOAD_DIR.exists() and any(UPLOAD_DIR.iterdir()):
            # No specific file IDs but uploads directory has files
            dpr_folder = str(UPLOAD_DIR)
            await logger.info(
                "Using all files in uploads directory",
                source="extract",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="No files uploaded. Please upload DPR files first.",
            )
    else:
        dpr_folder = request.dpr_folder or runtime.dpr_folder

    if not dpr_folder:
        raise HTTPException(status_code=400, detail="DPR folder path is required")

    await logger.info(
        f"Starting extraction: type={request.report_type.value}, "
        f"days={request.num_days}, folder={dpr_folder}, "
        f"concessions={len(request.concession_ids) or 'all'}",
        source="extract",
    )

    parser = ParserService()
    try:
        result_data = await parser.extract(
            report_type=request.report_type,
            dpr_folder=dpr_folder,
            date_dpr=request.date_dpr,
            auto_name=request.auto_detect_name,
            num_days=request.num_days,
            concatenate=request.concatenate,
            concession_ids=request.concession_ids,
        )
    except Exception as e:
        await logger.error(f"Extraction failed: {e}", source="extract")
        raise HTTPException(status_code=500, detail=str(e))

    extraction_id = uuid.uuid4().hex[:12]

    # Build typed arrays from parser result
    dc_data = result_data.get("dc_data", [])
    dw_data = result_data.get("dw_data", [])
    mc_data = result_data.get("mc_data", [])
    wt_data = result_data.get("wt_data", [])

    result = ExtractionResult(
        id=extraction_id,
        report_type=request.report_type,
        status=ProcessingStatus.COMPLETED,
        record_count=result_data["record_count"],
        columns=result_data["columns"],
        data=result_data["data"],
        dc_data=dc_data,
        dw_data=dw_data,
        mc_data=mc_data,
        wt_data=wt_data,
        dc_columns=sorted({k for row in dc_data for k in row}) if dc_data else [],
        dw_columns=sorted({k for row in dw_data for k in row}) if dw_data else [],
        mc_columns=sorted({k for row in mc_data for k in row}) if mc_data else [],
        wt_columns=sorted({k for row in wt_data for k in row}) if wt_data else [],
    )

    _extraction_store[extraction_id] = result

    # Persist to database
    extraction_store.save_extraction(result, dpr_folder=dpr_folder)

    await logger.success(
        f"Extraction complete: {result_data['record_count']} records "
        f"(DC={len(dc_data)}, DW={len(dw_data)}, MC={len(mc_data)}, WT={len(wt_data)}), "
        f"ID={extraction_id}",
        source="extract",
    )

    return result


@router.post("/auto-correct/{extraction_id}")
async def auto_correct(extraction_id: str) -> JSONResponse:
    """Run auto-correction on a previous extraction."""
    logger = LogService.get()

    result = _resolve_extraction(extraction_id)
    if not result:
        raise HTTPException(status_code=404, detail="Extraction not found")

    corrector = CorrectorService()
    total_corrections = []

    # Run correction on each typed data list separately
    for data_type, field in DATA_TYPE_FIELDS.items():
        data_list = getattr(result, field)
        if not data_list:
            continue
        corrected = await corrector.auto_correct(data_list)
        setattr(result, field, corrected["data"])
        total_corrections.extend(corrected["corrections"])

    # Re-sync combined data from typed lists
    _sync_combined(result)
    result.corrections = [
        CorrectionResult(**c) if isinstance(c, dict) else c
        for c in total_corrections
    ]

    # Persist changes to DB
    extraction_store.save_extraction(result)

    await logger.success(
        f"Auto-correction applied to {extraction_id}: "
        f"{len(total_corrections)} fixes",
        source="corrector",
    )

    return JSONResponse({
        "status": "corrected",
        "extraction_id": extraction_id,
        "record_count": result.record_count,
        "corrections_count": len(total_corrections),
        "corrections": [c if isinstance(c, dict) else c.model_dump() for c in total_corrections],
        "summary": {"total_corrections": len(total_corrections)},
    })


@router.post("/convert-units/{extraction_id}")
async def convert_units(
    extraction_id: str,
    direction: str = Query(default="sm3_to_nm3"),
) -> JSONResponse:
    """Apply SM3<->NM3 conversion on extraction data."""
    result = _resolve_extraction(extraction_id)
    if not result:
        raise HTTPException(status_code=404, detail="Extraction not found")

    corrector = CorrectorService()
    total_conversions = 0

    # Convert each typed data list separately
    for data_type, field in DATA_TYPE_FIELDS.items():
        data_list = getattr(result, field)
        if not data_list:
            continue
        converted = await corrector.convert_units(data_list, direction)
        setattr(result, field, converted["data"])
        total_conversions += converted["conversions"]

    # Re-sync combined data
    _sync_combined(result)

    # Persist changes to DB
    extraction_store.save_extraction(result)

    return JSONResponse({
        "status": "converted",
        "extraction_id": extraction_id,
        "direction": direction,
        "conversions": total_conversions,
    })


@router.post("/export-csv/{extraction_id}")
async def export_csv(
    extraction_id: str,
    report_type: ReportType = Query(default=ReportType.DAILY),
) -> JSONResponse:
    """Export extraction data to ProSource-compatible CSV."""
    logger = LogService.get()
    runtime = get_runtime_config()

    result = _resolve_extraction(extraction_id)
    if not result:
        raise HTTPException(status_code=404, detail="Extraction not found")

    # Select the correct typed data based on report_type
    type_data_map = {
        ReportType.DC: result.dc_data,
        ReportType.DW: result.dw_data,
        ReportType.MONTHLY: result.mc_data,
        ReportType.WELL_TEST: result.wt_data,
        ReportType.DAILY: result.dc_data + result.dw_data,  # combined daily
    }
    export_data = type_data_map.get(report_type, result.data)
    if not export_data:
        export_data = result.data  # fallback

    exporter = ExporterService()
    try:
        output_path = await exporter.export_csv(
            export_data,
            report_type=report_type,
            output_folder=runtime.output_folder,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return JSONResponse({
        "status": "exported",
        "filename": output_path.name,
        "record_count": len(export_data),
        "download_url": f"/api/download/{output_path.name}",
        "path": str(output_path),
    })


# ════════════════════════════════════════════════════════════════════════════
# CRUD — Record-level operations
# ════════════════════════════════════════════════════════════════════════════

@router.put("/records/{extraction_id}/{data_type}/{row_index}")
async def update_record(
    extraction_id: str, data_type: str, row_index: int, body: RecordUpdate
) -> JSONResponse:
    """Update a single cell in a record."""
    result = _resolve_extraction(extraction_id)
    if not result:
        raise HTTPException(404, "Extraction not found")

    data_list = _get_data_list(result, data_type)
    if row_index < 0 or row_index >= len(data_list):
        raise HTTPException(400, f"Row index {row_index} out of range (0..{len(data_list)-1})")

    row = data_list[row_index]
    old_value = row.get(body.field)
    row[body.field] = body.value
    _sync_combined(result)

    # Sync to DB
    extraction_store.sync_rows(extraction_id, data_type, data_list)

    return JSONResponse({
        "status": "updated",
        "row_index": row_index,
        "field": body.field,
        "old_value": old_value,
        "new_value": body.value,
        "record_count": result.record_count,
    })


@router.post("/records/{extraction_id}/{data_type}")
async def create_record(extraction_id: str, data_type: str) -> JSONResponse:
    """Add a new blank row to the specified data type."""
    result = _resolve_extraction(extraction_id)
    if not result:
        raise HTTPException(404, "Extraction not found")

    data_list = _get_data_list(result, data_type)
    col_field = DATA_TYPE_FIELDS[data_type].replace("_data", "_columns")
    cols = getattr(result, col_field, [])

    # If no columns yet, use the columns from existing rows or from result.columns
    if not cols and data_list:
        cols = list(data_list[0].keys())
    elif not cols:
        cols = result.columns

    new_row = {c: "" for c in cols}
    data_list.append(new_row)
    _sync_combined(result)

    # Update column list if it was empty
    if not getattr(result, col_field):
        setattr(result, col_field, cols)

    # Sync to DB
    extraction_store.sync_rows(extraction_id, data_type, data_list)

    return JSONResponse({
        "status": "created",
        "row_index": len(data_list) - 1,
        "row": new_row,
        "columns": cols,
        "record_count": result.record_count,
    })


@router.delete("/records/{extraction_id}/{data_type}/{row_index}")
async def delete_record(
    extraction_id: str, data_type: str, row_index: int
) -> JSONResponse:
    """Delete a single row."""
    result = _resolve_extraction(extraction_id)
    if not result:
        raise HTTPException(404, "Extraction not found")

    data_list = _get_data_list(result, data_type)
    if row_index < 0 or row_index >= len(data_list):
        raise HTTPException(400, f"Row index {row_index} out of range")

    removed = data_list.pop(row_index)
    _sync_combined(result)

    # Sync to DB
    extraction_store.sync_rows(extraction_id, data_type, data_list)

    return JSONResponse({
        "status": "deleted",
        "row_index": row_index,
        "record_count": result.record_count,
        "remaining": len(data_list),
    })


@router.post("/records/{extraction_id}/{data_type}/bulk-delete")
async def bulk_delete_records(
    extraction_id: str, data_type: str, body: BulkDeleteRequest
) -> JSONResponse:
    """Delete multiple rows at once. Indices must be sorted descending."""
    result = _resolve_extraction(extraction_id)
    if not result:
        raise HTTPException(404, "Extraction not found")

    data_list = _get_data_list(result, data_type)
    # Sort descending so we can pop from the end first
    indices = sorted(set(body.row_indices), reverse=True)
    deleted = 0
    for idx in indices:
        if 0 <= idx < len(data_list):
            data_list.pop(idx)
            deleted += 1

    _sync_combined(result)

    # Sync to DB
    extraction_store.sync_rows(extraction_id, data_type, data_list)

    return JSONResponse({
        "status": "bulk_deleted",
        "deleted_count": deleted,
        "record_count": result.record_count,
        "remaining": len(data_list),
    })


@router.get("/download/{filename}")
async def download_file(filename: str) -> FileResponse:
    """Download an exported CSV file."""
    runtime = get_runtime_config()
    out_dir = Path(runtime.output_folder) if runtime.output_folder else EXPORT_DIR

    filepath = out_dir / filename
    if not filepath.exists():
        # Try default export dir
        filepath = EXPORT_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=filepath, filename=filename, media_type="text/csv",
    )


@router.get("/extractions")
async def list_extractions_endpoint() -> JSONResponse:
    """List all extractions from DB (metadata only, no data)."""
    items = extraction_store.list_extractions()
    return JSONResponse(items)


@router.get("/extractions/{extraction_id}")
async def get_extraction(extraction_id: str) -> ExtractionResult:
    """Get full extraction result including data."""
    # Use the shared resolver (memory cache → DB fallback)
    result = _resolve_extraction(extraction_id)
    if not result:
        raise HTTPException(status_code=404, detail="Extraction not found")
    return result


@router.delete("/extractions/{extraction_id}")
async def delete_extraction_endpoint(extraction_id: str) -> JSONResponse:
    """Delete a saved extraction from both memory and DB."""
    logger = LogService.get()
    _extraction_store.pop(extraction_id, None)
    deleted = extraction_store.delete_extraction(extraction_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Extraction not found")
    await logger.info(f"Deleted extraction {extraction_id}", source="extract")
    return JSONResponse({"status": "deleted", "id": extraction_id})


@router.patch("/extractions/{extraction_id}")
async def rename_extraction(extraction_id: str, label: str = Query(...)) -> JSONResponse:
    """Rename/relabel a saved extraction."""
    updated = extraction_store.update_label(extraction_id, label)
    if not updated:
        raise HTTPException(status_code=404, detail="Extraction not found")
    return JSONResponse({"status": "renamed", "id": extraction_id, "label": label})


@router.get("/extractions/{id1}/compare/{id2}")
async def compare_extractions(id1: str, id2: str) -> JSONResponse:
    """Compare two extractions — returns diff stats and changed rows."""
    r1 = _resolve_extraction(id1)
    r2 = _resolve_extraction(id2)
    if not r1:
        raise HTTPException(404, f"Extraction {id1} not found")
    if not r2:
        raise HTTPException(404, f"Extraction {id2} not found")

    def _compare_type(d1: list[dict], d2: list[dict], type_name: str) -> dict:
        added = max(0, len(d2) - len(d1))
        removed = max(0, len(d1) - len(d2))
        changed = 0
        diffs = []
        for i in range(min(len(d1), len(d2))):
            row_diffs = {}
            all_keys = set(d1[i].keys()) | set(d2[i].keys())
            for k in all_keys:
                v1 = d1[i].get(k)
                v2 = d2[i].get(k)
                if str(v1) != str(v2):
                    row_diffs[k] = {"old": v1, "new": v2}
            if row_diffs:
                changed += 1
                diffs.append({"row": i, "fields": row_diffs})
        return {
            "type": type_name,
            "count_1": len(d1), "count_2": len(d2),
            "added": added, "removed": removed, "changed": changed,
            "diffs": diffs[:50],  # cap at 50 for response size
        }

    return JSONResponse({
        "extraction_1": {"id": id1, "label": getattr(r1, 'label', id1), "created_at": r1.created_at.isoformat()},
        "extraction_2": {"id": id2, "label": getattr(r2, 'label', id2), "created_at": r2.created_at.isoformat()},
        "dc": _compare_type(r1.dc_data, r2.dc_data, "dc"),
        "dw": _compare_type(r1.dw_data, r2.dw_data, "dw"),
        "mc": _compare_type(r1.mc_data, r2.mc_data, "mc"),
        "wt": _compare_type(r1.wt_data, r2.wt_data, "wt"),
    })



@router.get("/exports")
async def list_exports() -> JSONResponse:
    """List all exported CSV files."""
    runtime = get_runtime_config()
    exporter = ExporterService()
    exports = await exporter.list_exports(runtime.output_folder)
    return JSONResponse(exports)
