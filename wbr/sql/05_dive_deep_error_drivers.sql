-- Project: Weekly Operations Performance Dashboard - Automated WBR
-- Purpose: Dive deep - WHERE did the extra errors come from?
--
-- Compares the CURRENT period (the latest 3 complete weeks, the window v1
-- flagged) with a BASELINE (the 4 complete weeks before it), for every
-- team x task category. Several weeks per side, because one week of a small
-- team is too noisy to judge.
--
--     excess_errors = errors in current period
--                     - completed in current period x baseline error rate
--
-- This separates a real quality drop (the rate went up) from a busier
-- period (the volume went up). Segments at the top of the list are the
-- root-cause candidates to investigate first.

WITH complete_weeks AS (
    SELECT week_start,
           ROW_NUMBER() OVER (ORDER BY week_start DESC) AS weeks_ago   -- 1 = latest
    FROM public.operations_tasks
    GROUP BY week_start
    HAVING COUNT(DISTINCT task_date) >= 5
),
labelled AS (
    SELECT
        t.team_name,
        t.task_category,
        t.tasks_completed,
        t.errors_found,
        CASE WHEN w.weeks_ago <= 3 THEN 'current'
             WHEN w.weeks_ago <= 7 THEN 'baseline' END AS period
    FROM public.operations_tasks t
    JOIN complete_weeks w ON w.week_start = t.week_start
),
segments AS (
    SELECT
        team_name,
        task_category,
        SUM(CASE WHEN period = 'baseline' THEN tasks_completed END) AS baseline_completed,
        SUM(CASE WHEN period = 'baseline' THEN errors_found END)    AS baseline_errors,
        SUM(CASE WHEN period = 'current'  THEN tasks_completed END) AS current_completed,
        SUM(CASE WHEN period = 'current'  THEN errors_found END)    AS current_errors
    FROM labelled
    WHERE period IS NOT NULL
    GROUP BY team_name, task_category
),
compared AS (
    SELECT *,
        ROUND(100.0 * baseline_errors / NULLIF(baseline_completed, 0), 2) AS baseline_error_rate_pct,
        ROUND(100.0 * current_errors  / NULLIF(current_completed, 0), 2)  AS current_error_rate_pct,
        ROUND(current_errors
              - current_completed * (1.0 * baseline_errors / NULLIF(baseline_completed, 0)), 1) AS excess_errors
    FROM segments
)
SELECT
    team_name,
    task_category,
    CAST(baseline_errors AS INTEGER) AS baseline_errors,
    CAST(current_errors AS INTEGER)  AS current_errors,
    baseline_error_rate_pct,
    current_error_rate_pct,
    ROUND(current_error_rate_pct - baseline_error_rate_pct, 2) AS error_rate_change_pp,
    excess_errors,
    -- share of all the extra errors this segment explains
    ROUND(100.0 * GREATEST(excess_errors, 0)
          / NULLIF(SUM(GREATEST(excess_errors, 0)) OVER (), 0), 1) AS share_of_excess_pct
FROM compared
ORDER BY excess_errors DESC;
