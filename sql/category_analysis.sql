-- Project: Weekly Operations Performance Dashboard
-- Database: PostgreSQL
-- Table: public.operations_tasks
-- Purpose: Task category performance analysis

SELECT
    task_category,

    SUM(tasks_assigned) AS tasks_assigned,
    SUM(tasks_completed) AS tasks_completed,
    SUM(errors_found) AS total_errors,

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

GROUP BY task_category

ORDER BY error_rate_pct DESC;