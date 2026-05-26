"""Quick API test for dashboard fixes."""
import urllib.request
import json

r = urllib.request.urlopen('http://localhost:8000/api/dashboard/insights')
d = json.loads(r.read())
ps = d['production_summary']
ws = d.get('well_summary', [])

print(f"gas={ps['gas']} oil={ps['oil']} water={ps['water']} records={ps['records']}")
print(f"wells: {len(ws)}")
for w in ws[:8]:
    print(f"  {str(w['well'])[:25]:25s} conc={str(w['concession'])[:15]:15s} gas={w['gas']:>10.2f} wc={w['water_cut']:>5.1f}%")
