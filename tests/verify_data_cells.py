"""Comprehensive verification of all extracted data cells.

Checks for:
1. Type consistency - every cell value is JSON-serializable
2. Date formatting - ISO strings properly detected, no raw datetime objects
3. Numeric integrity - no NaN, Inf, or string-encoded numbers
4. Column alignment - row keys match declared columns
5. Empty cell handling - null/None/empty consistency
6. Data shape - {rows, cols} contract for frontend
7. Cross-type summary - stats for each data type
"""
# -*- coding: utf-8 -*-

import json
import math
import re
import sys
import io
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.extraction_store import list_extractions, load_extraction


def is_iso_date(val):
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}", str(val)))


def is_ddmmyyyy(val):
    return bool(re.match(r"^\d{2}/\d{2}/\d{4}", str(val)))


def classify_value(val):
    """Classify a cell value into a type category."""
    if val is None:
        return "null"
    if val == "":
        return "empty_string"
    if isinstance(val, bool):
        return "bool"
    if isinstance(val, int):
        return "int"
    if isinstance(val, float):
        if math.isnan(val):
            return "NaN"
        if math.isinf(val):
            return "Inf"
        return "float"
    if isinstance(val, str):
        if is_iso_date(val):
            return "date_iso"
        if is_ddmmyyyy(val):
            return "date_ddmmyyyy"
        # Check for string-encoded numbers
        stripped = val.strip()
        if stripped:
            try:
                float(stripped)
                return "string_number"  # potential issue
            except ValueError:
                pass
        if len(val) > 200:
            return "long_text"
        return "text"
    if isinstance(val, datetime):
        return "raw_datetime"  # PROBLEM
    if isinstance(val, list):
        return "list"  # PROBLEM
    if isinstance(val, dict):
        return "dict"  # PROBLEM
    return f"unknown({type(val).__name__})"


ISSUE_TYPES = {"raw_datetime", "NaN", "Inf", "string_number", "list", "dict"}


def main():
    print("=" * 70)
    print("  DPR Extraction Data Cell Verification")
    print("=" * 70)
    
    extraction_list = list_extractions()
    data = {}
    for e in extraction_list:
        result = load_extraction(e["id"])
        if result:
            data[e["id"]] = result
    if not data:
        print("\n[FAIL] No extraction data found!")
        return 1
    
    total_issues = 0
    total_cells = 0
    
    for eid, result in data.items():
        d = result.model_dump()
        print(f"\n{'-' * 70}")
        print(f"[EXTRACTION] {eid}")
        print(f"  Report type: {d.get('report_type', '?')}")
        print(f"  Created: {d.get('created_at', '?')}")
        print(f"  Status: {d.get('status', '?')}")
        
        for dtype in ["dc", "dw", "mc", "wt"]:
            rows = d.get(f"{dtype}_data", [])
            cols = d.get(f"{dtype}_columns", [])
            
            if not rows and not cols:
                continue
            
            print(f"\n  === {dtype.upper()} ===")
            print(f"  Declared columns ({len(cols)}): {cols}")
            print(f"  Rows: {len(rows)}")
            
            # Track per-column stats
            col_types = defaultdict(Counter)
            col_issues = defaultdict(list)
            type_counter = Counter()
            row_issues = []
            
            for ri, row in enumerate(rows):
                if not isinstance(row, dict):
                    row_issues.append(f"  [WARN] Row {ri}: not a dict, type={type(row).__name__}")
                    total_issues += 1
                    continue
                
                # Check column alignment
                row_keys = set(row.keys())
                col_set = set(cols)
                extra_keys = row_keys - col_set
                
                if extra_keys:
                    row_issues.append(f"  [WARN] Row {ri}: extra keys not in columns: {extra_keys}")
                    total_issues += 1
                
                # Check each cell
                for col in cols:
                    val = row.get(col)
                    vtype = classify_value(val)
                    col_types[col][vtype] += 1
                    type_counter[vtype] += 1
                    total_cells += 1
                    
                    # Flag issues
                    if vtype in ISSUE_TYPES or vtype.startswith("unknown"):
                        col_issues[col].append(f"Row {ri}: {vtype} => {repr(val)[:80]}")
                        total_issues += 1
            
            # Print row-level issues
            for issue in row_issues[:5]:
                print(issue)
            if len(row_issues) > 5:
                print(f"  ... and {len(row_issues) - 5} more row issues")
            
            # Print cell type distribution
            print(f"\n  Cell type distribution:")
            for vtype, count in type_counter.most_common():
                marker = "[ISSUE]" if vtype in ISSUE_TYPES or vtype.startswith("unknown") else "[OK]"
                print(f"    {marker} {vtype}: {count}")
            
            # Print per-column issues
            if col_issues:
                print(f"\n  Column-level issues:")
                for col, issues in col_issues.items():
                    print(f"    {col}: {len(issues)} issue(s)")
                    for issue in issues[:3]:
                        print(f"      -> {issue}")
                    if len(issues) > 3:
                        print(f"      ... and {len(issues) - 3} more")
            
            # Print fill rate per column
            print(f"\n  Fill rates:")
            for col in cols:
                filled = sum(c for t, c in col_types[col].items() if t not in ("null", "empty_string"))
                total = sum(col_types[col].values())
                pct = (filled / total * 100) if total > 0 else 0
                types_str = ", ".join(f"{t}:{c}" for t, c in col_types[col].most_common() if c > 0)
                status = "FULL" if pct == 100 else f"{pct:.0f}%"
                print(f"    {col}: {filled}/{total} ({status}) -- [{types_str}]")
    
    # Final summary
    print(f"\n{'=' * 70}")
    print(f"  SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total extractions: {len(data)}")
    print(f"  Total cells verified: {total_cells}")
    print(f"  Total issues found: {total_issues}")
    
    if total_issues == 0:
        print(f"\n  [PASS] ALL CELLS CLEAN -- No formatting or type issues detected!")
    else:
        print(f"\n  [FAIL] {total_issues} ISSUE(S) FOUND -- see details above")
    
    print(f"{'=' * 70}")
    return total_issues


if __name__ == "__main__":
    issues = main()
    sys.exit(1 if issues else 0)
