"""
Data-quality checks for cleaned records.
"""
from __future__ import annotations

import pandas as pd

import config
from pipeline import MASTER_COLUMNS


def check_master(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []

    # Check required columns.
    missing = [c for c in MASTER_COLUMNS if c not in df.columns]
    if missing:
        issues.append(f"missing expected columns: {missing}")
        return issues

    # Check that the table is not empty.
    if len(df) == 0:
        issues.append("no rows after cleaning")
        return issues

    # Check parsed dates.
    bad_dates = df["Date"].isna().sum()
    if bad_dates:
        issues.append(f"{bad_dates} rows have an unparseable date")

    # Check defect descriptions.
    blank = df["Defects Description"].fillna("").str.strip().eq("").sum()
    if blank:
        issues.append(f"{blank} rows have a blank defect description")

    # Check duplicate composite keys within the file.
    key = df[config.COMPOSITE_KEY].astype(str).apply(
        lambda r: "||".join(r.str.upper()), axis=1)
    dupes = key.duplicated().sum()
    if dupes:
        issues.append(f"{dupes} duplicate composite keys within this file")

    # Check allowed classification values.
    known_motor = {"Motorized", "Non-Motorized", "Unclassified"}
    bad_motor = set(df["Motorized/Non-Motorized"].dropna()) - known_motor
    if bad_motor:
        issues.append(f"unexpected Motorized values: {bad_motor}")

    return issues
