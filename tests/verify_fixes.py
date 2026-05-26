"""Post-fix verification script for all critical bugs."""

import asyncio
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from app.services import config_store
from app.services.parser import ParserService, _discover_files, _standard_names
from app.models.schemas import ReportType


async def main():
    print("=" * 70)
    print("DPR POST-FIX VERIFICATION")
    print("=" * 70)
    
    docs_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    
    # ----------------------------------------------------------------
    # TEST 1: Parser only produces rows for found DPR files (Bug 1.1)
    # ----------------------------------------------------------------
    print("\n[TEST 1] Parser skips concessions with missing DPR files")
    
    discovered = _discover_files(docs_folder)
    concessions = config_store.list_concessions()
    active_daily = [c for c in concessions if c.active_daily]
    
    # Only "Abir" should match
    expected_match_count = sum(
        1 for c in active_daily 
        if c.dpr_file_alias in discovered or c.name in discovered
    )
    print(f"  Active concessions: {len(active_daily)}, expected matches: {expected_match_count}")
    
    parser = ParserService()
    result = await parser.extract(
        report_type=ReportType.DAILY,
        dpr_folder=docs_folder,
        date_dpr=date(2024, 1, 15),
    )
    
    dc_data = result.get("dc_data", [])
    dw_data = result.get("dw_data", [])
    print(f"  DC rows: {len(dc_data)}, DW rows: {len(dw_data)}")
    
    # Verify no empty rows
    empty_rows = 0
    for row in dc_data:
        non_name_values = [v for k, v in row.items() 
                           if k != "DC001" and v and v != "" and v != 0 and v != 0.0]
        if not non_name_values:
            empty_rows += 1
    
    if empty_rows == 0 and len(dc_data) == expected_match_count:
        print(f"  PASS: {len(dc_data)} DC rows, all with data, no empty rows")
    else:
        print(f"  FAIL: {empty_rows} empty rows found, expected {expected_match_count} rows got {len(dc_data)}")
    
    # Show some actual values
    if dc_data:
        row = dc_data[0]
        print(f"  First DC row: concession={row.get('DC001')}")
        filled_fields = {k: v for k, v in row.items() if v and v != "" and v != 0}
        print(f"  Filled fields: {len(filled_fields)}/{len(row)} -> {list(filled_fields.keys())[:10]}...")

    # ----------------------------------------------------------------
    # TEST 2: _standard_names uses file_alias (Bug 2.4)
    # ----------------------------------------------------------------
    print("\n[TEST 2] _standard_names uses file_alias")
    
    from app.services.database import get_connection
    conn = get_connection()
    try:
        rules = conn.execute("SELECT * FROM naming_rules LIMIT 5").fetchall()
        naming_rules = [dict(r) for r in rules]
    finally:
        conn.close()
    
    if naming_rules:
        std = _standard_names(naming_rules)
        all_ok = True
        for alias, fname in list(std.items())[:5]:
            rule = next((r for r in naming_rules if r.get("alias") == alias), {})
            file_alias = rule.get("file_alias", alias)
            expected_fname = f"{file_alias}.{rule.get('extension', 'xlsx')}"
            if fname == expected_fname:
                print(f"  PASS: '{alias}' -> '{fname}'")
            else:
                print(f"  FAIL: '{alias}' -> '{fname}' (expected '{expected_fname}')")
                all_ok = False
        if all_ok:
            print("  PASS: All naming rules use file_alias correctly")
    else:
        print("  SKIP: No naming rules in DB")

    # ----------------------------------------------------------------
    # TEST 3: Corrector auto_correct doesn't crash (Bug 2.1+2.2)
    # ----------------------------------------------------------------
    print("\n[TEST 3] Corrector auto_correct works without crash")
    
    from app.services.corrector import CorrectorService
    corrector = CorrectorService()
    
    test_data = [
        {"DC001": "TEST_CONC", "DC002": "2024-01-15", "DC005": 100.0, "DC006": -50.0},
        {"DC001": "TEST_CONC2", "DC002": "2024-01-15", "DC005": 200.0, "DC006": 75.0},
    ]
    try:
        result_corr = await corrector.auto_correct(test_data)
        print(f"  PASS: auto_correct completed with {len(result_corr['corrections'])} corrections")
        print(f"  Output rows: {len(result_corr['data'])}")
        for c in result_corr['corrections']:
            print(f"    Correction: {c}")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")

    # ----------------------------------------------------------------
    # TEST 4: Extract router code review (Bug 1.3+1.4)
    # ----------------------------------------------------------------
    print("\n[TEST 4] Extract router uses typed data arrays")
    
    import inspect
    from app.routers import extract as extract_mod
    
    # Check auto_correct uses typed arrays
    source_ac = inspect.getsource(extract_mod.auto_correct)
    has_typed = "DATA_TYPE_FIELDS" in source_ac or "dc_data" in source_ac
    print(f"  auto_correct uses typed data: {'PASS' if has_typed else 'FAIL'}")
    
    # Check export uses typed data
    source_exp = inspect.getsource(extract_mod.export_csv)
    has_typed_exp = "type_data_map" in source_exp or "dc_data" in source_exp
    print(f"  export_csv uses typed data: {'PASS' if has_typed_exp else 'FAIL'}")
    
    # Check convert uses typed data
    source_conv = inspect.getsource(extract_mod.convert_units)
    has_typed_conv = "DATA_TYPE_FIELDS" in source_conv
    print(f"  convert_units uses typed data: {'PASS' if has_typed_conv else 'FAIL'}")

    # ----------------------------------------------------------------
    # TEST 5: Frontend refreshExtraction includes populateOutputPages
    # ----------------------------------------------------------------
    print("\n[TEST 5] Frontend refreshExtraction refreshes grids")
    
    app_js_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "js", "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find refreshExtraction function
    idx = content.find("async function refreshExtraction")
    if idx >= 0:
        snippet = content[idx:idx+400]
        has_populate = "populateOutputPages" in snippet
        print(f"  refreshExtraction calls populateOutputPages: {'PASS' if has_populate else 'FAIL'}")
    else:
        print("  FAIL: refreshExtraction function not found")
    
    # Check restoreLastExtraction no longer sets extractionData directly
    idx2 = content.find("async function restoreLastExtraction")
    if idx2 >= 0:
        snippet2 = content[idx2:idx2+600]
        sets_directly = "extractionData = {" in snippet2 or "extractionData.dc = " in snippet2
        print(f"  restoreLastExtraction avoids direct extractionData set: {'PASS' if not sets_directly else 'FAIL'}")

    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
