"""Deep investigation of why extracted values are empty even for matched files."""

import asyncio
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from pathlib import Path
from app.services import config_store, cell_reader
from app.services.parser import _discover_files, _standard_names, _auto_generate


async def main():
    docs_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    
    print("=" * 70)
    print("DEEP VALUE EXTRACTION DEBUG")
    print("=" * 70)
    
    # 1. What files are discovered?
    discovered = _discover_files(docs_folder)
    print(f"\nDiscovered files: {discovered}")
    
    # 2. What naming rules exist and what do they generate?
    from app.services.database import get_connection
    conn = get_connection()
    rules = [dict(r) for r in conn.execute("SELECT * FROM naming_rules").fetchall()]
    conn.close()
    
    auto = _auto_generate(date(2024, 1, 15), rules)
    print(f"\nAuto-generated filenames for 2024-01-15:")
    for alias, fname in auto.items():
        print(f"  '{alias}' -> '{fname}'")
    
    std = _standard_names(rules)
    print(f"\nStandard filenames:")
    for alias, fname in std.items():
        print(f"  '{alias}' -> '{fname}'")
    
    # 3. What does the ABIR concession look like?
    concessions = config_store.list_concessions()
    abir = [c for c in concessions if "ABIR" in c.name.upper()]
    if abir:
        c = abir[0]
        print(f"\nABIR concession: name='{c.name}', alias='{c.dpr_file_alias}'")
        
        detail = config_store.get_concession(c.id)
        if detail:
            print(f"  DPR sheet: '{detail.dpr_sheet}'")
            print(f"  DC mappings: {len(detail.mappings.dc)}")
            for m in detail.mappings.dc[:5]:
                print(f"    {m.attribute_code}: cell_ref='{m.cell_ref}', unit='{m.unit}'")
            
            # 4. Try to resolve the DPR name
            # Merge auto_generate + discovered
            dpr_list = {**auto, **{k: v for k, v in discovered.items() if k not in auto}}
            dpr_name = dpr_list.get(c.dpr_file_alias, "")
            if not dpr_name:
                dpr_name = dpr_list.get(c.name, "")
            print(f"\n  Resolved DPR name: '{dpr_name}'")
            
            # 5. Check if the file exists
            if dpr_name:
                full_path = Path(docs_folder) / dpr_name
                print(f"  Full path: '{full_path}'")
                print(f"  File exists: {full_path.exists()}")
                
                if not full_path.exists():
                    # List what's actually in the folder
                    print(f"\n  Files in {docs_folder}:")
                    for f in Path(docs_folder).iterdir():
                        print(f"    {f.name} ({f.stat().st_size} bytes)")
                
                # 6. Try reading a cell directly
                if full_path.exists():
                    print(f"\n  Attempting direct cell read from '{dpr_name}', sheet='{detail.dpr_sheet}'...")
                    for m in detail.mappings.dc[:3]:
                        if m.cell_ref:
                            val = cell_reader.resolve_ref(
                                m.cell_ref, docs_folder, dpr_name,
                                detail.dpr_sheet, dpr_list
                            )
                            print(f"    {m.attribute_code} ({m.cell_ref}): raw value = '{val}' (type={type(val).__name__})")
                else:
                    # The auto-generated name doesn't match the actual filename
                    # Let's try with the discovered name
                    discovered_name = discovered.get(c.dpr_file_alias, "")
                    if not discovered_name:
                        discovered_name = discovered.get("Abir", "")
                    print(f"\n  Auto-generated name doesn't exist. Discovered name: '{discovered_name}'")
                    if discovered_name:
                        full_path2 = Path(docs_folder) / discovered_name
                        print(f"  Discovered path exists: {full_path2.exists()}")
                        if full_path2.exists():
                            print(f"  Trying cell read with discovered name...")
                            for m in detail.mappings.dc[:3]:
                                if m.cell_ref:
                                    val = cell_reader.resolve_ref(
                                        m.cell_ref, docs_folder, discovered_name,
                                        detail.dpr_sheet, dpr_list
                                    )
                                    print(f"    {m.attribute_code} ({m.cell_ref}): raw value = '{val}' (type={type(val).__name__})")
    
    # 7. Check which concessions have empty alias
    print("\n\nConcessions with empty dpr_file_alias:")
    for c in concessions:
        if not c.dpr_file_alias:
            print(f"  '{c.name}' (active_daily={c.active_daily})")

    await cell_reader.clear_cache()


if __name__ == "__main__":
    asyncio.run(main())
