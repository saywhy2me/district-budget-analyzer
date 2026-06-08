# District Budget & Account Variance Analyzer

A small, runnable tool that mirrors the day-to-day work of a school-district
**Fiscal Services / Accountant** role: load a chart of accounts, verify account
balances, compare actual spending against the adopted budget, flag compliance
exceptions, and produce a clean report for non-technical reviewers.

> Built by **Brandon Bradley** as supporting portfolio material for the
> Vacaville Unified School District **Accountant – Fiscal Services** position
> (Job No. 26-2208). It demonstrates hands-on ability with budget reconciliation,
> variance analysis, and automated financial reporting using Python, SQL, and Excel.

---

## What it does

Given a CSV of budget lines (fund, account, adopted budget, actual expenditures),
the analyzer:

1. **Loads** the data into a SQLite database (a real relational ledger).
2. **Reconciles** account balances and validates that the data is internally
   consistent (no negative budgets, no orphan accounts, numbers parse cleanly).
3. **Computes variance** — dollar and percent — of actuals vs. budget for every
   line and rolled up by fund.
4. **Flags exceptions** for review:
   - **OVER BUDGET** — actual exceeds the adopted budget.
   - **WATCH** — spending is within a configurable threshold of the budget
     (default 90%), so it may need attention before year-end.
5. **Reports** the results to the console and to a formatted **Excel workbook**
   (and CSV), with conditional highlighting on the flagged rows.

This maps directly to the posted job duties: *"ensuring that overall fiscal
policies meet compliance requirements; maintaining accurate account balances;
evaluating feasibility of services within budget parameters; ... providing
financial information, guidance and recommendations."*

---

## Quick start

```bash
# 1. (optional) create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # macOS / Linux

# 2. install dependencies
pip install -r requirements.txt

# 3. run the analyzer on the bundled sample data
python -m src.budget_analyzer --input data/sample_budget.csv --out reports

# 4. (optional) run the tests
python -m pytest -q
```

Output is written to `reports/budget_report.xlsx` and `reports/budget_report.csv`,
and a summary is printed to the terminal.

---

## Sample input

`data/sample_budget.csv` uses the kind of fund/object-code structure common to
California K-12 districts (General Fund, Cafeteria, etc.):

| fund | account | description | budget | actual |
|------|---------|-------------|--------|--------|
| 01 General Fund | 1000 | Certificated Salaries | 4,200,000 | 4,050,000 |
| 01 General Fund | 4300 | Materials & Supplies | 180,000 | 201,500 |
| 13 Cafeteria | 4700 | Food | 950,000 | 905,000 |

(Figures are illustrative and contain no real district data.)

---

## Example output

```
=== District Budget Variance Summary ===
Lines analyzed: 12   |   Total budget: $9,930,000.00   |   Total actual: $9,714,800.00
Net variance: $215,200.00 under budget (2.17%)

FLAGGED FOR REVIEW
  [OVER BUDGET] 01 General Fund / 4300 Materials & Supplies  +$21,500.00 (+11.9%)
  [OVER BUDGET] 13 Cafeteria Fund / 4300 Supplies  +$7,300.00 (+16.2%)
  [OVER BUDGET] 40 Capital Outlay / 6170 Land Improvements  +$55,000.00 (+18.0%)
  [WATCH]       01 General Fund / 5800 Prof & Operating Svcs  98.2% of budget used
...
Report written to reports/budget_report.xlsx
```

---

## Project structure

```
district-budget-analyzer/
├── README.md
├── requirements.txt
├── data/
│   └── sample_budget.csv      # illustrative district budget lines
├── src/
│   ├── __init__.py
│   └── budget_analyzer.py     # load -> reconcile -> variance -> report
└── tests/
    └── test_budget_analyzer.py
```

## Notes

- All sample numbers are fabricated for demonstration. No confidential or real
  district financial data is included.
- The `WATCH` threshold and output paths are configurable via command-line flags
  (`--threshold`, `--out`). Run `python -m src.budget_analyzer --help`.
- For scheduled/CI use, add `--fail-on-over` to make the tool exit non-zero
  (code `2`) whenever any line is **OVER BUDGET**, so an automated fiscal check
  can fail the pipeline when an account breaches its adopted budget.
