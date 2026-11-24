-- Project: Weekly Operations Performance Dashboard - Automated WBR
-- Purpose: Reconcile v2 against every figure v1 published in Google Sheets.
--          Recomputes each v1 number from the clean task-level data, for the
--          v1 window (21 Sep - 18 Oct 2026), and flags any difference.
-- Error rate = errors / tasks completed throughout.

WITH v1_window AS (
    SELECT * FROM public.operations_tasks
    WHERE task_date BETWEEN DATE '2026-09-21' AND DATE '2026-10-18'
),
recomputed AS (
    SELECT 'completion_rate_pct' AS metric, 'week ' || CAST(week_start AS VARCHAR) AS scope,
           ROUND(100.0 * SUM(tasks_completed) / SUM(tasks_assigned), 2) AS v2_recomputed
    FROM v1_window GROUP BY week_start
    UNION ALL
    SELECT 'error_rate_pct', 'week ' || CAST(week_start AS VARCHAR),
           ROUND(100.0 * SUM(errors_found) / SUM(tasks_completed), 2)
    FROM v1_window GROUP BY week_start
    UNION ALL
    SELECT 'completion_rate_pct', 'overall', ROUND(100.0 * SUM(tasks_completed) / SUM(tasks_assigned), 2)
    FROM v1_window
    UNION ALL
    SELECT 'error_rate_pct', 'overall', ROUND(100.0 * SUM(errors_found) / SUM(tasks_completed), 2)
    FROM v1_window
    UNION ALL
    SELECT 'completion_rate_pct', 'team ' || team_name, ROUND(100.0 * SUM(tasks_completed) / SUM(tasks_assigned), 2)
    FROM v1_window GROUP BY team_name
    UNION ALL
    SELECT 'error_rate_pct', 'team ' || team_name, ROUND(100.0 * SUM(errors_found) / SUM(tasks_completed), 2)
    FROM v1_window GROUP BY team_name
    UNION ALL
    SELECT 'error_rate_pct', 'category ' || task_category, ROUND(100.0 * SUM(errors_found) / SUM(tasks_completed), 2)
    FROM v1_window GROUP BY task_category
)
SELECT
    p.metric,
    p.scope,
    p.v1_published,
    r.v2_recomputed,
    ROUND(r.v2_recomputed - p.v1_published, 2) AS difference,
    CASE WHEN ABS(r.v2_recomputed - p.v1_published) < 0.01 THEN 'match' ELSE 'MISMATCH' END AS status,
    p.v1_source
FROM public.v1_published p
LEFT JOIN recomputed r ON r.metric = p.metric AND r.scope = p.scope
ORDER BY status, p.metric, p.scope;
