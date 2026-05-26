"""Extraction persistence — SQLite storage for extraction results."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.models.schemas import ExtractionResult, ProcessingStatus, ReportType
from app.services.database import get_connection


# ── Save ────────────────────────────────────────────────────────────────

def save_extraction(
    result: ExtractionResult,
    dpr_folder: str = "",
    label: str = "",
) -> None:
    """Persist an ExtractionResult to the database.

    Stores metadata in `extractions` and each row as a JSON blob
    in `extraction_rows`.
    """
    conn = get_connection()
    try:
        # Upsert metadata
        conn.execute("""
            INSERT OR REPLACE INTO extractions
                (id, report_type, status, record_count,
                 dc_columns, dw_columns, mc_columns, wt_columns,
                 columns, dpr_folder, label, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.id,
            result.report_type.value,
            result.status.value,
            result.record_count,
            json.dumps(result.dc_columns),
            json.dumps(result.dw_columns),
            json.dumps(result.mc_columns),
            json.dumps(result.wt_columns),
            json.dumps(result.columns),
            dpr_folder,
            label or f"{result.report_type.value} — {result.created_at:%Y-%m-%d %H:%M}",
            result.created_at.isoformat(),
        ))

        # Delete old rows (in case of re-save / update)
        conn.execute(
            "DELETE FROM extraction_rows WHERE extraction_id = ?",
            (result.id,),
        )

        # Insert rows per data type
        rows_to_insert = []
        for data_type, data_list in [
            ("dc", result.dc_data),
            ("dw", result.dw_data),
            ("mc", result.mc_data),
            ("wt", result.wt_data),
        ]:
            for idx, row in enumerate(data_list):
                rows_to_insert.append((
                    result.id, data_type, idx, json.dumps(row, default=str),
                ))

        if rows_to_insert:
            conn.executemany("""
                INSERT INTO extraction_rows
                    (extraction_id, data_type, row_index, row_data)
                VALUES (?, ?, ?, ?)
            """, rows_to_insert)

        conn.commit()
    finally:
        conn.close()


# ── Load one ────────────────────────────────────────────────────────────

def load_extraction(extraction_id: str) -> ExtractionResult | None:
    """Load a full ExtractionResult from the database."""
    conn = get_connection()
    try:
        meta = conn.execute(
            "SELECT * FROM extractions WHERE id = ?", (extraction_id,)
        ).fetchone()
        if not meta:
            return None

        meta = dict(meta)

        # Load rows grouped by data_type
        typed_data: dict[str, list[dict]] = {"dc": [], "dw": [], "mc": [], "wt": []}
        rows = conn.execute(
            "SELECT data_type, row_data FROM extraction_rows "
            "WHERE extraction_id = ? ORDER BY data_type, row_index",
            (extraction_id,),
        ).fetchall()

        for r in rows:
            dt = r["data_type"]
            if dt in typed_data:
                typed_data[dt].append(json.loads(r["row_data"]))

        # Parse created_at
        created_at = datetime.fromisoformat(meta["created_at"]) if meta["created_at"] else datetime.now()

        # Build combined data
        all_data = typed_data["dc"] + typed_data["dw"] + typed_data["mc"] + typed_data["wt"]

        return ExtractionResult(
            id=meta["id"],
            report_type=ReportType(meta["report_type"]),
            status=ProcessingStatus(meta["status"]),
            record_count=meta["record_count"],
            columns=json.loads(meta["columns"]),
            data=all_data,
            dc_data=typed_data["dc"],
            dw_data=typed_data["dw"],
            mc_data=typed_data["mc"],
            wt_data=typed_data["wt"],
            dc_columns=json.loads(meta["dc_columns"]),
            dw_columns=json.loads(meta["dw_columns"]),
            mc_columns=json.loads(meta["mc_columns"]),
            wt_columns=json.loads(meta["wt_columns"]),
            created_at=created_at,
        )
    finally:
        conn.close()


# ── List (metadata only) ───────────────────────────────────────────────

def list_extractions() -> list[dict[str, Any]]:
    """Return metadata for all saved extractions (no row data).

    Uses a single query with LEFT JOIN to get per-type row counts,
    avoiding N+1 query overhead.
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                e.id, e.report_type, e.status, e.record_count,
                e.dc_columns, e.dw_columns, e.mc_columns, e.wt_columns,
                e.dpr_folder, e.label, e.created_at,
                SUM(CASE WHEN r.data_type = 'dc' THEN 1 ELSE 0 END) AS dc_count,
                SUM(CASE WHEN r.data_type = 'dw' THEN 1 ELSE 0 END) AS dw_count,
                SUM(CASE WHEN r.data_type = 'mc' THEN 1 ELSE 0 END) AS mc_count,
                SUM(CASE WHEN r.data_type = 'wt' THEN 1 ELSE 0 END) AS wt_count
            FROM extractions e
            LEFT JOIN extraction_rows r ON r.extraction_id = e.id
            GROUP BY e.id
            ORDER BY e.created_at DESC
        """).fetchall()

        return [
            {
                "id": r["id"],
                "report_type": r["report_type"],
                "status": r["status"],
                "record_count": r["record_count"],
                "dc_count": r["dc_count"] or 0,
                "dw_count": r["dw_count"] or 0,
                "mc_count": r["mc_count"] or 0,
                "wt_count": r["wt_count"] or 0,
                "dpr_folder": r["dpr_folder"],
                "label": r["label"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


# ── Delete ──────────────────────────────────────────────────────────────

def delete_extraction(extraction_id: str) -> bool:
    """Delete an extraction and all its rows. Returns True if found."""
    conn = get_connection()
    try:
        # CASCADE handles extraction_rows
        cur = conn.execute(
            "DELETE FROM extractions WHERE id = ?", (extraction_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ── Update label ────────────────────────────────────────────────────────

def update_label(extraction_id: str, label: str) -> bool:
    """Rename an extraction."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE extractions SET label = ? WHERE id = ?",
            (label, extraction_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ── Sync rows after CRUD ───────────────────────────────────────────────

def sync_rows(extraction_id: str, data_type: str, rows: list[dict]) -> None:
    """Replace all rows of a given data_type for an extraction.

    Called after add/delete/update operations to keep DB in sync.
    Also updates the record_count in the metadata table.
    """
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM extraction_rows WHERE extraction_id = ? AND data_type = ?",
            (extraction_id, data_type),
        )

        inserts = [
            (extraction_id, data_type, idx, json.dumps(row, default=str))
            for idx, row in enumerate(rows)
        ]
        if inserts:
            conn.executemany("""
                INSERT INTO extraction_rows
                    (extraction_id, data_type, row_index, row_data)
                VALUES (?, ?, ?, ?)
            """, inserts)

        # Update total record count
        total = conn.execute(
            "SELECT COUNT(*) FROM extraction_rows WHERE extraction_id = ?",
            (extraction_id,),
        ).fetchone()[0]
        conn.execute(
            "UPDATE extractions SET record_count = ? WHERE id = ?",
            (total, extraction_id),
        )

        conn.commit()
    finally:
        conn.close()
