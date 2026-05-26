"""
Test extraction pipeline using docs/Abir.xlsx.

This script tests the full extraction flow:
1. Upload the DPR file
2. Run extraction via the API
3. Report results or errors at each step

Usage:
    uv run python tests/test_extraction.py
"""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def main():
    from app.services import config_store
    from app.services.parser import ParserService
    from app.models.schemas import ReportType
    from app.services import cell_reader
    from app.services.database import init_database
    from app.services.logger import LogService

    # Initialize
    LogService.get()
    init_database()

    test_file = PROJECT_ROOT / "docs" / "Abir.xlsx"
    if not test_file.exists():
        print(f"ERROR: Test file not found: {test_file}")
        return

    print(f"Test file: {test_file} ({test_file.stat().st_size:,} bytes)")

    # ── Step 1: Check concession config for Abir ──────────────────
    separator("Step 1: Concession Configuration")

    concessions = config_store.list_concessions()
    print(f"Total concessions: {len(concessions)}")

    # Find Abir concession
    abir_conc = None
    for c in concessions:
        if "abir" in c.name.lower():
            abir_conc = c
            print(f"  Found: id={c.id}, name={c.name}, alias={c.dpr_file_alias}")
            print(f"    active_daily={c.active_daily}, active_monthly={c.active_monthly}")
            print(f"    dc_count={c.dc_count}, dw_count={c.dw_count}, mc_count={c.mc_count}, wt_count={c.wt_count}")
            break

    if not abir_conc:
        print("ERROR: No Abir concession found in database!")
        return

    # Get full detail
    detail = config_store.get_concession(abir_conc.id)
    if detail:
        print(f"  dpr_sheet: {detail.dpr_sheet}")
        print(f"  DC mappings: {len(detail.mappings.dc)}")
        print(f"  DW wells: {len(detail.mappings.dw)}")
        print(f"  MC mappings: {len(detail.mappings.mc)}")
        print(f"  WT mappings: {len(detail.mappings.wt)}")

        # Show first few DC mappings
        print("\n  Sample DC mappings:")
        for m in detail.mappings.dc[:5]:
            print(f"    {m.attribute_code}: ref={m.cell_ref}, unit={m.unit}, attr={m.attribute}")
    else:
        print("ERROR: Could not get concession detail!")
        return

    # ── Step 2: Check naming rules ────────────────────────────────
    separator("Step 2: Naming Rules")

    from app.services.database import get_connection
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM naming_rules WHERE alias LIKE '%Abir%' OR alias LIKE '%ABIR%' OR file_alias LIKE '%Abir%'").fetchall()
        if rows:
            for r in rows:
                d = dict(r)
                print(f"  Rule: alias={d.get('alias')}, file_alias={d.get('file_alias')}, "
                      f"ext={d.get('extension')}, fmt={d.get('date_format')}, "
                      f"left={d.get('left_sep')}, right={d.get('right_sep')}")
        else:
            print("  No specific Abir naming rules found")
            # Show all rules
            all_rules = conn.execute("SELECT alias, file_alias, extension FROM naming_rules ORDER BY id LIMIT 10").fetchall()
            print(f"  First 10 rules:")
            for r in all_rules:
                print(f"    alias={r['alias']}, file_alias={r['file_alias']}, ext={r['extension']}")
    finally:
        conn.close()

    # ── Step 3: Test file name generation ─────────────────────────
    separator("Step 3: Filename Generation")

    parser = ParserService()
    naming_rules = parser._load_naming_rules()
    print(f"  Total naming rules: {len(naming_rules)}")

    from app.services.parser import _auto_generate, _standard_names

    # Test with a date
    test_date = date(2025, 9, 6)
    auto_names = _auto_generate(test_date, naming_rules)
    std_names = _standard_names(naming_rules)

    # Check which key matches Abir
    print(f"\n  Looking for alias matching '{abir_conc.dpr_file_alias}' or '{abir_conc.name}':")
    found_key = None
    for key, fname in auto_names.items():
        if abir_conc.dpr_file_alias and abir_conc.dpr_file_alias in key:
            print(f"    MATCH auto: key='{key}' -> filename='{fname}'")
            found_key = key
        if abir_conc.name and abir_conc.name.lower() in key.lower():
            print(f"    MATCH auto (name): key='{key}' -> filename='{fname}'")
            found_key = key

    if not found_key:
        print(f"  WARNING: No auto-generated name matches alias '{abir_conc.dpr_file_alias}'")
        print(f"  All auto-generated keys: {list(auto_names.keys())[:10]}...")

    # ── Step 4: Test cell_reader with Abir.xlsx directly ──────────
    separator("Step 4: Direct Cell Reading")

    # Try reading some cells from Abir.xlsx
    test_folder = str(test_file.parent)
    test_filename = test_file.name  # "Abir.xlsx"
    test_sheet = detail.dpr_sheet or "Sheet1"

    print(f"  Folder: {test_folder}")
    print(f"  Filename: {test_filename}")
    print(f"  Sheet: {test_sheet}")

    # Try a few DC mappings
    errors = []
    successes = []
    for m in detail.mappings.dc[:10]:
        if not m.cell_ref:
            continue
        try:
            val = cell_reader.resolve_ref(
                m.cell_ref, test_folder, test_filename,
                test_sheet, {abir_conc.dpr_file_alias: test_filename}
            )
            successes.append((m.attribute_code, m.cell_ref, val))
            print(f"  OK  {m.attribute_code} ({m.cell_ref}): {repr(val)}")
        except Exception as e:
            errors.append((m.attribute_code, m.cell_ref, str(e)))
            print(f"  ERR {m.attribute_code} ({m.cell_ref}): {e}")

    print(f"\n  Results: {len(successes)} OK, {len(errors)} errors")

    # ── Step 5: Full extraction test ──────────────────────────────
    separator("Step 5: Full Extraction (Abir only)")

    try:
        result = await parser.extract(
            report_type=ReportType.DAILY,
            dpr_folder=test_folder,
            date_dpr=None,  # No date — use standard names
            auto_name=False,  # Use standard names so "Abir.xlsx" matches
            num_days=1,
            concatenate=False,
            concession_ids=[abir_conc.id],
        )

        print(f"  record_count: {result['record_count']}")
        print(f"  DC rows: {len(result.get('dc_data', []))}")
        print(f"  DW rows: {len(result.get('dw_data', []))}")
        print(f"  columns: {result.get('columns', [])[:10]}...")

        if result.get('dc_data'):
            print(f"\n  First DC row sample:")
            row = result['dc_data'][0]
            for k, v in list(row.items())[:15]:
                print(f"    {k}: {repr(v)}")

        if result.get('dw_data'):
            print(f"\n  First DW row sample:")
            row = result['dw_data'][0]
            for k, v in list(row.items())[:10]:
                print(f"    {k}: {repr(v)}")

    except Exception as e:
        import traceback
        print(f"  EXTRACTION FAILED: {e}")
        traceback.print_exc()

    # Cleanup
    await cell_reader.clear_cache()

    separator("Test Complete")


if __name__ == "__main__":
    asyncio.run(main())
