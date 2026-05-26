"""DPR filename generator — auto/standard naming based on date and rules."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from app.models.schemas import DPRNamingRule


# VBA date format -> Python strftime mapping
_FORMAT_MAP = {
    "ddmmyyyy": "%d%m%Y",
    "yyyymmdd": "%Y%m%d",
    "dd-mm-yyyy": "%d-%m-%Y",
    "mmmm dd, yyyy": "%B %d, %Y",     # e.g. "September 27, 2021"
    "mmmm_dd": "%B_%d",               # e.g. "September_27"
    "dd mmm yyyy": "%d %b %Y",
    "mmm dd": "%b %d",
    "dd/mm/yyyy": "%d/%m/%Y",
}


def _vba_date_format(dt: date, vba_fmt: str) -> str:
    """Convert a date using a VBA-style format string."""
    fmt = vba_fmt.strip().lower()
    py_fmt = _FORMAT_MAP.get(fmt)
    if py_fmt:
        return dt.strftime(py_fmt)
    # Fallback: try direct strftime
    return dt.strftime("%d%m%Y")


def auto_generate(dt: date, rules: list[DPRNamingRule]) -> dict[str, str]:
    """Generate DPR filenames for a given date.

    Returns a dict mapping DPR alias -> generated filename.
    Mirrors VBA `AutoDPRname()`.
    """
    result: dict[str, str] = {}
    day_of_year = dt.timetuple().tm_yday

    for rule in rules:
        ext = f".{rule.extension}"
        formatted_date = _vba_date_format(dt, rule.date_format)

        # Special case: RAPPORT MLD uses day-of-year
        if rule.alias == "RAPPORT MLD":
            sep = rule.right_sep.replace("0", "") if rule.right_sep else ""
            filename = f"{rule.file_alias}{sep}{day_of_year}{ext}"
            result[rule.alias] = filename
            continue

        # Special case: HSD Daily Prod
        if rule.alias == "HSD Daily Prod":
            sep = rule.right_sep.replace("0", "") if rule.right_sep else ""
            filename = f"{rule.file_alias}{sep}{formatted_date}{rule.suffix}{ext}"
            result[rule.alias] = filename
            continue

        # Standard logic
        if rule.left_sep:
            sep = rule.left_sep.replace("0", "")
            filename = f"{formatted_date}{sep}{rule.file_alias}{ext}"
        elif rule.right_sep:
            sep = rule.right_sep.replace("0", "")
            filename = f"{rule.file_alias}{sep}{formatted_date}{rule.suffix}{ext}"
        else:
            filename = f"{rule.file_alias} {formatted_date}{ext}"

        result[rule.alias] = filename

    return result


def standard_names(rules: list[DPRNamingRule]) -> dict[str, str]:
    """Generate standard (fixed) DPR filenames.

    Returns a dict mapping DPR alias -> standard filename.
    Mirrors VBA `StandardDPRName()`.
    """
    return {rule.alias: f"{rule.alias}.{rule.extension}" for rule in rules}


def validate_files_exist(
    dpr_path: str, dpr_list: dict[str, str]
) -> list[dict[str, bool]]:
    """Check which DPR files exist in the given folder.

    Returns list of {alias, filename, exists} dicts.
    """
    results = []
    folder = Path(dpr_path)

    for alias, filename in dpr_list.items():
        filepath = folder / filename
        results.append({
            "alias": alias,
            "filename": filename,
            "exists": filepath.exists(),
        })

    return results
