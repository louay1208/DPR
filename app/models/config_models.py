"""Pydantic models for the internalized DPR configuration.

These replace the moulinette + mapping file models with self-contained
app-managed structures stored in SQLite.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Cell-level mapping ─────────────────────────────────────────────────

class CellMapping(BaseModel):
    """A single cell-reference mapping (e.g. DC005 → E:22)."""
    id: int | None = None
    attribute_code: str          # "DC005"
    attribute: str               # "Production Gaz en k Sm3"
    cell_ref: str = ""           # "E:22", "B15", "?B15+B16"
    unit: str = ""               # "sm3", "bbl"
    sort_order: int = 0


class WellMapping(BaseModel):
    """A well with its field mappings (for DW/WT)."""
    well_name: str               # "ABIR", "Adam # 1"
    ubhi: str = ""               # "0994-00"
    completion: str = ""         # "ABR-001"
    fields: list[CellMapping] = []


# ── Concession ─────────────────────────────────────────────────────────

class ConcessionMappings(BaseModel):
    """All mappings for a concession, grouped by type."""
    dc: list[CellMapping] = []
    dw: list[WellMapping] = []
    mc: list[CellMapping] = []
    wt: list[WellMapping] = []


class ConcessionRead(BaseModel):
    """Concession as returned by the API."""
    id: str
    name: str
    dpr_file_alias: str = ""
    dpr_sheet: str = ""
    active_daily: bool = True
    active_monthly: bool = True
    active_well_test: bool = True
    date_format: str = "ddmmyyyy"
    monthly_report: str = ""
    created_at: str = ""
    updated_at: str = ""
    # Counts for quick overview
    dc_count: int = 0
    dw_count: int = 0
    mc_count: int = 0
    wt_count: int = 0
    well_count: int = 0


class ConcessionDetail(ConcessionRead):
    """Concession with full mapping data."""
    mappings: ConcessionMappings = Field(default_factory=ConcessionMappings)


class ConcessionCreate(BaseModel):
    """Request body to create a concession."""
    name: str
    dpr_file_alias: str = ""
    dpr_sheet: str = ""
    active_daily: bool = True
    active_monthly: bool = True
    active_well_test: bool = True
    date_format: str = "ddmmyyyy"
    monthly_report: str = ""


class ConcessionUpdate(BaseModel):
    """Request body to update a concession (all fields optional)."""
    name: str | None = None
    dpr_file_alias: str | None = None
    dpr_sheet: str | None = None
    active_daily: bool | None = None
    active_monthly: bool | None = None
    active_well_test: bool | None = None
    date_format: str | None = None
    monthly_report: str | None = None


# ── UOM ────────────────────────────────────────────────────────────────

class UOMEntryRead(BaseModel):
    unit: str
    factor: float
    target_unit: str = ""


class UOMEntryCreate(BaseModel):
    unit: str
    factor: float
    target_unit: str = ""


# ── QC ─────────────────────────────────────────────────────────────────

class QCRuleRead(BaseModel):
    id: int
    search_value: str
    replace_value: str = ""
    active: bool = True


class QCRuleCreate(BaseModel):
    search_value: str
    replace_value: str = ""
    active: bool = True


# ── Import ─────────────────────────────────────────────────────────────

class ImportResult(BaseModel):
    """Result of importing from an external file."""
    source: str
    concessions_imported: int = 0
    mappings_imported: int = 0
    uom_imported: int = 0
    qc_rules_imported: int = 0
    naming_rules_imported: int = 0
    warnings: list[str] = []


# ── DB Stats ───────────────────────────────────────────────────────────

class ConfigStats(BaseModel):
    """Quick overview of what's in the database."""
    concessions: int = 0
    concessions_active_daily: int = 0
    concessions_active_monthly: int = 0
    concessions_active_wt: int = 0
    total_mappings: int = 0
    uom_entries: int = 0
    qc_rules: int = 0
    naming_rules: int = 0
    db_size_kb: float = 0
