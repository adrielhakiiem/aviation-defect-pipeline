"""
pipeline.py  --  Transform raw equipment defect exports into a clean,
classified dataset ready for analysis / Power BI.

Stages (in order):
    1. Standardise text        (whitespace, spelling fixes)
    2. Extract equipment code  (pulled from the work-order description prefix)
    3. Reconcile Equipment ID  (merge equipment code + asset number)
    4. Classify                (equipment type, motorized, problem area,
                                failure mode, record class)
    5. Separate non-defects    (ops-support / admin rows -> review, not master)

Design principle used throughout: FLAG, DON'T DROP.
Rows with missing or conflicting identifiers are kept and flagged in a review
table rather than silently discarded, so no data goes missing quietly.

Run directly to clean a single raw file:
    python pipeline.py data/sample_raw/sample_raw_2026_01.xlsx
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

import config


# ---------------------------------------------------------------------------
# Keyword matching helper (shared by every classification rule)
# ---------------------------------------------------------------------------
def _rule_to_regex(keyword: str) -> re.Pattern:
    """Turn a keyword rule into a compiled regex.

    '*' becomes a wildcard (any characters). Everything else is literal.
    Matching is case-insensitive.
    """
    parts = [re.escape(p) for p in keyword.upper().split("*")]
    pattern = ".*".join(parts)
    return re.compile(pattern)


def first_match(text: str, rules, default: str) -> str:
    """Return the value of the FIRST rule whose keyword is found in text.

    rules is a list of (keyword, value) tuples, checked top-to-bottom.
    """
    if not isinstance(text, str) or not text.strip():
        return default
    upper = text.upper()
    for keyword, value in rules:
        if _rule_to_regex(keyword).search(upper):
            return value
    return default


def contains_any(text: str, keywords) -> bool:
    if not isinstance(text, str):
        return False
    upper = text.upper()
    return any(_rule_to_regex(k).search(upper) for k in keywords)


# ---------------------------------------------------------------------------
# Stage 1 -- text standardisation
# ---------------------------------------------------------------------------
def normalise_whitespace(value):
    if not isinstance(value, str):
        return value
    return re.sub(r"\s+", " ", value).strip()


def apply_spelling_map(text):
    if not isinstance(text, str):
        return text
    out = text
    for wrong, right in config.SPELLING_MAP.items():
        out = re.sub(rf"\b{re.escape(wrong)}\b", right, out, flags=re.IGNORECASE)
    return out


# ---------------------------------------------------------------------------
# Stage 2 -- equipment code + clean description
# ---------------------------------------------------------------------------
def split_description(description):
    """Split '<code> - <defect text>' into (equipment_code, defect_text).

    The raw export prefixes most descriptions with the equipment identifier,
    e.g. '10477. - TYRE REAR RIGHT PUNCTURED'. If there is no ' - ' separator
    the whole string is treated as the defect text.
    """
    if not isinstance(description, str) or " - " not in description:
        return None, description
    code, defect = description.split(" - ", 1)
    code = code.strip().rstrip(".").strip()
    return (code or None), defect.strip()


# ---------------------------------------------------------------------------
# Stage 3 -- Equipment ID reconciliation
# ---------------------------------------------------------------------------
def _norm_id(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip().upper() or None


def reconcile_equipment_id(equipment_code, asset_number):
    """Merge an extracted equipment code and an asset number into one ID.

    Returns (equipment_id, status). Status is one of:
        Match, Single Source, Auto-resolved (KLIA), Conflict, Missing.
    Conflicts are flagged, never guessed.
    """
    code = _norm_id(equipment_code)
    asset = _norm_id(asset_number)

    # Manual override always wins and survives every rerun.
    for raw in (code, asset):
        if raw in config.EQUIPMENT_ID_OVERRIDES:
            return config.EQUIPMENT_ID_OVERRIDES[raw], "Match"

    if code and asset:
        if code == asset:
            return code, "Match"
        is_klia = any(asset.startswith(p) for p in config.KLIA_PREFIXES) or \
                  any(code.startswith(p) for p in config.KLIA_PREFIXES)
        if is_klia:
            return asset, "Auto-resolved (KLIA)"
        return asset, "Conflict"          # kept + flagged for review
    if code or asset:
        return (code or asset), "Single Source"
    return None, "Missing"


# ---------------------------------------------------------------------------
# Stage 4 -- classification
# ---------------------------------------------------------------------------
def classify_equipment_type(asset_desc):
    return first_match(asset_desc, config.EQUIPMENT_TYPE_RULES,
                       config.EQUIPMENT_TYPE_UNMATCHED)


def classify_motorized(equipment_type):
    if equipment_type in config.NON_MOTORIZED_TYPES:
        return "Non-Motorized"
    if equipment_type == config.EQUIPMENT_TYPE_UNMATCHED:
        return "Unclassified"
    return "Motorized"


def classify_problem_area(defect_text):
    return first_match(defect_text, config.PROBLEM_AREA_RULES,
                       config.PROBLEM_AREA_UNMATCHED)


def classify_failure_mode(defect_text):
    return first_match(defect_text, config.FAILURE_MODE_RULES,
                       config.FAILURE_MODE_UNMATCHED)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
# Final column order of the cleaned master.
MASTER_COLUMNS = [
    "Permit No", "Work Status", "Equipment Code", "Asset Number",
    "Asset Description", "Defects Description", "Work Order Type",
    "Work Order Trade", "Action Taken", "Date", "By Month",
    "Equipment ID", "Equipment ID Status", "Equipment Type",
    "Motorized/Non-Motorized", "Problem Area", "Failure Mode", "Record Class",
]


def run_pipeline(raw: pd.DataFrame) -> dict:
    """Clean and classify a raw export.

    Returns a dict with:
        master        -- clean defect records (the Power BI table)
        non_defects   -- rows judged ops-support / admin (review)
        id_review     -- rows with conflicting / missing Equipment ID (review)
        qa            -- a small metrics table
    """
    cols = config.RAW_COLUMNS
    df = raw.rename(columns={v: k for k, v in cols.items()}).copy()

    stats = {"rows_read": len(df)}

    # Stage 1 ---------------------------------------------------------------
    for text_col in ["description", "asset_desc", "work_status",
                     "work_order_type", "work_order_trade", "action_taken"]:
        if text_col in df:
            df[text_col] = df[text_col].map(normalise_whitespace)
    df["description"] = df["description"].map(apply_spelling_map)

    # Stage 2 ---------------------------------------------------------------
    split = df["description"].map(split_description)
    df["Equipment Code"] = [s[0] for s in split]
    df["Defects Description"] = [s[1] for s in split]

    # Dates
    df["Date"] = pd.to_datetime(df["received_date"], errors="coerce").dt.normalize()
    df["By Month"] = df["Date"].dt.strftime("%B")
    stats["missing_or_unparsed_dates"] = int(df["Date"].isna().sum())

    # Stage 3 ---------------------------------------------------------------
    recon = [reconcile_equipment_id(c, a)
             for c, a in zip(df["Equipment Code"], df["asset_number"])]
    df["Equipment ID"] = [r[0] for r in recon]
    df["Equipment ID Status"] = [r[1] for r in recon]
    for status in ["Match", "Single Source", "Auto-resolved (KLIA)",
                   "Conflict", "Missing"]:
        stats[f"equipment_id: {status}"] = int(
            (df["Equipment ID Status"] == status).sum())

    # Stage 4 ---------------------------------------------------------------
    df["Equipment Type"] = df["asset_desc"].map(classify_equipment_type)
    df["Motorized/Non-Motorized"] = df["Equipment Type"].map(classify_motorized)
    df["Problem Area"] = df["Defects Description"].map(classify_problem_area)
    df["Failure Mode"] = df["Defects Description"].map(classify_failure_mode)

    # Does the defect text describe a real, classified problem?
    has_inspection_kw = df["Defects Description"].map(
        lambda t: contains_any(t, config.INSPECTION_KEYWORDS))
    problem_matched = ~df["Problem Area"].isin(
        [config.PROBLEM_AREA_UNMATCHED, config.NON_DEFECT_AREA])

    # Record Class: an inspection that surfaced a real defect is kept and
    # labelled; a routine inspection with no defect is separated out (below).
    df["Record Class"] = config.RECORD_CLASS_DEFECT
    df.loc[has_inspection_kw & problem_matched, "Record Class"] = \
        config.RECORD_CLASS_INSPECTION

    # Tidy source column names onto the master schema
    df = df.rename(columns={
        "permit_no": "Permit No", "work_status": "Work Status",
        "asset_number": "Asset Number", "asset_desc": "Asset Description",
        "work_order_type": "Work Order Type",
        "work_order_trade": "Work Order Trade", "action_taken": "Action Taken",
    })

    # Stage 5 -- separate rows that are not equipment defects ---------------
    # (a) Non-defect ops-support / admin rows.
    is_non_defect = (
        (df["Problem Area"] == config.NON_DEFECT_AREA)
        | (df["Work Order Type"].isin(config.NON_DEFECT_WORK_ORDER_TYPES))
    )
    # (b) Routine inspections / servicing with no actual defect described.
    is_routine_inspection = has_inspection_kw & ~problem_matched & ~is_non_defect

    non_defects = df[is_non_defect].copy()
    inspection_removed = df[is_routine_inspection].copy()
    master = df[~is_non_defect & ~is_routine_inspection].copy()

    stats["non_defect_rows_removed"] = int(len(non_defects))
    stats["routine_inspection_rows_removed"] = int(len(inspection_removed))

    # Collapse exact duplicate records (same composite key) within this file.
    # The same equipment can appear many times a day with DIFFERENT defects
    # (kept); identical Date + Equipment ID + Defect rows are true duplicates.
    key = master[config.COMPOSITE_KEY].astype(str).apply(
        lambda r: "||".join(r.str.upper()), axis=1)
    stats["duplicate_rows_collapsed"] = int(key.duplicated().sum())
    master = master[~key.duplicated()].copy()

    # Review table: anything that needs a human eye on the Equipment ID.
    id_review = master[master["Equipment ID Status"].isin(["Conflict", "Missing"])].copy()

    master = master[MASTER_COLUMNS].reset_index(drop=True)
    stats["rows_in_master"] = int(len(master))

    qa = pd.DataFrame(
        [(k, v) for k, v in stats.items()], columns=["Metric", "Value"])

    return {
        "master": master,
        "non_defects": non_defects.reset_index(drop=True),
        "inspection_removed": inspection_removed.reset_index(drop=True),
        "id_review": id_review[MASTER_COLUMNS].reset_index(drop=True),
        "qa": qa,
    }


def read_raw(path) -> pd.DataFrame:
    """Read a raw export (.xls or .xlsx), first sheet."""
    path = Path(path)
    engine = "xlrd" if path.suffix.lower() == ".xls" else None
    return pd.read_excel(path, sheet_name=0, engine=engine)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    raw = read_raw(sys.argv[1])
    result = run_pipeline(raw)
    print(result["qa"].to_string(index=False))
    out = Path("data/output/cleaned_preview.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out) as xl:
        result["master"].to_excel(xl, sheet_name="Cleaned Data", index=False)
        result["qa"].to_excel(xl, sheet_name="QA Summary", index=False)
        result["id_review"].to_excel(xl, sheet_name="Equipment ID Review", index=False)
        result["non_defects"].to_excel(xl, sheet_name="Non-Defect Removed", index=False)
        result["inspection_removed"].to_excel(xl, sheet_name="Inspection Removed", index=False)
    print(f"\nWrote {out}")
