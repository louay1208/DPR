"""Application lifecycle events (startup / shutdown)."""

from app.config import UPLOAD_DIR, EXPORT_DIR, MAPPING_DIR, LOG_DIR, DOCS_DIR, get_runtime_config
from app.services.database import init_database
from app.services.logger import LogService


async def on_startup() -> None:
    """Run once when the application starts."""
    for d in (UPLOAD_DIR, EXPORT_DIR, MAPPING_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)

    logger = LogService.get()

    # ── Initialize SQLite database ─────────────────────────────────
    init_database()
    await logger.info("SQLite database initialized", source="startup")

    # ── Auto-import on first run ───────────────────────────────────
    from app.services import config_store
    stats = config_store.get_stats()

    if stats.concessions == 0:
        await logger.info(
            "No concessions found — checking docs/ for importable files",
            source="startup",
        )
        from app.services import importer

        # Try importing moulinette first
        for pattern in ["PMS_Loader*.xlsm", "PMS_Loader*.xlsx"]:
            for path in DOCS_DIR.glob(pattern):
                try:
                    result = await importer.import_moulinette(path)
                    await logger.success(
                        f"Auto-imported {result.concessions_imported} concessions from {path.name}",
                        source="startup",
                    )
                    break  # Only import the first one found
                except Exception as e:
                    await logger.error(
                        f"Failed to auto-import moulinette: {e}", source="startup"
                    )

        # Then import any mapping files
        for path in sorted(DOCS_DIR.glob("Mapping_*.xlsx")):
            try:
                result = await importer.import_mapping_file(path)
                await logger.success(
                    f"Auto-imported {result.mappings_imported} mappings from {path.name}",
                    source="startup",
                )
            except Exception as e:
                await logger.error(
                    f"Failed to auto-import mapping {path.name}: {e}", source="startup"
                )

    # ── Load runtime config from DB ────────────────────────────────
    runtime = get_runtime_config()
    params = config_store.get_all_parameters()
    runtime.sm3_to_nm3 = float(params.get("sm3_to_nm3", "0.947916"))
    runtime.nm3_to_sm3 = float(params.get("nm3_to_sm3", "1.05494579688496"))
    runtime.dpr_folder = params.get("dpr_path", "")
    runtime.output_folder = params.get("output_path", str(EXPORT_DIR))

    stats = config_store.get_stats()
    await logger.success(
        f"Config ready: {stats.concessions} concessions, "
        f"{stats.total_mappings} mappings, {stats.uom_entries} UOM entries",
        source="startup",
    )

    # ── Extraction data is now lazy-loaded ──────────────────────────
    # Extractions are loaded from DB on first access via _resolve_extraction()
    # in the extract router, preventing unbounded memory growth at startup.
    from app.services import extraction_store
    ext_count = len(extraction_store.list_extractions())
    if ext_count:
        await logger.info(
            f"{ext_count} saved extraction(s) available in database (lazy-loaded on access)",
            source="startup",
        )


async def on_shutdown() -> None:
    """Run once when the application stops."""
    from app.services import cell_reader
    await cell_reader.clear_cache()
