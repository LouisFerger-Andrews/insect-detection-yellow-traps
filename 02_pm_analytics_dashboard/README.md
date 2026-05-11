# PM Analytics Dashboard

Internal Streamlit dashboard for project management analytics powered by GitHub repository data.

## What this MVP covers

- Pulls repository data from GitHub REST API (read-only):
  - issues
  - pull requests
  - labels
  - milestones
  - assignees
- Handles pagination (`per_page=100` + next-link traversal)
- Provides interactive dashboard sections:
  - Project Management
  - Quality
  - Deployment
  - Architecture
- Includes sidebar filters:
  - milestone (including current milestone shortcut)
  - date range
  - assignee
  - label
  - issue state
- Supports CSV export for filtered issues and PRs
- Includes an inferred Project -> Epic -> Feature tree with Feature -> Task drill-down and issue detail panel

## Project structure

```text
02_pm_analytics_dashboard/
├── app.py
├── requirements.txt
├── README.md
├── .env.example
└── src
    ├── github_client.py
    ├── data_loader.py
    ├── metrics.py
    ├── charts.py
    └── utils.py
```

## Prerequisites

- Python 3.10+
- A GitHub Personal Access Token with repository read access

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r 02_pm_analytics_dashboard/requirements.txt
```

3. Configure environment variables (example values shown):

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxx"
export GITHUB_OWNER="your-org-or-username"
export GITHUB_REPO="your-repository"
export DASHBOARD_PASSKEY="replace-with-strong-passkey"
export SHOW_INTERNAL_ERRORS="false"
```

Optional: copy `.env.example` to `.env` in `02_pm_analytics_dashboard/` and set values there.

For your current request you can set:

```bash
export DASHBOARD_PASSKEY="SOFA2026"
```

## Run locally

```bash
streamlit run 02_pm_analytics_dashboard/app.py
```

## Deploy to Streamlit Community Cloud (single app)

1. Push this branch to GitHub.
2. In Streamlit Community Cloud, create a new app:
   - Repository: this repo
   - Branch: deployment branch
   - Main file path: `02_pm_analytics_dashboard/app.py`
3. In app settings -> Secrets, set:

```toml
GITHUB_TOKEN = "your_read_only_token"
GITHUB_OWNER = "SPOHF"
GITHUB_REPO = "insect-detection-yellow-traps"
DASHBOARD_PASSKEY = "SOFA2026"
SHOW_INTERNAL_ERRORS = "false"
```

4. Deploy.

Notes:
- Keep this dashboard as the only deployed Streamlit app by using only the file path above.
- Private repository deployment is supported when your Streamlit account is connected to GitHub and has access to that private repo.
- If org policies block app authorization, an org owner must grant access.

## Security baseline implemented

- Access gate:
  - Dashboard now requires `DASHBOARD_PASSKEY` before loading any data.
  - Failed-attempt lockout after repeated wrong entries.
- Secret handling:
  - Uses Streamlit `st.secrets` first, environment variables as fallback.
  - No credentials hardcoded in code.
- Error exposure:
  - Production-safe generic API error by default.
  - Full traceback only when `SHOW_INTERNAL_ERRORS=true`.
- Transport:
  - Streamlit Cloud serves apps over HTTPS.

## Security operations checklist (recommended)

- Secrets and keys:
  - Use a fine-grained GitHub PAT with minimum required scopes.
  - Rotate `GITHUB_TOKEN` regularly.
  - Never commit `.env`.
- Data protection:
  - Keep data collection minimal (this app only reads GitHub metadata).
  - Do not log tokens, passkeys, or raw secret values.
- API/backend hardening:
  - Validate all user-controlled filters.
  - Keep read-only GitHub access for dashboard tokens.
- Dependency security:
  - Run `pip audit` and `npm audit` in CI.
  - Pin and update dependencies regularly.
- Repo security:
  - Enforce PR-only main branch changes.
  - Enable Dependabot and secret scanning.
- Monitoring:
  - Track failed login attempts and app errors.
  - Alert on unusual usage patterns.

## Assumptions

- Issue-focused metrics explicitly exclude pull requests by filtering out `issues` endpoint entries that include `pull_request`.
- PR metrics are sourced from the dedicated `/pulls` endpoint to include `merged_at` and accurate merge timing.
- Milestone completion percentage is computed from milestone aggregates (`closed_issues / (open_issues + closed_issues)`).
- Date range filters are applied on `created_at` timestamps.
- Hierarchy mapping (`Epic` -> `Feature` -> `Task`) is inferred from issue labels, title prefixes (`[Epic]`, `[Feature]`, `[Task]`), milestone context, and title/body keyword similarity.
- If labels are not standardized (e.g., missing `bug`, `feature`, `enhancement`), bug vs feature split may be empty.
- Dashboard is read-only and does not mutate repository state.

## Notes on robustness

- Handles missing milestones, labels, assignees, and empty datasets gracefully.
- Uses Streamlit cache (`ttl=900s`) to reduce repeated API calls.
- Architecture tab includes five presentation diagrams:
  - C4 Container Diagram
  - Component Diagram (backend internals)
  - Sequence Diagram (key workflow)
  - ER Diagram (data model)
  - Deployment Diagram (runtime topology)
