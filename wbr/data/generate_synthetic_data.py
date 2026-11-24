"""
Generate synthetic task-level data for the WBR, consistent with v1.

v1 (the Google Sheets dashboard) only published totals for 4 weeks
(21 Sep - 12 Oct 2026). This script rebuilds task-level rows that add up
EXACTLY to every v1 number, and adds 8 earlier weeks as history:

  v1 weekly totals   325/305/20, 335/311/24, 315/291/21, 150/138/11
  v1 team totals     Alpha 455/430/27, Beta 385/361/24, Gamma 285/254/25
  v1 category        Data Validation error rate 9.84% (the highest)

Each row = one team, one task category, one working day.
Same 3 teams and 3 categories as v1. Fixed random seed: same output every run.

Planted on purpose, so the WBR has something to find:
  - From 21 Sep, Team Gamma's Data Validation errors step up.
  - The week of 12 Oct only has 2 working days of data (as in v1).
  - Four bad rows (duplicate ID, missing team, completed > assigned,
    negative count). They are excluded, so v1 totals still reconcile.

Run:  python wbr/data/generate_synthetic_data.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

random.seed(7)
OUT_FILE = Path(__file__).parent / "operations_tasks_raw.csv"

TEAMS = ["Alpha", "Beta", "Gamma"]
CATEGORIES = ["Annotation", "Quality Review", "Data Validation"]

# ---------------------------------------------------------------------------
# Part 1: the v1 window, solved so it matches v1's published totals exactly
# ---------------------------------------------------------------------------
V1_WEEKS = [date(2026, 9, 21), date(2026, 9, 28), date(2026, 10, 5), date(2026, 10, 12)]
V1_WEEK_DAYS = [5, 5, 5, 2]                   # the last week is partial in v1
V1_WEEK_TOTALS = [(325, 305, 20), (335, 311, 24), (315, 291, 21), (150, 138, 11)]
V1_TEAM_TOTALS = {"Alpha": (455, 430, 27), "Beta": (385, 361, 24), "Gamma": (285, 254, 25)}
DV_COMPLETED, DV_ERRORS = 244, 24            # 24 / 244 = 9.84%

CATEGORY_SHARE = {"Annotation": 0.45, "Quality Review": 0.30, "Data Validation": 0.25}
TEAM_COMPLETION = {"Alpha": 0.945, "Beta": 0.938, "Gamma": 0.891}
PLANNED_ERROR_RATE = {  # what each segment's error rate "should" look like
    ("Alpha", "Annotation"): 0.05, ("Alpha", "Quality Review"): 0.05, ("Alpha", "Data Validation"): 0.07,
    ("Beta", "Annotation"): 0.05, ("Beta", "Quality Review"): 0.06, ("Beta", "Data Validation"): 0.07,
    ("Gamma", "Annotation"): 0.06, ("Gamma", "Quality Review"): 0.06, ("Gamma", "Data Validation"): 0.20,
}


def solve_v1_window() -> dict:
    """Integer program: find week x team x category counts that hit every v1 total."""
    cells = [(w, t, k) for w in range(4) for t in TEAMS for k in CATEGORIES]
    n = len(cells)
    # variables: a (assigned), c (completed), e (errors) per cell, then |deviation| helpers
    A, C, E, DA, DC, DE = (i * n for i in range(6))
    nvars = 6 * n
    rows, lo, hi = [], [], []

    def add(coefs: dict, low: float, high: float) -> None:
        row = np.zeros(nvars)
        for idx, v in coefs.items():
            row[idx] += v
        rows.append(row)
        lo.append(low)
        hi.append(high)

    for w, (wa, wc, we) in enumerate(V1_WEEK_TOTALS):
        idx = [i for i, cell in enumerate(cells) if cell[0] == w]
        add({A + i: 1 for i in idx}, wa, wa)
        add({C + i: 1 for i in idx}, wc, wc)
        add({E + i: 1 for i in idx}, we, we)
    for t, (ta, tc, te) in V1_TEAM_TOTALS.items():
        idx = [i for i, cell in enumerate(cells) if cell[1] == t]
        add({A + i: 1 for i in idx}, ta, ta)
        add({C + i: 1 for i in idx}, tc, tc)
        add({E + i: 1 for i in idx}, te, te)
    dv = [i for i, cell in enumerate(cells) if cell[2] == "Data Validation"]
    add({C + i: 1 for i in dv}, DV_COMPLETED, DV_COMPLETED)
    add({E + i: 1 for i in dv}, DV_ERRORS, DV_ERRORS)
    # Data Validation must stay the highest-error category (each other one <= 8%)
    for k in ["Annotation", "Quality Review"]:
        idx = [i for i, cell in enumerate(cells) if cell[2] == k]
        coefs = {E + i: 1 for i in idx}
        coefs.update({C + i: -0.08 for i in idx})
        add(coefs, -np.inf, 0)

    total_a = sum(x[0] for x in V1_WEEK_TOTALS)
    for i, (w, t, k) in enumerate(cells):
        add({C + i: 1, A + i: -1}, -np.inf, 0)               # completed <= assigned
        add({E + i: 1, C + i: -1}, -np.inf, 0)               # errors <= completed
        add({C + i: 1, A + i: -0.80}, 0, np.inf)              # completed >= 80% of assigned
        target_a = V1_WEEK_TOTALS[w][0] * V1_TEAM_TOTALS[t][0] / total_a * CATEGORY_SHARE[k]
        add({DA + i: 1, A + i: -1}, -target_a, np.inf)        # DA >= |a - target|
        add({DA + i: 1, A + i: 1}, target_a, np.inf)
        add({DC + i: 1, C + i: -1, A + i: TEAM_COMPLETION[t]}, 0, np.inf)
        add({DC + i: 1, C + i: 1, A + i: -TEAM_COMPLETION[t]}, 0, np.inf)
        p = PLANNED_ERROR_RATE[(t, k)]
        add({DE + i: 1, E + i: -1, C + i: p}, 0, np.inf)
        add({DE + i: 1, E + i: 1, C + i: -p}, 0, np.inf)

    objective = np.concatenate([np.zeros(3 * n), np.ones(n), np.full(n, 2.0), np.full(n, 3.0)])
    integrality = np.concatenate([np.ones(3 * n), np.zeros(3 * n)])
    lower = np.concatenate([np.ones(n), np.zeros(5 * n)])  # at least 1 task per cell
    result = milp(objective, integrality=integrality, bounds=Bounds(lower, np.inf),
                  constraints=LinearConstraint(np.array(rows), lo, hi))
    if not result.success:
        raise SystemExit(f"Could not match v1 totals: {result.message}")
    x = np.round(result.x).astype(int)
    return {cell: (x[A + i], x[C + i], x[E + i]) for i, cell in enumerate(cells)}


def split(total: int, parts: int) -> list[int]:
    """Split an integer into `parts` roughly equal, slightly random integers."""
    weights = [random.uniform(0.8, 1.2) for _ in range(parts)]
    raw = [total * w / sum(weights) for w in weights]
    out = [int(r) for r in raw]
    for i in sorted(range(parts), key=lambda i: raw[i] - out[i], reverse=True)[: total - sum(out)]:
        out[i] += 1
    return out


def split_capped(total: int, caps: list[int]) -> list[int]:
    """Split `total` across days without any day going over its cap."""
    out = [0] * len(caps)
    for _ in range(total):
        options = [i for i in range(len(caps)) if out[i] < caps[i]]
        out[random.choice(options)] += 1
    return out


def daily_rows(week_start: date, days: int, team: str, cat: str, a: int, c: int, e: int) -> list[dict]:
    assigned = split(a, days)
    completed = split_capped(c, assigned)
    errors = split_capped(e, completed)
    rows = []
    for d in range(days):
        rows.append({
            "task_date": (week_start + timedelta(days=d)).isoformat(),
            "team_name": team,
            "task_category": cat,
            "tasks_assigned": assigned[d],
            "tasks_completed": completed[d],
            "errors_found": errors[d],
            "status": "Completed" if completed[d] == assigned[d] else "Partially Completed",
        })
    return rows


# ---------------------------------------------------------------------------
# Part 2: 8 weeks of earlier history (27 Jul - 14 Sep), before the issue
# ---------------------------------------------------------------------------
HISTORY_WEEKS = [date(2026, 7, 27) + timedelta(weeks=i) for i in range(8)]
TEAM_SHARE = {"Alpha": 0.40, "Beta": 0.34, "Gamma": 0.26}
BASELINE_ERROR_RATE = {"Annotation": 0.05, "Quality Review": 0.05, "Data Validation": 0.07}


def history_rows() -> list[dict]:
    rows = []
    for week in HISTORY_WEEKS:
        weekly_volume = random.randint(315, 340)
        for t in TEAMS:
            for k in CATEGORIES:
                a = round(weekly_volume * TEAM_SHARE[t] * CATEGORY_SHARE[k])
                c = min(a, round(a * random.uniform(TEAM_COMPLETION[t] - 0.015, TEAM_COMPLETION[t] + 0.015)))
                rate = BASELINE_ERROR_RATE[k] + (0.01 if t == "Gamma" else 0)
                e = max(0, min(c, round(c * rate + random.gauss(0, 0.3))))
                rows.extend(daily_rows(week, 5, t, k, a, c, e))
    return rows


def main() -> None:
    rows = history_rows()
    for (w, t, k), (a, c, e) in sorted(solve_v1_window().items()):
        rows.extend(daily_rows(V1_WEEKS[w], V1_WEEK_DAYS[w], t, k, a, c, e))
    rows.sort(key=lambda r: (r["task_date"], r["team_name"], r["task_category"]))
    for i, row in enumerate(rows, start=1):
        row["task_id"] = f"T{i:05d}"

    # Planted bad rows (excluded by the checks, so v1 totals still reconcile)
    bad_day = "2026-10-07"
    n = len(rows)
    rows.append(dict(rows[-1]))                                         # duplicate task_id
    rows.append({"task_id": f"T{n + 1:05d}", "task_date": bad_day, "team_name": "",
                 "task_category": "Annotation", "tasks_assigned": 30, "tasks_completed": 28,
                 "errors_found": 1, "status": "Completed"})            # missing team
    rows.append({"task_id": f"T{n + 2:05d}", "task_date": bad_day, "team_name": "Beta",
                 "task_category": "Quality Review", "tasks_assigned": 20, "tasks_completed": 26,
                 "errors_found": 2, "status": "Completed"})            # completed > assigned
    rows.append({"task_id": f"T{n + 3:05d}", "task_date": bad_day, "team_name": "Alpha",
                 "task_category": "Annotation", "tasks_assigned": -5, "tasks_completed": 0,
                 "errors_found": 0, "status": "Completed"})            # negative count

    fields = ["task_id", "task_date", "team_name", "task_category",
              "tasks_assigned", "tasks_completed", "errors_found", "status"]
    with OUT_FILE.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()
