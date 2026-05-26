"""SQLite database initialization and connection management."""

from __future__ import annotations

import sqlite3
from pathlib import Path
import hashlib
import secrets

from app.config import BASE_DIR


DB_PATH = BASE_DIR / "dpr.db"

# ── Schema ──────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS parameters (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS uom_entries (
    unit        TEXT PRIMARY KEY,
    factor      REAL NOT NULL,
    target_unit TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS concessions (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    dpr_file_alias   TEXT NOT NULL DEFAULT '',
    dpr_sheet        TEXT NOT NULL DEFAULT '',
    active_daily     INTEGER NOT NULL DEFAULT 1,
    active_monthly   INTEGER NOT NULL DEFAULT 1,
    active_well_test INTEGER NOT NULL DEFAULT 1,
    date_format      TEXT NOT NULL DEFAULT 'ddmmyyyy',
    monthly_report   TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cell_mappings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    concession_id  TEXT NOT NULL,
    template_type  TEXT NOT NULL,           -- DC, DW, MC, WT
    well_name      TEXT NOT NULL DEFAULT '',
    ubhi           TEXT NOT NULL DEFAULT '',
    completion     TEXT NOT NULL DEFAULT '',
    attribute_code TEXT NOT NULL,            -- DC001, DW008, etc.
    attribute      TEXT NOT NULL,            -- "Production Gaz en k Sm3"
    cell_ref       TEXT NOT NULL DEFAULT '',  -- "E:22", "B15", etc.
    unit           TEXT NOT NULL DEFAULT '',  -- "sm3", "bbl", etc.
    sort_order     INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (concession_id) REFERENCES concessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mappings_conc
    ON cell_mappings(concession_id, template_type);

CREATE TABLE IF NOT EXISTS qc_rules (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    search_value  TEXT NOT NULL,
    replace_value TEXT NOT NULL DEFAULT '',
    active        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS naming_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    alias       TEXT NOT NULL,
    file_alias  TEXT NOT NULL DEFAULT '',
    extension   TEXT NOT NULL DEFAULT 'xlsx',
    date_format TEXT NOT NULL DEFAULT 'ddmmyyyy',
    left_sep    TEXT NOT NULL DEFAULT '',
    right_sep   TEXT NOT NULL DEFAULT '',
    prefix      TEXT NOT NULL DEFAULT '',
    suffix      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS extractions (
    id            TEXT PRIMARY KEY,
    report_type   TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'completed',
    record_count  INTEGER NOT NULL DEFAULT 0,
    dc_columns    TEXT NOT NULL DEFAULT '[]',
    dw_columns    TEXT NOT NULL DEFAULT '[]',
    mc_columns    TEXT NOT NULL DEFAULT '[]',
    wt_columns    TEXT NOT NULL DEFAULT '[]',
    columns       TEXT NOT NULL DEFAULT '[]',
    dpr_folder    TEXT NOT NULL DEFAULT '',
    label         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS extraction_rows (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    extraction_id  TEXT NOT NULL,
    data_type      TEXT NOT NULL,
    row_index      INTEGER NOT NULL,
    row_data       TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (extraction_id) REFERENCES extractions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_extr_rows
    ON extraction_rows(extraction_id, data_type, row_index);
"""

# ── Default UOM entries (from v2.8 UOM sheet) ──────────────────────────

_DEFAULT_UOM = [
    ("MSCF",     0.0283168,   "ksm3"),
    ("SCF",      2.8317e-05,  "ksm3"),
    ("BBLE",     0.158987,    "m3"),
    ("BBL",      0.158987,    "m3"),
    ("PSI",      6.89475728,  "kPa"),
    ("PSIA",     6.89475728,  "kPa"),
    ("PSIG",     6.89475728,  "kPa"),
    ("BAR",      100.0,       "kPa"),
    ("SM3",      0.001,       "ksm3"),
    ("NM3",      0.001,       "knm3"),
    ("KG/M3",    0.001,       "g/cm3"),
    ("BBLS",     0.158987,    "m3"),
    ("SM3/D",    0.001,       "ksm3"),
    ("BBLS/D",   0.158987,    "m3"),
    ("MSCF/DAY", 2.8317e-05,  "ksm3"),
    ("MMSCF",    28.3168,     "ksm3"),
    ("MSCF_DW",  28.3168,     "sm3"),
    ("BARG",     100.0,       "kPa"),
    ("KSm3_DW",  1000.0,      "sm3"),
]

_DEFAULT_PARAMS = {
    "sm3_to_nm3": "0.947916",
    "nm3_to_sm3": "1.05494579688496",
}


# ── Migrations ──────────────────────────────────────────────────────────
# Each migration is (version, description, sql).
# Migrations are applied in order; already-applied versions are skipped.
# The base schema above creates all tables via CREATE TABLE IF NOT EXISTS,
# so migrations are only needed for ALTER TABLE, new columns, new indices,
# or data transforms on existing databases.

_MIGRATIONS: list[tuple[int, str, str]] = [
    # ── v1: baseline (matches initial CREATE TABLE IF NOT EXISTS) ──
    (1, "baseline schema", ""),
    # ── v2: users table for authentication ──
    (2, "create users table", """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name     TEXT NOT NULL,
            email         TEXT NOT NULL UNIQUE,
            company       TEXT NOT NULL DEFAULT '',
            role          TEXT NOT NULL DEFAULT 'user',
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """),
    # ── v3: user_sessions table for token-based session validation ──
    (3, "create user_sessions table", """
        CREATE TABLE IF NOT EXISTS user_sessions (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """),
]


# ── Connection helpers ──────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """Get a database connection with WAL mode and FK enforcement."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database() -> None:
    """Create tables, run pending migrations, and seed defaults."""
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA)

        # ── Migration tracking table ───────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version     INTEGER PRIMARY KEY,
                description TEXT NOT NULL DEFAULT '',
                applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        _run_migrations(conn)

        # Seed default parameters if empty
        existing = conn.execute("SELECT COUNT(*) FROM parameters").fetchone()[0]
        if existing == 0:
            for key, value in _DEFAULT_PARAMS.items():
                conn.execute(
                    "INSERT OR IGNORE INTO parameters (key, value) VALUES (?, ?)",
                    (key, value),
                )

        # Seed default UOM if empty
        existing = conn.execute("SELECT COUNT(*) FROM uom_entries").fetchone()[0]
        if existing == 0:
            conn.executemany(
                "INSERT OR IGNORE INTO uom_entries (unit, factor, target_unit) VALUES (?, ?, ?)",
                _DEFAULT_UOM,
            )

        # Seed default admin user if empty
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing == 0:
            salt = secrets.token_hex(16)
            pwd_hash = hashlib.pbkdf2_hmac('sha256', b'admin', salt.encode('utf-8'), 100000).hex()
            conn.execute(
                """INSERT INTO users (full_name, email, company, role, password_hash, salt) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ('System Administrator', 'admin@etap.com', 'ETAP', 'admin', pwd_hash, salt)
            )

        conn.commit()
    finally:
        conn.close()


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Apply any pending migrations in order.

    Compares the ``_MIGRATIONS`` list against the ``schema_version``
    table and executes only the migrations whose version number has not
    yet been recorded.
    """
    applied = {
        row[0]
        for row in conn.execute("SELECT version FROM schema_version").fetchall()
    }

    for version, description, sql in _MIGRATIONS:
        if version in applied:
            continue
        if sql.strip():
            conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_version (version, description) VALUES (?, ?)",
            (version, description),
        )

    conn.commit()

