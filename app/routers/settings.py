"""Settings and configuration endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import (
    ALLOWED_EXTENSIONS,
    EXPORT_DIR,
    MAX_UPLOAD_SIZE,
    REPORT_TYPES,
    UPLOAD_DIR,
    get_runtime_config,
)
from app.models.schemas import AppConfig
from app.services import config_store, file_utils
from app.services.logger import LogService


router = APIRouter(prefix="/api", tags=["settings"])


class PathsRequest(BaseModel):
    dpr_folder: str = ""
    output_folder: str = ""


class MoulinetteLoadRequest(BaseModel):
    path: str = ""


@router.get("/config")
async def get_config() -> AppConfig:
    """Expose current backend settings to the frontend."""
    runtime = get_runtime_config()

    return AppConfig(
        upload_dir=str(UPLOAD_DIR),
        export_dir=str(EXPORT_DIR),
        max_upload_size=MAX_UPLOAD_SIZE,
        allowed_extensions=list(ALLOWED_EXTENSIONS),
        report_types=REPORT_TYPES,
        config_ready=True,
        dpr_folder=runtime.dpr_folder,
        output_folder=runtime.output_folder,
        sm3_to_nm3=runtime.sm3_to_nm3,
        nm3_to_sm3=runtime.nm3_to_sm3,
    )


@router.get("/dashboard/insights")
async def dashboard_insights(extraction_id: str | None = None) -> JSONResponse:
    """Aggregate smart insights for the dashboard.

    Query params:
        extraction_id: optional – if given, analyze that specific extraction.
                       Otherwise, pick the extraction with the most DC rows.
    """
    runtime = get_runtime_config()

    # Import extraction store lazily to avoid circular imports
    from app.services import extraction_store as ext_store

    # ── Stats from SQLite ─────────────────────────────────────
    stats = config_store.get_stats()
    params = config_store.get_all_parameters()

    moulinette = {
        "loaded": True,
        "template_mappings": stats.total_mappings,
        "uom_entries": stats.uom_entries,
        "naming_rules": stats.naming_rules,
        "sm3_to_nm3": float(params.get('sm3_to_nm3', '0.947916')),
        "nm3_to_sm3": float(params.get('nm3_to_sm3', '1.05494579688496')),
    }

    concessions = {"total": stats.concessions}

    # ── Extraction list for filter dropdown ────────────────────
    extraction_list = ext_store.list_extractions()

    # ── Determine which extraction to analyze ─────────────────
    production_summary = {"gas": 0, "oil": 0, "water": 0, "condensate": 0, "records": 0}
    conc_agg: dict[str, dict] = {}  # aggregated per-concession production
    gas_distribution = {"steg": 0, "miskar": 0, "gabes": 0, "flared": 0, "fuel": 0, "injected": 0}
    liquid_products = {
        "gpl": {"prod": 0, "ship": 0}, "butane": {"prod": 0, "ship": 0},
        "propane": {"prod": 0, "ship": 0}, "pentane": {"prod": 0, "ship": 0},
        "condensate": {"prod": 0, "ship": 0},
    }
    well_summary = []
    selected_extraction_id = extraction_id

    # If no extraction_id specified, pick the one with the most DC rows
    if not selected_extraction_id and extraction_list:
        best = None
        best_dc = -1
        for e in extraction_list:
            dc = e.get("dc_count", 0)
            if dc > best_dc:
                best_dc = dc
                best = e["id"]
        # If no extraction has DC, fall back to latest
        selected_extraction_id = best or extraction_list[0]["id"]

    # ── Load the selected extraction from DB ──────────────────
    extraction = None
    if selected_extraction_id:
        extraction = ext_store.load_extraction(selected_extraction_id)

    if extraction:
        _safe = _safe_float

        # ── DC data analytics ─────────────────────────────
        if extraction.dc_data:
            for row in extraction.dc_data:
                production_summary["gas"] += _safe(row, "DC005")
                production_summary["oil"] += _safe(row, "DC028")
                production_summary["water"] += _safe(row, "DC043")
                production_summary["condensate"] += _safe(row, "DC047")

                # Gas distribution
                gas_distribution["steg"] += _safe(row, "DC007")
                gas_distribution["miskar"] += _safe(row, "DC009")
                gas_distribution["gabes"] += _safe(row, "DC011")
                gas_distribution["flared"] += _safe(row, "DC021")
                gas_distribution["fuel"] += _safe(row, "DC022")
                gas_distribution["injected"] += _safe(row, "DC023")

                # Liquid products
                liquid_products["gpl"]["prod"] += _safe(row, "DC031")
                liquid_products["gpl"]["ship"] += _safe(row, "DC032")
                liquid_products["butane"]["prod"] += _safe(row, "DC034")
                liquid_products["butane"]["ship"] += _safe(row, "DC035")
                liquid_products["propane"]["prod"] += _safe(row, "DC037")
                liquid_products["propane"]["ship"] += _safe(row, "DC038")
                liquid_products["pentane"]["prod"] += _safe(row, "DC040")
                liquid_products["pentane"]["ship"] += _safe(row, "DC041")
                liquid_products["condensate"]["prod"] += _safe(row, "DC047")
                liquid_products["condensate"]["ship"] += _safe(row, "DC048")

                # Per-concession production (aggregated)
                conc_name = str(row.get("DC001") or "Unknown")
                if conc_name not in conc_agg:
                    conc_agg[conc_name] = {"name": conc_name, "gas": 0, "oil": 0, "water": 0}
                conc_agg[conc_name]["gas"] += _safe(row, "DC005")
                conc_agg[conc_name]["oil"] += _safe(row, "DC028")
                conc_agg[conc_name]["water"] += _safe(row, "DC043")

            production_summary["records"] = extraction.record_count

        # ── DW data analytics ─────────────────────────────
        if extraction.dw_data:
            for row in extraction.dw_data:
                gas = _safe_float(row, "DW007")
                oil = _safe_float(row, "DW008")
                water = _safe_float(row, "DW010")

                # Use DW011 (BSW%/Water Cut) directly if available,
                # otherwise fall back to computed ratio
                dw011 = row.get("DW011")
                if dw011 is not None and dw011 != "" and dw011 != "—":
                    try:
                        water_cut = float(dw011)
                    except (ValueError, TypeError):
                        total_liquid = oil + water
                        water_cut = (water / total_liquid * 100) if total_liquid > 0 else 0
                else:
                    total_liquid = oil + water
                    water_cut = (water / total_liquid * 100) if total_liquid > 0 else 0

                well_summary.append({
                    "well": str(row.get("DW003") or row.get("DW002") or "—"),
                    "concession": str(row.get("DW001") or "—"),
                    "gas": round(gas, 2),
                    "oil": round(oil, 2),
                    "water": round(water, 2),
                    "water_cut": round(water_cut, 1),
                })

            # Sort by gas production desc, top 15
            well_summary.sort(key=lambda w: w["gas"], reverse=True)
            well_summary = well_summary[:15]

    # Round production summary values
    for k in ["gas", "oil", "water", "condensate"]:
        production_summary[k] = round(production_summary[k], 2)

    # Round gas distribution
    for k in gas_distribution:
        gas_distribution[k] = round(gas_distribution[k], 2)

    # Round liquid products
    for product in liquid_products.values():
        product["prod"] = round(product["prod"], 2)
        product["ship"] = round(product["ship"], 2)

    # Build sorted concession_production list from aggregated dict
    concession_production = sorted(conc_agg.values(), key=lambda c: c["gas"], reverse=True)
    for cp in concession_production:
        cp["gas"] = round(cp["gas"], 2)
        cp["oil"] = round(cp["oil"], 2)
        cp["water"] = round(cp["water"], 2)

    return JSONResponse({
        "moulinette": moulinette,
        "concessions": concessions,
        "production_summary": production_summary,
        "concession_production": concession_production,
        "gas_distribution": gas_distribution,
        "liquid_products": liquid_products,
        "well_summary": well_summary,
        "extraction_list": extraction_list,
        "latest_extraction_id": selected_extraction_id,
    })


def _safe_float(row: dict, key: str) -> float:
    """Safely extract a numeric value from a row dict.

    Handles None, empty strings, NaN, Infinity, and non-numeric strings.
    """
    import math

    val = row.get(key)
    if val is None or val == "" or val == "—":
        return 0.0
    try:
        f = float(val)
        return f if math.isfinite(f) else 0.0
    except (ValueError, TypeError):
        return 0.0



@router.post("/config/paths")
async def set_paths(req: PathsRequest) -> JSONResponse:
    """Save user-configured folder paths (persisted to SQLite)."""
    runtime = get_runtime_config()

    if req.dpr_folder:
        info = file_utils.validate_path(req.dpr_folder)
        if not info["exists"]:
            raise HTTPException(status_code=400, detail=f"DPR folder not found: {req.dpr_folder}")
        runtime.dpr_folder = req.dpr_folder
        config_store.set_parameter("dpr_folder", req.dpr_folder)

    # Output folder — validate, create, and persist
    if req.output_folder:
        out_path = Path(req.output_folder)
        try:
            out_path.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot create output folder: {req.output_folder} ({e})",
            )
        runtime.output_folder = req.output_folder
        config_store.set_parameter("output_folder", req.output_folder)
    elif req.output_folder == "":
        # User cleared the field — reset to default
        runtime.output_folder = str(EXPORT_DIR)
        config_store.set_parameter("output_folder", str(EXPORT_DIR))

    return JSONResponse({
        "status": "paths_saved",
        "dpr_folder": runtime.dpr_folder,
        "output_folder": runtime.output_folder,
    })


@router.post("/config/load-moulinette")
async def load_moulinette(req: MoulinetteLoadRequest) -> JSONResponse:
    """Load and persist PMS_Loader moulinette config to SQLite.

    Uses the unified importer (app.services.importer) instead of the
    legacy in-memory-only MoulinetteLoader, ensuring configuration is
    persisted to the database and survives restarts.
    """
    logger = LogService.get()
    runtime = get_runtime_config()

    from app.config import DOCS_DIR
    from app.services import importer

    path = Path(req.path) if req.path else (DOCS_DIR / "PMS_Loader_v2.8 (1).xlsm")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Moulinette file not found: {path}")

    try:
        result = await importer.import_moulinette(path)
    except Exception as e:
        await logger.error(f"Failed to load moulinette: {e}", source="settings")
        raise HTTPException(status_code=500, detail=str(e))

    # Reload runtime config from DB after import
    params = config_store.get_all_parameters()
    runtime.sm3_to_nm3 = float(params.get("sm3_to_nm3", "0.947916"))
    runtime.nm3_to_sm3 = float(params.get("nm3_to_sm3", "1.05494579688496"))
    if not runtime.dpr_folder and params.get("dpr_path"):
        runtime.dpr_folder = params["dpr_path"]
    if not runtime.output_folder and params.get("output_path"):
        runtime.output_folder = params["output_path"]

    stats = config_store.get_stats()
    return JSONResponse({
        "status": "loaded",
        "concessions": result.concessions_imported,
        "uom_entries": result.uom_imported,
        "qc_rules": result.qc_rules_imported,
        "naming_rules": result.naming_rules_imported,
        "mappings": result.mappings_imported,
        "total_concessions": stats.concessions,
        "total_mappings": stats.total_mappings,
        "sm3_to_nm3": runtime.sm3_to_nm3,
        "nm3_to_sm3": runtime.nm3_to_sm3,
        "dpr_path": params.get("dpr_path", ""),
        "output_path": params.get("output_path", ""),
        "warnings": result.warnings,
    })


@router.get("/config/concessions")
async def list_concessions_legacy() -> JSONResponse:
    """List all concessions from SQLite."""
    concs = config_store.list_concessions()
    return JSONResponse([c.model_dump() for c in concs])


@router.get("/config/uom")
async def list_uom_legacy() -> JSONResponse:
    """List UOM conversion factors from SQLite."""
    entries = config_store.list_uom()
    return JSONResponse([e.model_dump() for e in entries])


@router.get("/config/qc-rules")
async def list_qc_rules_legacy() -> JSONResponse:
    """List QC cleaning rules from SQLite."""
    rules = config_store.list_qc_rules()
    return JSONResponse([r.model_dump() for r in rules])


@router.get("/config/schemas")
async def get_schemas() -> JSONResponse:
    """Get column schemas for all output types."""
    # Schemas are now embedded in mapping data; return empty for backward compat
    return JSONResponse({
        "dc": [],
        "dw": [],
        "mc": [],
        "wt": [],
    })


@router.post("/validate-paths")
async def validate_paths(req: PathsRequest) -> JSONResponse:
    """Validate folder paths and perform smart file detection."""
    from typing import Any

    results: dict[str, Any] = {}

    # ── DPR folder ─────────────────────────────────────────────
    if req.dpr_folder:
        info = file_utils.validate_path(req.dpr_folder)
        files = file_utils.scan_folder(req.dpr_folder) if info["exists"] else []
        ext_counts: dict[str, int] = {}
        for f in files:
            ext = f.get("extension", "")
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        sample = [f["name"] for f in files[:5]]
        results["dpr"] = {
            **info,
            "file_count": len(files),
            "extensions": ext_counts,
            "sample_files": sample,
            "hint": "dpr",
        }

    # ── Output folder ──────────────────────────────────────────
    if req.output_folder:
        info = file_utils.validate_path(req.output_folder)
        csv_files = file_utils.scan_folder(req.output_folder, extensions={".csv"}) if info["exists"] else []
        results["output"] = {
            **info,
            "file_count": len(csv_files),
            "sample_files": [f["name"] for f in csv_files[:5]],
            "hint": "output",
        }

    return JSONResponse(results)


@router.post("/validate-single-path")
async def validate_single_path(req: dict) -> JSONResponse:
    """Validate a single folder path on-the-fly (used by blur events)."""
    from typing import Any

    path = req.get("path", "").strip()
    hint = req.get("hint", "")  # 'dpr', 'mapping', or 'output'
    if not path:
        return JSONResponse({"exists": False, "empty": True})

    info = file_utils.validate_path(path)

    if not info["exists"]:
        return JSONResponse({**info, "hint": hint})

    # Scan with appropriate extensions
    if hint == "output":
        files = file_utils.scan_folder(path, extensions={".csv"})
    else:
        files = file_utils.scan_folder(path)

    ext_counts: dict[str, int] = {}
    for f in files:
        ext = f.get("extension", "")
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    result: dict[str, Any] = {
        **info,
        "file_count": len(files),
        "extensions": ext_counts,
        "sample_files": [f["name"] for f in files[:8]],
        "hint": hint,
    }

    # Mapping-specific: cross-ref concessions from SQLite
    if hint == "mapping":
        conc_list = config_store.list_concessions()
        mapping_names = {f["name"] for f in files}
        matched = sum(1 for c in conc_list if c.dpr_file_alias and any(c.dpr_file_alias in n for n in mapping_names))
        result["matched_concessions"] = matched
        result["total_expected"] = len(conc_list)
        result["missing_mappings"] = []

    return JSONResponse(result)


@router.post("/scan-folder")
async def scan_folder(req: PathsRequest) -> JSONResponse:
    """Scan a folder for DPR/Excel files."""
    folder = req.dpr_folder or req.output_folder
    if not folder:
        raise HTTPException(status_code=400, detail="No folder path provided")

    files = file_utils.scan_folder(folder)
    return JSONResponse({"folder": folder, "files": files, "count": len(files)})

