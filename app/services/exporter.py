"""CSV export service — generates ProSource-compatible files.

Uses real column schemas from DatafileDD and date-based filenames
matching the VBA savetoCSV subroutine.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import EXPORT_DIR
from app.models.schemas import ReportType
from app.services.logger import LogService


class ExporterService:
    """Exports processed data to ProSource-compatible CSV files."""

    def __init__(self) -> None:
        self.logger = LogService.get()

    async def export_csv(
        self,
        data: list[dict[str, Any]],
        report_type: ReportType = ReportType.DAILY,
        output_folder: str = "",
        date_dpr: date | None = None,
    ) -> Path:
        """Export data to a CSV file with ProSource column order.

        Uses real column schemas from the moulinette and date-based naming.
        Column headers are renamed from codes (DC001) to French attribute names
        (Nom Concession) to match the original VBA output format.
        """
        if not data:
            raise ValueError("No data to export")

        df = pd.DataFrame(data)

        # ── Detect date column BEFORE rename (BUG-10 fix) ─────────
        # Use attribute codes which are guaranteed to exist at this stage
        date_col = next(
            (c for c in df.columns if c in ("DC002", "MC002", "WT002", "DW002")),
            None,
        )

        # ── Sort columns by attribute code (BUG-09 fix) ───────────
        # Natural sort: DC001, DC002, ..., DC050, DW001, ...
        def _col_sort_key(col: str) -> tuple:
            prefix = col[:2] if len(col) >= 2 else col
            try:
                num = int(col[2:]) if len(col) > 2 and col[2:].isdigit() else 999
            except ValueError:
                num = 999
            return (prefix, num)

        sorted_cols = sorted(df.columns, key=_col_sort_key)
        df = df[sorted_cols]

        # ── Rename columns from codes to attribute names ──────────
        attr_map = self._get_attribute_map()
        rename_map = {c: attr_map[c] for c in df.columns if c in attr_map}
        # Track the renamed date column for filename generation
        date_col_renamed = rename_map.get(date_col) if date_col else None
        if rename_map:
            df = df.rename(columns=rename_map)

        # Generate filename with date (using pre-rename column detection)
        filename = self._build_filename(
            report_type, df, date_dpr,
            date_col=date_col_renamed or date_col,
        )

        # Determine output path
        out_dir = Path(output_folder) if output_folder else EXPORT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / filename

        # Write CSV (Windows-1252 for French characters, matching VBA xlCSVWindows)
        try:
            df.to_csv(
                output_path, index=False,
                encoding="cp1252", quoting=csv.QUOTE_MINIMAL,
            )
        except UnicodeEncodeError:
            # Fallback to UTF-8 with BOM
            df.to_csv(
                output_path, index=False,
                encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL,
            )

        await self.logger.success(
            f"Exported {len(df)} records to {filename}", source="exporter"
        )

        return output_path

    async def export_all(
        self,
        dc_data: list[dict[str, Any]],
        dw_data: list[dict[str, Any]],
        mc_data: list[dict[str, Any]] | None = None,
        wt_data: list[dict[str, Any]] | None = None,
        output_folder: str = "",
        date_dpr: date | None = None,
    ) -> list[Path]:
        """Export all 4 output types at once, like VBA savetoCSV."""
        paths: list[Path] = []

        if dc_data:
            p = await self.export_csv(dc_data, ReportType.DC, output_folder, date_dpr)
            paths.append(p)

        if dw_data:
            p = await self.export_csv(dw_data, ReportType.DW, output_folder, date_dpr)
            paths.append(p)

        if mc_data:
            p = await self.export_csv(mc_data, ReportType.MONTHLY, output_folder, date_dpr)
            paths.append(p)

        if wt_data:
            p = await self.export_csv(wt_data, ReportType.WELL_TEST, output_folder, date_dpr)
            paths.append(p)

        return paths

    async def list_exports(self, output_folder: str = "") -> list[dict[str, Any]]:
        """List all exported CSV files."""
        out_dir = Path(output_folder) if output_folder else EXPORT_DIR
        exports = []
        if out_dir.exists():
            for f in sorted(out_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True):
                stat = f.stat()
                exports.append({
                    "filename": f.name,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "path": str(f),
                })
        return exports

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_attribute_map(self) -> dict[str, str]:
        """Build code→name mapping from all concession mappings."""
        from app.services import config_store

        attr_map: dict[str, str] = {}
        for conc in config_store.list_concessions():
            detail = config_store.get_concession(conc.id)
            if not detail:
                continue
            for m in detail.mappings.dc:
                if m.attribute_code and m.attribute and m.attribute_code not in attr_map:
                    attr_map[m.attribute_code] = m.attribute
            for m in detail.mappings.mc:
                if m.attribute_code and m.attribute and m.attribute_code not in attr_map:
                    attr_map[m.attribute_code] = m.attribute
            for well in detail.mappings.dw:
                for m in well.fields:
                    if m.attribute_code and m.attribute and m.attribute_code not in attr_map:
                        attr_map[m.attribute_code] = m.attribute
            for well in detail.mappings.wt:
                for m in well.fields:
                    if m.attribute_code and m.attribute and m.attribute_code not in attr_map:
                        attr_map[m.attribute_code] = m.attribute
        return attr_map

    def _get_schema(
        self, report_type: ReportType
    ) -> list:
        """Get the column schema for a report type (placeholder for future use)."""
        return []

    def _build_filename(
        self, report_type: ReportType, df: pd.DataFrame, date_dpr: date | None,
        date_col: str | None = None,
    ) -> str:
        """Build date-based filename matching VBA savetoCSV naming.

        Single date:  Daily_Well_DDMMYYYY.csv
        Date range:   Daily_Well_DDMM_DDMMYYYY.csv

        Args:
            date_col: The column name containing dates (detected before
                      column rename for reliability).
        """
        prefix_map = {
            ReportType.DAILY: "Daily_Concession",
            ReportType.DC: "Daily_Concession",
            ReportType.DW: "Daily_Well",
            ReportType.MONTHLY: "Monthly_Concession",
            ReportType.WELL_TEST: "Well_Test",
        }
        prefix = prefix_map.get(report_type, "Export")

        # Try to find date range from data using the pre-detected column
        target_cols = []
        if date_col and date_col in df.columns:
            target_cols = [date_col]
        else:
            # Fallback: heuristic search for any column with "date" in the name
            target_cols = [c for c in df.columns if "date" in c.lower()]

        if target_cols:
            try:
                dates = pd.to_datetime(df[target_cols[0]], errors="coerce").dropna()
                if not dates.empty:
                    dt_min = dates.min()
                    dt_max = dates.max()
                    if dt_min == dt_max:
                        return f"{prefix}_{dt_max.strftime('%d%m%Y')}.csv"
                    else:
                        return f"{prefix}_{dt_min.strftime('%d%m')}_{dt_max.strftime('%d%m%Y')}.csv"
            except Exception:
                pass

        # Fallback: use provided date or timestamp
        if date_dpr:
            return f"{prefix}_{date_dpr.strftime('%d%m%Y')}.csv"

        ts = datetime.now().strftime("%d%m%Y_%H%M%S")
        return f"{prefix}_{ts}.csv"
