"""Configuration store — CRUD operations backed by SQLite.

Replaces the moulinette + mapping file system with app-managed persistence.
"""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from typing import Any

from app.models.config_models import (
    CellMapping,
    ConcessionCreate,
    ConcessionDetail,
    ConcessionMappings,
    ConcessionRead,
    ConcessionUpdate,
    ConfigStats,
    QCRuleCreate,
    QCRuleRead,
    UOMEntryCreate,
    UOMEntryRead,
    WellMapping,
)
from app.services.database import DB_PATH, get_connection


def _slugify(name: str) -> str:
    """Generate a URL-safe ID from a concession name."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


# ═══════════════════════════════════════════════════════════════════════
# Concessions
# ═══════════════════════════════════════════════════════════════════════

def list_concessions() -> list[ConcessionRead]:
    """List all concessions with mapping counts."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT c.*,
                   COALESCE(SUM(CASE WHEN m.template_type='DC' THEN 1 ELSE 0 END), 0) AS dc_count,
                   COALESCE(SUM(CASE WHEN m.template_type='DW' THEN 1 ELSE 0 END), 0) AS dw_count,
                   COALESCE(SUM(CASE WHEN m.template_type='MC' THEN 1 ELSE 0 END), 0) AS mc_count,
                   COALESCE(SUM(CASE WHEN m.template_type='WT' THEN 1 ELSE 0 END), 0) AS wt_count,
                   COUNT(DISTINCT CASE WHEN m.template_type IN ('DW','WT') AND m.well_name != '' THEN m.well_name END) AS well_count
            FROM concessions c
            LEFT JOIN cell_mappings m ON m.concession_id = c.id
            GROUP BY c.id
            ORDER BY c.name
        """).fetchall()
        return [ConcessionRead(**dict(r)) for r in rows]
    finally:
        conn.close()


def get_concession(conc_id: str) -> ConcessionDetail | None:
    """Get a concession with all its mappings."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM concessions WHERE id = ?", (conc_id,)
        ).fetchone()
        if not row:
            return None

        mappings_rows = conn.execute(
            "SELECT * FROM cell_mappings WHERE concession_id = ? ORDER BY template_type, sort_order",
            (conc_id,),
        ).fetchall()

        # Build structured mappings
        cm = _build_concession_mappings(mappings_rows)

        # Build counts
        dc_count = len(cm.dc)
        mc_count = len(cm.mc)
        dw_count = sum(len(w.fields) for w in cm.dw)
        wt_count = sum(len(w.fields) for w in cm.wt)
        well_count = len(cm.dw) + len(cm.wt)

        return ConcessionDetail(
            **dict(row),
            mappings=cm,
            dc_count=dc_count,
            dw_count=dw_count,
            mc_count=mc_count,
            wt_count=wt_count,
            well_count=well_count,
        )
    finally:
        conn.close()


