"""Application configuration."""

from pathlib import Path


# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

UPLOAD_DIR = BASE_DIR / "uploads"
EXPORT_DIR = Path.home() / "Documents" / "DPR_Exports"
MAPPING_DIR = BASE_DIR / "mappings"
LOG_DIR = BASE_DIR / "logs"
STATIC_DIR = BASE_DIR / "static"
DOCS_DIR = BASE_DIR / "docs"

# Ensure directories exist
for d in (UPLOAD_DIR, EXPORT_DIR, MAPPING_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)


# ── Application Settings ──────────────────────────────────────────────
APP_TITLE = "DPR — Production Data Manager"
APP_VERSION = "1.0.0"

# Maximum upload size (100 MB)
MAX_UPLOAD_SIZE = 100 * 1024 * 1024

# Supported file extensions for DPR uploads
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".csv"}

# Report types supported by the extraction engine
REPORT_TYPES = ["daily", "monthly", "dc", "dw", "well_test"]


# ── Moulinette Settings ───────────────────────────────────────────────
# Default path to the PMS_Loader moulinette workbook
MOULINETTE_PATH = DOCS_DIR / "PMS_Loader_v2.8 (1).xlsm"

# SM3 <-> NM3 conversion defaults (overridden by moulinette Parameters)
SM3_TO_NM3 = 0.947916
NM3_TO_SM3 = 1.05494579688496

# Month number -> Excel column letter (for monthly extraction)
MONTH_TO_COLUMN = {
    1: "B", 2: "C", 3: "D", 4: "E", 5: "F", 6: "G",
    7: "H", 8: "I", 9: "J", 10: "K", 11: "L", 12: "M",
}


# ── User-configurable paths (set from UI) ─────────────────────────────
class RuntimeConfig:
    """Mutable runtime configuration set by the user via the UI.

    On first access, folder paths are restored from the SQLite
    ``parameters`` table so they survive server restarts.
    """

    def __init__(self) -> None:
        self.dpr_folder: str = ""
        self.output_folder: str = str(EXPORT_DIR)  # always defaults to <project>/exports/
        self.sm3_to_nm3: float = SM3_TO_NM3
        self.nm3_to_sm3: float = NM3_TO_SM3
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy-load persisted paths from SQLite (avoids import cycles).

        If a stored path is invalid on this machine (e.g. different device),
        it falls back to the project-local defaults silently.
        """
        if self._loaded:
            return
        self._loaded = True
        try:
            from app.services.database import get_connection
            conn = get_connection()
            try:
                rows = conn.execute("SELECT key, value FROM parameters").fetchall()
                params = {r["key"]: r["value"] for r in rows}

                # DPR folder — only use if path is valid
                if params.get("dpr_folder"):
                    p = Path(params["dpr_folder"])
                    if p.exists():
                        self.dpr_folder = params["dpr_folder"]

                # Output folder — validate, try to create, or fall back
                if params.get("output_folder"):
                    try:
                        p = Path(params["output_folder"])
                        p.mkdir(parents=True, exist_ok=True)
                        self.output_folder = params["output_folder"]
                    except (OSError, PermissionError):
                        # Path invalid on this machine — keep default
                        pass

                if params.get("sm3_to_nm3"):
                    self.sm3_to_nm3 = float(params["sm3_to_nm3"])
                if params.get("nm3_to_sm3"):
                    self.nm3_to_sm3 = float(params["nm3_to_sm3"])
            finally:
                conn.close()
        except Exception:
            pass  # DB may not be initialized yet


# Singleton runtime config
_runtime = RuntimeConfig()


def get_runtime_config() -> RuntimeConfig:
    _runtime._ensure_loaded()
    return _runtime
