import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _empty_figure(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=title, xaxis_title=None, yaxis_title=None)
    fig.add_annotation(
        text="No data available for current filters",
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
    )
    return fig


def issues_opened_closed_over_time(issues_df: pd.DataFrame) -> go.Figure:
    if issues_df.empty:
        return _empty_figure("Issues Opened vs Closed Over Time")

    opened = issues_df.dropna(subset=["created_at"]).copy()
    opened["date"] = opened["created_at"].dt.date
    opened_daily = opened.groupby("date").size().reset_index(name="opened")

    closed = issues_df.dropna(subset=["closed_at"]).copy()
    closed["date"] = closed["closed_at"].dt.date
    closed_daily = closed.groupby("date").size().reset_index(name="closed")

    merged = pd.merge(opened_daily, closed_daily, on="date", how="outer").fillna(0).sort_values("date")
    if merged.empty:
        return _empty_figure("Issues Opened vs Closed Over Time")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=merged["date"], y=merged["opened"], mode="lines", name="Opened"))
    fig.add_trace(go.Scatter(x=merged["date"], y=merged["closed"], mode="lines", name="Closed"))
    fig.update_layout(title="Issues Opened vs Closed Over Time", yaxis_title="Count")
    return fig


def prs_opened_merged_over_time(prs_df: pd.DataFrame) -> go.Figure:
    if prs_df.empty:
        return _empty_figure("PRs Opened vs Merged Over Time")

    opened = prs_df.dropna(subset=["created_at"]).copy()
    opened["date"] = opened["created_at"].dt.date
    opened_daily = opened.groupby("date").size().reset_index(name="opened")

    merged = prs_df.dropna(subset=["merged_at"]).copy()
    merged["date"] = merged["merged_at"].dt.date
    merged_daily = merged.groupby("date").size().reset_index(name="merged")

    trend = pd.merge(opened_daily, merged_daily, on="date", how="outer").fillna(0).sort_values("date")
    if trend.empty:
        return _empty_figure("PRs Opened vs Merged Over Time")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=trend["date"], y=trend["opened"], mode="lines", name="Opened"))
    fig.add_trace(go.Scatter(x=trend["date"], y=trend["merged"], mode="lines", name="Merged"))
    fig.update_layout(title="PRs Opened vs Merged Over Time", yaxis_title="Count")
    return fig


def cumulative_completed_issues(issues_df: pd.DataFrame) -> go.Figure:
    closed = issues_df.dropna(subset=["closed_at"]).copy() if not issues_df.empty else pd.DataFrame()
    if closed.empty:
        return _empty_figure("Cumulative Completed Issues")

    closed["date"] = closed["closed_at"].dt.date
    daily = closed.groupby("date").size().reset_index(name="completed")
    daily = daily.sort_values("date")
    daily["cumulative"] = daily["completed"].cumsum()

    fig = px.area(daily, x="date", y="cumulative", title="Cumulative Completed Issues")
    fig.update_yaxes(title="Completed Issues")
    return fig


def issues_by_label(issues_df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    if issues_df.empty or "labels" not in issues_df.columns:
        return _empty_figure("Issues by Label")

    exploded = issues_df.explode("labels")
    exploded = exploded.dropna(subset=["labels"])
    if exploded.empty:
        return _empty_figure("Issues by Label")

    counts = exploded.groupby("labels").size().reset_index(name="count").sort_values("count", ascending=False).head(top_n)
    fig = px.bar(counts, x="labels", y="count", title="Issues by Label")
    fig.update_xaxes(title="Label")
    return fig


def issues_by_assignee(issues_df: pd.DataFrame) -> go.Figure:
    if issues_df.empty or "assignees" not in issues_df.columns:
        return _empty_figure("Issues by Assignee")

    exploded = issues_df.explode("assignees")
    exploded = exploded.dropna(subset=["assignees"])
    if exploded.empty:
        return _empty_figure("Issues by Assignee")

    counts = exploded.groupby("assignees").size().reset_index(name="count").sort_values("count", ascending=False)
    fig = px.bar(counts, x="assignees", y="count", title="Issues by Assignee")
    fig.update_xaxes(title="Assignee")
    return fig


def issues_by_milestone(issues_df: pd.DataFrame) -> go.Figure:
    if issues_df.empty:
        return _empty_figure("Issues by Milestone")

    data = issues_df.copy()
    data["milestone"] = data["milestone"].fillna("No milestone")
    counts = data.groupby("milestone").size().reset_index(name="count").sort_values("count", ascending=False)
    if counts.empty:
        return _empty_figure("Issues by Milestone")

    fig = px.bar(counts, x="milestone", y="count", title="Issues by Milestone")
    return fig


def bug_vs_feature_split(issues_df: pd.DataFrame) -> go.Figure:
    if issues_df.empty:
        return _empty_figure("Bug vs Feature Split")

    bug_keys = {"bug", "type:bug"}
    feature_keys = {"feature", "enhancement", "type:feature"}

    bug_count = 0
    feature_count = 0

    for labels in issues_df.get("labels", []):
        normalized = {str(label).strip().lower() for label in labels}
        if normalized & bug_keys:
            bug_count += 1
        if normalized & feature_keys:
            feature_count += 1

    values = pd.DataFrame({"category": ["Bug", "Feature"], "count": [bug_count, feature_count]})
    if values["count"].sum() == 0:
        return _empty_figure("Bug vs Feature Split")

    fig = px.pie(values, values="count", names="category", title="Bug vs Feature Split")
    return fig


def open_issue_aging(issues_df: pd.DataFrame) -> go.Figure:
    if issues_df.empty:
        return _empty_figure("Aging of Open Issues")

    open_issues = issues_df[issues_df["state"] == "open"].copy()
    if open_issues.empty:
        return _empty_figure("Aging of Open Issues")

    now_utc = pd.Timestamp.now(tz="UTC")
    open_issues["age_days"] = (now_utc - open_issues["created_at"]).dt.days
    fig = px.histogram(open_issues, x="age_days", nbins=20, title="Aging of Open Issues")
    fig.update_xaxes(title="Age (days)")
    return fig
