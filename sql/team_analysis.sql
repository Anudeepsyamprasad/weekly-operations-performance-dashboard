-- Project: Weekly Operations Performance Dashboard
-- Database: PostgreSQL
-- Table: public.operations_tasks
-- Purpose: Team performance and operational KPI analysis

SELECT
    team_name,

    SUM(tasks_assigned) AS tasks_assigned,
    SUM(tasks_completed) AS tasks_completed,
    SUM(errors_found) AS total_errors,

    SUM(tasks_assigned) - SUM(tasks_completed)
        AS tasks_not_completed,

    ROUND(
        100.0 * SUM(tasks_completed)
        / NULLIF(SUM(tasks_assigned), 0),
        2
    ) AS completion_rate_pct,

    ROUND(
        100.0 * SUM(errors_found)
        / NULLIF(SUM(tasks_completed), 0),
        2
    ) AS error_rate_pct

FROM public.operations_tasks

GROUP BY team_name

ORDER BY completion_rate_pct ASC;