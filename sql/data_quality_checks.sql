-- Project: Weekly Operations Performance Dashboard
-- Database: PostgreSQL
-- Table: public.operations_tasks
-- Purpose: Data quality validation


-- 1. Check for duplicate task IDs
-- Expected result: Zero rows

SELECT
    task_id,
    COUNT(*) AS record_count

FROM public.operations_tasks

GROUP BY task_id

HAVING COUNT(*) > 1;


-- 2. Check for missing critical fields
-- Expected result: All missing-value counts should be zero

SELECT
    COUNT(*) FILTER (
        WHERE task_id IS NULL
    ) AS missing_task_id,

    COUNT(*) FILTER (
        WHERE task_date IS NULL
    ) AS missing_task_date,

    COUNT(*) FILTER (
        WHERE team_name IS NULL
    ) AS missing_team_name,

    COUNT(*) FILTER (
        WHERE task_category IS NULL
    ) AS missing_task_category,

    COUNT(*) FILTER (
        WHERE tasks_assigned IS NULL
    ) AS missing_tasks_assigned,

    COUNT(*) FILTER (
        WHERE tasks_completed IS NULL
    ) AS missing_tasks_completed,

    COUNT(*) FILTER (
        WHERE errors_found IS NULL
    ) AS missing_errors_found,

    COUNT(*) FILTER (
        WHERE status IS NULL
    ) AS missing_status

FROM public.operations_tasks;


-- 3. Check for negative counts and impossible task totals
-- Expected result: Zero rows

SELECT *
FROM public.operations_tasks

WHERE tasks_assigned < 0
   OR tasks_completed < 0
   OR errors_found < 0
   OR tasks_completed > tasks_assigned
   OR errors_found > tasks_completed;


-- 4. Summarize task statuses
-- Review the distribution for unexpected or inconsistent values

SELECT
    status,
    COUNT(*) AS record_count

FROM public.operations_tasks

GROUP BY status

ORDER BY record_count DESC;