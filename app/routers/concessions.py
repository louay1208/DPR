"""Concession and configuration management endpoints.

CRUD for concessions, cell mappings, UOM entries, QC rules.
Import endpoints for moulinette and mapping files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse

from app.config import DOCS_DIR, UPLOAD_DIR
from app.models.config_models import (
    ConcessionCreate,
    ConcessionDetail,
    ConcessionRead,
    ConcessionUpdate,
    ImportResult,
    QCRuleCreate,
    QCRuleRead,
    UOMEntryCreate,
    UOMEntryRead,
)
from app.services import config_store, importer
from app.services.database import get_connection as _get_db
from app.services.logger import LogService


router = APIRouter(prefix="/api", tags=["config"])


# ═══════════════════════════════════════════════════════════════════════
# Concessions CRUD
# ═══════════════════════════════════════════════════════════════════════

@router.get("/concessions", response_model=list[ConcessionRead])
async def list_concessions():
    """List all concessions with mapping counts."""
    return config_store.list_concessions()


@router.get("/concessions/{conc_id}")
async def get_concession(conc_id: str) -> ConcessionDetail:
    """Get concession with full mapping data."""
    conc = config_store.get_concession(conc_id)
    if not conc:
        raise HTTPException(status_code=404, detail="Concession not found")
    return conc


@router.post("/concessions", response_model=ConcessionRead, status_code=201)
async def create_concession(data: ConcessionCreate):
    """Create a new concession."""
    return config_store.create_concession(data)


@router.put("/concessions/{conc_id}", response_model=ConcessionRead)
async def update_concession(conc_id: str, data: ConcessionUpdate):
    """Update an existing concession."""
    result = config_store.update_concession(conc_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Concession not found")
    return result


@router.delete("/concessions/{conc_id}")
async def delete_concession(conc_id: str):
    """Delete a concession and all its mappings."""
    if not config_store.delete_concession(conc_id):
        raise HTTPException(status_code=404, detail="Concession not found")
    return {"status": "deleted", "id": conc_id}


# ═══════════════════════════════════════════════════════════════════════
# Cell Mappings
# ═══════════════════════════════════════════════════════════════════════

@router.get("/concessions/{conc_id}/mappings/{template_type}")
async def get_mappings(conc_id: str, template_type: str):
    """Get cell mappings for a concession and type (DC/DW/MC/WT)."""
    if template_type.upper() not in ("DC", "DW", "MC", "WT"):
        raise HTTPException(status_code=400, detail="Invalid template type")
    return config_store.get_mappings(conc_id, template_type)


@router.put("/concessions/{conc_id}/mappings/{template_type}")
async def set_mappings(conc_id: str, template_type: str, mappings: list[dict]):
    """Replace all mappings for a concession and type."""
    if template_type.upper() not in ("DC", "DW", "MC", "WT"):
        raise HTTPException(status_code=400, detail="Invalid template type")

    conc = config_store.get_concession(conc_id)
    if not conc:
        raise HTTPException(status_code=404, detail="Concession not found")

    count = config_store.set_mappings(conc_id, template_type, mappings)
    return {"status": "updated", "count": count}


# ═══════════════════════════════════════════════════════════════════════
# UOM
# ═══════════════════════════════════════════════════════════════════════

@router.get("/uom", response_model=list[UOMEntryRead])
async def list_uom():
    """List all unit conversion entries."""
    return config_store.list_uom()


@router.post("/uom", response_model=UOMEntryRead, status_code=201)
async def add_uom(entry: UOMEntryCreate):
    """Add or update a UOM conversion entry."""
    return config_store.add_uom(entry)


@router.delete("/uom/{unit}")
async def delete_uom(unit: str):
    """Delete a UOM entry."""
    if not config_store.delete_uom(unit):
        raise HTTPException(status_code=404, detail="UOM entry not found")
    return {"status": "deleted", "unit": unit}


# ═══════════════════════════════════════════════════════════════════════
# QC Rules
# ═══════════════════════════════════════════════════════════════════════

@router.get("/qc-rules", response_model=list[QCRuleRead])
async def list_qc_rules():
    """List all QC cleaning rules."""
    return config_store.list_qc_rules()


@router.post("/qc-rules", response_model=QCRuleRead, status_code=201)
async def add_qc_rule(rule: QCRuleCreate):
    """Add a QC rule."""
    return config_store.add_qc_rule(rule)


@router.delete("/qc-rules/{rule_id}")
async def delete_qc_rule(rule_id: int):
    """Delete a QC rule."""
    if not config_store.delete_qc_rule(rule_id):
        raise HTTPException(status_code=404, detail="QC rule not found")
    return {"status": "deleted", "id": rule_id}


# ═══════════════════════════════════════════════════════════════════════
# Parameters
# ═══════════════════════════════════════════════════════════════════════

@router.get("/parameters")
async def get_parameters():
    """Get all parameters."""
    return config_store.get_all_parameters()


@router.put("/parameters/{key}")
async def set_parameter(key: str, value: str = Query(...)):
    """Set a parameter value."""
    config_store.set_parameter(key, value)
    return {"status": "updated", "key": key, "value": value}


# ═══════════════════════════════════════════════════════════════════════
# Import
# ═══════════════════════════════════════════════════════════════════════

@router.post("/import/moulinette", response_model=ImportResult)
async def import_moulinette_endpoint(file: UploadFile = File(...)):
    """Import configuration from a PMS_Loader moulinette file."""
    logger = LogService.get()

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".xlsm", ".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail="File must be an Excel workbook")

    # Save uploaded file temporarily
    save_path = UPLOAD_DIR / file.filename
    try:
        content = await file.read()
        save_path.write_bytes(content)

        result = await importer.import_moulinette(save_path)
        return result
    except Exception as e:
        await logger.error(f"Moulinette import failed: {e}", source="importer")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp file
        if save_path.exists():
            save_path.unlink(missing_ok=True)


@router.post("/import/mapping", response_model=ImportResult)
async def import_mapping_endpoint(
    file: UploadFile = File(...),
    concession_id: str = Query(default="", description="Target concession ID (auto-detect if empty)"),
):
    """Import cell mappings from a Mapping_*.xlsx file."""
    logger = LogService.get()

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail="File must be an Excel workbook")

    save_path = UPLOAD_DIR / file.filename
    try:
        content = await file.read()
        save_path.write_bytes(content)

        result = await importer.import_mapping_file(
            save_path,
            concession_id=concession_id or None,
        )
        return result
    except Exception as e:
        await logger.error(f"Mapping import failed: {e}", source="importer")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if save_path.exists():
            save_path.unlink(missing_ok=True)


@router.post("/import/auto-detect")
async def auto_detect_from_docs():
    """Auto-import from docs/ folder if moulinette and mapping files exist."""
    logger = LogService.get()
    results = []

    # Find moulinette files
    for pattern in ["PMS_Loader*.xlsm", "PMS_Loader*.xlsx"]:
        for path in DOCS_DIR.glob(pattern):
            try:
                result = await importer.import_moulinette(path)
                results.append(result.model_dump())
                await logger.info(f"Auto-imported moulinette: {path.name}", source="importer")
            except Exception as e:
                await logger.error(f"Auto-import failed for {path.name}: {e}", source="importer")

    # Find mapping files
    for path in DOCS_DIR.glob("Mapping_*.xlsx"):
        try:
            result = await importer.import_mapping_file(path)
            results.append(result.model_dump())
            await logger.info(f"Auto-imported mapping: {path.name}", source="importer")
        except Exception as e:
            await logger.error(f"Auto-import failed for {path.name}: {e}", source="importer")

    return {"results": results, "total_files": len(results)}


# ═══════════════════════════════════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════════════════════════════════

@router.get("/config/stats")
async def get_config_stats():
    """Get database statistics for the dashboard."""
    return config_store.get_stats()


# ═══════════════════════════════════════════════════════════════════════
# Bulk Operations
# ═══════════════════════════════════════════════════════════════════════

@router.post("/concessions/bulk/toggle")
async def bulk_toggle(
    ids: list[str],
    field: str = Query(..., description="active_daily, active_monthly, or active_well_test"),
    value: bool = Query(...),
):
    """Batch enable/disable concessions."""
    # Safe column lookup — only pre-approved columns can be toggled
    _TOGGLE_COLUMNS = {
        "active_daily": "active_daily",
        "active_monthly": "active_monthly",
        "active_well_test": "active_well_test",
    }
    column = _TOGGLE_COLUMNS.get(field)
    if not column:
        raise HTTPException(status_code=400, detail="Invalid field")

    conn = _get_db()
    try:
        placeholders = ",".join("?" for _ in ids)
        conn.execute(
            f"UPDATE concessions SET {column} = ?, updated_at = datetime('now') WHERE id IN ({placeholders})",
            [int(value)] + ids,
        )
        conn.commit()
        return {"status": "updated", "count": len(ids), "field": field, "value": value}
    finally:
        conn.close()


@router.post("/concessions/{source_id}/copy-mappings/{target_id}")
async def copy_mappings(
    source_id: str,
    target_id: str,
    types: str = Query(default="DC,DW,MC,WT", description="Comma-separated types to copy"),
):
    """Copy all mappings from one concession to another."""
    source = config_store.get_concession(source_id)
    target = config_store.get_concession(target_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source concession not found")
    if not target:
        raise HTTPException(status_code=404, detail="Target concession not found")

    type_list = [t.strip().upper() for t in types.split(",")]
    conn = _get_db()
    total = 0
    try:
        for tt in type_list:
            if tt not in ("DC", "DW", "MC", "WT"):
                continue
            # Delete existing target mappings of this type
            conn.execute(
                "DELETE FROM cell_mappings WHERE concession_id = ? AND template_type = ?",
                (target_id, tt),
            )
            # Copy from source
            conn.execute(f"""
                INSERT INTO cell_mappings
                    (concession_id, template_type, well_name, ubhi, completion,
                     attribute_code, attribute, cell_ref, unit, sort_order)
                SELECT ?, template_type, well_name, ubhi, completion,
                       attribute_code, attribute, cell_ref, unit, sort_order
                FROM cell_mappings WHERE concession_id = ? AND template_type = ?
            """, (target_id, source_id, tt))
            total += conn.execute(
                "SELECT COUNT(*) FROM cell_mappings WHERE concession_id = ? AND template_type = ?",
                (target_id, tt),
            ).fetchone()[0]
        conn.commit()
        return {"status": "copied", "mappings_copied": total, "types": type_list}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
# Config Backup / Restore
# ═══════════════════════════════════════════════════════════════════════

@router.get("/config/backup")
async def backup_config():
    """Export entire config as JSON."""
    conn = _get_db()
    try:
        backup = {
            "version": "1.0",
            "concessions": [dict(r) for r in conn.execute("SELECT * FROM concessions ORDER BY name").fetchall()],
            "cell_mappings": [dict(r) for r in conn.execute("SELECT * FROM cell_mappings ORDER BY concession_id, template_type, sort_order").fetchall()],
            "uom_entries": [dict(r) for r in conn.execute("SELECT * FROM uom_entries ORDER BY unit").fetchall()],
            "qc_rules": [dict(r) for r in conn.execute("SELECT * FROM qc_rules ORDER BY id").fetchall()],
            "naming_rules": [dict(r) for r in conn.execute("SELECT * FROM naming_rules ORDER BY id").fetchall()],
            "parameters": [dict(r) for r in conn.execute("SELECT * FROM parameters ORDER BY key").fetchall()],
        }
        return JSONResponse(backup)
    finally:
        conn.close()


@router.post("/config/restore")
async def restore_config(data: dict):
    """Restore config from JSON backup. Replaces all existing data."""
    logger = LogService.get()

    conn = _get_db()
    try:
        # Clear all tables
        for table in ("cell_mappings", "concessions", "uom_entries", "qc_rules", "naming_rules", "parameters"):
            conn.execute(f"DELETE FROM {table}")

        counts = {}

        # Restore concessions
        for c in data.get("concessions", []):
            conn.execute("""
                INSERT INTO concessions (id, name, dpr_file_alias, dpr_sheet,
                    active_daily, active_monthly, active_well_test,
                    date_format, monthly_report, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                c["id"], c["name"], c.get("dpr_file_alias", ""), c.get("dpr_sheet", ""),
                c.get("active_daily", 1), c.get("active_monthly", 1), c.get("active_well_test", 1),
                c.get("date_format", "ddmmyyyy"), c.get("monthly_report", ""),
                c.get("created_at", ""), c.get("updated_at", ""),
            ))
        counts["concessions"] = len(data.get("concessions", []))

        # Restore mappings
        for m in data.get("cell_mappings", []):
            conn.execute("""
                INSERT INTO cell_mappings
                    (concession_id, template_type, well_name, ubhi, completion,
                     attribute_code, attribute, cell_ref, unit, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m["concession_id"], m["template_type"],
                m.get("well_name", ""), m.get("ubhi", ""), m.get("completion", ""),
                m["attribute_code"], m["attribute"],
                m.get("cell_ref", ""), m.get("unit", ""), m.get("sort_order", 0),
            ))
        counts["mappings"] = len(data.get("cell_mappings", []))

        # Restore UOM
        for u in data.get("uom_entries", []):
            conn.execute(
                "INSERT OR REPLACE INTO uom_entries (unit, factor, target_unit) VALUES (?, ?, ?)",
                (u["unit"], u["factor"], u.get("target_unit", "")),
            )
        counts["uom"] = len(data.get("uom_entries", []))

        # Restore QC rules
        for r in data.get("qc_rules", []):
            conn.execute(
                "INSERT INTO qc_rules (search_value, replace_value, active) VALUES (?, ?, ?)",
                (r["search_value"], r.get("replace_value", ""), r.get("active", 1)),
            )
        counts["qc_rules"] = len(data.get("qc_rules", []))

        # Restore naming rules
        for n in data.get("naming_rules", []):
            conn.execute("""
                INSERT INTO naming_rules (alias, file_alias, extension, date_format,
                    left_sep, right_sep, prefix, suffix)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                n["alias"], n.get("file_alias", ""), n.get("extension", "xlsx"),
                n.get("date_format", "ddmmyyyy"),
                n.get("left_sep", ""), n.get("right_sep", ""),
                n.get("prefix", ""), n.get("suffix", ""),
            ))
        counts["naming_rules"] = len(data.get("naming_rules", []))

        # Restore parameters
        for p in data.get("parameters", []):
            conn.execute(
                "INSERT OR REPLACE INTO parameters (key, value) VALUES (?, ?)",
                (p["key"], p["value"]),
            )
        counts["parameters"] = len(data.get("parameters", []))

        conn.commit()
        await logger.success(f"Config restored: {counts}", source="config")
        return {"status": "restored", "counts": counts}
    except Exception as e:
        conn.rollback()
        await logger.error(f"Config restore failed: {e}", source="config")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
# Extraction Test
# ═══════════════════════════════════════════════════════════════════════

@router.post("/extraction/test")
async def test_extraction(
    concession_id: str = Query(...),
    dpr_folder: str = Query(...),
    report_type: str = Query(default="daily"),
):
    """Test extraction for a single concession — returns preview data."""
    from datetime import date
    from app.services.parser import ParserService
    from app.models.schemas import ReportType

    conc = config_store.get_concession(concession_id)
    if not conc:
        raise HTTPException(status_code=404, detail="Concession not found")

    parser = ParserService()
    try:
        result = await parser.extract(
            report_type=ReportType(report_type),
            dpr_folder=dpr_folder,
            date_dpr=date.today(),
            auto_name=True,
            num_days=1,
            concession_ids=[concession_id],
        )
        return {
            "status": "success",
            "concession": conc.name,
            "record_count": result["record_count"],
            "columns": result["columns"],
            "preview": result["data"][:10],  # First 10 rows only
        }
    except Exception as e:
        return {
            "status": "error",
            "concession": conc.name,
            "error": str(e),
        }

