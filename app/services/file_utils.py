"""File utilities — path validation, file checks, folder scanning."""

from __future__ import annotations

from pathlib import Path

from app.models.schemas import FileCheckResult


def validate_path(path: str) -> dict[str, bool | str]:
    """Validate that a filesystem path exists and is accessible."""
    p = Path(path)
    return {
        "path": path,
        "exists": p.exists(),
        "is_directory": p.is_dir(),
        "is_file": p.is_file(),
        "readable": p.exists() and (p.is_file() or p.is_dir()),
    }


def scan_folder(
    folder: str, extensions: set[str] | None = None
) -> list[dict[str, str | int]]:
    """Scan a folder and list matching files.

    Returns list of {name, size, extension} dicts.
    """
    if extensions is None:
        extensions = {".xlsx", ".xls", ".xlsm"}

    p = Path(folder)
    if not p.exists() or not p.is_dir():
        return []

    files = []
    for f in sorted(p.iterdir()):
        if f.is_file() and f.suffix.lower() in extensions:
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "extension": f.suffix.lower(),
                "path": str(f),
            })

    return files


def check_files_exist(
    folder: str, filenames: list[str]
) -> list[FileCheckResult]:
    """Check which files exist in a folder.

    Used for pre-flight validation before extraction.
    """
    p = Path(folder)
    results = []

    for name in filenames:
        filepath = p / name
        results.append(FileCheckResult(
            filename=name,
            exists=filepath.exists(),
            path=str(filepath) if filepath.exists() else "",
        ))

    return results


def check_dpr_and_mapping_files(
    dpr_folder: str,
    mapping_folder: str,
    dpr_files: dict[str, str],
    mapping_files: list[str],
) -> dict[str, list[FileCheckResult]]:
    """Check all DPR and mapping files before extraction.

    Returns {dpr_results, mapping_results}.
    """
    dpr_results = check_files_exist(dpr_folder, list(dpr_files.values()))
    mapping_results = check_files_exist(mapping_folder, mapping_files)

    return {
        "dpr_results": dpr_results,
        "mapping_results": mapping_results,
        "all_dpr_exist": all(r.exists for r in dpr_results),
        "all_mapping_exist": all(r.exists for r in mapping_results),
    }
