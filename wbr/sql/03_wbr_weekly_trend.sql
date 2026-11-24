-- Project: Weekly Operations Performance Dashboard - Automated WBR
-- Purpose: The WBR headline table. One row per week with:
--   - this week's KPIs
--   - whether the week is complete (all 5 working days reported)
--   - week-over-week (WoW) change, using LAG(), between COMPLETE weeks only
--   - 4-week trailing average over complete weeks, using a window frame
--   - target and whether the week met it
-- Rates are in percent; WoW changes are in percentage points (pp).
-- Error rate = errors / tasks COMPLETED (same as v1's SQL and headline 7.27%).

WITH weekly AS (
    SELECT
        week_start,
        COUNT(DISTINCT task_date) AS days_reported,
        SUM(tasks_assigned)  AS tasks_assigned,
        SUM(tasks_completed) AS tasks_completed,
        SUM(errors_found)    AS total_errors,
        ROUND(100.0 * SUM(tasks_completed) / NULLIF(SUM(tasks_assigned), 0), 2)  AS completion_rate_pct,
        ROUND(100.0 * SUM(errors_found)    / NULLIF(SUM(tasks_completed), 0), 2) AS error_rate_pct
    FROM public.operations_tasks
    GROUP BY week_start
),
complete_weeks AS (
    SELECT
        week_start,
        ROUND(completion_rate_pct - LAG(completion_rate_pct) OVER (ORDER BY week_start), 2) AS completion_wow_pp,
        ROUND(AVG(completion_rate_pct) OVER (ORDER BY week_start ROWS BETWEEN 3 PRECEDING AND CURRENT ROW), 2)
            AS completion_4wk_avg_pct,
        ROUND(error_rate_pct - LAG(error_rate_pct) OVER (ORDER BY week_start), 2) AS error_wow_pp,
        ROUND(AVG(error_rate_pct) OVER (ORDER BY week_start ROWS BETWEEN 3 PRECEDING AND CURRENT ROW), 2)
            AS error_4wk_avg_pct
    FROM weekly
    WHERE days_reported >= 5
),
targets AS (
    SELECT
        MAX(CASE WHEN metric = 'completion_rate_pct' THEN target_pct END) AS completion_target_pct,
        MAX(CASE WHEN metric = 'error_rate_pct'      THEN target_pct END) AS error_target_pct
    FROM public.wbr_targets
)
SELECT
    w.week_start,
    w.days_reported,
    w.days_reported >= 5 AS is_complete_week,
    w.tasks_assigned,
    w.tasks_completed,
    w.total_errors,

    w.completion_rate_pct,
    c.completion_wow_pp,
    c.completion_4wk_avg_pct,
    t.completion_target_pct,
    w.completion_rate_pct >= t.completion_target_pct AS completion_met_target,

    w.error_rate_pct,
    c.error_wow_pp,
    c.error_4wk_avg_pct,
    t.error_target_pct,
    w.error_rate_pct <= t.error_target_pct AS error_met_target

FROM weekly w
LEFT JOIN complete_weeks c ON c.week_start = w.week_start
CROSS JOIN targets t
ORDER BY w.week_start;
