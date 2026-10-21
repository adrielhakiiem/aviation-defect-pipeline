"""
generate_sample_data.py  --  Create realistic but 100% FAKE raw defect exports.

No real operational data is used. The generator reproduces the *shape* and
*messiness* of a real ground-support-equipment export so the pipeline can be
demonstrated and practised on safely:

    * same 9 raw columns
    * equipment identifier embedded in the description prefix
    * missing asset numbers (~12% of rows)
    * spelling variants and Malay terms mixed into free text
    * KLIA-prefixed identifiers that conflict with the embedded code
    * routine-inspection rows and non-defect ops-support rows mixed in

Usage:
    python generate_sample_data.py                 # 3 months, ~500 rows each
    python generate_sample_data.py --months 2026-01 2026-02 --rows 400
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import pandas as pd

OUT_DIR = Path("data/sample_raw")

# (asset_description, equipment_code_style)  grouped so classification varies.
FLEET = [
    ("ACFT NB TUG (B737-800)", "num"),
    ("NARROW BODY AIRCRAFT TRACTOR-F180", "num"),
    ("MT{n:02d} - MOTOTOK PUSHBACK AIRCRAFT", "mt"),
    ("BAGGAGE TRACTOR", "num"),
    ("CARGO TOWING TRACTOR", "num"),
    ("CONVEYOR BELT LOADER", "num"),
    ("STANDARD LOWER DECK LOADER", "num"),
    ("MAIN DECK LOADER", "num"),
    ("GPU {k}KVA", "num"),
    ("AIR CONDITIONING UNIT - TYPE GF40", "num"),
    ("ASU - AIR START UNIT", "num"),
    ("POTABLE WATER TRUCK", "num"),
    ("LAVATORY TRUCK", "num"),
    ("CATERING HI-LIFT - MCAT", "ct"),
    ("PAXSTEP(737)", "num"),
    ("BAGGAGE TROLLEY", "num"),
    ("PALLET DOLLY", "num"),
    ("TOW BAR A320", "num"),
    ("CHT - CHOCK TROLLEY", "num"),
    ("HEADSET WIRELESS FOR MOTOTOK", "hw"),
    ("HINO LORRY XZU600", "plate"),
    ("CATERING VAN (APM)", "plate"),
    ("PERODUA AXIA", "plate"),
    ("DIESEL TANKER", "num"),
    ("FORKLIFT", "num"),
]

# defect phrasings grouped loosely by the problem they should classify into.
DEFECTS = [
    "TYRE REAR RIGHT PUNCTURED (NON NEGLIGENCE) LOC A{loc}",
    "FRONT TYRE WORNOUT NEED REPLACEMENT",
    "TAYAR BELAKANG PANCIT LOC C{loc}",            # Malay -> spelling map
    "ENGINE UNABLE TO START AT BAY {loc}",
    "ENGINE OVERHEAT AND AUTO SHUTDOWN",
    "BATTERY WEAK CANNOT START",
    "HEADLAMP NOT WORKING",
    "HYDRAULIC OIL LEAK AT MAIN CYLINDER",
    "BRAKE NOT FUNCTION PROPERLY",
    "STEERING HARD TO TURN",
    "CONVEYOR BELT TORN",
    "PLATFORM CANNOT RAISE",
    "DOOR HINGE BROKEN",
    "SIDE MIRROR CRACKED",
    "LAVATORY DUMP VALVE LEAKING",
    "WATER PUMP NOT WORKING",
    "TOWBAR SHEAR PIN MISSING",
    "AIRCOND NOT COLD",
    "GEARBOX MALFUNCTION",
    "BEACON LAMP U/S",
    "HORN NOT FUNCTION",
    "WIPER MOTOR FAULTY",
    " wiring short circuit intermittent",            # messy casing
]

# Routine inspections with NO actual defect -> separated to "Inspection Removed".
ROUTINE_INSPECTIONS = [
    "FULL INSPECTION - PMC MONTHLY CHECK",
    "ANNUAL LOAD TEST CERTIFICATION",
    "LOADTEST VERIFICATION AS PER SCHEDULE",
    "FULL INSP 500 HOURS ROUTINE",
    "PMC QUARTERLY INSPECTION",
]

NON_DEFECTS = [
    "STANDBY UNIT FOR VVIP MOVEMENT",
    "LOAN TO MAB LICENSING",
    "WASHING AND CLEANING",
]

WORK_STATUS = ["Closed", "Closed", "Closed", "In Progress", "Cancelled"]
WORK_ORDER_TYPE = ["Breakdown", "Breakdown", "Corrective", "Inspection", "Accident"]
TRADES = ["GSE-FLM", "Mechanical", "Tyre Shop", "Electrical Support", "Contract"]


def _equipment_code(style: str, rng: random.Random) -> str:
    if style == "mt":
        return f"MT{rng.randint(1, 13):02d}"
    if style == "ct":
        return f"CT{rng.randint(1, 27):02d}"
    if style == "hw":
        return f"HW{rng.randint(1, 17):02d}"
    if style == "plate":
        letters = "".join(rng.choice("ABCDEFGHJKLMNPQRSTVWXYZ") for _ in range(3))
        return f"{letters} 8291"
    return str(rng.randint(10000, 10999))          # numeric asset code


def _permit(seq: int, year: int, rng: random.Random) -> str:
    return f"KUL{str(year)[2:]}{seq:06d}"


def generate_month(year: int, month: int, n_rows: int, rng: random.Random,
                   start_seq: int) -> pd.DataFrame:
    records = []
    for i in range(n_rows):
        asset_desc_tpl, style = rng.choice(FLEET)
        asset_desc = asset_desc_tpl.format(
            n=rng.randint(1, 13), k=rng.choice([90, 140, 180]))
        code = _equipment_code(style, rng)

        # Choose record flavour. Proportions are tuned so the cleaned master
        # ends up near ~45% of raw (matching a real GSE export: lots of routine
        # inspections and ops-support rows get separated out).
        roll = rng.random()
        if roll < 0.25:                                  # non-defect ops support
            defect = rng.choice(NON_DEFECTS)
            wot = "Projects"
        elif roll < 0.58:                                # inspection / servicing
            wot = "Inspection"
            if rng.random() < 0.12:                      # found a real defect
                defect = "INSPECTION - FOUND " + \
                    rng.choice(DEFECTS).format(loc=rng.randint(1, 60))
            else:                                        # routine, no defect
                defect = rng.choice(ROUTINE_INSPECTIONS)
        else:                                            # genuine breakdown
            defect = rng.choice(DEFECTS).format(loc=rng.randint(1, 60))
            wot = rng.choice(WORK_ORDER_TYPE[:3])

        description = f"{code}. - {defect}"

        # asset number: usually matches code, sometimes missing, sometimes a
        # KLIA-prefixed conflict (to exercise reconciliation).
        r2 = rng.random()
        if r2 < 0.12:
            asset_number = None                      # missing -> flagged
        elif r2 < 0.18:
            asset_number = f"KUL{rng.randint(1000, 9999)}"   # KLIA conflict
        else:
            asset_number = code

        day = rng.randint(1, 28)
        received = pd.Timestamp(year=year, month=month, day=day,
                                hour=rng.randint(6, 22), minute=rng.randint(0, 59))

        records.append({
            "Permit No.": _permit(start_seq + i, year, rng),
            "Work Status": rng.choice(WORK_STATUS),
            "Work Order Description": description,
            "Work Order Type": wot,
            "Received Date": received,
            "Asset Number": asset_number,
            "Asset Description": asset_desc if rng.random() > 0.05 else None,
            "Action Taken": None if rng.random() < 0.6 else "Rectified and tested",
            "Work Order Trade": rng.choice(TRADES),
        })
    return pd.DataFrame(records)


def main():
    ap = argparse.ArgumentParser(description="Generate fake raw defect exports.")
    ap.add_argument("--months", nargs="+",
                    default=["2026-01", "2026-02", "2026-03", "2026-04",
                             "2026-05", "2026-06", "2026-07", "2026-08"],
                    help="Months as YYYY-MM (space separated).")
    ap.add_argument("--rows", type=int, default=2000, help="Rows per month.")
    ap.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    seq = 1
    for ym in args.months:
        year, month = (int(x) for x in ym.split("-"))
        df = generate_month(year, month, args.rows, rng, seq)
        seq += args.rows
        out = OUT_DIR / f"sample_raw_{year}_{month:02d}.xlsx"
        df.to_excel(out, index=False)
        print(f"Wrote {out}  ({len(df)} rows)")


if __name__ == "__main__":
    main()
