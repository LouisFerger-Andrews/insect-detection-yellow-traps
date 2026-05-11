import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from src.github_client import GitHubClient
from src.utils import ensure_datetime

logger = logging.getLogger(__name__)


def _extract_label_names(labels: List[Dict[str, Any]]) -> List[str]:
    return [label.get("name", "") for label in labels if label.get("name")]


def _extract_assignees(assignees: List[Dict[str, Any]]) -> List[str]:
    return [assignee.get("login", "") for assignee in assignees if assignee.get("login")]


def _normalize_issue(item: Dict[str, Any], project_fields: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    milestone = item.get("milestone") or {}
    fields = project_fields or {}
    return {
        "id": item.get("id"),
        "number": item.get("number"),
        "title": item.get("title"),
        "body": item.get("body"),
        "state": item.get("state"),
        "state_reason": item.get("state_reason"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "closed_at": item.get("closed_at"),
        "author": (item.get("user") or {}).get("login"),
        "labels": _extract_label_names(item.get("labels", [])),
        "assignees": _extract_assignees(item.get("assignees", [])),
        "milestone": milestone.get("title"),
        "sprint": fields.get("sprint"),
        "project_status": fields.get("project_status"),
        "project_size": fields.get("size"),
        "url": item.get("html_url"),
    }


def _normalize_pr(item: Dict[str, Any]) -> Dict[str, Any]:
    milestone = item.get("milestone") or {}
    return {
        "id": item.get("id"),
        "number": item.get("number"),
        "title": item.get("title"),
        "state": item.get("state"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "closed_at": item.get("closed_at"),
        "merged_at": item.get("merged_at"),
        "author": (item.get("user") or {}).get("login"),
        "labels": _extract_label_names(item.get("labels", [])),
        "assignees": _extract_assignees(item.get("assignees", [])),
        "milestone": milestone.get("title"),
        "url": item.get("html_url"),
    }


def _normalize_commit(item: Dict[str, Any]) -> Dict[str, Any]:
    commit = item.get("commit") or {}
    author = commit.get("author") or {}
    return {
        "sha": item.get("sha"),
        "author": (item.get("author") or {}).get("login") or author.get("name"),
        "message": commit.get("message"),
        "date": author.get("date"),
        "url": item.get("html_url"),
    }


def _normalize_workflow_run(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": item.get("id"),
        "name": item.get("name") or item.get("display_title"),
        "status": item.get("status"),
        "conclusion": item.get("conclusion"),
        "event": item.get("event"),
        "run_started_at": item.get("run_started_at"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "url": item.get("html_url"),
    }


def _normalize_issue_event(issue_number: int, item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": item.get("id"),
        "issue_number": issue_number,
        "event": item.get("event"),
        "created_at": item.get("created_at"),
        "actor": (item.get("actor") or {}).get("login"),
        "label": ((item.get("label") or {}).get("name") if isinstance(item.get("label"), dict) else None),
    }


def _normalize_pr_review(pr_number: int, item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": item.get("id"),
        "pr_number": pr_number,
        "state": item.get("state"),
        "submitted_at": item.get("submitted_at"),
        "author": (item.get("user") or {}).get("login"),
    }


def _normalize_pr_detail(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "number": item.get("number"),
        "additions": item.get("additions", 0),
        "deletions": item.get("deletions", 0),
        "changed_files": item.get("changed_files", 0),
        "draft": bool(item.get("draft", False)),
    }


def _to_dataframe(records: List[Dict[str, Any]], datetime_columns: List[str]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df

    for column in datetime_columns:
        df[column] = ensure_datetime(df, column)

    return df


def load_repository_data(owner: str, repo: str, token: str) -> Dict[str, pd.DataFrame]:
    client = GitHubClient(owner=owner, repo=repo, token=token)

    raw_issues = client.get_issues()
    raw_pulls = client.get_pulls()
    raw_labels = client.get_labels()
    raw_milestones = client.get_milestones()
    raw_assignees = client.get_assignees()
    try:
        raw_commits = client.get_commits()
    except Exception:
        raw_commits = []
    try:
        raw_workflow_runs = client.get_workflow_runs()
    except Exception:
        raw_workflow_runs = []

    issue_project_fields: Dict[int, Dict[str, str]] = {}
    try:
        issue_project_fields = client.get_issue_project_fields()
    except Exception:
        issue_project_fields = {}

    issue_records = [
        _normalize_issue(item, project_fields=issue_project_fields.get(int(item.get("number", -1)), {}))
        for item in raw_issues
        if "pull_request" not in item
    ]
    pr_records = [_normalize_pr(item) for item in raw_pulls]
    commit_records = [_normalize_commit(item) for item in raw_commits]
    workflow_records = [_normalize_workflow_run(item) for item in raw_workflow_runs]

    pr_details_records: List[Dict[str, Any]] = []
    pr_reviews_records: List[Dict[str, Any]] = []
    issue_events_records: List[Dict[str, Any]] = []
    # Keep enrichment bounded so dashboard stays responsive and avoids API rate-limit spikes.
    max_pr_enrichment = 150
    max_issue_enrichment = 200

    for pr in pr_records[:max_pr_enrichment]:
        pr_number = int(pr.get("number", 0) or 0)
        if pr_number <= 0:
            continue
        try:
            detail = client.get_pull(pr_number)
            pr_details_records.append(_normalize_pr_detail(detail))
        except Exception as exc:
            logger.warning("Failed to enrich PR details for #%s: %s", pr_number, exc)
        try:
            reviews = client.get_pull_reviews(pr_number)
            pr_reviews_records.extend([_normalize_pr_review(pr_number, r) for r in reviews])
        except Exception as exc:
            logger.warning("Failed to fetch PR reviews for #%s: %s", pr_number, exc)
        try:
            comments = client.get_pull_review_comments(pr_number)
            pr_record = next((x for x in pr_records if int(x.get("number", -1) or -1) == pr_number), None)
            if pr_record is not None:
                pr_record["review_comments_count"] = len(comments)
        except Exception as exc:
            logger.warning("Failed to fetch PR review comments for #%s: %s", pr_number, exc)

    for issue in issue_records[:max_issue_enrichment]:
        issue_number = int(issue.get("number", 0) or 0)
        if issue_number <= 0:
            continue
        try:
            events = client.get_issue_events(issue_number)
            issue_events_records.extend([_normalize_issue_event(issue_number, e) for e in events])
        except Exception as exc:
            logger.warning("Failed to fetch issue events for #%s: %s", issue_number, exc)

    issues_df = _to_dataframe(issue_records, ["created_at", "updated_at", "closed_at"])
    prs_df = _to_dataframe(pr_records, ["created_at", "updated_at", "closed_at", "merged_at"])
    commits_df = _to_dataframe(commit_records, ["date"])
    workflows_df = _to_dataframe(workflow_records, ["run_started_at", "created_at", "updated_at"])
    pr_reviews_df = _to_dataframe(pr_reviews_records, ["submitted_at"])
    issue_events_df = _to_dataframe(issue_events_records, ["created_at"])
    pr_details_df = pd.DataFrame(pr_details_records)
    if not pr_details_df.empty and not prs_df.empty:
        prs_df = prs_df.merge(pr_details_df, on="number", how="left")
    for col in ["additions", "deletions", "changed_files", "review_comments_count"]:
        if col in prs_df.columns:
            prs_df[col] = prs_df[col].fillna(0)
    if "draft" in prs_df.columns:
        prs_df["draft"] = prs_df["draft"].fillna(False).astype(bool)

    labels_df = pd.DataFrame(
        [{"name": label.get("name"), "color": label.get("color")} for label in raw_labels]
    )
    milestones_df = pd.DataFrame(
        [
            {
                "title": milestone.get("title"),
                "state": milestone.get("state"),
                "open_issues": milestone.get("open_issues", 0),
                "closed_issues": milestone.get("closed_issues", 0),
                "due_on": milestone.get("due_on"),
            }
            for milestone in raw_milestones
        ]
    )
    assignees_df = pd.DataFrame([{"login": assignee.get("login")} for assignee in raw_assignees])

    if not milestones_df.empty:
        milestones_df["due_on"] = ensure_datetime(milestones_df, "due_on")

    return {
        "issues": issues_df,
        "pulls": prs_df,
        "commits": commits_df,
        "workflows": workflows_df,
        "pr_reviews": pr_reviews_df,
        "issue_events": issue_events_df,
        "labels": labels_df,
        "milestones": milestones_df,
        "assignees": assignees_df,
    }
