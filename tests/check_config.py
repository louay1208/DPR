"""Check ABIR and ADAM mappings to understand the cell layout."""
import sqlite3

conn = sqlite3.connect("dpr.db")
conn.row_factory = sqlite3.Row

# Find actual concession IDs
for r in conn.execute("SELECT id, name FROM concessions").fetchall():
    if "ABIR" in r["name"] or "ADAM" in r["name"]:
        print(f"ID: {r['id']}, Name: {r['name']}")

print("\n--- ABIR DC mappings ---")
rows = conn.execute(
    "SELECT attribute_code, attribute, cell_ref FROM cell_mappings "
    "WHERE concession_id LIKE '%abir%' AND template_type='DC' ORDER BY sort_order LIMIT 15"
).fetchall()
for r in rows:
    print(f"  {r['attribute_code']:8s} {r['attribute']:40s} cell={r['cell_ref']}")

print("\n--- ABIR DW mappings (first well) ---")
rows = conn.execute(
    "SELECT attribute_code, attribute, cell_ref, well_name FROM cell_mappings "
    "WHERE concession_id LIKE '%abir%' AND template_type='DW' ORDER BY sort_order LIMIT 15"
).fetchall()
for r in rows:
    print(f"  {r['attribute_code']:8s} well={str(r['well_name']):15s} {r['attribute']:40s} cell={r['cell_ref']}")

# Get ABIR's dpr_sheet
r = conn.execute("SELECT dpr_sheet FROM concessions WHERE id LIKE '%abir%'").fetchone()
if r:
    print(f"\nABIR sheet: '{r['dpr_sheet']}'")

conn.close()
