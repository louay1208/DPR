"""Quick debug script to inspect concession config."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services import config_store
from app.services.database import init_database, get_connection
init_database()

# Check what concessions are active for daily
concs = config_store.list_concessions()
active = [c for c in concs if c.active_daily]
print(f"Total: {len(concs)}, Active Daily: {len(active)}")
for c in active:
    alias = c.dpr_file_alias or ""
    print(f"  {c.name} | alias={alias!r} | DC={c.dc_count} DW={c.dw_count}")

# Check naming rules
conn = get_connection()
rules = conn.execute("SELECT alias, file_alias, extension, date_format FROM naming_rules ORDER BY alias").fetchall()
conn.close()
print(f"\nNaming rules: {len(rules)}")
for r in rules[:10]:
    print(f"  alias={r['alias']!r} file_alias={r['file_alias']!r} ext={r['extension']}")

# Check Abir detail
detail = config_store.get_concession("abir_new")
if detail:
    print(f"\n--- ABIR NEW ---")
    print(f"Sheet: {detail.dpr_sheet!r}")
    print(f"Alias: {detail.dpr_file_alias!r}")
    print(f"DC mappings: {len(detail.mappings.dc)}")
    for m in detail.mappings.dc[:5]:
        print(f"  {m.attribute_code}: ref={m.cell_ref!r} unit={m.unit!r}")
    print(f"DW wells: {len(detail.mappings.dw)}")
    for w in detail.mappings.dw[:2]:
        print(f"  Well: {w.well_name!r} ubhi={w.ubhi!r} fields={len(w.fields)}")
        for f in w.fields[:3]:
            print(f"    {f.attribute_code}: ref={f.cell_ref!r}")

# Check what file discovery would find in docs/
from app.services.parser import _discover_files, _standard_names, _auto_generate
docs_folder = str(Path(__file__).parent.parent / "docs")
discovered = _discover_files(docs_folder)
print(f"\nDiscovered files in docs/: {len(discovered)}")
for alias, fname in sorted(discovered.items()):
    print(f"  {alias!r} -> {fname}")

# Check standard names
rules_dicts = [dict(r) for r in get_connection().execute("SELECT * FROM naming_rules").fetchall()]
std = _standard_names(rules_dicts)
print(f"\nStandard names (from naming rules): {len(std)}")
for alias, fname in sorted(list(std.items()))[:10]:
    print(f"  {alias!r} -> {fname}")

# Test: does "Abir" match dpr_file_alias?
print(f"\nAbir alias match test:")
print(f"  dpr_file_alias = {detail.dpr_file_alias!r}")
print(f"  'Abir' in discovered: {'Abir' in discovered}")
print(f"  'Abir' in std: {'Abir' in std}")
print(f"  alias in discovered: {detail.dpr_file_alias in discovered}")
print(f"  alias in std: {detail.dpr_file_alias in std}")
