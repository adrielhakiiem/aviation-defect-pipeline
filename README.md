# Aviation Defect Pipeline

A Python ETL pipeline for cleaning and classifying ground-support-equipment
(GSE) defect exports. It reads Excel files, applies configurable rules,
stores cleaned records in SQLite, and exports an Excel master file.

The repository contains synthetic sample data only. No operational data is
included.

## How it works

```text
Monthly Excel export
   |
   v
  add_month.py
   |
   v
 Clean and standardize text
   |
   v
 Match equipment codes and asset numbers
   |
   v
 Classify equipment and defect details
   |
   v
 Validate the cleaned records
   |
   v
 Add new records to data/output/defects.db
   |
   v
 Write data/output/EDR_MASTER.xlsx
```

The database keeps the accumulated records. The Excel workbook is regenerated
after every successful run.

## What you need to do

### First run

1. Install Python.
2. Open a terminal in this project folder.
3. Install the project dependencies:

```bash
pip install -r requirements.txt
```

If you are using the included sample data, generate the monthly files:

```bash
python generate_sample_data.py
```

### Each month

Put the new Excel export in `data/sample_raw/`, then run one command. For
example:

```bash
python add_month.py data/sample_raw/sample_raw_2026_01.xlsx
```

Replace the filename with the new month. The command adds that month to the
existing master; it does not replace earlier months.

To process all bundled sample months in order:

```bash
for file in data/sample_raw/sample_raw_*.xlsx; do
  python add_month.py "$file"
done
```

### Results

After the command finishes, open these files:

- `defects.db`: SQLite master database.
- `EDR_MASTER.xlsx`: master records and summary tables.

The command also prints validation results, inserted rows, duplicate rows, and
records that need equipment ID review.

## Why use the terminal?

This project is a Python script rather than a desktop application. The
terminal is the control panel: you provide the input filename, and the script
does the cleaning, validation, database update, and Excel export. You do not
need to run each internal step separately.

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
