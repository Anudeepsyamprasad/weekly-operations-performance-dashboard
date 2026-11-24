# Walkthrough: explaining the WBR in an interview

A plain-language tour of the code, in the order it runs. Read it with the
files open next to it.

## The 30-second version

"v1 was a Google Sheets snapshot: 4 weeks, and it flagged Team Gamma and Data
Validation. v2 makes that a weekly routine. One command validates the raw
data, keeps bad rows out, calculates the KPIs against targets, finds which team
and category drove the increase in errors, and writes the WBR pack. While
building it, I reconciled every number v1 had published and found that one tab
used a different error-rate formula from the rest. GitHub Actions runs it every
Monday, and unit tests check the math."

## Step by step

**1. Load (`refresh_wbr.py`, `load_data`)**
Reads three CSV files into tables: raw task data, targets, and v1's published
figures. DuckDB is a small database that runs inside Python, so the same SQL I
would run on PostgreSQL runs here on files.

**2. Validate first (`01_data_quality_checks.sql`)**
Four checks, glued together with `UNION ALL` so the result is one list of
problems: duplicate IDs (found with `ROW_NUMBER()`: any copy numbered 2 or
more is a duplicate), missing team or category, negative counts, and totals
that can't happen (more completed than assigned).
*Why first:* a WBR with wrong numbers is worse than a late WBR.

**3. Clean view (`02_clean_tasks_view.sql`)**
The same rules, reversed: keep only rows that pass. Every report reads from
this view, so no report can accidentally use bad rows.

**4. Weekly trend (`03_wbr_weekly_trend.sql`)**
- `DATE_TRUNC('week', ...)` groups days into Monday-start weeks.
- `COUNT(DISTINCT task_date)` counts working days. Under 5 = partial week.
  The week of 12 Oct has 2 days; comparing it with a full week would mislead,
  so it is shown but not compared.
- `LAG(rate) OVER (ORDER BY week_start)` gets last week's value, so
  "this week minus last week" = week-over-week change in percentage points.
- `AVG(...) OVER (... ROWS BETWEEN 3 PRECEDING AND CURRENT ROW)` = the
  4-week trailing average, which smooths out one noisy week.
- `NULLIF(x, 0)` avoids dividing by zero.

**5. Dive deep (`05_dive_deep_error_drivers.sql`)**
The question: errors went up, but where? A team doing more work makes more
errors even if quality is unchanged. So for each team and category, compare
the last 3 complete weeks with the 4 weeks before:

> expected errors = tasks completed in the last 3 weeks x the earlier error rate
> excess errors = actual errors - expected errors

A big positive number means quality really dropped there. The top row is
Gamma / Data Validation: its error rate doubled, and it explains 46% of the
extra errors. Why 3 weeks against 4, not one week against one: at about 20
Data Validation tasks a week for Gamma, a single week is too noisy to judge.

**6. Reconcile with v1 (`06_v1_reconciliation.sql`)**
Recomputes each of the 17 numbers v1 published and compares. 13 match. The 4
weekly error rates on the Weekly_Metrics tab don't: that tab divides errors by
tasks *assigned* (20 / 325 = 6.15%), while the headline 7.27% and the team
figures divide by tasks *completed* (20 / 305 = 6.56%). Same data, two
definitions. v2 uses one definition everywhere.

**7. Publish (`write_callouts`, `write_outputs`)**
Turns the top rows into sentences, then writes the Excel tabs, the charts, the
CSVs for new tabs in the Google Sheet, and the clean extract for BI tools.
Each chart shows one metric with its target as a dashed line; two metrics
never share one chart with two y-axes.

**8. Trust it (`tests/test_wbr.py`)**
A tiny dataset where I know the answers by hand (10 errors / 90 completed =
11.11%), plus tests that the project data still reconciles to v1 and that the
dive deep still finds Gamma / Data Validation. If someone changes the SQL and
breaks the math, the test fails before the WBR goes out.

## How the data was made (`data/generate_synthetic_data.py`)

v1 only published totals. To work at task level I needed rows that add up to
exactly those totals. The script solves that as a small integer program
(SciPy's `milp`): find counts per week, team and category that hit every
weekly total, every team total and the Data Validation total. Then it splits
them into days and adds 8 earlier weeks as a baseline. You don't need to
explain the solver in depth; "it rebuilds rows that reconcile to v1's totals"
is enough.

## Questions to be ready for

- *Why exclude bad rows instead of fixing them?* You don't guess at data.
  Exclude, report, and send the list to the data owner to fix at the source.
- *Which error-rate definition is right?* Errors ÷ completed: you can only
  make an error on work you did. The point is to pick one and use it everywhere.
- *Why percentage points, not percent?* 6% to 7% is +1 pp, but +16.7%.
  Saying "pp" removes the ambiguity.
- *What would you do with the Gamma finding?* Check what changed in that
  workflow around 21 Sep (a guideline update, a tool change, new joiners),
  confirm with the team lead, then track whether the rate recovers.
- *How would this run in production?* Point `load_data` at the real database
  instead of CSV files, keep the SQL, and schedule it.
