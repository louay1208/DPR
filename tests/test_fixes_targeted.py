"""Targeted tests for the 5 issues fixed in this batch."""

import os
import sys
import time
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_upload_priority():
    """Issue 5: Upload file priority — newest file should win."""
    from app.services.parser import _discover_files

    with tempfile.TemporaryDirectory() as td:
        # Create two 'upload-prefixed' files for the same original name
        f1 = Path(td) / "aaa111bbb222_Abir.xlsx"
        f1.write_bytes(b"old")
        time.sleep(0.05)  # ensure different mtime
        f2 = Path(td) / "ccc333ddd444_Abir.xlsx"
        f2.write_bytes(b"new")

        result = _discover_files(td)

        # 'Abir' should map to the NEWEST file (f2)
        assert result["Abir"] == "ccc333ddd444_Abir.xlsx", (
            f"FAIL: got {result.get('Abir')}"
        )
        print("PASS: Upload priority — newest file wins for same original stem")


def test_sync_combined_rebuilds_columns():
    """Issue 1: _sync_combined must rebuild column lists."""
    from app.models.schemas import ExtractionResult, ProcessingStatus, ReportType
    from app.routers.extract import _sync_combined

    result = ExtractionResult(
        id="test",
        report_type=ReportType.DAILY,
        status=ProcessingStatus.COMPLETED,
        dc_data=[{"DC001": "Test", "DC002": "2024-01-01", "DC_NEW": "added"}],
        dc_columns=["DC001", "DC002"],  # missing DC_NEW
        dw_data=[],
        mc_data=[],
        wt_data=[],
    )
    _sync_combined(result)
    assert "DC_NEW" in result.dc_columns, f"FAIL: dc_columns={result.dc_columns}"
    assert result.record_count == 1
    print("PASS: _sync_combined rebuilds columns from data")


def test_extractiondata_shape_consistency():
    """Issue 2: extractionData must always be {rows, cols} not raw array."""
    with open("static/js/app.js", "r", encoding="utf-8") as f:
        code = f.read()

    # Check that loadSavedExtraction does NOT set extractionData directly
    # Find the loadSavedExtraction function
    idx = code.find("async function loadSavedExtraction")
    assert idx > 0, "loadSavedExtraction not found"
    func_end = code.find("\n    async function ", idx + 10)
    func_body = code[idx:func_end] if func_end > 0 else code[idx:idx+2000]

    # Should NOT contain 'extractionData =' or 'extractionData=' direct assignment
    if "extractionData =" in func_body or "extractionData=" in func_body:
        print("FAIL: loadSavedExtraction still sets extractionData directly")
        assert False
    else:
        print("PASS: loadSavedExtraction delegates to populateOutputPages")


def test_monthly_file_discovery():
    """Issue 4: Monthly extraction should merge discovered files like daily."""
    with open("app/services/parser.py", "r", encoding="utf-8") as f:
        code = f.read()

    # Find _extract_monthly
    idx = code.find("async def _extract_monthly")
    assert idx > 0, "_extract_monthly not found"
    func_end = code.find("\n    async def ", idx + 10)
    func_body = code[idx:func_end] if func_end > 0 else code[idx:idx+3000]

    # Should merge discovered into dpr_list (not use std_names separately)
    assert "dpr_list" in func_body, "FAIL: monthly should use merged dpr_list"
    assert "std_names.get" not in func_body, (
        "FAIL: monthly still uses separate std_names lookup"
    )
    # Should validate file exists on disk
    assert "not (Path(dpr_folder) / dpr_name).exists()" in func_body, (
        "FAIL: monthly should validate file existence"
    )
    # Should try conc.name as fallback
    assert "dpr_list.get(conc.name" in func_body, (
        "FAIL: monthly should try conc.name as fallback"
    )
    print("PASS: Monthly extraction merges discovered files correctly")


if __name__ == "__main__":
    print("=" * 60)
    print("TARGETED FIX VERIFICATION")
    print("=" * 60)
    print()
    test_upload_priority()
    test_sync_combined_rebuilds_columns()
    test_extractiondata_shape_consistency()
    test_monthly_file_discovery()
    print()
    print("=" * 60)
    print("ALL TARGETED TESTS PASSED")
    print("=" * 60)
