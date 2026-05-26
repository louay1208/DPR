"""Check well names in all concessions."""
from app.services import config_store

for conc in config_store.list_concessions():
    d = config_store.get_concession(conc.id)
    if not d or not d.mappings.dw:
        continue
    print(f"\n{conc.name} ({len(d.mappings.dw)} wells):")
    for w in d.mappings.dw:
        print(f"  well_name={w.well_name!r:25s} ubhi={w.ubhi!r:15s}")
