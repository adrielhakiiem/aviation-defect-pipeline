# Data Dictionary

Two schemas: the **raw export** that goes in, and the **cleaned master** that comes out.

---

## Raw export (input) — 9 columns

As produced by the CMMS / maintenance system. Messy by nature: free text,
missing values, inconsistent spelling.

| Column | Description |
|---|---|
| `Permit No.` | Work-order / permit reference. |
| `Work Status` | Open / Closed / In Progress / Cancelled. |
| `Work Order Description` | Free text. Usually prefixed with the equipment identifier, e.g. `10477. - TYRE REAR PUNCTURED`. |
| `Work Order Type` | Breakdown / Corrective / Inspection / Projects / Accident. |
| `Received Date` | Timestamp the job was logged. |
| `Asset Number` | Equipment asset number. **~12% missing.** |
| `Asset Description` | Free-text equipment name, e.g. `ACFT NB TUG (B737-800)`. |
| `Action Taken` | Free text; often blank. |
| `Work Order Trade` | Trade group that handled the job. |

---

## Cleaned master (output) — 18 columns

Produced by `pipeline.py`. The first columns are cleaned source fields; the
**bold** ones are *derived* — they did not exist in the raw data and are the
analytical value this project adds.

| Column | Source | Description |
|---|---|---|
| `Permit No` | raw | Trimmed permit reference. |
| `Work Status` | raw | Normalised status. |
| `Equipment Code` | **derived** | Identifier extracted from the description prefix. |
| `Asset Number` | raw | Asset number as given. |
| `Asset Description` | raw | Trimmed equipment name. |
| `Defects Description` | **derived** | The description with the code prefix stripped off — the actual defect text. |
| `Work Order Type` | raw | Normalised type. |
| `Work Order Trade` | raw | Normalised trade. |
| `Action Taken` | raw | As given. |
| `Date` | **derived** | `Received Date` parsed to a date. |
| `By Month` | **derived** | Month name, for time grouping. |
| **`Equipment ID`** | **derived** | Single reconciled identifier (merges `Equipment Code` + `Asset Number`). |
| **`Equipment ID Status`** | **derived** | How the ID was resolved: `Match`, `Single Source`, `Auto-resolved (KLIA)`, `Conflict`, `Missing`. |
| **`Equipment Type`** | **derived** | One of ~25 GSE types, from `Asset Description` keywords. `Unclassified` when no rule matches. |
| **`Motorized/Non-Motorized`** | **derived** | Powered vs manual, from `Equipment Type`. |
| **`Problem Area`** | **derived** | What system failed (Tyres & Wheels, Engine, Electrical…), from defect-text keywords. |
| **`Failure Mode`** | **derived** | How it failed (Puncture, Leak, Won't Start…), from defect-text keywords. |
| **`Record Class`** | **derived** | `Defect` vs `Defect Found at Inspection` (routine inspection hits are separated). |

---

## Review / QA outputs

| Sheet | What it holds |
|---|---|
| `QA Summary` | Row counts and per-stage metrics for the month. |
| `Equipment ID Review` | Rows with a **Conflict** or **Missing** ID — kept, flagged, never guessed. |
| `Non-Defect Removed` | Ops-support / admin rows (standby, washing, licensing) excluded from the defect master. |
| `Inspection Removed` | Routine inspection / servicing rows with no actual defect, excluded from the master. (Inspections that *found* a defect stay in the master, tagged `Defect Found at Inspection`.) |

---

## Classification value sets

All keyword rules live in [`config.py`](../config.py) and are the only thing
you edit to tune classification.

- **Equipment Type** → `EQUIPMENT_TYPE_RULES`
- **Motorized/Non-Motorized** → `NON_MOTORIZED_TYPES`
- **Problem Area** → `PROBLEM_AREA_RULES`
- **Failure Mode** → `FAILURE_MODE_RULES`
- **Record Class** → `INSPECTION_KEYWORDS`
- **Spelling fixes** → `SPELLING_MAP`
- **Manual ID corrections** → `EQUIPMENT_ID_OVERRIDES`
