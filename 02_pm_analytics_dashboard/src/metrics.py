from typing import Dict

import numpy as np
import pandas as pd

from src.utils import days_between


def _duration_days(df: pd.DataFrame, end_col: str, start_col: str = "created_at") -> pd.Series:
    if df.empty or end_col not in df.columns or start_col not in df.columns:
        return pd.Series(dtype=float)
    valid = df[df[end_col].notna() & df[start_col].notna()]
    if valid.empty:
        return pd.Series(dtype=float)
    return days_between(valid[end_col], valid[start_col])


def overview_metrics(issues_df: pd.DataFrame, prs_df: pd.DataFrame, milestones_df: pd.DataFrame) -> Dict[str, float]:
    issue_open = int((issues_df.get("state") == "open").sum()) if not issues_df.empty else 0
    issue_closed = int((issues_df.get("state") == "closed").sum()) if not issues_df.empty else 0
    pr_open = int((prs_df.get("state") == "open").sum()) if not prs_df.empty else 0
    pr_closed = int((prs_df.get("state") == "closed").sum()) if not prs_df.empty else 0

    issue_close_days = _duration_days(issues_df, "closed_at")
    avg_issue_close_time = float(issue_close_days.mean()) if not issue_close_days.empty else np.nan

    if milestones_df.empty:
        milestone_completion = np.nan
    else:
        open_total = milestones_df.get("open_issues", pd.Series(dtype=float)).fillna(0).sum()
        closed_total = milestones_df.get("closed_issues", pd.Series(dtype=float)).fillna(0).sum()
        total = open_total + closed_total
        milestone_completion = float((closed_total / total) * 100) if total > 0 else np.nan

    return {
        "open_issues": issue_open,
        "closed_issues": issue_closed,
        "open_prs": pr_open,
        "closed_prs": pr_closed,
        "avg_issue_close_days": avg_issue_close_time,
        "milestone_completion_pct": milestone_completion,
    }


def cycle_metrics(issues_df: pd.DataFrame, prs_df: pd.DataFrame) -> Dict[str, float]:
    issue_cycle = _duration_days(issues_df, "closed_at")
    pr_merge = _duration_days(prs_df, "merged_at")

    return {
        "avg_cycle_days": float(issue_cycle.mean()) if not issue_cycle.empty else np.nan,
        "median_cycle_days": float(issue_cycle.median()) if not issue_cycle.empty else np.nan,
        "avg_pr_merge_days": float(pr_merge.mean()) if not pr_merge.empty else np.nan,
        "median_pr_merge_days": float(pr_merge.median()) if not pr_merge.empty else np.nan,
    }


def stale_issues(issues_df: pd.DataFrame, stale_days: int) -> pd.DataFrame:
    if issues_df.empty:
        return issues_df

    open_issues = issues_df[issues_df["state"] == "open"].copy()
    if open_issues.empty:
        return open_issues

    now_utc = pd.Timestamp.now(tz="UTC")
    cutoff = now_utc - pd.Timedelta(days=stale_days)
    stale = open_issues[open_issues["updated_at"] < cutoff].copy()
    stale["days_since_update"] = (now_utc - stale["updated_at"]).dt.days
    return stale.sort_values("days_since_update", ascending=False)


def health_summary(issues_df: pd.DataFrame, prs_df: pd.DataFrame, stale_df: pd.DataFrame) -> Dict[str, int]:
    return {
        "total_issues": int(len(issues_df)),
        "total_prs": int(len(prs_df)),
        "stale_open_issues": int(len(stale_df)),
    }
