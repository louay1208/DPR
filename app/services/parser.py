"""Mapping-driven parser for DPR extraction.

Mirrors VBA ExtractDailyData, ExtractMonthlyData, ExtractWellTestData.
Reads mapping configuration from SQLite (via config_store) instead of
the legacy moulinette Excel file.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.config import MONTH_TO_COLUMN, get_runtime_config
from app.models.schemas import ReportType
from app.services import cell_reader, config_store
from app.services.database import get_connection
from app.services.logger import LogService


class ParserService:
    """Mapping-driven DPR parser — reads config from SQLite."""

    def __init__(self) -> None:
        self.logger = LogService.get()

    async def extract(
        self,
        report_type: ReportType,
        dpr_folder: str,
        date_dpr: date | None = None,
        auto_name: bool = True,
        num_days: int = 1,
        concatenate: bool = False,
        concession_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Main extraction entry point.

        Args:
            concession_ids: If provided, only extract these concessions.
                            If empty/None, extract all active concessions.

        Returns dict with keys: columns, data, record_count,
        plus dc_data, dw_data, mc_data, wt_data for typed access.
        """
        await self.logger.info(
            f"Starting {report_type.value} extraction, {num_days} day(s)",
            source="parser",
        )

        # Load UOM conversion map from SQLite
        uom_map = self._load_uom_map()

        # Load naming rules from SQLite
        naming_rules = self._load_naming_rules()

        if report_type in (ReportType.DAILY, ReportType.DC, ReportType.DW):
            return await self._extract_daily(
                dpr_folder, date_dpr, auto_name, num_days, uom_map, naming_rules,
                concession_ids=concession_ids,
            )
        elif report_type == ReportType.MONTHLY:
            return await self._extract_monthly(
                dpr_folder, date_dpr, uom_map,
                concession_ids=concession_ids,
            )
        elif report_type == ReportType.WELL_TEST:
            return await self._extract_well_test(
                dpr_folder, date_dpr, auto_name, num_days, uom_map, naming_rules,
                concession_ids=concession_ids,
            )
        else:
            raise ValueError(f"Unsupported report type: {report_type}")

    # ── Daily extraction ───────────────────────────────────────────────

    async def _extract_daily(
        self,
        dpr_folder: str,
        date_dpr: date | None,
        auto_name: bool,
        num_days: int,
        uom_map: dict[str, float],
        naming_rules: list[dict],
        concession_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Extract daily DC + DW data from SQLite-stored mappings."""
        dc_rows: list[dict[str, Any]] = []
        dw_rows: list[dict[str, Any]] = []

        # Load concessions that are active for daily extraction
        concessions = config_store.list_concessions()
        active_daily = [c for c in concessions if c.active_daily]
        # Filter by requested concession IDs if provided
        if concession_ids:
            active_daily = [c for c in active_daily if c.id in concession_ids]

        for day_offset in range(num_days):
            current_date = (date_dpr - timedelta(days=day_offset)) if date_dpr else None

            # Generate DPR filenames from naming rules
            dpr_list = _auto_generate(current_date, naming_rules) if (auto_name and current_date) else _standard_names(naming_rules)

            # Discover actual files in the folder
            discovered = _discover_files(dpr_folder)
            # Merge discovered files: prefer discovered over auto-generated
            # if the auto-generated file doesn't exist on disk
            for alias, fname in discovered.items():
                if alias not in dpr_list:
                    dpr_list[alias] = fname
                elif not (Path(dpr_folder) / dpr_list[alias]).exists():
                    # Auto-generated name doesn't exist, use discovered file
                    dpr_list[alias] = fname

            for conc in active_daily:
                # Get full concession detail with mappings
                detail = config_store.get_concession(conc.id)
                if not detail:
                    continue

                # Skip concessions with empty alias
                alias = conc.dpr_file_alias or ""
                if not alias.strip():
                    await self.logger.warning(
                        f"Skipping {conc.name}: no DPR file alias configured",
                        source="parser",
                    )
                    continue

                # Resolve DPR filename ONCE for this concession
                dpr_name = dpr_list.get(alias, "")
                if not dpr_name:
                    dpr_name = dpr_list.get(conc.name, "")

                # Final validation: does the file actually exist?
                if dpr_name and not (Path(dpr_folder) / dpr_name).exists():
                    await self.logger.warning(
                        f"Skipping {conc.name}: file '{dpr_name}' not found in {dpr_folder}",
                        source="parser",
                    )
                    continue

                if not dpr_name:
                    await self.logger.warning(
                        f"Skipping {conc.name}: no DPR file found "
                        f"(alias='{conc.dpr_file_alias}')",
                        source="parser",
                    )
                    continue

                await self.logger.info(
                    f"Processing DC/DW: {conc.name} -> {dpr_name}",
                    source="parser",
                )

                # ── DC extraction ──────────────────────────────────
                dc_row: dict[str, Any] = {}
                for m in detail.mappings.dc:
                    if not m.cell_ref:
                        continue

                    val = cell_reader.resolve_ref(
                        m.cell_ref, dpr_folder, dpr_name,
                        detail.dpr_sheet, dpr_list
                    )

                    # Unit conversion
                    if m.unit and m.unit.upper() in uom_map and _is_numeric(val):
                        try:
                            val = float(val) * uom_map[m.unit.upper()]
                        except (ValueError, TypeError):
                            pass

                    # DC001 always = concession name
                    if m.attribute_code == "DC001":
                        val = conc.name

                    dc_row[m.attribute_code] = _serialize_value(val)

                if dc_row:
                    dc_rows.append(dc_row)

                # ── DW extraction ──────────────────────────────────
                for well in detail.mappings.dw:
                    dw_row: dict[str, Any] = {}
                    for m in well.fields:
                        if not m.cell_ref:
                            continue

                        val = cell_reader.resolve_ref(
                            m.cell_ref, dpr_folder, dpr_name,
                            detail.dpr_sheet, dpr_list
                        )

                        if m.unit and m.unit.upper() in uom_map and _is_numeric(val):
                            try:
                                val = float(val) * uom_map[m.unit.upper()]
                            except (ValueError, TypeError):
                                pass

                        # Special field overrides
                        if m.attribute_code == "DW001":
                            val = conc.name
                        elif m.attribute_code == "DW003":
                            val = well.well_name or well.ubhi or ""
                        elif m.attribute_code == "DW004":
                            val = well.ubhi
                        elif m.attribute_code == "DW005":
                            val = well.completion

                        dw_row[m.attribute_code] = _serialize_value(val)

                    if dw_row:
                        dw_rows.append(dw_row)

        await cell_reader.clear_cache()

        # Build column list as union of ALL rows' keys (different concessions may map different fields)
        dc_columns = sorted({k for row in dc_rows for k in row}) if dc_rows else []
        dw_columns = sorted({k for row in dw_rows for k in row}) if dw_rows else []
        all_data = dc_rows + dw_rows

        await self.logger.success(
            f"Extracted {len(dc_rows)} DC rows, {len(dw_rows)} DW rows",
            source="parser",
        )

        return {
            "columns": dc_columns or dw_columns,
            "data": all_data,
            "record_count": len(all_data),
            "dc_data": dc_rows,
            "dw_data": dw_rows,
        }

    # ── Monthly extraction ─────────────────────────────────────────────

    async def _extract_monthly(
        self,
        dpr_folder: str,
        date_dpr: date | None,
        uom_map: dict[str, float],
        concession_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Extract monthly MC data from SQLite-stored mappings."""
        mc_rows: list[dict[str, Any]] = []

        month_col = MONTH_TO_COLUMN.get(date_dpr.month, "B") if date_dpr else "B"

        concessions = config_store.list_concessions()
        active_monthly = [c for c in concessions if c.active_monthly]
        if concession_ids:
            active_monthly = [c for c in active_monthly if c.id in concession_ids]

        # Pre-load naming rules and file discovery once
        naming_rules = self._load_naming_rules()
        dpr_list = _standard_names(naming_rules)
        discovered = _discover_files(dpr_folder)
        # Merge discovered files: prefer discovered over non-existent standard names
        for alias, fname in discovered.items():
            if alias not in dpr_list:
                dpr_list[alias] = fname
            elif not (Path(dpr_folder) / dpr_list[alias]).exists():
                dpr_list[alias] = fname

        for conc in active_monthly:
            detail = config_store.get_concession(conc.id)
            if not detail:
                continue

            # Resolve DPR filename ONCE for this concession
            monthly_file = conc.monthly_report or ""
            dpr_name = ""

            # 1. Try explicit monthly_report filename
            if monthly_file:
                monthly_path = Path(dpr_folder) / monthly_file
                if monthly_path.exists():
                    dpr_name = monthly_file
                else:
                    # Also check if discovered under monthly_file stem
                    stem = Path(monthly_file).stem
                    dpr_name = dpr_list.get(stem, "")
                    if dpr_name:
                        await self.logger.info(
                            f"Monthly file '{monthly_file}' not found, "
                            f"falling back to '{dpr_name}'",
                            source="parser",
                        )

            # 2. Fall back to dpr_file_alias lookup
            if not dpr_name:
                alias = conc.dpr_file_alias or ""
                dpr_name = dpr_list.get(alias, "")
                if not dpr_name:
                    dpr_name = dpr_list.get(conc.name, "")

            # 3. Validate file exists
            if dpr_name and not (Path(dpr_folder) / dpr_name).exists():
                await self.logger.warning(
                    f"Skipping MC {conc.name}: file '{dpr_name}' not found in {dpr_folder}",
                    source="parser",
                )
                continue

            if not dpr_name:
                await self.logger.warning(
                    f"Skipping MC {conc.name}: no monthly/DPR file found",
                    source="parser",
                )
                continue

            await self.logger.info(
                f"Processing MC: {conc.name} -> {dpr_name}",
                source="parser",
            )

            mc_row: dict[str, Any] = {}
            for m in detail.mappings.mc:
                if not m.cell_ref:
                    continue

                # MC cell_ref may use a column letter that should be swapped
                # to the month-specific column — but only for value fields
                # (MC005+), not header fields like MC001 (concession name).
                ref = m.cell_ref.replace(":", "")
                code_num = 0
                try:
                    code_num = int(m.attribute_code[2:]) if m.attribute_code and len(m.attribute_code) >= 3 else 0
                except ValueError:
                    pass

                # Only swap column for data fields (MC005 and above)
                if code_num >= 5:
                    import re as _re
                    _m = _re.match(r"([A-Za-z]+)(\d+)", ref)
                    if _m:
                        ref = month_col + _m.group(2)

                val = cell_reader.resolve_ref(
                    ref, dpr_folder, dpr_name, detail.dpr_sheet
                )

                if m.unit and m.unit.upper() in uom_map and _is_numeric(val):
                    try:
                        val = float(val) * uom_map[m.unit.upper()]
                    except (ValueError, TypeError):
                        pass

                if m.attribute_code == "MC001":
                    val = conc.name

                mc_row[m.attribute_code] = _serialize_value(val)

            if mc_row:
                mc_rows.append(mc_row)

        await cell_reader.clear_cache()

        await self.logger.success(
            f"Extracted {len(mc_rows)} MC rows", source="parser"
        )

        columns = sorted({k for row in mc_rows for k in row}) if mc_rows else []
        return {
            "columns": columns,
            "data": mc_rows,
            "record_count": len(mc_rows),
            "mc_data": mc_rows,
        }

    # ── Well Test extraction ───────────────────────────────────────────

    async def _extract_well_test(
        self,
        dpr_folder: str,
        date_dpr: date | None,
        auto_name: bool,
        num_days: int,
        uom_map: dict[str, float],
        naming_rules: list[dict],
        concession_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Extract well test data from SQLite-stored mappings."""
        wt_rows: list[dict[str, Any]] = []

        concessions = config_store.list_concessions()
        active_wt = [c for c in concessions if c.active_well_test]
        if concession_ids:
            active_wt = [c for c in active_wt if c.id in concession_ids]

        for day_offset in range(num_days):
            current_date = (date_dpr - timedelta(days=day_offset)) if date_dpr else None

            dpr_list = _auto_generate(current_date, naming_rules) if (auto_name and current_date) else _standard_names(naming_rules)

            # Discover actual files and prefer discovered over non-existent auto-generated
            discovered = _discover_files(dpr_folder)
            for alias, fname in discovered.items():
                if alias not in dpr_list:
                    dpr_list[alias] = fname
                elif not (Path(dpr_folder) / dpr_list[alias]).exists():
                    dpr_list[alias] = fname

            for conc in active_wt:
                detail = config_store.get_concession(conc.id)
                if not detail:
                    continue

                alias = conc.dpr_file_alias or ""
                if not alias.strip():
                    continue

                # Resolve DPR filename ONCE for this concession
                dpr_name = dpr_list.get(alias, "")
                if not dpr_name:
                    dpr_name = dpr_list.get(conc.name, "")

                # Validate file exists
                if dpr_name and not (Path(dpr_folder) / dpr_name).exists():
                    await self.logger.warning(
                        f"Skipping WT {conc.name}: file '{dpr_name}' not found",
                        source="parser",
                    )
                    continue

                if not dpr_name:
                    await self.logger.warning(
                        f"Skipping WT {conc.name}: no DPR file found",
                        source="parser",
                    )
                    continue

                await self.logger.info(
                    f"Processing WT: {conc.name} -> {dpr_name}",
                    source="parser",
                )

                for well in detail.mappings.wt:
                    wt_row: dict[str, Any] = {}
                    for m in well.fields:
                        if not m.cell_ref:
                            continue

                        val = cell_reader.resolve_ref(
                            m.cell_ref, dpr_folder, dpr_name,
                            detail.dpr_sheet, dpr_list
                        )

                        if m.unit and m.unit.upper() in uom_map and _is_numeric(val):
                            try:
                                val = float(val) * uom_map[m.unit.upper()]
                            except (ValueError, TypeError):
                                pass

                        if m.attribute_code == "WT001":
                            val = conc.name
                        elif m.attribute_code == "WT003":
                            val = well.well_name or well.ubhi or ""
                        elif m.attribute_code == "WT004":
                            val = well.ubhi
                        elif m.attribute_code == "WT005":
                            val = well.completion

                        wt_row[m.attribute_code] = _serialize_value(val)

                    if wt_row:
                        wt_rows.append(wt_row)

        await cell_reader.clear_cache()

        await self.logger.success(
            f"Extracted {len(wt_rows)} WT rows", source="parser"
        )

        columns = sorted({k for row in wt_rows for k in row}) if wt_rows else []
        return {
            "columns": columns,
            "data": wt_rows,
            "record_count": len(wt_rows),
            "wt_data": wt_rows,
        }

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _load_uom_map() -> dict[str, float]:
        """Load UOM conversion factors from SQLite."""
        entries = config_store.list_uom()
        return {e.unit.upper(): e.factor for e in entries}

    @staticmethod
    def _load_naming_rules() -> list[dict]:
        """Load naming rules from SQLite."""
        conn = get_connection()
        try:
            rows = conn.execute("SELECT * FROM naming_rules ORDER BY id").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# ── Module-level helpers ───────────────────────────────────────────────

# VBA date format -> Python strftime mapping
_FORMAT_MAP = {
    "ddmmyyyy": "%d%m%Y",
    "yyyymmdd": "%Y%m%d",
    "dd-mm-yyyy": "%d-%m-%Y",
    "mmmm dd, yyyy": "%B %d, %Y",
    "mmmm_dd": "%B_%d",
    "dd mmm yyyy": "%d %b %Y",
    "mmm dd": "%b %d",
    "dd/mm/yyyy": "%d/%m/%Y",
    "dd mm yyyy": "%d %m %Y",
}


def _vba_date_format(dt: date, vba_fmt: str) -> str:
    """Convert a date using a VBA-style format string."""
    fmt = vba_fmt.strip().lower()
    py_fmt = _FORMAT_MAP.get(fmt)
    if py_fmt:
        return dt.strftime(py_fmt)
    return dt.strftime("%d%m%Y")


def _auto_generate(dt: date | None, rules: list[dict]) -> dict[str, str]:
    """Generate DPR filenames for a given date from naming rules."""
    if not dt:
        return _standard_names(rules)

    result: dict[str, str] = {}
    day_of_year = dt.timetuple().tm_yday

    for rule in rules:
        alias = rule.get("alias", "")
        file_alias = rule.get("file_alias", alias)
        ext = f".{rule.get('extension', 'xlsx')}"
        fmt = rule.get("date_format", "ddmmyyyy")
        left = rule.get("left_sep", "")
        right = rule.get("right_sep", "")
        suffix = rule.get("suffix", "")

        formatted_date = _vba_date_format(dt, fmt)

        # Special case: RAPPORT MLD uses day-of-year
        if alias == "RAPPORT MLD":
            sep = right.replace("0", "") if right else ""
            result[alias] = f"{file_alias}{sep}{day_of_year}{ext}"
            continue

        # Special case: HSD Daily Prod
        if alias == "HSD Daily Prod":
            sep = right.replace("0", "") if right else ""
            result[alias] = f"{file_alias}{sep}{formatted_date}{suffix}{ext}"
            continue

        # Standard logic
        if left:
            sep = left.replace("0", "")
            result[alias] = f"{formatted_date}{sep}{file_alias}{ext}"
        elif right:
            sep = right.replace("0", "")
            result[alias] = f"{file_alias}{sep}{formatted_date}{suffix}{ext}"
        else:
            result[alias] = f"{file_alias} {formatted_date}{ext}"

    return result


def _standard_names(rules: list[dict]) -> dict[str, str]:
    """Generate standard (fixed) DPR filenames."""
    return {
        rule.get("alias", ""): f"{rule.get('file_alias', rule.get('alias', ''))}.{rule.get('extension', 'xlsx')}"
        for rule in rules
    }


def _discover_files(dpr_folder: str) -> dict[str, str]:
    """Scan folder for .xlsx/.xlsm files and build alias→filename map.

    Handles both regular filenames (e.g. Abir.xlsx → {"Abir": "Abir.xlsx"})
    and upload-prefixed filenames (e.g. a1b2c3_Abir.xlsx → {"Abir": "a1b2c3_Abir.xlsx"}).

    When multiple upload-prefixed files share the same original name,
    the most recently modified file takes priority.
    """
    folder = Path(dpr_folder)
    if not folder.is_dir():
        return {}

    # Collect all Excel files, sorted by modification time (newest first)
    # so the most recent upload wins when there are duplicates
    files = sorted(
        (f for f in folder.iterdir()
         if f.is_file() and f.suffix.lower() in (".xlsx", ".xlsm")),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    result: dict[str, str] = {}
    for f in files:
        stem = f.stem
        # Always register the raw stem (first seen = newest wins)
        if stem not in result:
            result[stem] = f.name
        # If the filename has an upload prefix (12-char hex + underscore),
        # also register the original name without the prefix
        if len(stem) > 13 and stem[12] == "_":
            prefix = stem[:12]
            # Verify it looks like a hex UUID prefix
            try:
                int(prefix, 16)
                original_stem = stem[13:]
                if original_stem and original_stem not in result:
                    result[original_stem] = f.name
            except ValueError:
                pass
    return result


def _is_numeric(val: Any) -> bool:
    if val is None or val == "":
        return False
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False


def _serialize_value(val: Any) -> Any:
    """Ensure a value is JSON-serializable.

    Converts datetime objects to ISO format strings.
    Converts NaN/Infinity to None for clean JSON output.
    """
    import math
    from datetime import datetime as _dt, date as _d

    if isinstance(val, float) and not math.isfinite(val):
        return None
    if isinstance(val, _dt):
        return val.isoformat()
    if isinstance(val, _d):
        return val.isoformat()
    return val