def create_concession(data: ConcessionCreate) -> ConcessionRead:
    """Create a new concession."""
    conn = get_connection()
    try:
        conc_id = _slugify(data.name)

        # Ensure unique ID
        existing = conn.execute(
            "SELECT id FROM concessions WHERE id = ?", (conc_id,)
        ).fetchone()
        if existing:
            i = 2
            while conn.execute(
                "SELECT id FROM concessions WHERE id = ?", (f"{conc_id}_{i}",)
            ).fetchone():
                i += 1
            conc_id = f"{conc_id}_{i}"

        conn.execute("""
            INSERT INTO concessions (id, name, dpr_file_alias, dpr_sheet,
                active_daily, active_monthly, active_well_test,
                date_format, monthly_report)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conc_id, data.name, data.dpr_file_alias, data.dpr_sheet,
            int(data.active_daily), int(data.active_monthly),
            int(data.active_well_test), data.date_format, data.monthly_report,
        ))
        conn.commit()

        return ConcessionRead(
            id=conc_id, name=data.name,
            dpr_file_alias=data.dpr_file_alias,
            dpr_sheet=data.dpr_sheet,
            active_daily=data.active_daily,
            active_monthly=data.active_monthly,
            active_well_test=data.active_well_test,
            date_format=data.date_format,
            monthly_report=data.monthly_report,
        )
    finally:
        conn.close()


def update_concession(conc_id: str, data: ConcessionUpdate) -> ConcessionRead | None:
    """Update an existing concession."""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM concessions WHERE id = ?", (conc_id,)
        ).fetchone()
        if not existing:
            return None

        updates = {}
        for field in ["name", "dpr_file_alias", "dpr_sheet", "date_format", "monthly_report"]:
            val = getattr(data, field)
            if val is not None:
                updates[field] = val
        for field in ["active_daily", "active_monthly", "active_well_test"]:
            val = getattr(data, field)
            if val is not None:
                updates[field] = int(val)

        if updates:
            updates["updated_at"] = "datetime('now')"
            set_clause = ", ".join(
                f"{k} = datetime('now')" if k == "updated_at" else f"{k} = ?"
                for k in updates
            )
            values = [v for k, v in updates.items() if k != "updated_at"]
            conn.execute(
                f"UPDATE concessions SET {set_clause} WHERE id = ?",
                (*values, conc_id),
            )
            conn.commit()

        row = conn.execute(
            "SELECT * FROM concessions WHERE id = ?", (conc_id,)
        ).fetchone()
        return ConcessionRead(**dict(row))
    finally:
        conn.close()


def delete_concession(conc_id: str) -> bool:
    """Delete a concession and all its mappings."""
    conn = get_connection()
    try:
        # CASCADE handles cell_mappings
        result = conn.execute(
            "DELETE FROM concessions WHERE id = ?", (conc_id,)
        )
        conn.commit()
        return result.rowcount > 0
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
# Cell Mappings
# ═══════════════════════════════════════════════════════════════════════

def get_mappings(conc_id: str, template_type: str) -> list[dict]:
    """Get mappings for a concession + type (DC/DW/MC/WT)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM cell_mappings WHERE concession_id = ? AND template_type = ? ORDER BY sort_order",
            (conc_id, template_type.upper()),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def set_mappings(
    conc_id: str,
    template_type: str,
    mappings: list[dict],
) -> int:
    """Replace all mappings for a concession + type."""
    conn = get_connection()
    try:
        tt = template_type.upper()
        conn.execute(
            "DELETE FROM cell_mappings WHERE concession_id = ? AND template_type = ?",
            (conc_id, tt),
        )

        count = 0
        for i, m in enumerate(mappings):
            conn.execute("""
                INSERT INTO cell_mappings
                    (concession_id, template_type, well_name, ubhi, completion,
                     attribute_code, attribute, cell_ref, unit, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conc_id, tt,
                m.get("well_name", ""),
                m.get("ubhi", ""),
                m.get("completion", ""),
                m.get("attribute_code", ""),
                m.get("attribute", ""),
                m.get("cell_ref", ""),
                m.get("unit", ""),
                i,
            ))
            count += 1

        conn.commit()
        return count
    finally:
        conn.close()


def bulk_insert_mappings(conc_id: str, mappings: list[dict]) -> int:
    """Insert multiple mappings (mixed types) for a concession."""
    conn = get_connection()
    try:
        count = 0
        for m in mappings:
            conn.execute("""
                INSERT INTO cell_mappings
                    (concession_id, template_type, well_name, ubhi, completion,
                     attribute_code, attribute, cell_ref, unit, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conc_id,
                m.get("template_type", ""),
                m.get("well_name", ""),
                m.get("ubhi", ""),
                m.get("completion", ""),
                m.get("attribute_code", ""),
                m.get("attribute", ""),
                m.get("cell_ref", ""),
                m.get("unit", ""),
                m.get("sort_order", count),
            ))
            count += 1

        conn.commit()
        return count
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
# UOM
# ═══════════════════════════════════════════════════════════════════════

def list_uom() -> list[UOMEntryRead]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM uom_entries ORDER BY unit").fetchall()
        return [UOMEntryRead(**dict(r)) for r in rows]
    finally:
        conn.close()


def add_uom(entry: UOMEntryCreate) -> UOMEntryRead:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO uom_entries (unit, factor, target_unit) VALUES (?, ?, ?)",
            (entry.unit.upper(), entry.factor, entry.target_unit),
        )
        conn.commit()
        return UOMEntryRead(unit=entry.unit.upper(), factor=entry.factor, target_unit=entry.target_unit)
    finally:
        conn.close()


