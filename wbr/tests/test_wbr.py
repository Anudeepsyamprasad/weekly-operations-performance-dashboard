"""
Checks that the WBR numbers are right.
  - Small hand-made data: KPI math, partial weeks, bad-row handling.
  - The real project data: it reconciles to every figure v1 published.
Run:  pytest wbr/tests
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

WBR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WBR_DIR))
import refresh_wbr  # noqa: E402

HEADER = "task_id,task_date,team_name,task_category,tasks_assigned,tasks_completed,errors_found,status\n"
TARGETS = """metric,target_pct,direction
completion_rate_pct,95.00,higher_is_better
error_rate_pct,10.00,lower_is_better
"""


def small_dataset() -> str:
    """Two complete weeks and one 2-day week, one team, plus three bad rows."""
    rows, n = [], 0
    weeks = [(date(2026, 10, 5), 5, 18, 2), (date(2026, 10, 12), 5, 19, 4), (date(2026, 10, 19), 2, 19, 1)]
    for start, days, completed, errors in weeks:
        for d in range(days):   # per day: 20 assigned, `completed` done, `errors` errors
            n += 1
            day = (start + timedelta(days=d)).isoformat()
            rows.append(f"T{n},{day},Alpha,Annotation,20,{completed},{errors},Partially Completed")
    rows.append(f"T{n},2026-10-13,Alpha,Annotation,20,19,4,Partially Completed")   # duplicate ID
    rows.append("B1,2026-10-13,,Annotation,10,10,1,Completed")                     # missing team
    rows.append("B2,2026-10-13,Alpha,Annotation,10,12,1,Completed")                # completed > assigned
    return HEADER + "\n".join(rows) + "\n"


@pytest.fixture()
def small(tmp_path):
    (tmp_path / "raw.csv").write_text(small_dataset())
    (tmp_path / "targets.csv").write_text(TARGETS)
    con = duckdb.connect()
    refresh_wbr.load_data(con, tmp_path / "raw.csv", tmp_path / "targets.csv")
    return refresh_wbr.build_wbr(con)


@pytest.fixture(scope="module")
def project():
    con = duckdb.connect()
    refresh_wbr.load_data(con, WBR_DIR / "data/operations_tasks_raw.csv", WBR_DIR / "data/targets.csv",
                          WBR_DIR / "data/v1_published_figures.csv")
    return refresh_wbr.build_wbr(con)


def test_bad_rows_are_flagged_and_excluded(small):
    assert set(small["issues"]["check_name"]) == {"duplicate_task_id", "missing_critical_field", "impossible_total"}
    assert len(small["clean"]) == 12                     # 5 + 5 + 2 good daily rows


def test_weekly_kpis_wow_and_partial_week(small):
    w1, w2, w3 = (small["trend"].iloc[i] for i in range(3))
    assert w1["completion_rate_pct"] == 90.00            # 90 / 100
    assert w1["error_rate_pct"] == pytest.approx(11.11)  # 10 / 90
    assert w2["error_rate_pct"] == pytest.approx(21.05)  # 20 / 95
    assert w2["error_wow_pp"] == pytest.approx(9.94)     # 21.05 - 11.11
    assert bool(w2["completion_met_target"])             # 95 >= 95
    assert not bool(w3["is_complete_week"])              # only 2 days
    assert w3["error_wow_pp"] != w3["error_wow_pp"]      # NaN: partial weeks are not compared


def test_project_data_reconciles_to_v1(project):
    rec = project["reconciliation"]
    mismatches = rec[rec["status"] != "match"]
    # Everything matches except the Weekly_Metrics error rates, which v1 divided by tasks assigned
    assert set(mismatches["v1_source"]) == {"Weekly_Metrics tab"}
    assert set(mismatches["metric"]) == {"error_rate_pct"}
    assert (rec["status"] == "match").sum() == 13


def test_project_dive_deep_finds_the_planted_issue(project):
    top = project["drivers"].iloc[0]
    assert (top["team_name"], top["task_category"]) == ("Gamma", "Data Validation")
    assert top["excess_errors"] > 0
