"""Tests for the District Budget & Account Variance Analyzer."""

import pandas as pd
import pytest

from src.budget_analyzer import (
    ValidationError,
    compute_variance,
    flag_exceptions,
    format_fund_rollup,
    fund_rollup,
    load_to_sqlite,
    main,
    status_counts,
    summarize,
    validate,
)


def _write_csv(path, frame):
    frame.to_csv(path, index=False)
    return str(path)


def _frame():
    return pd.DataFrame(
        {
            "fund": ["01 General Fund", "01 General Fund", "13 Cafeteria"],
            "account": [1000, 4300, 4700],
            "description": ["Salaries", "Supplies", "Food"],
            "budget": [100000, 50000, 80000],
            "actual": [95000, 55000, 70000],
        }
    )


def test_validate_accepts_clean_data():
    df = validate(_frame())
    assert len(df) == 3
    assert df["budget"].dtype.kind in "if"


def test_validate_rejects_missing_column():
    df = _frame().drop(columns=["actual"])
    with pytest.raises(ValidationError):
        validate(df)


def test_validate_rejects_negative_budget():
    df = _frame()
    df.loc[0, "budget"] = -1
    with pytest.raises(ValidationError):
        validate(df)


def test_validate_rejects_duplicate_lines():
    df = _frame()
    df.loc[2, "fund"] = "01 General Fund"
    df.loc[2, "account"] = 1000  # now a duplicate of row 0
    with pytest.raises(ValidationError):
        validate(df)


def test_compute_variance_math():
    conn = load_to_sqlite(validate(_frame()))
    detail = compute_variance(conn)
    conn.close()
    supplies = detail[detail["account"] == 4300].iloc[0]
    assert supplies["variance"] == 5000          # 55000 - 50000
    assert supplies["variance_pct"] == 10.0       # 5000 / 50000


def test_flag_exceptions_classifies_statuses():
    conn = load_to_sqlite(validate(_frame()))
    detail = flag_exceptions(compute_variance(conn), threshold=0.90)
    conn.close()
    by_acct = detail.set_index("account")["status"].to_dict()
    assert by_acct[4300] == "OVER BUDGET"   # 55k > 50k
    assert by_acct[1000] == "WATCH"         # 95k is 95% of 100k
    assert by_acct[4700] == "OK"            # 70k is 87.5% of 80k -> under threshold


def test_watch_threshold_is_inclusive_boundary():
    # 72000 / 80000 = 0.90 exactly -> WATCH at threshold 0.90
    df = pd.DataFrame(
        {
            "fund": ["01 General Fund"],
            "account": [4700],
            "description": ["Food"],
            "budget": [80000],
            "actual": [72000],
        }
    )
    conn = load_to_sqlite(validate(df))
    detail = flag_exceptions(compute_variance(conn), threshold=0.90)
    conn.close()
    assert detail.set_index("account").loc[4700, "status"] == "WATCH"


def test_status_counts_covers_all_statuses():
    conn = load_to_sqlite(validate(_frame()))
    detail = flag_exceptions(compute_variance(conn), threshold=0.90)
    conn.close()
    counts = status_counts(detail)
    assert counts == {"OVER BUDGET": 1, "WATCH": 1, "OK": 1}
    # Every known status key is present even when its count is zero.
    assert set(counts) == {"OVER BUDGET", "WATCH", "OK"}


def test_fund_rollup_groups_by_fund():
    conn = load_to_sqlite(validate(_frame()))
    rollup = fund_rollup(conn)
    conn.close()
    gf = rollup[rollup["fund"] == "01 General Fund"].iloc[0]
    assert gf["budget"] == 150000   # 100000 + 50000
    assert gf["actual"] == 150000   # 95000 + 55000


def test_format_fund_rollup_lists_each_fund():
    conn = load_to_sqlite(validate(_frame()))
    rollup = fund_rollup(conn)
    conn.close()
    text = format_fund_rollup(rollup)
    assert "FUND ROLLUP" in text
    assert "01 General Fund" in text
    assert "13 Cafeteria" in text
    # header row + one row per fund (2 funds in the fixture)
    assert len(text.splitlines()) == 4


def test_format_fund_rollup_renders_negative_variance():
    # Single fund, actual under budget -> variance should show with a minus sign.
    df = pd.DataFrame(
        {
            "fund": ["01 General Fund"],
            "account": [1000],
            "description": ["Salaries"],
            "budget": [100000],
            "actual": [90000],
        }
    )
    conn = load_to_sqlite(validate(df))
    rollup = fund_rollup(conn)
    conn.close()
    assert "-$10,000.00" in format_fund_rollup(rollup)


def test_summary_net_variance():
    s = summarize(validate(_frame()))
    assert s.line_count == 3
    assert s.total_budget == 230000
    assert s.total_actual == 220000
    assert s.net_variance == -10000


def test_main_returns_zero_without_fail_flag(tmp_path):
    csv = _write_csv(tmp_path / "budget.csv", _frame())  # contains an OVER BUDGET line
    rc = main(["--input", csv, "--out", str(tmp_path / "reports")])
    assert rc == 0


def test_main_fail_on_over_returns_two(tmp_path):
    csv = _write_csv(tmp_path / "budget.csv", _frame())  # 4300 is over budget
    rc = main(["--input", csv, "--out", str(tmp_path / "reports"), "--fail-on-over"])
    assert rc == 2


def test_main_fail_on_over_passes_when_within_budget(tmp_path):
    clean = _frame()
    clean["actual"] = [80000, 40000, 60000]  # every line comfortably under budget
    csv = _write_csv(tmp_path / "budget.csv", clean)
    rc = main(["--input", csv, "--out", str(tmp_path / "reports"), "--fail-on-over"])
    assert rc == 0
