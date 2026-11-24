-- Project: Weekly Operations Performance Dashboard - Automated WBR
-- Purpose: Team view for the latest COMPLETE week vs the complete week before.
--          Answers "which team moved, and by how much?"
--          A partial week is left out: comparing 2 days against 5 misleads.

WITH team_weekly AS (
    SELECT
        week_start,
        team_name,
        COUNT(DISTINCT task_date) AS days_reported,
        SUM(tasks_assigned)  AS tasks_assigned,
        SUM(tasks_completed) AS tasks_completed,
        SUM(errors_found)    AS total_errors,
        ROUND(100.0 * SUM(tasks_completed) / NULLIF(SUM(tasks_assigned), 0), 2)  AS completion_rate_pct,
        ROUND(100.0 * SUM(errors_found)    / NULLIF(SUM(tasks_completed), 0), 2) AS error_rate_pct
    FROM public.operations_tasks
    GROUP BY week_start, team_name
),
complete AS (
    SELECT * FROM team_weekly WHERE days_reported >= 5
),
with_prior AS (
    SELECT *,
        LAG(completion_rate_pct) OVER (PARTITION BY team_name ORDER BY week_start) AS prior_completion_pct,
        LAG(error_rate_pct)      OVER (PARTITION BY team_name ORDER BY week_start) AS prior_error_pct
    FROM complete
)
SELECT
    week_start,
    team_name,
    tasks_assigned,
    tasks_completed,
    total_errors,
    completion_rate_pct,
    ROUND(completion_rate_pct - prior_completion_pct, 2) AS completion_wow_pp,
    error_rate_pct,
    ROUND(error_rate_pct - prior_error_pct, 2)           AS error_wow_pp
FROM with_prior
WHERE week_start = (SELECT MAX(week_start) FROM complete)
ORDER BY error_rate_pct DESC;
