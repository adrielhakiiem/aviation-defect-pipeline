# Aviation Defect Pipeline

A Python ETL pipeline for cleaning and classifying ground-support-equipment
(GSE) defect exports. It reads Excel files, applies configurable rules,
stores cleaned records in SQLite, and exports an Excel master file.

The repository contains synthetic sample data only. No operational data is
included.

## Process

Each monthly input is:

1. Standardized for text and source column names.
2. Reconciled using equipment codes and asset numbers.
3. Classified by equipment type, problem area, failure mode, and record class.
4. Split into defect, non-defect, and routine inspection records.
5. Validated before loading.
6. Merged into SQLite using a composite key.
7. Exported to Excel with summary tables.

Rows with missing or conflicting equipment identifiers are retained and marked
for review. Duplicate records are skipped when a month is rerun.

## Setup and usage

Install the dependencies:

```bash
pip install -r requirements.txt
```

Generate sample exports if needed:

```bash
python generate_sample_data.py
```

Process one month:

```bash
python add_month.py data/sample_raw/sample_raw_2026_01.xlsx
```

Process all bundled sample months:

```bash
for file in data/sample_raw/sample_raw_*.xlsx; do
  python add_month.py "$file"
done
```

Generated files are written to `data/output/`:

- `defects.db`: SQLite master database.
- `EDR_MASTER.xlsx`: master records and summary tables.

## Repository structure

```text
aviation-defect-pipeline/
├── config.py               # keyword maps and configuration
├── pipeline.py             # cleaning, reconciliation, and classification
├── database.py             # SQLite storage, queries, and Excel export
├── add_month.py            # monthly pipeline entry point
├── validate.py             # data-quality checks
├── generate_sample_data.py # synthetic input generator
├── data/
│   ├── sample_raw/         # synthetic monthly exports
│   └── output/             # generated database and workbook
├── docs/DATA_DICTIONARY.md # column definitions
└── tests/test_pipeline.py  # tests
```

Classification rules can be updated in [`config.py`](config.py). Column
definitions are documented in
[`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md).

## Tests

```bash
pytest -q
```

## Dependencies

Python, pandas, SQLite, openpyxl, and pytest.

## License

MIT. See [LICENSE](LICENSE).
