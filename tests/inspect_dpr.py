"""List active daily concessions and their mappings."""
import urllib.request, json

r = urllib.request.urlopen("http://localhost:8000/api/concessions").read()
data = json.loads(r)
if isinstance(data, dict):
    data = data.get("data", data)
active = [c for c in data if c.get("active_daily")]
print(f"Active daily concessions: {len(active)}")
for c in active:
    print(f"  {c['name']:30s} alias=[{c.get('dpr_file_alias',''):15s}] DC={c.get('dc_count',0)} DW={c.get('dw_count',0)}")
