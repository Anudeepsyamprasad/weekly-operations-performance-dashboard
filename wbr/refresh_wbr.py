"""
Refresh the Weekly Business Review (WBR) in one command.

What it does, in order:
  1. Loads the raw task data, the KPI targets and v1's published figures.
  2. Runs data-quality checks. Bad rows are reported and kept OUT of the metrics.
  3. Runs the WBR SQL: weekly trend (WoW, 4-week average, vs target, partial
     weeks flagged), team view, error-driver dive deep, and a reconciliation
     of every figure the v1 Google Sheets dashboard published.
  4. Writes the outputs:
       outputs/WBR_<week>.xlsx       - one tab per section
       outputs/WBR_summary.md        - the written callouts
       outputs/charts/*.png          - trend and driver charts
       outputs/google_sheets/*.csv   - ready to import as new tabs in the v1 Sheet
       outputs/wbr_dataset_clean.csv - clean extract for QuickSight / Tableau

The SQL is PostgreSQL syntax. DuckDB runs it locally on the CSV files, so no
database server is needed.

Run:  python wbr/refresh_wbr.py
"""

from pathlib import Path

import duckdb
import matplotlib
import pandas as pd

matplotlib.use("Agg")  # draw charts to files, no screen needed
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).parent
DATA = HERE / "data"
SQL = HERE / "sql"
OUT = HERE / "outputs"
CHARTS = OUT / "charts"
SHEETS = OUT / "google_sheets"

LINE_COLOR = "#2a6fdb"     # the metric
TARGET_COLOR = "#8a8f98"   # the target line
TEXT_COLOR = "#3c4043"


def read_sql(name: str) -> str:
    return (SQL / name).read_text()


def load_data(con: duckdb.DuckDBPyConnection, raw_csv: Path, targets_csv: Path,
              v1_csv: Path | None = None) -> None:
    """Load the CSV files into tables named like the production schema."""
    con.execute("CREATE SCHEMA IF NOT EXISTS public")
    con.execute(f"""
        CREATE OR REPLACE TABLE public.operations_tasks_raw AS
        SELECT * FROM read_csv('{raw_csv}', header = true,
            columns = {{
                'task_id': 'VARCHAR', 'task_date': 'DATE', 'team_name': 'VARCHAR',
                'task_category': 'VARCHAR', 'tasks_assigned': 'INTEGER',
                'tasks_completed': 'INTEGER', 'errors_found': 'INTEGER', 'status': 'VARCHAR'
            }})
    """)
    con.execute(f"CREATE OR REPLACE TABLE public.wbr_targets AS SELECT * FROM read_csv('{targets_csv}', header = true)")
    if v1_csv is not None:
        con.execute(f"CREATE OR REPLACE TABLE public.v1_published AS SELECT * FROM read_csv('{v1_csv}', header = true)")


def build_wbr(con: duckdb.DuckDBPyConnection) -> dict:
    """Run every WBR query and return the results as DataFrames."""
    issues = con.execute(read_sql("01_data_quality_checks.sql")).df()
    con.execute(read_sql("02_clean_tasks_view.sql"))
    has_v1 = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'v1_published'"
    ).fetchone()[0]
    return {
        "issues": issues,
        "trend": con.execute(read_sql("03_wbr_weekly_trend.sql")).df(),
        "teams": con.execute(read_sql("04_wbr_team_latest_week.sql")).df(),
        "drivers": con.execute(read_sql("05_dive_deep_error_drivers.sql")).df(),
        "reconciliation": con.execute(read_sql("06_v1_reconciliation.sql")).df() if has_v1 else pd.DataFrame(),
        "clean": con.execute("SELECT * FROM public.operations_tasks ORDER BY task_date, task_id").df(),
        "raw_rows": con.execute("SELECT COUNT(*) FROM public.operations_tasks_raw").fetchone()[0],
    }


