from datetime import date
from typing import Optional

import pandas as pd


def ensure_datetime(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype="datetime64[ns, UTC]")
    return pd.to_datetime(df[column], utc=True, errors="coerce")


def days_between(end: pd.Series, start: pd.Series) -> pd.Series:
    end_utc = pd.to_datetime(end, utc=True, errors="coerce")
    start_utc = pd.to_datetime(start, utc=True, errors="coerce")
    return (end_utc - start_utc).dt.total_seconds() / 86400.0


def contains_in_list(values: list[str], target: Optional[str]) -> bool:
    if not target or target == "All":
        return True
    return target in values


def apply_issue_filters(
    issues_df: pd.DataFrame,
    start_date: date,
    end_date: date,
    assignee: str,
    label: str,
    milestone: str,
    issue_state: str,
) -> pd.DataFrame:
    if issues_df.empty:
        return issues_df

    data = issues_df.copy()
    created = ensure_datetime(data, "created_at")
    start_ts = pd.Timestamp(start_date, tz="UTC")
    end_ts = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    mask = (created >= start_ts) & (created <= end_ts)

    if issue_state != "all":
        mask &= data["state"].str.lower() == issue_state.lower()

    if assignee != "All":
        mask &= data["assignees"].apply(lambda vals: contains_in_list(vals, assignee))

    if label != "All":
        mask &= data["labels"].apply(lambda vals: contains_in_list(vals, label))

    if milestone == "No milestone":
        mask &= data["milestone"].isna()
    elif milestone != "All":
        mask &= data["milestone"].fillna("") == milestone

    return data.loc[mask].copy()


def apply_pr_date_filter(prs_df: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    if prs_df.empty:
        return prs_df

    created = ensure_datetime(prs_df, "created_at")
    start_ts = pd.Timestamp(start_date, tz="UTC")
    end_ts = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return prs_df.loc[(created >= start_ts) & (created <= end_ts)].copy()
