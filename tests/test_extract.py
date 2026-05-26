"""Quick extraction test selecting specific concessions with files."""
import urllib.request, json

body = json.dumps({
    "report_type": "daily",
    "dpr_folder": r"c:\Users\louay\Documents\FreeLance\DPR\docs\dpr",
    "auto_detect_name": False,
    "num_days": 1,
    "concession_ids": ["abir_new", "cherouq_test", "jebel_grouz_test", "ksar_hadada_test", "sidi_marzoug_test"],
}).encode()

req = urllib.request.Request("http://localhost:8000/api/extract", body, method="POST")
req.add_header("Content-Type", "application/json")
r = json.loads(urllib.request.urlopen(req).read())

print(f"Extraction {r['id']}: DC={len(r['dc_data'])}, DW={len(r['dw_data'])}, total={r['record_count']}")
print()
for i, dc in enumerate(r['dc_data']):
    name = dc.get('DC001', '?')
    oil = dc.get('DC028', '-')
    gas = dc.get('DC005', '-')
    date = dc.get('DC002', '-')
    print(f"  DC[{i}] {name:20s} date={str(date):20s} oil={oil}, gas={gas}")

print()
for i, dw in enumerate(r['dw_data'][:8]):
    well = dw.get('DW002', dw.get('DW001', '?'))
    oil = dw.get('DW010', '-')
    gas = dw.get('DW008', '-')
    print(f"  DW[{i}] {str(well):20s} oil={oil}, gas={gas}")
