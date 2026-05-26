"""Auto-correction engine — QC cleaning + SM3↔NM3 conversion.

Mirrors VBA QC_Cleaning and ConvertSM_To_NM subroutines.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from app.models.schemas import (
    CorrectionResult,
    QCIssue,
    QCSummary,
)
from app.services.logger import LogService
from app.services import config_store


class CorrectorService:
    """Validates and auto-corrects extracted DPR data."""

    def __init__(self) -> None:
        self.logger = LogService.get()

    async def auto_correct(self, data: list[dict[str, Any]]) -> dict[str, Any]:
        """Run all correction passes on the data.

        Returns dict with keys: data, corrections, summary.
        """
        if not data:
            return {"data": [], "corrections": [], "summary": self._empty_summary()}

        df = pd.DataFrame(data)
        corrections: list[CorrectionResult] = []

        await self.logger.info(
            f"Starting auto-correction on {len(df)} records", source="corrector"
        )

        # ── Pass 1: Remove fully empty rows ────────────────────────────
        before = len(df)
        df.dropna(how="all", inplace=True)
        dropped = before - len(df)
        if dropped:
            await self.logger.info(
                f"Removed {dropped} empty rows", source="corrector"
            )

        # ── Pass 2: Table-driven QC cleaning (from SQLite) ──────────────
        qc_rules = config_store.list_qc_rules()
        active_rules = [r for r in qc_rules if r.active]
        if active_rules:
            df, qc_fixes = self._apply_qc_rules(df, active_rules)
            corrections.extend(qc_fixes)
            if qc_fixes:
                await self.logger.info(
                    f"QC cleaning: {len(qc_fixes)} replacements", source="corrector"
                )

        # ── Pass 3: Replace line breaks with " --> " ───────────────────
        line_break_cols = self._get_text_columns(df)
        for col in line_break_cols:
            mask = df[col].astype(str).str.contains("\n", na=False)
            count = mask.sum()
            if count > 0:
                df[col] = df[col].astype(str).str.replace("\n", " --> ", regex=False)
                await self.logger.info(
                    f"Replaced line breaks in '{col}': {count} cells", source="corrector"
                )

        # ── Pass 4: Fix negative production values ─────────────────────
        numeric_cols = [c for c in df.columns if self._is_production_col(c)]
        for col in numeric_cols:
            if col in df.columns:
                series = pd.to_numeric(df[col], errors="coerce")
                mask = series < 0
                for idx in df[mask].index:
                    original = df.at[idx, col]
                    corrected = abs(float(original)) if original is not None else 0
                    corrections.append(
                        CorrectionResult(
                            field=col, row=int(idx),
                            original_value=original, corrected_value=corrected,
                            reason="Negative value converted to absolute",
                        )
                    )
                    df.at[idx, col] = corrected

        # ── Pass 5: Cap operating hours at 24 ──────────────────────────
        hour_cols = [c for c in df.columns if "heur" in c.lower() or "hour" in c.lower() or "temps" in c.lower()]
        for col in hour_cols:
            series = pd.to_numeric(df[col], errors="coerce")
            mask = series > 24
            for idx in df[mask].index:
                original = df.at[idx, col]
                corrections.append(
                    CorrectionResult(
                        field=col, row=int(idx),
                        original_value=original, corrected_value=24,
                        reason="Operating hours capped at 24",
                    )
                )
                df.at[idx, col] = 24

        # ── Pass 6: Remove duplicate rows ──────────────────────────────
        before = len(df)
        df.drop_duplicates(inplace=True)
        dupes = before - len(df)
        if dupes:
            await self.logger.info(
                f"Removed {dupes} duplicate rows", source="corrector"
            )

        # Replace NaN with None for JSON
        df = df.where(pd.notnull(df), None)

        await self.logger.success(
            f"Auto-correction complete: {len(corrections)} fixes applied",
            source="corrector",
        )

        return {
            "data": df.to_dict(orient="records"),
            "corrections": [c.model_dump() for c in corrections],
            "summary": self._build_summary(df, corrections),
        }

    # ── SM3 ↔ NM3 Conversion ──────────────────────────────────────────

    # Attribute-code pairs: (SM3 code, NM3 code)
    # Based on VBA ConvertSM_To_NM — maps gas volume columns between SM3 and NM3
    _SM3_NM3_PAIRS = [
        ("DC005", "DC006"),   # Production Gaz SM3 ↔ NM3
        ("DC007", "DC008"),   # Gaz vendu STEG SM3 ↔ NM3
        ("DC009", "DC010"),   # Gaz vendu MISKAR SM3 ↔ NM3
        ("DC011", "DC012"),   # Gaz vendu Gabès SM3 ↔ NM3
        ("DC021", "DC022"),   # Torchère / Fuel Gas SM3 ↔ NM3
        ("DC023", "DC024"),   # Gaz Injection SM3 ↔ NM3
        ("DW007", "DW008"),   # Well Gas production SM3 ↔ NM3
    ]

    async def convert_units(
        self,
        data: list[dict[str, Any]],
        direction: str = "sm3_to_nm3",
    ) -> dict[str, Any]:
        """Apply SM3↔NM3 gas volume conversion using attribute codes.

        Mirrors VBA ConvertSM_To_NM. Only fills target column if source
        has value AND target is empty.

        direction: "sm3_to_nm3" or "nm3_to_sm3"
        """
        params = config_store.get_all_parameters()
        sm3_nm3 = float(params.get('sm3_to_nm3', '0.947916'))
        nm3_sm3 = float(params.get('nm3_to_sm3', '1.05494579688496'))

        factor = sm3_nm3 if direction == "sm3_to_nm3" else nm3_sm3
        df = pd.DataFrame(data)
        conversions = 0

        # Build pairs in the correct direction
        if direction == "sm3_to_nm3":
            pairs = self._SM3_NM3_PAIRS
        else:
            pairs = [(nm3, sm3) for sm3, nm3 in self._SM3_NM3_PAIRS]

        for src_code, tgt_code in pairs:
            if src_code not in df.columns or tgt_code not in df.columns:
                continue

            for i in range(len(df)):
                src_val = df.iloc[i][src_code]
                tgt_val = df.iloc[i][tgt_code]

                src_empty = pd.isna(src_val) or src_val == "" or src_val is None
                tgt_empty = pd.isna(tgt_val) or tgt_val == "" or tgt_val is None

                if not src_empty and tgt_empty:
                    try:
                        df.at[df.index[i], tgt_code] = float(src_val) * factor
                        conversions += 1
                    except (ValueError, TypeError):
                        pass

        await self.logger.success(
            f"Unit conversion ({direction}): {conversions} values converted "
            f"with factor {factor}",
            source="corrector",
        )

        df = df.where(pd.notnull(df), None)
        return {"data": df.to_dict(orient="records"), "conversions": conversions}

    # ── QC Checks ──────────────────────────────────────────────────────

    async def run_qc(self, data: list[dict[str, Any]]) -> QCSummary:
        """Run quality-control checks and return a summary."""
        if not data:
            return self._empty_summary()

        df = pd.DataFrame(data)
        issues: list[QCIssue] = []

        # Check for missing key identifiers
        for col_pattern in ["concession", "nom concession", "nom consession"]:
            matching = [c for c in df.columns if col_pattern in c.lower()]
            for col in matching:
                nulls = df[col].isnull().sum() + (df[col] == "").sum()
                if nulls:
                    issues.append(QCIssue(
                        severity="error", field=col,
                        message=f"{nulls} records have missing concession names",
                    ))

        # Check for missing dates
        date_cols = [c for c in df.columns if "date" in c.lower()]
        for col in date_cols:
            nulls = df[col].isnull().sum()
            if nulls:
                issues.append(QCIssue(
                    severity="error", field=col,
                    message=f"{nulls} records have missing dates",
                ))

        # Check for outliers in numeric production columns
        prod_cols = [c for c in df.columns if self._is_production_col(c)]
        for col in prod_cols:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(series) > 5:
                q1, q3 = series.quantile(0.25), series.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    upper = q3 + 3 * iqr
                    outliers = (series > upper).sum()
                    if outliers:
                        issues.append(QCIssue(
                            severity="warning", field=col,
                            message=f"{outliers} potential outliers (> {upper:.1f})",
                        ))

        # Check for zero production
        for col in prod_cols[:3]:  # limit to first 3 prod cols
            series = pd.to_numeric(df[col], errors="coerce")
            zeros = (series == 0).sum()
            if zeros:
                issues.append(QCIssue(
                    severity="info", field=col,
                    message=f"{zeros} records with zero production",
                ))

        total = len(df)
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        score = max(0.0, 100.0 - (error_count * 10) - (warning_count * 3))

        return QCSummary(
            total_records=total,
            valid_records=total - error_count,
            issues=issues,
            quality_score=round(score, 1),
        )

    # ── Internal helpers ───────────────────────────────────────────────

    def _apply_qc_rules(
        self, df: pd.DataFrame, rules: list
    ) -> tuple[pd.DataFrame, list[CorrectionResult]]:
        """Apply table-driven find/replace QC rules.

        Rules from SQLite have: search_value, replace_value, active.
        Applied as simple string find/replace across all string columns.
        """
        corrections: list[CorrectionResult] = []

        for rule in rules:
            if not rule.active:
                continue

            search = str(rule.search_value)
            replace = str(rule.replace_value)

            # Apply to all columns
            for col in df.columns:
                mask = df[col].astype(str) == search
                count = mask.sum()
                if count > 0:
                    df.loc[mask, col] = replace
                    corrections.append(CorrectionResult(
                        field=col, row=-1,
                        original_value=search,
                        corrected_value=replace,
                        reason=f"QC rule: replaced '{search}' with '{replace}'",
                    ))

        return df, corrections

    def _is_production_col(self, col_name: str) -> bool:
        """Check if a column contains production data using attribute codes.

        Matches DC/DW/MC numeric production columns by code range.
        Works reliably before or after column renaming.
        """
        code = col_name.strip().upper()
        # DC005-DC050: concession-level production fields
        # DW007-DW020: well-level production fields
        # MC005-MC050: monthly production fields
        if re.match(r"^DC0(?:[0-4]\d|50)$", code):
            return True
        if re.match(r"^DW0(?:0[7-9]|1\d|20)$", code):
            return True
        if re.match(r"^MC0(?:[0-4]\d|50)$", code):
            return True
        # Fallback: also match French/English names after renaming
        lower = col_name.lower()
        keywords = ["production", "gaz", "gas", "huile", "oil", "eau", "water",
                     "injection", "expédi", "expedie", "torch", "fuel"]
        return any(k in lower for k in keywords)

    def _get_text_columns(self, df: pd.DataFrame) -> list[str]:
        """Get columns likely containing text (remarks, source)."""
        return [c for c in df.columns
                if any(k in c.lower() for k in ["remarque", "remark", "source", "comment"])]

    def _build_summary(self, df: pd.DataFrame, corrections: list[CorrectionResult]) -> dict:
        return {
            "total_records": len(df),
            "corrections_applied": len(corrections),
            "columns": list(df.columns),
        }

    def _empty_summary(self) -> QCSummary:
        return QCSummary(
            total_records=0, valid_records=0, issues=[], quality_score=100.0
        )
