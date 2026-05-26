"""Debug: simulate the exact API extraction call the UI makes."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.database import init_database
from app.services.logger import LogService
init_database()
LogService.get()

async def main():
    from app.services.parser import ParserService, _discover_files
    from app.models.schemas import ReportType

    parser = ParserService()

    # Test 1: Using docs/ folder (has Abir.xlsx) - like the test does
    docs_folder = str(Path(__file__).parent.parent / "docs")
    print(f"=== Test 1: Folder mode with docs/ ===")
    print(f"Folder: {docs_folder}")
    print(f"Folder exists: {Path(docs_folder).exists()}")

    discovered = _discover_files(docs_folder)
    print(f"Discovered files: {discovered}")

    try:
        result = await parser.extract(
            report_type=ReportType.DAILY,
            dpr_folder=docs_folder,
            date_dpr=None,
            auto_name=False,
            num_days=1,
            concatenate=False,
            concession_ids=[],  # all active
        )
        dc = result.get("dc_data", [])
        dw = result.get("dw_data", [])
        print(f"DC rows: {len(dc)}, DW rows: {len(dw)}")
        if dc:
            print(f"DC[0] filled fields: {sum(1 for v in dc[0].values() if v not in ('', None, 0, 0.0))}/{len(dc[0])}")
            for k, v in dc[0].items():
                if v not in ('', None, 0, 0.0):
                    print(f"  {k}: {v!r}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()

    # Test 2: Using the folder the UI is configured with
    print(f"\n=== Test 2: Folder from UI config ===")
    from app.config import get_runtime_config
    runtime = get_runtime_config()
    print(f"DPR folder from config: {runtime.dpr_folder!r}")
    print(f"Exists: {Path(runtime.dpr_folder).exists() if runtime.dpr_folder else 'N/A'}")

    # Test 3: Upload mode simulation
    print(f"\n=== Test 3: Upload folder ===")
    from app.config import UPLOAD_DIR
    print(f"Upload dir: {UPLOAD_DIR}")
    print(f"Exists: {UPLOAD_DIR.exists()}")
    if UPLOAD_DIR.exists():
        files = list(UPLOAD_DIR.iterdir())
        print(f"Files in uploads: {len(files)}")
        for f in files[:5]:
            print(f"  {f.name}")
        discovered_uploads = _discover_files(str(UPLOAD_DIR))
        print(f"Discovered in uploads: {discovered_uploads}")

asyncio.run(main())
