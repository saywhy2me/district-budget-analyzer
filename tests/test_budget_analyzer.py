"""Tests for the District Budget & Account Variance Analyzer."""

import pandas as pd
import pytest

from src.budget_analyzer import (
    ValidationError,
    compute_variance,
    flag_exceptions,
    fund_rollup,
    load_to_sqlite,
    summarize,
    validate,
)


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


def test_fund_rollup_groups_by_fund():
    conn = load_to_sqlite(validate(_frame()))
    rollup = fund_rollup(conn)
    conn.close()
    gf = rollup[rollup["fund"] == "01 General Fund"].iloc[0]
    assert gf["budget"] == 150000   # 100000 + 50000
    assert gf["actual"] == 150000   # 95000 + 55000


def test_summary_net_variance():
    s = summarize(validate(_frame()))
    assert s.line_count == 3
    assert s.total_budget == 230000
    assert s.total_actual == 220000
    assert s.net_variance == -10000
