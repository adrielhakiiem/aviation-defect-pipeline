# Aviation Defect Pipeline

A rule-based ETL pipeline that turns messy ground-support-equipment (GSE)
defect exports into a clean, classified, analysis-ready dataset — built so a
**non-technical successor can run it every month with a single command**.

Python + SQLite. No machine learning, no cloud, no new tooling to learn —
deliberately. The hard part here is not the algorithm; it's the *data
judgment*: handling missing identifiers, conflicting keys, inconsistent free
text and routine-vs-real defects in a way that is transparent and auditable.

> **Note on data:** This repository ships **100% synthetic sample data** that
> reproduces the shape and messiness of the real dataset. No real operational
> data is included. The pipeline and logic are the real thing.

---

## What it does

Raw maintenance export  →  clean  →  reconcile  →  classify  →  SQLite  →  Excel for Power BI

```
  raw .xls/.xlsx                 pipeline.py                 database.py
 ┌──────────────┐   clean +   ┌──────────────┐   merge +   ┌──────────────┐
 │ 9 messy cols │ ─classify─► │ 18 clean cols│ ─dedupe───► │  SQLite DB   │
 │ free text,   │             │ + 6 derived  │  (composite │  + Excel     │
 │ nulls, typos │             │   columns    │     key)    │  master      │
 └──────────────┘             └──────────────┘             └──────────────┘
        │                             │
        └── non-defects & ID conflicts kept and flagged, never dropped ──┘
```

**Six derived columns** are added from free text using editable keyword rules:
`Equipment ID`, `Equipment Type`, `Motorized/Non-Motorized`, `Problem Area`,
`Failure Mode`, `Record Class`. (See [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md).)

---

## Highlights

- **Consolidated ~16,000 raw work-orders into ~7,300 analysis-ready defect
  records** by rule-based cleaning and separating non-defect (ops-support)
  rows, cutting noise ~55% without losing traceability.
- **Classified 100% of records into Equipment Type, Problem Area and Failure
  Mode using 260+ auditable keyword rules** — no black-box model, so any
  stakeholder can see exactly why a record was categorised the way it was.
- **Retained ~8% of records with missing identifiers (≈1,400 rows) by flagging
  instead of dropping**, surfacing data-quality gaps as a metric rather than
  hiding them.
- **Reconciled a composite business key (Date + Equipment ID + Defect)** so the
  same equipment logged multiple times a day is handled correctly and monthly
  re-runs are idempotent (safe to repeat).
- **Designed for handover:** all business logic lives in one plain-English
  config file; a successor edits dictionaries, not code.

---

## Design principles

**1. Flag, don't drop.** Rows with missing or conflicting identifiers (~8–15%)
are kept and routed to a review table, not silently deleted. Silent data loss
is the most dangerous kind.

**2. Surface data quality, don't hide it.** Missing IDs, typos and non-defect
rows are counted in a QA summary every run, so problems are visible and
accountable.

**3. Conflicts are flagged, never guessed.** When an equipment code and asset
number genuinely disagree, the row is marked `Conflict` for a human — unless a
confirmed correction exists in `EQUIPMENT_ID_OVERRIDES`, which persists across
every rerun.

**4. Clarity over cleverness.** The stack is intentionally simple so the people
who inherit it can actually maintain it. Complexity was added only where the
data demanded it.

---

## Quickstart

```bash
# 1. install
pip install -r requirements.txt

# 2. generate synthetic sample exports (3 months)
python generate_sample_data.py

# 3. clean + classify + merge one month into the master
python add_month.py data/sample_raw/sample_raw_2026_01.xlsx

# 4. add the next month (re-running any month is safe — duplicates are skipped)
python add_month.py data/sample_raw/sample_raw_2026_02.xlsx
```

Outputs land in `data/output/`:
- `defects.db` — the SQLite master database
- `EDR_MASTER.xlsx` — the master table + summary queries, ready for Power BI

Run the tests:

```bash
pytest -q
```

---

## The monthly workflow (for a new intern)

Each month, you get one new raw export. You run **one command**:

```bash
python add_month.py path/to/next_month.xlsx
```

It cleans and classifies the file, validates it, and merges only the *new*
rows into the master (de-duplicating on the composite key). It prints a QA
summary and tells you how many rows need Equipment ID review. That's it.

To improve classification, edit [`config.py`](config.py) — add a keyword to the
relevant list. No other code changes needed.

---

## Repository layout

```
aviation-defect-pipeline/
├── config.py               # ALL business rules (keyword maps) — edit this
├── pipeline.py             # clean + reconcile + classify
├── database.py             # SQLite load / merge / dedupe / queries / export
├── add_month.py            # the one-command monthly entry point
├── validate.py             # data-quality checks (run before every merge)
├── generate_sample_data.py # synthetic raw-data generator
├── data/
│   ├── sample_raw/         # synthetic monthly exports (safe to practise on)
│   └── output/             # generated DB + master (git-ignored)
├── docs/DATA_DICTIONARY.md # every column explained
└── tests/test_pipeline.py  # pytest suite
```

---

## Where this would go next (at production scale)

Kept out of scope on purpose — this dataset is single-site, monthly-batch and
one table, so the simple stack is the correct choice. At larger scale the
natural next steps would be: orchestration (Airflow/Prefect), a warehouse
(BigQuery/Snowflake) with dbt for the transforms, and automated ingestion from
the CMMS API instead of manual Excel exports. The architecture here maps
cleanly onto that path.

---

## Tech

Python (pandas) · SQLite · pytest · Excel I/O (openpyxl) · Power BI (downstream)

## License

MIT — see [LICENSE](LICENSE).
