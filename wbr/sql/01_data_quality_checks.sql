-- Project: Weekly Operations Performance Dashboard - Automated WBR
-- Database: PostgreSQL syntax (runs unchanged in DuckDB for the local refresh)
-- Table: public.operations_tasks_raw
-- Purpose: Validate raw data BEFORE any metric is reported.
--          Returns one row per failing record. Zero rows = data is clean.

-- 1. Duplicate task IDs (every copy after the first is flagged)
SELECT 'duplicate_task_id' AS check_name, task_id, task_date, team_name
FROM (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY task_id ORDER BY task_date) AS copy_number
    FROM public.operations_tasks_raw
) numbered
WHERE copy_number > 1

UNION ALL

-- 2. Missing critical fields
SELECT 'missing_critical_field', task_id, task_date, team_name
FROM public.operations_tasks_raw
WHERE task_id IS NULL
   OR task_date IS NULL
   OR team_name IS NULL OR team_name = ''
   OR task_category IS NULL OR task_category = ''

UNION ALL

-- 3. Negative counts
SELECT 'negative_count', task_id, task_date, team_name
FROM public.operations_tasks_raw
WHERE tasks_assigned < 0 OR tasks_completed < 0 OR errors_found < 0

UNION ALL

-- 4. Impossible totals: more completed than assigned, or more errors than completed
SELECT 'impossible_total', task_id, task_date, team_name
FROM public.operations_tasks_raw
WHERE tasks_completed > tasks_assigned
   OR errors_found > tasks_completed

ORDER BY check_name, task_id;
