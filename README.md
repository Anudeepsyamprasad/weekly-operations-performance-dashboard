## Tools: 
PostgreSQL, SQL, Excel/Google Sheets, Git, GitHub. 

## Key capabilities: 
Weekly KPI reporting, team performance analysis, category-level error analysis, and data-quality validation.

# weekly-operations-performance-dashboard
SQL-driven operations analytics project featuring weekly KPIs, team and category analysis, data-quality validation, and a Google Sheets dashboard.

## New in v2: Automated Weekly Business Review

**[`wbr/`](wbr/README.md)** carries out v1's four recommended actions and turns them into a weekly routine: data-quality checks, week-over-week KPIs against targets, a dive deep that traces the error increase to **Team Gamma / Data Validation**, and an Excel WBR pack with charts and Google Sheets-ready tabs. Its task-level data reconciles exactly to every v1 total. It is tested with pytest and scheduled with GitHub Actions.

> **v1 correction found by v2:** the Weekly_Metrics tab divides errors by tasks *assigned*, while the dashboard headline (7.27%) and team figures divide by tasks *completed*. Using one definition (completed), the weekly error rates are 6.56%, 7.72%, 7.22% and 7.97%, and the latest week (12 Oct) holds only 2 working days. The v1 findings below describe the original 4-week snapshot.

```bash
pip install -r wbr/requirements.txt && python wbr/refresh_wbr.py
```

## Live Dashboard

**[Open the Interactive Google Sheets Dashboard](https://docs.google.com/spreadsheets/d/1JMYr6Crc37rYLAKmLGatFd8JOZos8KqSbY_yd6HPihk/edit?usp=sharing)**

The dashboard presents weekly operational KPIs, team-level performance,
category-level error analysis, and data-quality validation.
<img width="959" height="476" alt="image" src="https://github.com/user-attachments/assets/4998ce93-9d54-4751-b29c-750ac18f15ba" />

# Business Findings and Recommendations
## Project Scope
This project analyzes synthetic weekly operations data to demonstrate
KPI reporting, category-level analysis, and data-quality validation.

## Key Findings
1. Overall completion rate is approximately 92.89%.
2. The latest displayed week has 150 tasks assigned and 138 completed.
3. Data Validation has the highest category-level error rate at 9.84%.
4. Team Gamma has the lowest completion rate among the displayed teams, at 89.12%.
5. Team Gamma also has the highest displayed team-level error rate, at 9.84%.

## Recommended Actions
1. Investigate error patterns in Data Validation.
2. Review Team Gamma's task workflow and error categories.
3. Compare weekly completion and error-rate trends.
4. Validate source data and KPI calculations before reporting.

## Limitations
The dataset is synthetic and is intended for demonstration.
The observed patterns do not establish the root causes of errors.

**Data disclaimer:** This project uses synthetic data for demonstration
and portfolio purposes. It does not contain actual Amazon operational data.
