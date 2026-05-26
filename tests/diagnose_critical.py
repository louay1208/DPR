"""Diagnostic script to confirm all critical bugs before fixing."""

import asyncio
import sys
import os

# Force UTF-8 output
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import config_store
from app.services.parser import ParserService, _discover_files, _standard_names


async def main():
    print("=" * 70)
    print("DPR CRITICAL BUG DIAGNOSIS")
    print("=" * 70)

    # -- Bug 1.1: Parser produces empty rows for missing DPR files --
    print("\n-- BUG 1.1: Empty rows from missing DPR files --")
    
    docs_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    discovered = _discover_files(docs_folder)
    print(f"Files discovered in docs/: {discovered}")
    
    concessions = config_store.list_concessions()
    active_daily = [c for c in concessions if c.active_daily]
    print(f"Active daily concessions: {len(active_daily)}")
    
    matched = 0
    unmatched = 0
    for c in active_daily:
        alias = c.dpr_file_alias or ""
        name = c.name
        found = alias in discovered or name in discovered
        status = "FOUND" if found else "MISSING"
        if found:
            matched += 1
        else:
            unmatched += 1
        print(f"  {c.name}: alias='{alias}' -> {status}")
    
    print(f"\n  RESULT: {matched} matched, {unmatched} unmatched")
    print(f"  BUG: Parser will produce {unmatched} empty rows with only DC001 filled")
    
    # Actually run extraction to confirm
    parser = ParserService()
    from datetime import date
    result = await parser.extract(
        report_type="daily",
        dpr_folder=docs_folder,
        date_dpr=date(2024, 1, 15),
    )
    
    dc_data = result.get("dc_data", [])
    dw_data = result.get("dw_data", [])
    print(f"\n  Extraction result: {len(dc_data)} DC rows, {len(dw_data)} DW rows")
    
    empty_dc = 0
    filled_dc = 0
    for row in dc_data:
        # Count non-DC001 fields that have real values
        non_name_values = [v for k, v in row.items() if k != "DC001" and v and v != "" and v != 0 and v != 0.0]
        if non_name_values:
            filled_dc += 1
            print(f"  + FILLED: {row.get('DC001')} has {len(non_name_values)} values: {list(row.keys())[:5]}...")
        else:
            empty_dc += 1
            print(f"  - EMPTY:  {row.get('DC001')} - only DC001 filled, rest empty")
    
    print(f"\n  CONFIRMED BUG 1.1: {empty_dc} empty DC rows, {filled_dc} filled DC rows")

    # -- Bug 2.1: Corrector _apply_qc_rules crash --
    print("\n\n-- BUG 2.1: Corrector _apply_qc_rules crash --")
    
    from app.services.corrector import CorrectorService
    corrector = CorrectorService()
    
    test_data = [{"DC001": "TEST", "DC002": "2024-01-15", "DC005": 100.0}]
    try:
        result_corr = await corrector.auto_correct(test_data)
        print(f"  auto_correct completed: {len(result_corr['corrections'])} corrections")
        print("  OK - No crash (QC rules may be empty or method not reached)")
    except AttributeError as e:
        print(f"  CRASH: AttributeError: {e}")
    except Exception as e:
        print(f"  CRASH: {type(e).__name__}: {e}")
    
    # Check if QC rules exist that would trigger the bug
    qc_rules = config_store.list_qc_rules()
    print(f"  QC rules in DB: {len(qc_rules)}")
    if qc_rules:
        for r in qc_rules[:3]:
            print(f"    rule: search='{r.search_value}' replace='{r.replace_value}' active={r.active}")
        # Check if QCRuleRead has column_range
        attrs = [a for a in dir(qc_rules[0]) if not a.startswith('_')]
        print(f"    QCRuleRead attrs: {attrs}")
        has_col_range = hasattr(qc_rules[0], 'column_range')
        print(f"    Has column_range attr: {has_col_range}")

    # -- Bug 2.4: _standard_names uses alias instead of file_alias --
    print("\n\n-- BUG 2.4: _standard_names uses alias instead of file_alias --")
    
    from app.services.database import get_connection
    conn = get_connection()
    try:
        rules = conn.execute("SELECT * FROM naming_rules LIMIT 5").fetchall()
        naming_rules = [dict(r) for r in rules]
    finally:
        conn.close()
    
    if naming_rules:
        std = _standard_names(naming_rules)
        for alias, fname in list(std.items())[:5]:
            rule = next((r for r in naming_rules if r.get("alias") == alias), {})
            file_alias = rule.get("file_alias", "")
            if alias != file_alias:
                print(f"  BUG: '{alias}' -> '{fname}' (should use file_alias='{file_alias}' -> '{file_alias}.{rule.get('extension', 'xlsx')}')")
            else:
                print(f"  OK: '{alias}' -> '{fname}'")
    else:
        print("  No naming rules in DB -- bug doesn't manifest")

    # -- Bug 1.3+1.4: Export/AutoCorrect use combined data --
    print("\n\n-- BUG 1.3+1.4: Export/AutoCorrect use combined data --")
    print("  Reviewing extract.py source...")
    
    import inspect
    from app.routers import extract as extract_mod
    
    # Check auto_correct
    source = inspect.getsource(extract_mod.auto_correct)
    uses_combined = "result.data" in source and "dc_data" not in source
    print(f"  auto_correct() operates on result.data only: {'BUG CONFIRMED' if uses_combined else 'OK'}")
    
    # Check export
    source_export = inspect.getsource(extract_mod.export_csv)
    uses_combined_exp = "result.data" in source_export and "dc_data" not in source_export
    print(f"  export_csv() operates on result.data only: {'BUG CONFIRMED' if uses_combined_exp else 'OK'}")

    print("\n" + "=" * 70)
    print("DIAGNOSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