def write_callouts(wbr: dict) -> list[str]:
    """Turn the numbers into the sentences a WBR reader needs."""
    trend = wbr["trend"]
    complete = trend[trend["is_complete_week"]]
    latest = complete.iloc[-1]
    week = pd.Timestamp(latest["week_start"]).strftime("%d %b %Y")
    lines = [f"**Week of {week}** (latest complete week)", ""]

    met = "met" if latest["completion_met_target"] else "missed"
    lines.append(
        f"- Completion rate {latest['completion_rate_pct']:.2f}% "
        f"({latest['completion_wow_pp']:+.2f} pp WoW), {met} the "
        f"{latest['completion_target_pct']:.2f}% target."
    )
    met = "met" if latest["error_met_target"] else "missed"
    above = int((~complete.tail(3)["error_met_target"].astype(bool)).sum())
    lines.append(
        f"- Error rate {latest['error_rate_pct']:.2f}% "
        f"({latest['error_wow_pp']:+.2f} pp WoW), {met} the "
        f"{latest['error_target_pct']:.2f}% target; above target in {above} of the last 3 weeks "
        f"(4-week average {latest['error_4wk_avg_pct']:.2f}%)."
    )

    top = wbr["drivers"].iloc[0]
    if top["excess_errors"] > 0:
        lines.append(
            f"- Main driver: {top['team_name']} / {top['task_category']}. Its error rate went from "
            f"{top['baseline_error_rate_pct']:.2f}% (prior 4 weeks) to {top['current_error_rate_pct']:.2f}% "
            f"(last 3 weeks), explaining {top['share_of_excess_pct']:.0f}% of the extra errors. "
            f"Next step: check for a guideline or tooling change in this workflow."
        )

    partial = trend[~trend["is_complete_week"].astype(bool)]
    for _, row in partial.iterrows():
        lines.append(
            f"- Week of {pd.Timestamp(row['week_start']).strftime('%d %b')} has only "
            f"{row['days_reported']} of 5 working days, so it is shown but not compared WoW."
        )

    if len(wbr["issues"]):
        excluded = wbr["raw_rows"] - len(wbr["clean"])
        kinds = ", ".join(sorted(wbr["issues"]["check_name"].unique()))
        lines.append(
            f"- Data quality: {excluded} of {wbr['raw_rows']} raw rows were excluded after "
            f"{len(wbr['issues'])} failed checks ({kinds})."
        )

    rec = wbr["reconciliation"]
    if len(rec):
        matched = int((rec["status"] == "match").sum())
        lines.append(f"- v1 reconciliation: {matched} of {len(rec)} published v1 figures match.")
        bad = rec[rec["status"] != "match"]
        if len(bad):
            sources = ", ".join(sorted(bad["v1_source"].unique()))
            lines.append(
                f"  The {len(bad)} mismatches are all in the {sources}: it divides errors by tasks "
                f"assigned, while the rest of v1 divides by tasks completed. Fix that tab's formula."
            )
    return lines


