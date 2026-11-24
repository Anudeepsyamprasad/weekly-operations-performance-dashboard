-- Project: Weekly Operations Performance Dashboard - Automated WBR
-- Purpose: The only table the WBR reads from. Keeps rows that pass every
--          check in 01_data_quality_checks.sql; failing rows are left out
--          of the metrics and listed in the data-quality report instead.

CREATE OR REPLACE VIEW public.operations_tasks AS
SELECT
    task_id,
    task_date,
    DATE_TRUNC('week', task_date)::DATE AS week_start,
    team_name,
    task_category,
    tasks_assigned,
    tasks_completed,
    errors_found,
    status
FROM (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY task_id ORDER BY task_date) AS copy_number
    FROM public.operations_tasks_raw
) numbered
WHERE copy_number = 1
  AND task_id IS NOT NULL
  AND task_date IS NOT NULL
  AND team_name IS NOT NULL AND team_name <> ''
  AND task_category IS NOT NULL AND task_category <> ''
  AND tasks_assigned >= 0 AND tasks_completed >= 0 AND errors_found >= 0
  AND tasks_completed <= tasks_assigned
  AND errors_found <= tasks_completed;