def delete_uom(unit: str) -> bool:
    conn = get_connection()
    try:
        result = conn.execute("DELETE FROM uom_entries WHERE unit = ?", (unit.upper(),))
        conn.commit()
        return result.rowcount > 0
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
# QC Rules
# ═══════════════════════════════════════════════════════════════════════

def list_qc_rules() -> list[QCRuleRead]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM qc_rules ORDER BY id").fetchall()
        return [QCRuleRead(**dict(r)) for r in rows]
    finally:
        conn.close()


def add_qc_rule(rule: QCRuleCreate) -> QCRuleRead:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO qc_rules (search_value, replace_value, active) VALUES (?, ?, ?)",
            (rule.search_value, rule.replace_value, int(rule.active)),
        )
        conn.commit()
        return QCRuleRead(id=cursor.lastrowid, **rule.model_dump())
    finally:
        conn.close()


def delete_qc_rule(rule_id: int) -> bool:
    conn = get_connection()
    try:
        result = conn.execute("DELETE FROM qc_rules WHERE id = ?", (rule_id,))
        conn.commit()
        return result.rowcount > 0
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
# Parameters
# ═══════════════════════════════════════════════════════════════════════

def get_parameter(key: str) -> str | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT value FROM parameters WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def set_parameter(key: str, value: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO parameters (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_parameters() -> dict[str, str]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT key, value FROM parameters").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════════════════════════════════

def get_stats() -> ConfigStats:
    conn = get_connection()
    try:
        conc = conn.execute("SELECT COUNT(*) FROM concessions").fetchone()[0]
        active_d = conn.execute("SELECT COUNT(*) FROM concessions WHERE active_daily = 1").fetchone()[0]
        active_m = conn.execute("SELECT COUNT(*) FROM concessions WHERE active_monthly = 1").fetchone()[0]
        active_wt = conn.execute("SELECT COUNT(*) FROM concessions WHERE active_well_test = 1").fetchone()[0]
        maps = conn.execute("SELECT COUNT(*) FROM cell_mappings").fetchone()[0]
        uom = conn.execute("SELECT COUNT(*) FROM uom_entries").fetchone()[0]
        qc = conn.execute("SELECT COUNT(*) FROM qc_rules").fetchone()[0]
        naming = conn.execute("SELECT COUNT(*) FROM naming_rules").fetchone()[0]

        db_size = DB_PATH.stat().st_size / 1024 if DB_PATH.exists() else 0

        return ConfigStats(
            concessions=conc,
            concessions_active_daily=active_d,
            concessions_active_monthly=active_m,
            concessions_active_wt=active_wt,
            total_mappings=maps,
            uom_entries=uom,
            qc_rules=qc,
            naming_rules=naming,
            db_size_kb=round(db_size, 1),
        )
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _build_concession_mappings(rows: list[sqlite3.Row]) -> ConcessionMappings:
    """Group flat mapping rows into structured ConcessionMappings."""
    dc: list[CellMapping] = []
    mc: list[CellMapping] = []
    dw_wells: dict[str, WellMapping] = {}
    wt_wells: dict[str, WellMapping] = {}

    for r in rows:
        d = dict(r)
        tt = d["template_type"]
        cm = CellMapping(
            id=d["id"],
            attribute_code=d["attribute_code"],
            attribute=d["attribute"],
            cell_ref=d["cell_ref"],
            unit=d["unit"],
            sort_order=d["sort_order"],
        )

        if tt == "DC":
            dc.append(cm)
        elif tt == "MC":
            mc.append(cm)
        elif tt == "DW":
            key = d["completion"] or d["well_name"] or "_default"
            if key not in dw_wells:
                dw_wells[key] = WellMapping(
                    well_name=d["well_name"],
                    ubhi=d["ubhi"],
                    completion=d["completion"],
                )
            dw_wells[key].fields.append(cm)
        elif tt == "WT":
            key = d["completion"] or d["well_name"] or "_default"
            if key not in wt_wells:
                wt_wells[key] = WellMapping(
                    well_name=d["well_name"],
                    ubhi=d["ubhi"],
                    completion=d["completion"],
                )
            wt_wells[key].fields.append(cm)

    return ConcessionMappings(
        dc=dc,
        mc=mc,
        dw=list(dw_wells.values()),
        wt=list(wt_wells.values()),
    )
