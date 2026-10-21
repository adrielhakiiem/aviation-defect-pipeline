"""
database.py  --  SQLite storage, merge and analytics for cleaned defect records.

SQLite is used because it ships with Python (no server to install), the whole
database is a single portable file, and anyone can open it with free tools like
DB Browser for SQLite.

What this module does:
    * create the defects table
    * merge cleaned rows in, de-duplicating on the composite key
      (Date + Equipment ID + Defects Description) so re-running a month is safe
    * run a few analytical SQL queries
    * export the current master back to Excel for Power BI

Composite-key de-duplication is the core idea: the same equipment legitimately
appears many times a day with different defects, so the key is all three fields
together -- not equipment number alone.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

import config

DB_PATH = Path("data/output/defects.db")
TABLE = "defects"

# SQLite type for each column. record_key is the composite primary key.
SCHEMA = {
    "record_key": "TEXT PRIMARY KEY",
    "Permit No": "TEXT",
    "Work Status": "TEXT",
    "Equipment Code": "TEXT",
    "Asset Number": "TEXT",
    "Asset Description": "TEXT",
    "Defects Description": "TEXT",
    "Work Order Type": "TEXT",
    "Work Order Trade": "TEXT",
    "Action Taken": "TEXT",
    "Date": "TEXT",
    "By Month": "TEXT",
    "Equipment ID": "TEXT",
    "Equipment ID Status": "TEXT",
    "Equipment Type": "TEXT",
    "Motorized/Non-Motorized": "TEXT",
    "Problem Area": "TEXT",
    "Failure Mode": "TEXT",
    "Record Class": "TEXT",
}


def _make_key(row) -> str:
    """Build the composite key for one row (Date + Equipment ID + Defect)."""
    parts = []
    for col in config.COMPOSITE_KEY:
        val = row.get(col)
        parts.append("" if pd.isna(val) else str(val).strip().upper())
    return "||".join(parts)


def connect(db_path=DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def init_db(conn: sqlite3.Connection) -> None:
    cols = ", ".join(f'"{name}" {typ}' for name, typ in SCHEMA.items())
    conn.execute(f'CREATE TABLE IF NOT EXISTS {TABLE} ({cols})')
    conn.commit()


def merge_records(conn: sqlite3.Connection, master: pd.DataFrame) -> dict:
    """Insert cleaned rows, skipping ones already present (by composite key).

    Returns counts: {incoming, inserted, duplicates_skipped, total_after}.
    """
    init_db(conn)
    df = master.copy()
    df["Date"] = df["Date"].astype(str)
    df["record_key"] = df.apply(_make_key, axis=1)

    before = conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]

    ordered = ["record_key"] + [c for c in SCHEMA if c != "record_key"]
    placeholders = ", ".join("?" for _ in ordered)
    col_sql = ", ".join(f'"{c}"' for c in ordered)
    rows = [tuple(None if pd.isna(r.get(c)) else r.get(c) for c in ordered)
            for _, r in df.iterrows()]

    # Keep existing records when the composite key is already present.
    conn.executemany(
        f"INSERT OR IGNORE INTO {TABLE} ({col_sql}) VALUES ({placeholders})",
        rows,
    )
    conn.commit()

    after = conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
    inserted = after - before
    return {
        "incoming": len(df),
        "inserted": inserted,
        "duplicates_skipped": len(df) - inserted,
        "total_after": after,
    }


def load_master(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql(f"SELECT * FROM {TABLE}", conn)
    return df.drop(columns=["record_key"], errors="ignore")


# Summary queries exported with the master table.
QUERIES = {
    "defects_by_equipment_type": f"""
        SELECT "Equipment Type", COUNT(*) AS defects
        FROM {TABLE}
        WHERE "Record Class" = 'Defect'
        GROUP BY "Equipment Type"
        ORDER BY defects DESC
    """,
    "defects_by_problem_area": f"""
        SELECT "Problem Area", COUNT(*) AS defects
        FROM {TABLE}
        WHERE "Record Class" = 'Defect'
        GROUP BY "Problem Area"
        ORDER BY defects DESC
    """,
    "monthly_trend": f"""
        SELECT "By Month", COUNT(*) AS defects
        FROM {TABLE}
        WHERE "Record Class" = 'Defect'
        GROUP BY "By Month"
    """,
    "motorized_split": f"""
        SELECT "Motorized/Non-Motorized", COUNT(*) AS records
        FROM {TABLE}
        GROUP BY "Motorized/Non-Motorized"
    """,
}


def run_query(conn: sqlite3.Connection, name: str) -> pd.DataFrame:
    return pd.read_sql(QUERIES[name], conn)


def export_master(conn: sqlite3.Connection,
                  out_path="data/output/EDR_MASTER.xlsx") -> Path:
    """Write the current master + summary queries to Excel for Power BI."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    master = load_master(conn)
    with pd.ExcelWriter(out_path) as xl:
        master.to_excel(xl, sheet_name="Master", index=False)
        for name in QUERIES:
            run_query(conn, name).to_excel(xl, sheet_name=name[:31], index=False)
    return out_path