def draw_trend_chart(trend: pd.DataFrame, column: str, target_col: str, title: str, path: Path) -> None:
    """One metric per chart, complete weeks only, target as a dashed line (never two y-axes)."""
    data = trend[trend["is_complete_week"].astype(bool)]
    fig, ax = plt.subplots(figsize=(8, 3.2), dpi=150)
    weeks = pd.to_datetime(data["week_start"])
    ax.plot(weeks, data[column], color=LINE_COLOR, linewidth=2, marker="o", markersize=4)
    ax.axhline(data[target_col].iloc[0], color=TARGET_COLOR, linewidth=1.2, linestyle="--")
    ax.text(weeks.iloc[0], data[target_col].iloc[0], "  target", va="bottom",
            color=TARGET_COLOR, fontsize=8)
    last = data.iloc[-1]
    ax.annotate(f"{last[column]:.2f}%", (weeks.iloc[-1], last[column]),
                textcoords="offset points", xytext=(6, 0), va="center",
                fontsize=9, color=TEXT_COLOR)
    ax.set_title(f"{title} (complete weeks)", loc="left", fontsize=11, color=TEXT_COLOR)
    ax.set_ylabel("%", color=TEXT_COLOR)
    ax.grid(axis="y", color="#e6e6e6", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=TEXT_COLOR, labelsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def draw_driver_chart(drivers: pd.DataFrame, path: Path) -> None:
    """Horizontal bars: excess errors by team / category, biggest at the top."""
    top = drivers.iloc[::-1]
    labels = top["team_name"] + " / " + top["task_category"]
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
    ax.barh(labels, top["excess_errors"], color=LINE_COLOR, height=0.6)
    ax.axvline(0, color=TEXT_COLOR, linewidth=0.8)
    for y, value in enumerate(top["excess_errors"]):
        ax.text(value, y, f" {value:+.1f} ", va="center",
                ha="left" if value >= 0 else "right", fontsize=8, color=TEXT_COLOR)
    ax.set_title("Excess errors: last 3 weeks vs the 4 weeks before", loc="left",
                 fontsize=11, color=TEXT_COLOR)
    ax.grid(axis="x", color="#e6e6e6", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=TEXT_COLOR, labelsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def write_outputs(wbr: dict, callouts: list[str]) -> Path:
    for folder in (OUT, CHARTS, SHEETS):
        folder.mkdir(exist_ok=True)
    complete = wbr["trend"][wbr["trend"]["is_complete_week"].astype(bool)]
    week = pd.Timestamp(complete.iloc[-1]["week_start"]).strftime("%Y-%m-%d")

    sections = {
        "Weekly Trend": wbr["trend"],
        "Teams (latest week)": wbr["teams"],
        "Dive Deep - Errors": wbr["drivers"],
        "v1 Reconciliation": wbr["reconciliation"],
        "Data Quality": wbr["issues"],
    }
    excel_path = OUT / f"WBR_{week}.xlsx"
    with pd.ExcelWriter(excel_path) as xl:
        pd.DataFrame({"WBR callouts": [c.replace("**", "").strip() for c in callouts if c]}).to_excel(
            xl, sheet_name="Summary", index=False)
        for name, df in sections.items():
            df.to_excel(xl, sheet_name=name, index=False)

    # Same sections as CSVs, named for new tabs in the v1 Sheet (File > Import > Insert new sheet)
    for name, df in sections.items():
        tab = "WBR_v2_" + name.split(" (")[0].replace(" - ", "_").replace(" ", "_")
        df.to_csv(SHEETS / f"{tab}.csv", index=False)

    draw_trend_chart(wbr["trend"], "completion_rate_pct", "completion_target_pct",
                     "Weekly completion rate vs target", CHARTS / "completion_rate_trend.png")
    draw_trend_chart(wbr["trend"], "error_rate_pct", "error_target_pct",
                     "Weekly error rate vs target", CHARTS / "error_rate_trend.png")
    draw_driver_chart(wbr["drivers"], CHARTS / "error_drivers.png")

    summary = ["# Weekly Business Review", ""] + callouts + [
        "", "![Completion rate](charts/completion_rate_trend.png)",
        "", "![Error rate](charts/error_rate_trend.png)",
        "", "![Error drivers](charts/error_drivers.png)",
        "", "_Synthetic data for demonstration. Generated by `refresh_wbr.py`._", ""]
    (OUT / "WBR_summary.md").write_text("\n".join(summary))

    wbr["clean"].to_csv(OUT / "wbr_dataset_clean.csv", index=False)
    return excel_path


def main() -> None:
    con = duckdb.connect()
    load_data(con, DATA / "operations_tasks_raw.csv", DATA / "targets.csv", DATA / "v1_published_figures.csv")
    wbr = build_wbr(con)
    callouts = write_callouts(wbr)
    excel_path = write_outputs(wbr, callouts)
    print("\n".join(callouts))
    print(f"\nWBR written to {excel_path.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
