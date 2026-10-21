"""
Monthly pipeline entry point.

Given a raw export, this script will:
    1. clean + classify the new records   (pipeline.py)
    2. check the result is sane            (validate.py)
    3. merge into the running master, skipping any rows already there
       (database.py -- de-dupes on Date + Equipment ID + Defect)
    4. export the updated master to Excel for Power BI

Usage:
    python add_month.py data/sample_raw/sample_raw_2026_04.xlsx

Re-running the same file is safe: duplicates are detected and skipped.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pipeline
import database
import validate


def add_month(raw_path: str) -> None:
    raw_path = Path(raw_path)
    if not raw_path.exists():
        sys.exit(f"File not found: {raw_path}")

    print(f"Reading   {raw_path}")
    raw = pipeline.read_raw(raw_path)

    print("Cleaning + classifying ...")
    result = pipeline.run_pipeline(raw)
    master_new = result["master"]

    print("Validating ...")
    issues = validate.check_master(master_new)
    if issues:
        print("\n  VALIDATION PROBLEMS -- nothing was merged:")
        for msg in issues:
            print(f"   - {msg}")
        sys.exit(1)
    print("   validation passed.")

    print("Merging into master database ...")
    conn = database.connect()
    counts = database.merge_records(conn, master_new)

    out = database.export_master(conn)
    conn.close()

    # Print the quality summary and merge counts.
    print("\n--- This month ---")
    print(result["qa"].to_string(index=False))
    print(f"\n   new rows inserted : {counts['inserted']}")
    print(f"   duplicates skipped: {counts['duplicates_skipped']}")
    print(f"   master total now  : {counts['total_after']}")
    if len(result["id_review"]):
        print(f"\n   NOTE: {len(result['id_review'])} rows need Equipment ID review "
              f"(conflict/missing) -- see the review sheet.")
    print(f"\nUpdated master exported to: {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    add_month(sys.argv[1])
