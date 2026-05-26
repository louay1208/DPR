"""
Deep extraction test — covers all report types, cell ref types,
edge cases, and data integrity checks using docs/Abir.xlsx.

Usage:  uv run python tests/test_extraction_deep.py
"""

import asyncio
import sys
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PASS = 0
FAIL = 0
WARN = 0

def ok(msg): global PASS; PASS += 1; print(f"  [OK] {msg}")
def fail(msg): global FAIL; FAIL += 1; print(f"  [FAIL] {msg}")
def warn(msg): global WARN; WARN += 1; print(f"  [WARN] {msg}")
def sep(title): print(f"\n{'='*60}\n  {title}\n{'='*60}")


async def main():
    from app.services import config_store, cell_reader
    from app.services.parser import ParserService, _auto_generate, _standard_names
    from app.services.database import init_database, get_connection
    from app.services.logger import LogService
    from app.models.schemas import ReportType

    LogService.get()
    init_database()

    test_file = PROJECT_ROOT / "docs" / "Abir.xlsx"
    test_folder = str(test_file.parent)
    test_filename = test_file.name

    detail = config_store.get_concession("abir_new")
    if not detail:
        fail("Could not load Abir concession"); return

    parser = ParserService()

    # ════════════════════════════════════════════════════════════
    #  TEST 1: Cell Reader — All DC mappings
    # ════════════════════════════════════════════════════════════
    sep("Test 1: Cell Reader — All 52 DC Mappings")

    dpr_list = {"Abir": test_filename}
    sheet = detail.dpr_sheet  # "ABIR Concession"
    empty_count = 0
    read_count = 0
    errors = []

    for m in detail.mappings.dc:
        if not m.cell_ref:
            continue
        try:
            val = cell_reader.resolve_ref(m.cell_ref, test_folder, test_filename, sheet, dpr_list)
            read_count += 1
            if val == "" or val is None or val == 0 or val == 0.0:
                empty_count += 1
        except Exception as e:
            errors.append((m.attribute_code, m.cell_ref, str(e)))

    if errors:
        fail(f"{len(errors)} cell read errors:")
        for code, ref, err in errors:
            print(f"      {code} ({ref}): {err}")
    else:
        ok(f"All {read_count} DC cells read without errors")

    if empty_count > 0:
        warn(f"{empty_count}/{read_count} DC cells returned empty/zero (may be normal for test file)")

    # ════════════════════════════════════════════════════════════
    #  TEST 2: Cell Reader — DW Mappings (Well-level)
    # ════════════════════════════════════════════════════════════
    sep("Test 2: Cell Reader — DW Mappings")

    dw_read = 0
    dw_empty = 0
    dw_errors = []

    for well in detail.mappings.dw:
        for m in well.fields:
            if not m.cell_ref:
                continue
            try:
                val = cell_reader.resolve_ref(m.cell_ref, test_folder, test_filename, sheet, dpr_list)
                dw_read += 1
                if val == "" or val is None or val == 0 or val == 0.0:
                    dw_empty += 1
            except Exception as e:
                dw_errors.append((well.well_name, m.attribute_code, m.cell_ref, str(e)))

    if dw_errors:
        fail(f"{len(dw_errors)} DW cell errors:")
        for wn, code, ref, err in dw_errors:
            print(f"      Well {wn} / {code} ({ref}): {err}")
    else:
        ok(f"All {dw_read} DW cells read without errors ({len(detail.mappings.dw)} wells)")
    if dw_empty > 0:
        warn(f"{dw_empty}/{dw_read} DW cells returned empty/zero")

    # ════════════════════════════════════════════════════════════
    #  TEST 3: Cell Reader — MC Mappings (Monthly)
    # ════════════════════════════════════════════════════════════
    sep("Test 3: Cell Reader — MC Mappings")

    mc_read = 0
    mc_empty = 0
    mc_errors = []

    for m in detail.mappings.mc:
        if not m.cell_ref:
            continue
        try:
            val = cell_reader.resolve_ref(m.cell_ref, test_folder, test_filename, sheet, dpr_list)
            mc_read += 1
            if val == "" or val is None or val == 0 or val == 0.0:
                mc_empty += 1
        except Exception as e:
            mc_errors.append((m.attribute_code, m.cell_ref, str(e)))

    if mc_errors:
        fail(f"{len(mc_errors)} MC cell errors:")
        for code, ref, err in mc_errors:
            print(f"      {code} ({ref}): {err}")
    else:
        ok(f"All {mc_read} MC cells read without errors")

    # ════════════════════════════════════════════════════════════
    #  TEST 4: Cell Reader — WT Mappings (Well Test)
    # ════════════════════════════════════════════════════════════
    sep("Test 4: Cell Reader — WT Mappings")

    wt_read = 0
    wt_empty = 0
    wt_errors = []

    for well in detail.mappings.wt:
        for m in well.fields:
            if not m.cell_ref:
                continue
            try:
                val = cell_reader.resolve_ref(m.cell_ref, test_folder, test_filename, sheet, dpr_list)
                wt_read += 1
                if val == "" or val is None or val == 0 or val == 0.0:
                    wt_empty += 1
            except Exception as e:
                wt_errors.append((well.well_name, m.attribute_code, m.cell_ref, str(e)))

    if wt_errors:
        fail(f"{len(wt_errors)} WT cell errors:")
        for wn, code, ref, err in wt_errors:
            print(f"      Well {wn} / {code} ({ref}): {err}")
    else:
        ok(f"All {wt_read} WT cells read without errors ({len(detail.mappings.wt)} wells)")

    # ════════════════════════════════════════════════════════════
    #  TEST 5: Calculated References (?B15+B16)
    # ════════════════════════════════════════════════════════════
    sep("Test 5: Calculated Cell References")

    # Find all calculated refs in all mappings
    calc_refs = []
    for m in detail.mappings.dc:
        if m.cell_ref and m.cell_ref.startswith("?"):
            calc_refs.append(("DC", m.attribute_code, m.cell_ref))
    for well in detail.mappings.dw:
        for m in well.fields:
            if m.cell_ref and m.cell_ref.startswith("?"):
                calc_refs.append(("DW", m.attribute_code, m.cell_ref))
    for m in detail.mappings.mc:
        if m.cell_ref and m.cell_ref.startswith("?"):
            calc_refs.append(("MC", m.attribute_code, m.cell_ref))
    for well in detail.mappings.wt:
        for m in well.fields:
            if m.cell_ref and m.cell_ref.startswith("?"):
                calc_refs.append(("WT", m.attribute_code, m.cell_ref))

    print(f"  Found {len(calc_refs)} calculated references")
    calc_errors = []
    for rtype, code, ref in calc_refs:
        try:
            val = cell_reader.resolve_ref(ref, test_folder, test_filename, sheet, dpr_list)
            print(f"    {rtype}/{code} ({ref}): {repr(val)}")
        except Exception as e:
            calc_errors.append((rtype, code, ref, str(e)))
            print(f"    ERR {rtype}/{code} ({ref}): {e}")

    if calc_errors:
        fail(f"{len(calc_errors)} calculated ref errors")
    elif calc_refs:
        ok(f"All {len(calc_refs)} calculated refs resolved")
    else:
        warn("No calculated references found in Abir mappings")

    # ════════════════════════════════════════════════════════════
    #  TEST 6: Multi-file References (![alias/sheet]ref)
    # ════════════════════════════════════════════════════════════
    sep("Test 6: Multi-file Cell References")

    multi_refs = []
    for m in detail.mappings.dc:
        if m.cell_ref and m.cell_ref.startswith("!"):
            multi_refs.append(("DC", m.attribute_code, m.cell_ref))
    for well in detail.mappings.dw:
        for m in well.fields:
            if m.cell_ref and m.cell_ref.startswith("!"):
                multi_refs.append(("DW", m.attribute_code, m.cell_ref))

    print(f"  Found {len(multi_refs)} multi-file references")
    if multi_refs:
        for rtype, code, ref in multi_refs[:5]:
            try:
                val = cell_reader.resolve_ref(ref, test_folder, test_filename, sheet, dpr_list)
                print(f"    {rtype}/{code} ({ref[:40]}...): {repr(val)}")
            except Exception as e:
                print(f"    ERR {rtype}/{code}: {e}")
    else:
        ok("No multi-file references in Abir (expected)")

    # ════════════════════════════════════════════════════════════
    #  TEST 7: Full Daily Extraction
    # ════════════════════════════════════════════════════════════
    sep("Test 7: Full Daily Extraction")

    try:
        result = await parser.extract(
            report_type=ReportType.DAILY,
            dpr_folder=test_folder,
            date_dpr=None,
            auto_name=False,
            num_days=1,
            concatenate=False,
            concession_ids=["abir_new"],
        )

        dc = result.get("dc_data", [])
        dw = result.get("dw_data", [])

        if len(dc) > 0:
            ok(f"DC extraction: {len(dc)} rows, {len(dc[0])} columns")
        else:
            fail("DC extraction returned 0 rows")

        if len(dw) > 0:
            ok(f"DW extraction: {len(dw)} rows, {len(dw[0])} columns")
        else:
            fail("DW extraction returned 0 rows")

        # Validate DC data integrity
        if dc:
            row = dc[0]
            # DC001 should be concession name
            if row.get("DC001") == "ABIR NEW":
                ok("DC001 = concession name (ABIR NEW)")
            else:
                fail(f"DC001 = {repr(row.get('DC001'))}, expected 'ABIR NEW'")

            # DC002 should be a date
            dc002 = row.get("DC002")
            if isinstance(dc002, datetime):
                ok(f"DC002 = date ({dc002})")
            elif dc002:
                warn(f"DC002 = {repr(dc002)} (not a datetime)")
            else:
                fail("DC002 is empty (should be date)")

            # DC005 should be numeric (production)
            dc005 = row.get("DC005")
            if dc005 is not None and dc005 != "":
                try:
                    float(dc005)
                    ok(f"DC005 = numeric ({dc005})")
                except (ValueError, TypeError):
                    warn(f"DC005 = non-numeric ({repr(dc005)})")
            else:
                warn("DC005 is empty")

        # Validate DW data integrity
        if dw:
            row = dw[0]
            if row.get("DW001") == "ABIR NEW":
                ok("DW001 = concession name")
            else:
                fail(f"DW001 = {repr(row.get('DW001'))}")

    except Exception as e:
        fail(f"Daily extraction failed: {e}")
        traceback.print_exc()

    # ════════════════════════════════════════════════════════════
    #  TEST 8: Full Monthly Extraction
    # ════════════════════════════════════════════════════════════
    sep("Test 8: Full Monthly Extraction")

    try:
        result = await parser.extract(
            report_type=ReportType.MONTHLY,
            dpr_folder=test_folder,
            date_dpr=date(2021, 5, 26),
            auto_name=False,
            num_days=1,
            concession_ids=["abir_new"],
        )

        mc = result.get("mc_data", [])
        if len(mc) > 0:
            ok(f"MC extraction: {len(mc)} rows, {len(mc[0])} columns")
            # Show sample
            row = mc[0]
            for k, v in list(row.items())[:5]:
                print(f"      {k}: {repr(v)}")
        else:
            fail("MC extraction returned 0 rows")

    except Exception as e:
        fail(f"Monthly extraction failed: {e}")
        traceback.print_exc()

    # ════════════════════════════════════════════════════════════
    #  TEST 9: Full Well Test Extraction
    # ════════════════════════════════════════════════════════════
    sep("Test 9: Full Well Test Extraction")

    try:
        result = await parser.extract(
            report_type=ReportType.WELL_TEST,
            dpr_folder=test_folder,
            date_dpr=None,
            auto_name=False,
            num_days=1,
            concession_ids=["abir_new"],
        )

        wt = result.get("wt_data", [])
        if len(wt) > 0:
            ok(f"WT extraction: {len(wt)} rows, {len(wt[0])} columns")
            row = wt[0]
            for k, v in list(row.items())[:5]:
                print(f"      {k}: {repr(v)}")
        else:
            fail("WT extraction returned 0 rows")

    except Exception as e:
        fail(f"Well Test extraction failed: {e}")
        traceback.print_exc()

    # ════════════════════════════════════════════════════════════
    #  TEST 10: Date-based Naming
    # ════════════════════════════════════════════════════════════
    sep("Test 10: Date-based Naming & Auto-detection")

    naming_rules = parser._load_naming_rules()

    # Test multiple date formats
    for dt in [date(2021, 5, 26), date(2025, 1, 15), date(2024, 12, 31)]:
        auto = _auto_generate(dt, naming_rules)
        abir_name = auto.get("Abir", "NOT FOUND")
        print(f"  Date {dt} -> Abir filename: {abir_name}")

    std = _standard_names(naming_rules)
    abir_std = std.get("Abir", "NOT FOUND")
    print(f"  Standard -> Abir filename: {abir_std}")

    if "Abir" in std and std["Abir"] == "Abir.xlsx":
        ok("Standard Abir name = Abir.xlsx")
    else:
        fail(f"Standard Abir name = {abir_std}")

    # ════════════════════════════════════════════════════════════
    #  TEST 11: Data Types & Serialization
    # ════════════════════════════════════════════════════════════
    sep("Test 11: Data Types & JSON Serialization")

    try:
        result = await parser.extract(
            report_type=ReportType.DAILY,
            dpr_folder=test_folder,
            date_dpr=None,
            auto_name=False,
            num_days=1,
            concession_ids=["abir_new"],
        )

        import json

        dc = result.get("dc_data", [])
        if dc:
            row = dc[0]
            # Check for types that won't serialize to JSON
            bad_types = {}
            for k, v in row.items():
                if v is not None and not isinstance(v, (str, int, float, bool)):
                    bad_types[k] = f"{type(v).__name__}: {repr(v)}"

            if bad_types:
                fail(f"{len(bad_types)} fields have non-JSON-serializable types:")
                for k, v in bad_types.items():
                    print(f"      {k}: {v}")
            else:
                ok("All DC fields are JSON-serializable")

            # Try actual JSON serialization
            try:
                json.dumps(dc, default=str)
                ok("DC data serializes to JSON (with default=str fallback)")
            except Exception as e:
                fail(f"DC JSON serialization failed: {e}")

        dw = result.get("dw_data", [])
        if dw:
            bad_types = {}
            for k, v in dw[0].items():
                if v is not None and not isinstance(v, (str, int, float, bool)):
                    bad_types[k] = f"{type(v).__name__}: {repr(v)}"

            if bad_types:
                fail(f"{len(bad_types)} DW fields have non-JSON types:")
                for k, v in bad_types.items():
                    print(f"      {k}: {v}")
            else:
                ok("All DW fields are JSON-serializable")

    except Exception as e:
        fail(f"Serialization test failed: {e}")
        traceback.print_exc()

    # ════════════════════════════════════════════════════════════
    #  TEST 12: UOM Conversion Integrity
    # ════════════════════════════════════════════════════════════
    sep("Test 12: UOM Conversions")

    uom_map = parser._load_uom_map()
    print(f"  UOM entries: {len(uom_map)}")
    for unit, factor in list(uom_map.items())[:5]:
        print(f"    {unit}: {factor}")

    # Check that sm3 conversion is applied correctly
    sm3_fields = [m for m in detail.mappings.dc if m.unit and m.unit.lower() == "sm3"]
    print(f"  DC fields with unit 'sm3': {len(sm3_fields)}")
    for m in sm3_fields[:3]:
        raw = cell_reader.resolve_ref(m.cell_ref, test_folder, test_filename, sheet, dpr_list)
        factor = uom_map.get("SM3", 1)
        if raw and raw != "":
            try:
                converted = float(raw) * factor
                print(f"    {m.attribute_code}: raw={raw}, factor={factor}, converted={converted}")
            except:
                print(f"    {m.attribute_code}: raw={repr(raw)} (not numeric)")

    # ════════════════════════════════════════════════════════════
    #  TEST 13: ExtractionResult Schema Build
    # ════════════════════════════════════════════════════════════
    sep("Test 13: ExtractionResult Schema")

    from app.models.schemas import ExtractionResult, ProcessingStatus
    import uuid

    try:
        result = await parser.extract(
            report_type=ReportType.DAILY,
            dpr_folder=test_folder,
            date_dpr=None,
            auto_name=False,
            num_days=1,
            concession_ids=["abir_new"],
        )

        dc_data = result.get("dc_data", [])
        dw_data = result.get("dw_data", [])

        extraction = ExtractionResult(
            id=uuid.uuid4().hex[:12],
            report_type=ReportType.DAILY,
            status=ProcessingStatus.COMPLETED,
            record_count=result["record_count"],
            columns=result["columns"],
            data=result["data"],
            dc_data=dc_data,
            dw_data=dw_data,
            mc_data=[],
            wt_data=[],
            dc_columns=list(dc_data[0].keys()) if dc_data else [],
            dw_columns=list(dw_data[0].keys()) if dw_data else [],
            mc_columns=[],
            wt_columns=[],
        )

        ok(f"ExtractionResult built: id={extraction.id}, records={extraction.record_count}")

        # Test JSON serialization of the full model
        try:
            json_str = extraction.model_dump_json()
            ok(f"ExtractionResult serializes to JSON ({len(json_str)} bytes)")
        except Exception as e:
            fail(f"ExtractionResult JSON serialization failed: {e}")
            traceback.print_exc()

    except Exception as e:
        fail(f"ExtractionResult build failed: {e}")
        traceback.print_exc()

    # Cleanup
    await cell_reader.clear_cache()

    # ════════════════════════════════════════════════════════════
    #  SUMMARY
    # ════════════════════════════════════════════════════════════
    sep("SUMMARY")
    print(f"  PASS: {PASS}")
    print(f"  FAIL: {FAIL}")
    print(f"  WARN: {WARN}")
    print()
    if FAIL == 0:
        print("  ALL TESTS PASSED!")
    else:
        print(f"  {FAIL} TEST(S) FAILED -- needs fixing")


if __name__ == "__main__":
    asyncio.run(main())
