"""
Tests for the core classification and de-duplication logic.

Run with:  pytest -q
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
import pipeline
import database


# --- keyword matching ------------------------------------------------------
def test_first_match_wins_top_to_bottom():
    rules = [("PUNCTURE", "Tyres & Wheels"), ("TYRE", "Tyres & Wheels")]
    assert pipeline.first_match("TYRE PUNCTURE", rules, "X") == "Tyres & Wheels"


def test_wildcard_matches_across_gap():
    rules = [("NOT*START", "Won't Start")]
    assert pipeline.first_match("ENGINE NOT ABLE TO START", rules, "X") == "Won't Start"


def test_unmatched_returns_default():
    assert pipeline.first_match("something random", [("TYRE", "T")], "DEF") == "DEF"


# --- description splitting --------------------------------------------------
def test_split_description_extracts_code():
    code, defect = pipeline.split_description("10477. - TYRE REAR PUNCTURED")
    assert code == "10477"
    assert defect == "TYRE REAR PUNCTURED"


def test_split_description_no_separator():
    code, defect = pipeline.split_description("JUST A DEFECT")
    assert code is None
    assert defect == "JUST A DEFECT"


# --- equipment type + motorized --------------------------------------------
def test_equipment_type_and_motorized():
    assert pipeline.classify_equipment_type("ACFT NB TUG (B737-800)") == "Aircraft Tow Tractor"
    assert pipeline.classify_motorized("Aircraft Tow Tractor") == "Motorized"
    assert pipeline.classify_equipment_type("BAGGAGE TROLLEY") == "Baggage Trolley"
    assert pipeline.classify_motorized("Baggage Trolley") == "Non-Motorized"


# --- Equipment ID reconciliation -------------------------------------------
def test_reconcile_match():
    assert pipeline.reconcile_equipment_id("10477", "10477") == ("10477", "Match")


def test_reconcile_single_source():
    assert pipeline.reconcile_equipment_id("10477", None) == ("10477", "Single Source")


def test_reconcile_conflict_is_flagged_not_guessed():
    eid, status = pipeline.reconcile_equipment_id("10477", "99999")
    assert status == "Conflict"


def test_reconcile_klia_prefers_asset():
    eid, status = pipeline.reconcile_equipment_id("10477", "KUL1234")
    assert eid == "KUL1234"
    assert status == "Auto-resolved (KLIA)"


# --- end-to-end + dedup -----------------------------------------------------
def _tiny_raw():
    return pd.DataFrame([{
        "Permit No.": "KUL26000001", "Work Status": "Closed",
        "Work Order Description": "10477. - TYRE REAR PUNCTURED LOC A12",
        "Work Order Type": "Breakdown", "Received Date": "2026-01-05 10:00",
        "Asset Number": "10477", "Asset Description": "ACFT NB TUG (B737-800)",
        "Action Taken": None, "Work Order Trade": "GSE-FLM",
    }])


def test_pipeline_produces_master_row():
    result = pipeline.run_pipeline(_tiny_raw())
    m = result["master"]
    assert len(m) == 1
    assert m.iloc[0]["Problem Area"] == "Tyres & Wheels"
    assert m.iloc[0]["Failure Mode"] == "Puncture"
    assert m.iloc[0]["Equipment Type"] == "Aircraft Tow Tractor"


def test_merge_is_idempotent(tmp_path):
    result = pipeline.run_pipeline(_tiny_raw())
    conn = database.connect(tmp_path / "t.db")
    c1 = database.merge_records(conn, result["master"])
    c2 = database.merge_records(conn, result["master"])  # same data again
    assert c1["inserted"] == 1
    assert c2["inserted"] == 0                 # dedup worked
    assert c2["duplicates_skipped"] == 1
    conn.close()
