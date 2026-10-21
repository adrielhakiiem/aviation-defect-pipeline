"""
validate.py  --  Loud, simple data-quality checks.

These run automatically inside add_month.py before anything is merged, so a bad
file is caught early instead of quietly corrupting the master. Each check
returns a human-readable message when something is wrong; an empty list means
the data passed.

Philosophy: surface problems, don't hide them. Missing/conflicting IDs are
expected and allowed (they are flagged, not fatal); structural problems
(missing columns, bad dates, duplicate keys within one file) are fatal.
"""
from __future__ import annotations

import pandas as pd

import config
from pipeline import MASTER_COLUMNS


def check_master(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []

    # 1. expected columns present
    missing = [c for c in MASTER_COLUMNS if c not in df.columns]
    if missing:
        issues.append(f"missing expected columns: {missing}")
        return issues  # further checks would just cascade

    # 2. not empty
    if len(df) == 0:
        issues.append("no rows after cleaning")
        return issues

    # 3. dates all parsed
    bad_dates = df["Date"].isna().sum()
    if bad_dates:
        issues.append(f"{bad_dates} rows have an unparseable date")

    # 4. no blank defect descriptions
    blank = df["Defects Description"].fillna("").str.strip().eq("").sum()
    if blank:
        issues.append(f"{blank} rows have a blank defect description")

    # 5. no duplicate composite keys WITHIN this file
    key = df[config.COMPOSITE_KEY].astype(str).apply(
        lambda r: "||".join(r.str.upper()), axis=1)
    dupes = key.duplicated().sum()
    if dupes:
        issues.append(f"{dupes} duplicate composite keys within this file")

    # 6. classified values fall in the known value sets
    known_motor = {"Motorized", "Non-Motorized", "Unclassified"}
    bad_motor = set(df["Motorized/Non-Motorized"].dropna()) - known_motor
    if bad_motor:
        issues.append(f"unexpected Motorized values: {bad_motor}")

    return issues
