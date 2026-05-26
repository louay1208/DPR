"""Pydantic schemas for request/response validation."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────

class ReportType(str, Enum):
    DAILY = "daily"
    MONTHLY = "monthly"
    DC = "dc"
    DW = "dw"
    WELL_TEST = "well_test"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    CORRECTING = "correcting"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    ERROR = "error"


# ── Moulinette Config Models ──────────────────────────────────────────

class ColumnSchema(BaseModel):
    """A single column in an output schema (DC/DW/MC/WT)."""
    attribute: str          # e.g. "Nom Concession"
    code: str               # e.g. "DC001"
    column_index: int       # e.g. 1


class ConcessionConfig(BaseModel):
    """One concession/operator entry from the Parameters sheet."""
    name: str               # e.g. "ADAM NEW"
    active_daily: bool = False
    active_monthly: bool = False
    active_well_test: bool = False
    monthly_report: str = ""
    mapping_file: str = ""  # e.g. "Mapping_Adam.xlsx"


class DPRNamingRule(BaseModel):
    """Auto-filename generation rule for a DPR file."""
    alias: str              # e.g. "Adam"
    file_alias: str         # e.g. "Adam"
    extension: str = "xlsx"
    date_format: str = "ddmmyyyy"
    left_sep: str = ""
    right_sep: str = ""
    prefix: str = ""
    suffix: str = ""


class UOMEntry(BaseModel):
    """Unit-of-measure conversion entry."""
    unit: str               # e.g. "MSCF"
    factor: float           # e.g. 0.0283168
    target_unit: str = ""   # e.g. "ksm3"


class QCRule(BaseModel):
    """A single QC cleaning find/replace rule."""
    sheet: str              # e.g. "OutputDW"
    column_range: str       # e.g. "G2:L"
    search_value: str       # e.g. "N/A"
    replace_value: str = "" # replacement (often empty)
    active: bool = True


class MappingEntry(BaseModel):
    """A cell-reference mapping from the Template sheet."""
    file_alias: str         # DPR workbook alias
    sheet_name: str         # worksheet name inside DPR file
    well_name: str = ""     # well name (operator naming)
    ubhi: str = ""          # UBHI code for ProSource
    completion: str = ""    # completion name for ProSource
    template_type: str      # "DC", "DW", "MC", "WT"
    attribute: str          # human name e.g. "Production Gaz en Sm3"
    attribute_code: str     # e.g. "DW008"
    cell_ref: str = ""      # e.g. "B15", "?B15+B16", "![alias/sheet]ref"
    unit: str = ""          # e.g. "MSCF", "BBL" (for conversion)


class MoulinetteConfig(BaseModel):
    """Full configuration extracted from the PMS_Loader moulinette."""
    schema_dc: list[ColumnSchema] = []
    schema_dw: list[ColumnSchema] = []
    schema_mc: list[ColumnSchema] = []
    schema_wt: list[ColumnSchema] = []
    uom_entries: list[UOMEntry] = []
    concessions: list[ConcessionConfig] = []
    naming_rules: list[DPRNamingRule] = []
    qc_rules: list[QCRule] = []
    template_mappings: list[MappingEntry] = []
    sm3_to_nm3: float = 0.947916
    nm3_to_sm3: float = 1.05494579688496
    mapping_path: str = ""
    dpr_path: str = ""
    output_path: str = ""


# ── File Models ────────────────────────────────────────────────────────

class FileInfo(BaseModel):
    """Metadata for an uploaded file."""
    id: str
    filename: str
    original_name: str
    size: int
    uploaded_at: datetime
    operator: str | None = None
    report_type: ReportType | None = None
    status: ProcessingStatus = ProcessingStatus.PENDING


class FileListResponse(BaseModel):
    files: list[FileInfo]
    total: int


class FileCheckResult(BaseModel):
    """Result of checking whether a file exists."""
    filename: str
    exists: bool
    path: str = ""


# ── Extraction Models ─────────────────────────────────────────────────

class ExtractionRequest(BaseModel):
    """Request to extract data from DPR files."""
    report_type: ReportType = ReportType.DAILY
    date_dpr: date | None = None
    dpr_source: str = "folder"              # "folder" or "upload"
    dpr_folder: str = ""
    output_folder: str = ""
    auto_detect_name: bool = True
    concatenate: bool = False
    num_days: int = 1
    concession_ids: list[str] = []           # empty = all active
    uploaded_file_ids: list[str] = []        # file IDs from upload endpoint
    extract_dc: bool = True                  # daily sub-types
    extract_dw: bool = True


class CorrectionResult(BaseModel):
    """Result of an auto-correction pass."""
    field: str
    row: int
    original_value: Any
    corrected_value: Any
    reason: str


class RecordUpdate(BaseModel):
    """Payload for updating a single cell in a record."""
    field: str          # column name, e.g. "DC005"
    value: Any          # new value (string, number, or None)


class BulkDeleteRequest(BaseModel):
    """Payload for deleting multiple rows."""
    row_indices: list[int]  # sorted descending on the frontend


class ExtractionResult(BaseModel):
    """Result of a data extraction."""
    id: str
    report_type: ReportType
    status: ProcessingStatus
    record_count: int = 0
    columns: list[str] = []
    data: list[dict[str, Any]] = []
    dc_data: list[dict[str, Any]] = []
    dw_data: list[dict[str, Any]] = []
    mc_data: list[dict[str, Any]] = []
    wt_data: list[dict[str, Any]] = []
    dc_columns: list[str] = []
    dw_columns: list[str] = []
    mc_columns: list[str] = []
    wt_columns: list[str] = []
    corrections: list[CorrectionResult] = []
    errors: list[str] = []
    created_at: datetime = Field(default_factory=datetime.now)


# ── QC Models ──────────────────────────────────────────────────────────

class QCIssue(BaseModel):
    """A quality-control issue found in the data."""
    severity: str  # "error", "warning", "info"
    field: str
    row: int | None = None
    message: str
    auto_fixable: bool = False


class QCSummary(BaseModel):
    """Quality-control summary for a dataset."""
    total_records: int
    valid_records: int
    issues: list[QCIssue]
    quality_score: float = Field(ge=0.0, le=100.0)


# ── Config Models ──────────────────────────────────────────────────────

class AppConfig(BaseModel):
    """Application configuration exposed to the frontend."""
    upload_dir: str
    export_dir: str
    max_upload_size: int
    allowed_extensions: list[str]
    report_types: list[str]
    config_ready: bool = True
    dpr_folder: str = ""
    output_folder: str = ""
    sm3_to_nm3: float = 0.947916
    nm3_to_sm3: float = 1.05494579688496


# ── Log Models ─────────────────────────────────────────────────────────

class LogEntry(BaseModel):
    """A single log entry."""
    timestamp: datetime = Field(default_factory=datetime.now)
    level: str = "info"
    source: str = ""
    message: str


# ── Dashboard Models ───────────────────────────────────────────────────

class DashboardStats(BaseModel):
    """Aggregated stats for the dashboard."""
    files_uploaded: int = 0
    files_processed: int = 0
    records_extracted: int = 0
    exports_generated: int = 0
    avg_quality_score: float = 0.0
    recent_activity: list[LogEntry] = []
