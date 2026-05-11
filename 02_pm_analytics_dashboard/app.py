import os
import json
import re
import subprocess
import sys
import hmac
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(ROOT_DIR, ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.data_loader import load_repository_data  # noqa: E402
from src.metrics import cycle_metrics, overview_metrics  # noqa: E402
from src.utils import apply_issue_filters, apply_pr_date_filter  # noqa: E402

load_dotenv(os.path.join(ROOT_DIR, ".env"))

st.set_page_config(page_title="SDLC Analytics Dashboard", layout="wide")

st.markdown(
    """
    <style>
      .sdlc-subtitle {color: #6b7280; margin-top: -0.2rem; margin-bottom: 0.8rem;}
      .sdlc-panel {
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 0.7rem 1rem;
        background: #fcfcfd;
        margin-bottom: 0.8rem;
      }
      .sdlc-detail {
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 0.8rem 1rem;
        background: #ffffff;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("## SDLC Analytics Dashboard")
st.markdown(
    "<p class='sdlc-subtitle'>Software delivery life cycle visibility across Project Management, Quality, Deployment, and Architecture.</p>",
    unsafe_allow_html=True,
)

COSMIC_PURPLE = "#673366"
COSMIC_PALETTE = ["#673366", "#835281", "#9C729A", "#B796B7", "#D2BDD2"]


@st.cache_data(ttl=900, show_spinner=False)
def fetch_data(owner: str, repo: str, token: str):
    return load_repository_data(owner=owner, repo=repo, token=token)


def fmt_days(value: float) -> str:
    return "N/A" if pd.isna(value) else f"{value:.1f} days"


def fmt_pct(value: float) -> str:
    return "N/A" if pd.isna(value) else f"{value:.1f}%"


def _get_config(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        # st.secrets may be unavailable depending on runtime; fall back to environment variables.
        pass
    return str(os.getenv(name, default))


def _get_config_bool(name: str, default: bool = False) -> bool:
    raw = _get_config(name, "true" if default else "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _require_dashboard_access() -> None:
    expected_key = _get_config("DASHBOARD_PASSKEY", "")
    if not expected_key:
        st.error("Dashboard access key is not configured. Set `DASHBOARD_PASSKEY` in environment/secrets.")
        st.stop()

    st.session_state.setdefault("dashboard_authenticated", False)
    st.session_state.setdefault("dashboard_failed_attempts", 0)
    st.session_state.setdefault("dashboard_lock_until", 0.0)

    if st.session_state["dashboard_authenticated"]:
        return

    now_ts = datetime.utcnow().timestamp()
    lock_until = float(st.session_state.get("dashboard_lock_until", 0.0) or 0.0)
    if lock_until > now_ts:
        remaining = int(lock_until - now_ts)
        st.error(f"Too many failed attempts. Try again in {remaining}s.")
        st.stop()

    st.markdown("### Dashboard Access")
    st.caption("Enter passkey to access this internal dashboard.")
    with st.form("dashboard_access_form", clear_on_submit=False):
        entered_key = st.text_input("Passkey", type="password", key="dashboard_passkey_input")
        submitted = st.form_submit_button("Enter Dashboard")
    if submitted:
        if hmac.compare_digest(entered_key or "", expected_key):
            st.session_state["dashboard_authenticated"] = True
            st.session_state["dashboard_failed_attempts"] = 0
            st.rerun()
        else:
            failures = int(st.session_state.get("dashboard_failed_attempts", 0)) + 1
            st.session_state["dashboard_failed_attempts"] = failures
            if failures >= 5:
                st.session_state["dashboard_lock_until"] = datetime.utcnow().timestamp() + 60
            st.error("Invalid passkey.")
    st.stop()


def _utc_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def _delta_days(end_series: pd.Series, start_series: pd.Series) -> pd.Series:
    return (_utc_series(end_series) - _utc_series(start_series)).dt.total_seconds() / 86400.0


def _delta_hours(end_series: pd.Series, start_series: pd.Series) -> pd.Series:
    return (_utc_series(end_series) - _utc_series(start_series)).dt.total_seconds() / 3600.0


def _apply_brand_style(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#2F1F2E"),
    )
    for idx, trace in enumerate(fig.data):
        color = COSMIC_PALETTE[idx % len(COSMIC_PALETTE)]
        ttype = getattr(trace, "type", "")
        if ttype in {"bar", "histogram"}:
            trace.marker.color = color
        elif ttype in {"scatter"}:
            trace.line.color = color
            trace.marker.color = color
        elif ttype in {"pie"}:
            if hasattr(trace, "labels") and trace.labels is not None:
                n = len(trace.labels)
                trace.marker.colors = [COSMIC_PALETTE[i % len(COSMIC_PALETTE)] for i in range(n)]
            else:
                trace.marker.colors = COSMIC_PALETTE
    return fig


def render_chart(fig: go.Figure, key: str, brand_style: bool = True) -> Optional[object]:
    if brand_style:
        fig = _apply_brand_style(fig)
    return st.plotly_chart(fig, key=key, width="stretch", on_select="rerun")


def issue_state_pie(issues_df: pd.DataFrame) -> go.Figure:
    if issues_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Issue State Distribution")
        return fig
    counts = issues_df.groupby("state").size().reset_index(name="count")
    return px.pie(counts, names="state", values="count", hole=0.45, title="Issue State Distribution")


def milestone_completion_bar(milestones_df: pd.DataFrame) -> go.Figure:
    if milestones_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Milestone Completion")
        return fig

    data = milestones_df.copy()
    total = data["open_issues"].fillna(0) + data["closed_issues"].fillna(0)
    data["completion_pct"] = ((data["closed_issues"].fillna(0) / total) * 100).fillna(0)
    data = data.sort_values("completion_pct", ascending=False)
    return px.bar(data, x="title", y="completion_pct", title="Milestone Completion (%)")


def weekly_issue_throughput(issues_df: pd.DataFrame) -> go.Figure:
    if issues_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Weekly Issue Throughput")
        return fig

    opened = issues_df.dropna(subset=["created_at"]).copy()
    opened["week"] = opened["created_at"].dt.tz_localize(None).dt.to_period("W").dt.start_time
    opened = opened.groupby("week").size().reset_index(name="opened")

    closed = issues_df.dropna(subset=["closed_at"]).copy()
    closed["week"] = closed["closed_at"].dt.tz_localize(None).dt.to_period("W").dt.start_time
    closed = closed.groupby("week").size().reset_index(name="closed")

    trend = pd.merge(opened, closed, on="week", how="outer").fillna(0).sort_values("week")
    if trend.empty:
        fig = go.Figure()
        fig.update_layout(title="Weekly Issue Throughput")
        return fig

    fig = go.Figure()
    fig.add_bar(x=trend["week"], y=trend["opened"], name="Opened")
    fig.add_bar(x=trend["week"], y=trend["closed"], name="Closed")
    fig.update_layout(title="Weekly Issue Throughput", barmode="group", yaxis_title="Count")
    return fig


def _phase_window(today: date) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(date(today.year, 2, 1), tz="UTC")
    end = pd.Timestamp(date(today.year, 6, 30), tz="UTC")
    return start, end


def _delivery_window(
    scope_issues: pd.DataFrame,
    milestones_df: pd.DataFrame,
    milestone_filter: str,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    if milestone_filter == "All":
        return _phase_window(date.today())

    created_series = scope_issues.get("created_at", pd.Series(dtype="datetime64[ns, UTC]"))
    start = created_series.min() if not scope_issues.empty and created_series.notna().any() else pd.Timestamp.now(tz="UTC")
    end = created_series.max() if not scope_issues.empty and created_series.notna().any() else pd.Timestamp.now(tz="UTC")

    if not milestones_df.empty and isinstance(milestone_filter, str) and milestone_filter not in {"All", "No milestone"}:
        match = milestones_df[milestones_df["title"] == milestone_filter]
        if not match.empty and pd.notna(match.iloc[0].get("due_on")):
            selected_due = match.iloc[0]["due_on"]
            end = selected_due

            # Sequential assumption:
            # milestone N starts when milestone N-1 is due/finished.
            dated = milestones_df.dropna(subset=["due_on"]).sort_values("due_on").copy()
            earlier = dated[dated["due_on"] < selected_due]
            if not earlier.empty:
                prev_due = earlier.iloc[-1]["due_on"]
                start = prev_due + pd.Timedelta(days=1)

    start = pd.to_datetime(start, utc=True, errors="coerce")
    end = pd.to_datetime(end, utc=True, errors="coerce")
    if pd.isna(start):
        start = pd.Timestamp.now(tz="UTC")
    if pd.isna(end):
        end = pd.Timestamp.now(tz="UTC")
    if start > end:
        start, end = end, start
    return start, end


def _planned_vs_actual(
    scope_issues: pd.DataFrame,
    issue_type: str,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    as_of: pd.Timestamp,
) -> dict[str, float]:
    if scope_issues.empty:
        return {"total": 0, "done_total": 0, "expected_now": 0, "done_now": 0}

    data = scope_issues.copy()
    data = data[~data.apply(_is_duplicate_or_wontfix_issue, axis=1)].copy()
    data["issue_type"] = data.apply(_infer_issue_type, axis=1)
    data = data[data["issue_type"] == issue_type].copy()
    if data.empty:
        return {"total": 0, "done_total": 0, "expected_now": 0, "done_now": 0}

    total = len(data)
    done_total = int((data["state"].str.lower() == "closed").sum())

    total_days = max((window_end - window_start).days, 1)
    elapsed_days = (min(max(as_of, window_start), window_end) - window_start).days
    elapsed_ratio = max(0.0, min(1.0, elapsed_days / total_days))
    expected_now = int(round(total * elapsed_ratio))

    done_now = int(
        (
            (data["state"].str.lower() == "closed")
            & (data["closed_at"].notna())
            & (data["closed_at"] <= as_of)
        ).sum()
    )
    return {
        "total": int(total),
        "done_total": int(done_total),
        "expected_now": int(expected_now),
        "done_now": int(done_now),
    }


def _hierarchy_level(row: pd.Series) -> str:
    issue_type = _infer_issue_type(row)
    return issue_type if issue_type in {"epic", "feature", "task"} else "other"


def hierarchy_completion_chart(scope_issues: pd.DataFrame) -> go.Figure:
    if scope_issues.empty:
        fig = go.Figure()
        fig.update_layout(title="Hierarchy Completion by Level")
        return fig
    data = scope_issues.copy()
    data = data[~data.apply(_is_duplicate_or_wontfix_issue, axis=1)].copy()
    data["level"] = data.apply(_hierarchy_level, axis=1)
    data = data[data["level"].isin(["epic", "feature", "task"])].copy()
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title="Hierarchy Completion by Level")
        return fig

    rows = []
    for level in ["epic", "feature", "task"]:
        subset = data[data["level"] == level]
        total = len(subset)
        done = int((subset["state"].str.lower() == "closed").sum()) if total else 0
        rows.append({"level": level.title(), "Done": done, "Remaining": max(total - done, 0)})
    plot_df = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_bar(x=plot_df["level"], y=plot_df["Done"], name="Done", marker_color="#6A3A6A")
    fig.add_bar(x=plot_df["level"], y=plot_df["Remaining"], name="Remaining", marker_color="#D9C9D9")
    fig.update_layout(title="Hierarchy Completion by Level", barmode="stack", yaxis_title="Items")
    return fig


def hierarchy_status_mix_chart(scope_issues: pd.DataFrame) -> go.Figure:
    if scope_issues.empty:
        fig = go.Figure()
        fig.update_layout(title="Status Mix by Hierarchy Level")
        return fig
    data = scope_issues.copy()
    data = data[~data.apply(_is_duplicate_or_wontfix_issue, axis=1)].copy()
    data["level"] = data.apply(_hierarchy_level, axis=1)
    data = data[data["level"].isin(["epic", "feature", "task"])].copy()
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title="Status Mix by Hierarchy Level")
        return fig
    data["status"] = data.apply(_progress_status, axis=1)

    rows = []
    for level in ["epic", "feature", "task"]:
        subset = data[data["level"] == level]
        total = len(subset)
        if total == 0:
            continue
        for status in ["backlog", "in_progress", "done"]:
            count = int((subset["status"] == status).sum())
            rows.append({"level": level.title(), "status": status, "pct": (count / total) * 100})
    mix_df = pd.DataFrame(rows)
    if mix_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Status Mix by Hierarchy Level")
        return fig

    color_map = {"backlog": "#D9C9D9", "in_progress": "#A86CA8", "done": "#673366"}
    fig = px.bar(
        mix_df,
        x="level",
        y="pct",
        color="status",
        title="Status Mix by Hierarchy Level (%)",
        color_discrete_map=color_map,
    )
    fig.update_layout(barmode="stack", yaxis_title="Percent")
    return fig


def phase_burnup_chart(scope_issues: pd.DataFrame, phase_start: pd.Timestamp, phase_end: pd.Timestamp) -> go.Figure:
    if scope_issues.empty:
        fig = go.Figure()
        fig.update_layout(title="Phase Burn-up (Feb-Jun)")
        return fig
    data = scope_issues.copy()
    data = data[~data.apply(_is_duplicate_or_wontfix_issue, axis=1)].copy()
    data = data[data["closed_at"].notna()].copy()
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title="Phase Burn-up (Feb-Jun)")
        return fig

    phase = data[(data["closed_at"] >= phase_start) & (data["closed_at"] <= phase_end + pd.Timedelta(days=1))].copy()
    if phase.empty:
        fig = go.Figure()
        fig.update_layout(title="Phase Burn-up (Feb-Jun)")
        return fig
    phase["month"] = phase["closed_at"].dt.tz_convert("UTC").dt.to_period("M").dt.to_timestamp()
    monthly = phase.groupby("month").size().reset_index(name="completed")
    monthly = monthly.sort_values("month")
    monthly["cumulative"] = monthly["completed"].cumsum()
    total_scope = max(len(scope_issues[~scope_issues.apply(_is_duplicate_or_wontfix_issue, axis=1)]), 1)
    monthly["target"] = monthly["month"].apply(
        lambda m: max(
            0.0,
            min(
                float(total_scope),
                ((m.tz_localize("UTC") - phase_start).days / max((phase_end - phase_start).days, 1)) * total_scope,
            ),
        )
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=monthly["month"], y=monthly["cumulative"], mode="lines+markers", name="Completed"))
    fig.add_trace(
        go.Scatter(
            x=monthly["month"],
            y=monthly["target"],
            mode="lines",
            name="Linear target",
            line=dict(dash="dash"),
        )
    )
    fig.update_layout(title="Phase Burn-up (Feb-Jun)", yaxis_title="Cumulative completed items")
    return fig


def phase_progress_chart(time_elapsed_pct: float, work_completed_pct: float) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(x=["Time elapsed", "Work completed"], y=[time_elapsed_pct, work_completed_pct], marker_color=COSMIC_PALETTE[:2])
    fig.update_layout(title="Phase Progress Balance (Feb-Jun)", yaxis_title="Percent", yaxis_range=[0, 100])
    return fig


def milestone_plan_position_chart(
    expected_pct: float,
    actual_pct: float,
    phase_start: pd.Timestamp,
    phase_end: pd.Timestamp,
) -> go.Figure:
    exp = max(0.0, min(100.0, float(expected_pct)))
    act = max(0.0, min(100.0, float(actual_pct)))
    delta = act - exp
    gap_color = "#16A34A" if delta >= 0 else "#DC2626"
    gap_label_prefix = "Ahead" if delta >= 0 else "Behind"

    fig = go.Figure()
    # Thin baseline timeline (bottom)
    fig.add_shape(
        type="line",
        x0=0,
        x1=100,
        y0=0.18,
        y1=0.18,
        line=dict(color="#6B7280", width=2),
    )
    # Gap between expected and actual on timeline
    fig.add_shape(
        type="line",
        x0=min(exp, act),
        x1=max(exp, act),
        y0=0.18,
        y1=0.18,
        line=dict(color=gap_color, width=6),
    )
    # Expected marker on timeline
    fig.add_trace(
        go.Scatter(
            x=[exp],
            y=[0.18],
            mode="markers+text",
            marker=dict(size=11, color="#111827"),
            text=["Should be now"],
            textposition="top center",
            hoverinfo="skip",
            showlegend=False,
        )
    )
    # Actual marker on timeline
    fig.add_trace(
        go.Scatter(
            x=[act],
            y=[0.18],
            mode="markers+text",
            marker=dict(size=13, color="#673366"),
            text=["We are"],
            textposition="bottom center",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # Two bars above timeline
    fig.add_shape(type="rect", x0=0, x1=exp, y0=0.56, y1=0.70, line=dict(width=0), fillcolor="#D9C9D9")
    fig.add_shape(type="rect", x0=0, x1=act, y0=0.76, y1=0.90, line=dict(width=0), fillcolor="#673366")

    fig.add_annotation(
        x=0,
        y=0.63,
        text="Should be now",
        showarrow=False,
        xanchor="left",
        font=dict(color="#374151", size=14),
    )
    fig.add_annotation(
        x=0,
        y=0.83,
        text="We are",
        showarrow=False,
        xanchor="left",
        font=dict(color="#FFFFFF", size=14),
    )
    fig.add_annotation(
        x=max(act - 1.0, 1.5),
        y=0.83,
        text=f"{act:.1f}%",
        showarrow=False,
        xanchor="right",
        font=dict(color="#FFFFFF", size=14),
    )
    fig.add_annotation(
        x=max(exp - 1.0, 1.5),
        y=0.63,
        text=f"{exp:.1f}%",
        showarrow=False,
        xanchor="right",
        font=dict(color="#111827", size=14),
    )

    fig.update_layout(
        title="Plan vs Actual Position",
        xaxis_title="",
        yaxis_title="",
        xaxis=dict(range=[0, 100], showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(visible=False, range=[0, 1]),
        showlegend=False,
        height=340,
    )
    fig.add_annotation(x=0, y=0.06, text=str(phase_start.date()), showarrow=False, xanchor="left", font=dict(size=13))
    fig.add_annotation(x=100, y=0.06, text=str(phase_end.date()), showarrow=False, xanchor="right", font=dict(size=13))
    fig.add_annotation(
        x=(exp + act) / 2,
        y=0.30,
        text=f"{gap_label_prefix}: {abs(delta):.1f}%",
        showarrow=False,
        font=dict(color=gap_color, size=14),
    )
    return fig


def completed_hierarchy_counts(scope_issues: pd.DataFrame) -> pd.DataFrame:
    if scope_issues.empty:
        return pd.DataFrame(columns=["level", "completed"])
    data = scope_issues.copy()
    data = data[~data.apply(_is_duplicate_or_wontfix_issue, axis=1)].copy()
    data["issue_type"] = data.apply(_infer_issue_type, axis=1)
    data = data[data["issue_type"].isin(["epic", "feature", "task"])].copy()
    if data.empty:
        return pd.DataFrame(columns=["level", "completed"])
    done = data[data["state"].str.lower() == "closed"].copy()
    rows = []
    for level in ["epic", "feature", "task"]:
        rows.append(
            {
                "level": level.title(),
                "completed": int((done["issue_type"] == level).sum()),
            }
        )
    return pd.DataFrame(rows)


def completed_hierarchy_chart(scope_issues: pd.DataFrame) -> go.Figure:
    counts = completed_hierarchy_counts(scope_issues)
    if counts.empty:
        fig = go.Figure()
        fig.update_layout(title="Completed Epics / Features / Tasks")
        return fig
    return px.bar(counts, x="level", y="completed", title="Completed Epics / Features / Tasks")


def _average_completed_counts(all_issues: pd.DataFrame) -> pd.DataFrame:
    if all_issues.empty:
        return pd.DataFrame(columns=["level", "avg_completed"])
    data = all_issues.copy()
    data = data[~data.apply(_is_duplicate_or_wontfix_issue, axis=1)].copy()
    data = data[data["milestone"].notna()].copy()
    data["issue_type"] = data.apply(_infer_issue_type, axis=1)
    data = data[data["issue_type"].isin(["epic", "feature", "task"])].copy()
    data = data[data["state"].str.lower() == "closed"].copy()
    if data.empty:
        return pd.DataFrame(columns=["level", "avg_completed"])

    grouped = data.groupby(["milestone", "issue_type"]).size().reset_index(name="completed")
    pivot = grouped.pivot(index="milestone", columns="issue_type", values="completed").fillna(0)
    for col in ["epic", "feature", "task"]:
        if col not in pivot.columns:
            pivot[col] = 0
    avg = pivot[["epic", "feature", "task"]].mean().reset_index()
    avg.columns = ["level", "avg_completed"]
    avg["level"] = avg["level"].str.title()
    return avg


def hierarchy_vs_average_chart(
    scope_issues: pd.DataFrame,
    all_issues: pd.DataFrame,
    scope_label: str,
) -> go.Figure:
    current = completed_hierarchy_counts(scope_issues)
    avg = _average_completed_counts(all_issues)
    if current.empty:
        fig = go.Figure()
        fig.update_layout(title="Completed Hierarchy vs Milestone Average")
        return fig
    merged = current.merge(avg, on="level", how="left").fillna(0)
    fig = go.Figure()
    fig.add_bar(x=merged["level"], y=merged["completed"], name=f"{scope_label} Completed")
    fig.add_bar(x=merged["level"], y=merged["avg_completed"], name="Milestone Average Completed")
    fig.update_layout(title="Completed Hierarchy vs Milestone Average", barmode="group", yaxis_title="Count")
    return fig


def _has_label(labels: list[str], name: str) -> bool:
    return any(str(label).strip().lower() == name.lower() for label in labels)


def _title_prefix(title: str) -> str:
    match = re.match(r"\s*\[([^\]]+)\]", title or "")
    return match.group(1).strip().lower() if match else ""


def _clean_title(title: str) -> str:
    return re.sub(r"^\s*(\[[^\]]+\]\s*)+", "", title or "").strip()


def _infer_issue_type(row: pd.Series) -> str:
    title = row.get("title", "") or ""
    prefix = _title_prefix(title)

    if prefix == "epic":
        return "epic"
    if prefix == "feature":
        return "feature"
    if prefix == "task":
        return "task"
    return "other"


def _normalize_text(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "").replace("_", "").replace(" ", "")


def _is_duplicate_or_wontfix_issue(row: pd.Series) -> bool:
    labels = row.get("labels", [])
    if not isinstance(labels, list):
        labels = []
    normalized_labels = {_normalize_text(label) for label in labels}
    excluded_markers = {
        "duplicate",
        "wontfix",
        "wontdo",
        "invalid",
        "notplanned",
        "declined",
    }
    if normalized_labels & excluded_markers:
        return True

    state_reason = _normalize_text(row.get("state_reason", ""))
    if state_reason in {"notplanned", "duplicate"}:
        return True

    return False


def _is_active_hierarchy_issue(row: pd.Series) -> bool:
    return str(row.get("state", "")).strip().lower() != "closed" and not _is_duplicate_or_wontfix_issue(row)


def _extract_issue_refs(text: str) -> list[int]:
    text = text or ""
    hash_refs = re.findall(r"#(\d+)", text)
    url_refs = re.findall(r"/issues/(\d+)", text)
    combined = hash_refs + url_refs
    unique = []
    seen = set()
    for ref in combined:
        n = int(ref)
        if n in seen:
            continue
        seen.add(n)
        unique.append(n)
    return unique


def _token_set(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]{3,}", (text or "").lower())
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "workflow",
        "implement",
        "implementation",
        "document",
        "documentation",
        "ensure",
        "data",
        "system",
        "project",
    }
    return {w for w in words if w not in stop}


def _similarity_score(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _choose_parent(child_tokens: set[str], candidates: pd.DataFrame, milestone: Optional[str]) -> Optional[int]:
    if candidates.empty:
        return None

    local = candidates
    if milestone:
        same_milestone = candidates[candidates["milestone"] == milestone]
        if not same_milestone.empty:
            local = same_milestone

    best_number = None
    best_score = -1.0
    for _, row in local.iterrows():
        score = _similarity_score(child_tokens, row["tokens"])
        if score > best_score:
            best_score = score
            best_number = int(row["number"])

    if best_score <= 0:
        return None
    return best_number


def _normalize_labels(labels: list[str]) -> set[str]:
    if not isinstance(labels, list):
        return set()
    return {str(l).strip().lower().replace("-", " ").replace("_", " ") for l in labels}


def _progress_status(row: pd.Series) -> str:
    if str(row.get("state", "")).strip().lower() == "closed":
        return "done"
    labels = _normalize_labels(row.get("labels", []))
    if any(x in labels for x in {"in progress", "wip", "doing"}):
        return "in_progress"
    return "backlog"


def _task_weight(row: pd.Series, use_size: bool) -> int:
    if use_size:
        return 1
    return 1


def _markdown_to_plain(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"```[\s\S]*?```", " ", value)
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"(^|\s)#{1,6}\s*", " ", value)
    value = re.sub(r"[*_~>-]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _short_description(text: str, limit: int = 280) -> str:
    clean = _markdown_to_plain(text)
    if not clean:
        return "No description"
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "..."


def _short_box_description(text: str) -> str:
    clean = _markdown_to_plain(text)
    if not clean:
        return ""
    return clean


def _wrap_box_text(text: str, line_chars: int = 42) -> str:
    clean = _short_box_description(text)
    if not clean:
        return "No description"
    words = clean.split()
    lines: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        add_len = len(word) if not current else len(word) + 1
        if current and current_len + add_len > line_chars:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += add_len
    if current:
        lines.append(" ".join(current))
    return "<br>".join(lines)


def _build_progress_hierarchy(scope_issues: pd.DataFrame, use_size: bool, include_epics: bool) -> pd.DataFrame:
    columns = [
        "epic_label",
        "feature_label",
        "task_label",
        "status",
        "weight",
        "kind",
        "description",
        "issue_number",
        "body_markdown",
    ]
    if scope_issues.empty:
        return pd.DataFrame(columns=columns)

    work = scope_issues.copy()
    work = work[~work.apply(_is_duplicate_or_wontfix_issue, axis=1)].copy()
    work["issue_type"] = work.apply(_infer_issue_type, axis=1)
    work["clean_title"] = work["title"].fillna("").apply(_clean_title)
    work["refs"] = work["body"].fillna("").apply(_extract_issue_refs)
    work["tokens"] = work["clean_title"].apply(_token_set)

    epics = work[work["issue_type"] == "epic"].copy()
    features = work[work["issue_type"] == "feature"].copy()
    tasks = work[work["issue_type"] == "task"].copy()

    epic_numbers = set(epics["number"].dropna().astype(int).tolist()) if not epics.empty else set()
    feature_numbers = set(features["number"].dropna().astype(int).tolist()) if not features.empty else set()
    task_numbers = set(tasks["number"].dropna().astype(int).tolist()) if not tasks.empty else set()

    feature_to_epic: dict[int, int] = {}
    for _, feature in features.iterrows():
        fnum = int(feature["number"])
        refs = [int(r) for r in feature.get("refs", []) if int(r) in epic_numbers]
        if refs:
            feature_to_epic[fnum] = min(refs)
    for _, epic in epics.iterrows():
        enum = int(epic["number"])
        refs = [int(r) for r in epic.get("refs", []) if int(r) in feature_numbers]
        for fnum in refs:
            feature_to_epic.setdefault(fnum, enum)
    if include_epics and not features.empty and not epics.empty:
        for _, feature in features.iterrows():
            fnum = int(feature["number"])
            if fnum in feature_to_epic:
                continue
            milestone = feature.get("milestone") if pd.notna(feature.get("milestone")) else None
            parent = _choose_parent(feature["tokens"], epics[["number", "tokens", "milestone"]], milestone)
            if parent is not None:
                feature_to_epic[fnum] = int(parent)

    feature_to_tasks: dict[int, set[int]] = {int(n): set() for n in feature_numbers}
    for _, feature in features.iterrows():
        fnum = int(feature["number"])
        refs = [int(r) for r in feature.get("refs", []) if int(r) in task_numbers]
        feature_to_tasks.setdefault(fnum, set()).update(refs)
    for _, task in tasks.iterrows():
        tnum = int(task["number"])
        refs = [int(r) for r in task.get("refs", []) if int(r) in feature_numbers]
        for fnum in refs:
            feature_to_tasks.setdefault(fnum, set()).add(tnum)
    if not tasks.empty and not features.empty:
        for _, task in tasks.iterrows():
            tnum = int(task["number"])
            linked = any(tnum in v for v in feature_to_tasks.values())
            if linked:
                continue
            milestone = task.get("milestone") if pd.notna(task.get("milestone")) else None
            parent = _choose_parent(task["tokens"], features[["number", "tokens", "milestone"]], milestone)
            if parent is not None:
                feature_to_tasks.setdefault(int(parent), set()).add(tnum)

    feature_lookup = {int(r["number"]): r for _, r in features.iterrows()}
    task_lookup = {int(r["number"]): r for _, r in tasks.iterrows()}
    epic_lookup = {int(r["number"]): r for _, r in epics.iterrows()}

    rows: list[dict] = []
    assigned_tasks: set[int] = set()

    for fnum in sorted(feature_lookup.keys()):
        feature = feature_lookup[fnum]
        epic_label = ""
        if include_epics:
            enum = feature_to_epic.get(fnum)
            if enum and enum in epic_lookup:
                erow = epic_lookup[enum]
                epic_label = f"#{int(erow['number'])} {erow['clean_title']}"
            else:
                epic_label = "Unmapped Epic"

        feature_label = f"#{fnum} {feature['clean_title']}"
        child_tasks = sorted(feature_to_tasks.get(fnum, set()))

        if child_tasks:
            for tnum in child_tasks:
                if tnum not in task_lookup:
                    continue
                trow = task_lookup[tnum]
                assigned_tasks.add(tnum)
                rows.append(
                    {
                        "epic_label": epic_label,
                        "feature_label": feature_label,
                        "task_label": f"#{tnum} {trow['clean_title']}",
                        "status": _progress_status(trow),
                        "weight": _task_weight(trow, use_size=use_size),
                        "kind": "task",
                        "description": _short_description(trow.get("body", "")),
                        "issue_number": int(tnum),
                        "body_markdown": str(trow.get("body", "") or ""),
                    }
                )
        else:
            rows.append(
                {
                    "epic_label": epic_label,
                    "feature_label": feature_label,
                    "task_label": "No linked task",
                    "status": _progress_status(feature),
                    "weight": 1,
                    "kind": "feature_no_task",
                    "description": _short_description(feature.get("body", "")),
                    "issue_number": int(fnum),
                    "body_markdown": str(feature.get("body", "") or ""),
                }
            )

    for tnum in sorted(task_lookup.keys()):
        if tnum in assigned_tasks:
            continue
        trow = task_lookup[tnum]
        rows.append(
            {
                "epic_label": "Unmapped Epic" if include_epics else "",
                "feature_label": "Unmapped Feature",
                "task_label": f"#{tnum} {trow['clean_title']}",
                "status": _progress_status(trow),
                "weight": _task_weight(trow, use_size=use_size),
                "kind": "task_orphan",
                "description": _short_description(trow.get("body", "")),
                "issue_number": int(tnum),
                "body_markdown": str(trow.get("body", "") or ""),
            }
        )

    return pd.DataFrame(rows, columns=columns)


def progress_heatmap_chart(blocks_df: pd.DataFrame, title: str, include_epics: bool) -> go.Figure:
    if blocks_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    color_map = {
        "done": "#86EFAC",
        "in_progress": "#FDBA74",
        "backlog": "#CBD5E1",
    }
    data = blocks_df.copy()
    data["root"] = "Scope"
    data["task_box_label"] = data["task_label"]
    task_mask = data["kind"].isin(["task", "task_orphan"])
    data.loc[task_mask, "task_box_label"] = data.loc[task_mask].apply(
        lambda r: f"{r['task_label']}<br>Description:<br>{_wrap_box_text(r['body_markdown'])}",
        axis=1,
    )
    path = ["root", "feature_label", "task_label"]
    if include_epics:
        path = ["root", "epic_label", "feature_label", "task_label"]
    path = [p if p != "task_label" else "task_box_label" for p in path]

    fig = px.treemap(
        data,
        path=path,
        values="weight",
            color="status",
            color_discrete_map=color_map,
            title=title,
            custom_data=["kind", "weight", "status", "description", "issue_number", "body_markdown"],
    )
    fig.update_traces(
        textinfo="label",
        texttemplate="%{label}",
        textfont=dict(size=16),
        hoverinfo="skip",
        hovertemplate=None,
    )
    fig.update_layout(
        margin=dict(l=8, r=8, t=56, b=8),
        height=680,
    )
    return fig


def _extract_selected_task_customdata(selection: object) -> Optional[list]:
    if selection is None:
        return None
    payload = selection
    if hasattr(selection, "selection"):
        payload = getattr(selection, "selection")
    if hasattr(payload, "get"):
        points = payload.get("points", [])
    else:
        points = getattr(payload, "points", [])
    if not points:
        return None
    point = points[0]
    if hasattr(point, "get"):
        return point.get("customdata")
    return getattr(point, "customdata", None)


def choose_current_milestone(milestones_df: pd.DataFrame) -> Optional[str]:
    if milestones_df.empty:
        return None

    open_milestones = milestones_df[milestones_df["state"].str.lower() == "open"].copy() if "state" in milestones_df.columns else milestones_df.copy()
    if open_milestones.empty:
        return None

    open_milestones["due_rank"] = open_milestones["due_on"].fillna(pd.Timestamp.max.tz_localize("UTC"))
    open_milestones = open_milestones.sort_values(["due_rank", "open_issues"], ascending=[True, False])
    top = open_milestones.iloc[0]
    return str(top.get("title")) if pd.notna(top.get("title")) else None


QUALITY_HISTORY_PATH = os.path.join(ROOT_DIR, "quality_history.json")


def _run_check(cmd: list[str], cwd: str) -> dict:
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=1200,
            check=False,
        )
        return {
            "name": " ".join(cmd),
            "status": "PASS" if result.returncode == 0 else "FAIL",
            "returncode": result.returncode,
            "stdout": (result.stdout or "")[-2000:],
            "stderr": (result.stderr or "")[-2000:],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "name": " ".join(cmd),
            "status": "FAIL",
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
        }


def _python_has_module(python_bin: str, module_name: str, cwd: str) -> bool:
    check = subprocess.run(
        [python_bin, "-c", f"import {module_name}"],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return check.returncode == 0


def _parse_pytest_counts(stdout: str, stderr: str) -> dict:
    text = f"{stdout}\n{stderr}"
    passed = 0
    failed = 0
    errors = 0
    m = re.search(r"(\d+)\s+passed", text)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+)\s+failed", text)
    if m:
        failed = int(m.group(1))
    m = re.search(r"(\d+)\s+error", text)
    if m:
        errors = int(m.group(1))
    return {"passed_tests": passed, "failed_tests": failed + errors}


def _parse_coverage_pct(stdout: str, stderr: str) -> float:
    text = f"{stdout}\n{stderr}"
    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", text)
    if match:
        return float(match.group(1))
    return 0.0


def _parse_coverage_json(path: str) -> dict:
    if not os.path.exists(path):
        return {"coverage_pct": 0.0, "covered_lines": 0, "total_lines": 0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        totals = payload.get("totals", {}) if isinstance(payload, dict) else {}
        total_lines = int(totals.get("num_statements", 0) or 0)
        covered_lines = int(totals.get("covered_lines", 0) or 0)
        pct = (covered_lines / total_lines * 100.0) if total_lines else 0.0
        return {"coverage_pct": pct, "covered_lines": covered_lines, "total_lines": total_lines}
    except Exception:  # noqa: BLE001
        return {"coverage_pct": 0.0, "covered_lines": 0, "total_lines": 0}


def _parse_frontend_coverage_json(path: str) -> dict:
    if not os.path.exists(path):
        return {"coverage_pct": 0.0, "covered_lines": 0, "total_lines": 0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        total = payload.get("total", {}) if isinstance(payload, dict) else {}
        lines = total.get("lines", {}) if isinstance(total, dict) else {}
        total_lines = int(lines.get("total", 0) or 0)
        covered_lines = int(lines.get("covered", 0) or 0)
        pct = float(lines.get("pct", 0.0) or 0.0)
        return {"coverage_pct": pct, "covered_lines": covered_lines, "total_lines": total_lines}
    except Exception:  # noqa: BLE001
        return {"coverage_pct": 0.0, "covered_lines": 0, "total_lines": 0}


def _run_backend_tests(repo_root: str) -> dict:
    backend_cov_json = os.path.join(repo_root, "03_application", "backend", ".coverage_backend.json")
    root_venv_python = os.path.join(repo_root, ".venv", "bin", "python")
    py_candidates = [root_venv_python, "python3"]
    for py in py_candidates:
        if py != "python3" and not os.path.exists(py):
            continue
        if not _python_has_module(py, "pytest", repo_root):
            continue
        result = _run_check(
            [
                py,
                "-m",
                "pytest",
                "-q",
                "03_application/tests/backend",
                "--cov=03_application/backend/app",
                "--cov-report=term",
                f"--cov-report=json:{backend_cov_json}",
            ],
            repo_root,
        )
        result["label"] = "Backend tests: pytest (03 application backend)"
        counts = _parse_pytest_counts(result.get("stdout", ""), result.get("stderr", ""))
        result.update(counts)
        result.update(_parse_coverage_json(backend_cov_json))
        return result

    return {
        "label": "Backend tests: pytest (03 application backend)",
        "name": "pytest not available",
        "status": "FAIL",
        "returncode": 1,
        "passed_tests": 0,
        "failed_tests": 0,
        "coverage_pct": 0.0,
        "covered_lines": 0,
        "total_lines": 0,
        "stdout": "",
        "stderr": "pytest is not installed in project .venv or system python.",
    }


def _parse_vitest_counts(stdout: str, stderr: str) -> dict:
    text = f"{stdout}\n{stderr}"
    passed = 0
    failed = 0
    m = re.search(r"(\d+)\s+passed", text)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+)\s+failed", text)
    if m:
        failed = int(m.group(1))
    return {"passed_tests": passed, "failed_tests": failed}


def _run_frontend_tests(repo_root: str) -> dict:
    frontend_dir = os.path.join(repo_root, "03_application", "frontend")
    frontend_cov_json = os.path.join(frontend_dir, "coverage", "coverage-summary.json")
    result = _run_check(["npm", "run", "test", "--", "--coverage"], frontend_dir)
    result["label"] = "Frontend tests: vitest (03 application frontend)"
    result.update(_parse_vitest_counts(result.get("stdout", ""), result.get("stderr", "")))
    result.update(_parse_frontend_coverage_json(frontend_cov_json))
    return result


def run_quality_snapshot(repo_root: str) -> dict:
    backend_result = _run_backend_tests(repo_root)
    backend_result["category"] = "backend_runtime"
    frontend_result = _run_frontend_tests(repo_root)
    frontend_result["category"] = "frontend_runtime"
    runs = [backend_result, frontend_result]

    total = len(runs)
    passed = sum(1 for r in runs if r.get("status") == "PASS")
    failed = sum(1 for r in runs if r.get("status") == "FAIL")
    considered = total
    snapshot = {
        "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "total_checks": total,
        "passed_checks": passed,
        "failed_checks": failed,
        "pass_rate_pct": round((passed / considered) * 100, 1) if considered else 0.0,
        "checks": runs,
    }
    for cat in ["backend_runtime", "frontend_runtime"]:
        cat_checks = [r for r in runs if r.get("category") == cat]
        c_pass = sum(1 for r in cat_checks if r.get("status") == "PASS")
        c_fail = sum(1 for r in cat_checks if r.get("status") == "FAIL")
        c_considered = len(cat_checks)
        snapshot[f"{cat}_summary"] = {"passed": c_pass, "failed": c_fail, "total": len(cat_checks)}
        snapshot[f"{cat}_pass_rate_pct"] = round((c_pass / c_considered) * 100, 1) if c_considered else 0.0

    rt_passed_tests = int(backend_result.get("passed_tests", 0)) + int(frontend_result.get("passed_tests", 0))
    rt_failed_tests = int(backend_result.get("failed_tests", 0)) + int(frontend_result.get("failed_tests", 0))
    rt_total_tests = rt_passed_tests + rt_failed_tests
    snapshot["runtime_tests_summary"] = {
        "passed_tests": rt_passed_tests,
        "failed_tests": rt_failed_tests,
        "total_tests": rt_total_tests,
    }
    snapshot["runtime_tests_pass_rate_pct"] = round((rt_passed_tests / rt_total_tests) * 100, 1) if rt_total_tests else 0.0
    snapshot["backend_coverage_pct"] = float(backend_result.get("coverage_pct", 0.0))
    snapshot["frontend_coverage_pct"] = float(frontend_result.get("coverage_pct", 0.0))

    backend_total = int(backend_result.get("total_lines", 0))
    frontend_total = int(frontend_result.get("total_lines", 0))
    backend_covered = int(backend_result.get("covered_lines", 0))
    frontend_covered = int(frontend_result.get("covered_lines", 0))
    app_total = backend_total + frontend_total
    app_covered = backend_covered + frontend_covered
    snapshot["application_coverage_pct"] = round((app_covered / app_total) * 100, 1) if app_total else 0.0
    snapshot["coverage_pct"] = snapshot["application_coverage_pct"]
    return snapshot


def load_quality_history() -> list[dict]:
    if not os.path.exists(QUALITY_HISTORY_PATH):
        return []
    try:
        with open(QUALITY_HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def save_quality_history(history: list[dict]) -> None:
    with open(QUALITY_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def runtime_test_results_chart(history: list[dict]) -> go.Figure:
    title = "Weekly Runtime Tests (Passed vs Failed)"
    if not history:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig

    rows: list[dict] = []
    for item in history:
        ts = pd.to_datetime(item.get("timestamp"), utc=True, errors="coerce")
        if pd.isna(ts):
            continue
        week = ts.tz_convert("UTC").to_period("W").start_time
        summary = item.get("runtime_tests_summary", {}) or {}
        passed = int(summary.get("passed_tests", 0))
        failed = int(summary.get("failed_tests", 0))
        total = passed + failed
        pass_rate = (passed / total * 100.0) if total else 0.0
        rows.append(
            {
                "week": week,
                "passed": passed,
                "failed": failed,
                "total": total,
                "pass_rate_pct": pass_rate,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig

    # Keep last snapshot per week.
    df = df.sort_values("week").groupby("week", as_index=False).last()

    fig = go.Figure()
    fig.add_bar(
        x=df["week"],
        y=df["passed"],
        name="Passed",
        marker_color="#16A34A",
        text=df["passed"].astype(str),
        textposition="inside",
    )
    fig.add_bar(
        x=df["week"],
        y=df["failed"],
        name="Failed",
        marker_color="#DC2626",
        text=df["failed"].astype(str),
        textposition="inside",
    )
    fig.add_trace(
        go.Scatter(
            x=df["week"],
            y=df["total"],
            mode="text",
            text=[f"{v:.1f}% pass" for v in df["pass_rate_pct"]],
            textposition="top center",
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.update_layout(title=title, barmode="stack")
    fig.update_yaxes(title="Tests")
    return fig


def coverage_trend_chart(history: list[dict]) -> go.Figure:
    title = "Weekly Test Coverage"
    if not history:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    rows = []
    for item in history[-12:]:
        ts = pd.to_datetime(item.get("timestamp"), utc=True, errors="coerce")
        rows.append({"timestamp": ts, "coverage_pct": float(item.get("coverage_pct", 0.0))})
    df = pd.DataFrame(rows).dropna()
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    df["week"] = df["timestamp"].dt.tz_convert("UTC").dt.to_period("W").dt.start_time
    df = df.sort_values("timestamp").groupby("week", as_index=False).last()
    fig = px.bar(df, x="week", y="coverage_pct", title=title, text="coverage_pct")
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_yaxes(range=[0, 100], title="Coverage (%)")
    return fig


def deployment_placeholder_chart(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=title)
    fig.add_annotation(
        text="No deployment data yet",
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
    )
    return fig


def weekly_pr_throughput(prs_df: pd.DataFrame) -> go.Figure:
    if prs_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Weekly PR Throughput")
        return fig
    opened = prs_df.dropna(subset=["created_at"]).copy()
    opened["week"] = opened["created_at"].dt.tz_localize(None).dt.to_period("W").dt.start_time
    opened = opened.groupby("week").size().reset_index(name="opened")

    merged = prs_df.dropna(subset=["merged_at"]).copy()
    merged["week"] = merged["merged_at"].dt.tz_localize(None).dt.to_period("W").dt.start_time
    merged = merged.groupby("week").size().reset_index(name="merged")

    trend = pd.merge(opened, merged, on="week", how="outer").fillna(0).sort_values("week")
    fig = go.Figure()
    fig.add_bar(x=trend["week"], y=trend["opened"], name="Opened")
    fig.add_bar(x=trend["week"], y=trend["merged"], name="Merged")
    fig.update_layout(title="Weekly PR Throughput", barmode="group", yaxis_title="PR count")
    return fig


def pr_merge_time_distribution(prs_df: pd.DataFrame) -> go.Figure:
    if prs_df.empty or "merged_at" not in prs_df.columns:
        fig = go.Figure()
        fig.update_layout(title="PR Merge Time Distribution (Days)")
        return fig
    data = prs_df.dropna(subset=["created_at", "merged_at"]).copy()
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title="PR Merge Time Distribution (Days)")
        return fig
    data["merge_days"] = _delta_days(data["merged_at"], data["created_at"])
    fig = px.histogram(data, x="merge_days", nbins=20, title="PR Merge Time Distribution (Days)")
    fig.update_xaxes(title="Days to merge")
    fig.update_yaxes(title="PR count")
    return fig


def bug_status_pie(issues_df: pd.DataFrame) -> go.Figure:
    if issues_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Bug Issue Status")
        return fig
    bugs = issues_df[
        issues_df["labels"].apply(
            lambda labels: isinstance(labels, list)
            and any("bug" in str(label).strip().lower() for label in labels)
        )
    ].copy()
    if bugs.empty:
        fig = go.Figure()
        fig.update_layout(title="Bug Issue Status")
        return fig
    counts = bugs.groupby("state").size().reset_index(name="count")
    return px.pie(counts, names="state", values="count", hole=0.45, title="Bug Issue Status")


def bug_open_close_trend(issues_df: pd.DataFrame) -> go.Figure:
    if issues_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Bug Opened vs Closed Trend")
        return fig
    bugs = issues_df[
        issues_df["labels"].apply(
            lambda labels: isinstance(labels, list)
            and any("bug" in str(label).strip().lower() for label in labels)
        )
    ].copy()
    if bugs.empty:
        fig = go.Figure()
        fig.update_layout(title="Bug Opened vs Closed Trend")
        return fig
    opened = bugs.dropna(subset=["created_at"]).copy()
    opened["week"] = opened["created_at"].dt.tz_localize(None).dt.to_period("W").dt.start_time
    opened = opened.groupby("week").size().reset_index(name="opened")
    closed = bugs.dropna(subset=["closed_at"]).copy()
    closed["week"] = closed["closed_at"].dt.tz_localize(None).dt.to_period("W").dt.start_time
    closed = closed.groupby("week").size().reset_index(name="closed")
    trend = pd.merge(opened, closed, on="week", how="outer").fillna(0).sort_values("week")
    fig = go.Figure()
    fig.add_bar(x=trend["week"], y=trend["opened"], name="Opened")
    fig.add_bar(x=trend["week"], y=trend["closed"], name="Closed")
    fig.update_layout(title="Bug Opened vs Closed Trend", barmode="group", yaxis_title="Bug issues")
    return fig


def top_contributors_chart(issues_df: pd.DataFrame, prs_df: pd.DataFrame) -> go.Figure:
    issue_authors = (
        issues_df["author"].dropna().value_counts().rename("issues")
        if not issues_df.empty and "author" in issues_df.columns else pd.Series(dtype=int)
    )
    pr_authors = (
        prs_df["author"].dropna().value_counts().rename("prs")
        if not prs_df.empty and "author" in prs_df.columns else pd.Series(dtype=int)
    )
    combined = pd.concat([issue_authors, pr_authors], axis=1).fillna(0)
    if combined.empty:
        fig = go.Figure()
        fig.update_layout(title="Top Contributors (Issues + PRs)")
        return fig
    combined["total"] = combined["issues"] + combined["prs"]
    combined = combined.sort_values("total", ascending=False).head(10).reset_index(names="author")
    fig = go.Figure()
    fig.add_bar(x=combined["author"], y=combined["issues"], name="Issues")
    fig.add_bar(x=combined["author"], y=combined["prs"], name="PRs")
    fig.update_layout(title="Top Contributors (Issues + PRs)", barmode="stack", yaxis_title="Contributions")
    return fig


def _pr_with_first_review(prs_df: pd.DataFrame, pr_reviews_df: pd.DataFrame) -> pd.DataFrame:
    if prs_df.empty:
        return prs_df.copy()
    out = prs_df.copy()
    if pr_reviews_df.empty or "pr_number" not in pr_reviews_df.columns:
        out["first_review_at"] = pd.NaT
        return out
    review_times = (
        pr_reviews_df.dropna(subset=["submitted_at"])
        .groupby("pr_number", as_index=False)["submitted_at"]
        .min()
        .rename(columns={"submitted_at": "first_review_at"})
    )
    return out.merge(review_times, left_on="number", right_on="pr_number", how="left")


def weekly_commit_activity(commits_df: pd.DataFrame) -> go.Figure:
    title = "Weekly Commit Activity"
    if commits_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    data = commits_df.dropna(subset=["date"]).copy()
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    data["week"] = data["date"].dt.tz_localize(None).dt.to_period("W").dt.start_time
    trend = data.groupby("week", as_index=False).size().rename(columns={"size": "commits"})
    fig = px.bar(trend, x="week", y="commits", title=title)
    fig.update_yaxes(title="Commits")
    return fig


def commits_per_developer_chart(commits_df: pd.DataFrame) -> go.Figure:
    title = "Commits per Developer"
    if commits_df.empty or "author" not in commits_df.columns:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    counts = commits_df["author"].dropna().value_counts().head(12).reset_index()
    if counts.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    counts.columns = ["author", "commits"]
    fig = px.bar(counts, x="author", y="commits", title=title)
    fig.update_yaxes(title="Commits")
    return fig


def code_churn_by_week_chart(prs_df: pd.DataFrame) -> go.Figure:
    title = "Weekly Code Churn from Merged PRs"
    req = {"merged_at", "additions", "deletions"}
    if prs_df.empty or not req.issubset(set(prs_df.columns)):
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    data = prs_df.dropna(subset=["merged_at"]).copy()
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    data["week"] = data["merged_at"].dt.tz_localize(None).dt.to_period("W").dt.start_time
    trend = data.groupby("week", as_index=False)[["additions", "deletions"]].sum()
    fig = go.Figure()
    fig.add_bar(x=trend["week"], y=trend["additions"], name="Additions", marker_color="#374151")
    fig.add_bar(x=trend["week"], y=trend["deletions"], name="Deletions", marker_color="#9CA3AF")
    fig.update_layout(title=title, barmode="group")
    fig.update_yaxes(title="Lines")
    return fig


def workflow_weekly_outcomes_chart(workflows_df: pd.DataFrame) -> go.Figure:
    title = "Weekly Pipeline Outcomes"
    if workflows_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    data = workflows_df.dropna(subset=["created_at"]).copy()
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    data["week"] = data["created_at"].dt.tz_localize(None).dt.to_period("W").dt.start_time
    data["outcome"] = data["conclusion"].fillna("other").str.lower()
    data["outcome"] = data["outcome"].where(data["outcome"].isin(["success", "failure", "cancelled"]), "other")
    trend = data.groupby(["week", "outcome"], as_index=False).size().rename(columns={"size": "count"})
    fig = px.bar(
        trend,
        x="week",
        y="count",
        color="outcome",
        title=title,
        color_discrete_map={"success": "#16A34A", "failure": "#DC2626", "cancelled": "#F59E0B", "other": "#9CA3AF"},
    )
    fig.update_layout(barmode="stack")
    return fig


def workflow_duration_trend_chart(workflows_df: pd.DataFrame) -> go.Figure:
    title = "Pipeline Duration Trend"
    if workflows_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    data = workflows_df.dropna(subset=["created_at", "updated_at"]).copy()
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    data["duration_min"] = _delta_hours(data["updated_at"], data["created_at"]) * 60.0
    data = data[data["duration_min"] >= 0].copy()
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    data["week"] = data["created_at"].dt.tz_localize(None).dt.to_period("W").dt.start_time
    trend = data.groupby("week", as_index=False)["duration_min"].median()
    fig = px.line(trend, x="week", y="duration_min", markers=True, title=title)
    fig.update_yaxes(title="Median duration (min)")
    return fig


def bug_severity_distribution_chart(defects_df: pd.DataFrame) -> go.Figure:
    title = "Bug Severity Distribution"
    if defects_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig

    def severity_from_labels(labels: list[str]) -> str:
        vals = {str(x).strip().lower() for x in (labels or [])}
        if any(x in vals for x in {"severity: critical", "critical", "sev1", "p0"}):
            return "critical"
        if any(x in vals for x in {"severity: high", "high", "sev2", "p1"}):
            return "high"
        if any(x in vals for x in {"severity: medium", "medium", "sev3", "p2"}):
            return "medium"
        if any(x in vals for x in {"severity: low", "low", "sev4", "p3"}):
            return "low"
        return "unlabeled"

    data = defects_df.copy()
    data["severity"] = data["labels"].apply(severity_from_labels)
    counts = data["severity"].value_counts().reset_index()
    counts.columns = ["severity", "count"]
    fig = px.bar(
        counts,
        x="severity",
        y="count",
        title=title,
        color="severity",
        color_discrete_map={
            "critical": "#B91C1C",
            "high": "#DC2626",
            "medium": "#F59E0B",
            "low": "#9CA3AF",
            "unlabeled": "#D1D5DB",
        },
    )
    return fig


def collaboration_distribution_chart(issues_df: pd.DataFrame, prs_df: pd.DataFrame, commits_df: pd.DataFrame) -> go.Figure:
    title = "Contribution Distribution (Issues + PRs + Commits)"
    issue_auth = issues_df["author"].dropna().value_counts() if not issues_df.empty else pd.Series(dtype=int)
    pr_auth = prs_df["author"].dropna().value_counts() if not prs_df.empty else pd.Series(dtype=int)
    commit_auth = commits_df["author"].dropna().value_counts() if not commits_df.empty else pd.Series(dtype=int)
    merged = pd.concat([issue_auth.rename("issues"), pr_auth.rename("prs"), commit_auth.rename("commits")], axis=1).fillna(0)
    if merged.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig
    merged["total"] = merged.sum(axis=1)
    merged = merged.sort_values("total", ascending=False).head(12).reset_index(names="author")
    fig = go.Figure()
    fig.add_bar(x=merged["author"], y=merged["issues"], name="Issues", marker_color="#111827")
    fig.add_bar(x=merged["author"], y=merged["prs"], name="PRs", marker_color="#6B7280")
    fig.add_bar(x=merged["author"], y=merged["commits"], name="Commits", marker_color="#9CA3AF")
    fig.update_layout(title=title, barmode="stack")
    return fig

def _dot_header(rankdir: str = "LR") -> str:
    return (
        "digraph G {\n"
        f'  rankdir={rankdir};\n'
        '  graph [bgcolor="white", pad="0.25", nodesep="0.5", ranksep="0.7", splines=ortho];\n'
        '  node [shape=box, style="rounded,filled", color="#64748b", fillcolor="#f1f5f9", fontname="Helvetica", fontsize=11, margin="0.12,0.08"];\n'
        '  edge [color="#64748b", arrowsize=0.7, penwidth=1.2];\n'
    )


def c4_container_diagram_dot() -> str:
    return (
        _dot_header("LR")
        + '  user [label="Users"];\n'
        + '  frontend [label="Web Frontend\\nReact + Vite"];\n'
        + '  backend [label="Application Backend\\nFastAPI"];\n'
        + '  inference [label="Inference Service\\nYOLO Runtime"];\n'
        + '  postgres [label="Postgres\\nRelational Data"];\n'
        + '  neo4j [label="Neo4j\\nGraph Relationships"];\n'
        + '  storage [label="Object/File Storage\\nTrap Images + Artifacts"];\n'
        + '  weather [label="External Weather API\\nOpen-Meteo"];\n'
        + "  user -> frontend;\n"
        + "  frontend -> backend;\n"
        + "  backend -> inference;\n"
        + "  backend -> postgres;\n"
        + "  backend -> neo4j;\n"
        + "  backend -> storage;\n"
        + "  backend -> weather;\n"
        + "}\n"
    )


def backend_component_diagram_dot() -> str:
    return (
        _dot_header("LR")
        + '  auth_router [label="Auth Router"];\n'
        + '  map_router [label="Map Router"];\n'
        + '  analysis_router [label="Analysis Router"];\n'
        + '  env_router [label="Environment Router"];\n'
        + '  analytics_router [label="Analytics Router"];\n'
        + '  deps [label="Deps + Security"];\n'
        + '  graph_svc [label="Graph Service"];\n'
        + '  env_svc [label="Environment Service"];\n'
        + '  infer_svc [label="Inference Service"];\n'
        + '  upload_svc [label="Upload Service"];\n'
        + '  schemas [label="Pydantic Schemas"];\n'
        + '  models [label="SQLAlchemy Models"];\n'
        + '  session [label="DB Session"];\n'
        + '  stores [label="Postgres / Neo4j / Storage"];\n'
        + "  {rank=same; auth_router; map_router; analysis_router; env_router; analytics_router;}\n"
        + "  auth_router -> deps;\n"
        + "  map_router -> deps;\n"
        + "  analysis_router -> deps;\n"
        + "  env_router -> deps;\n"
        + "  analytics_router -> deps;\n"
        + "  map_router -> graph_svc;\n"
        + "  analysis_router -> infer_svc;\n"
        + "  analysis_router -> upload_svc;\n"
        + "  analysis_router -> env_svc;\n"
        + "  env_router -> env_svc;\n"
        + "  analytics_router -> env_svc;\n"
        + "  auth_router -> schemas;\n"
        + "  map_router -> schemas;\n"
        + "  analysis_router -> schemas;\n"
        + "  env_router -> schemas;\n"
        + "  graph_svc -> session;\n"
        + "  env_svc -> session;\n"
        + "  infer_svc -> session;\n"
        + "  upload_svc -> session;\n"
        + "  deps -> session;\n"
        + "  session -> models;\n"
        + "  models -> stores;\n"
        + "  session -> stores;\n"
        + "}\n"
    )


def sequence_diagram_upload_workflow() -> go.Figure:
    participants = ["User", "Frontend", "Backend API", "Auth", "Graph Service", "Inference", "Postgres", "Neo4j"]
    x_positions = {name: idx for idx, name in enumerate(participants)}
    steps = [
        ("User", "Frontend", "Open app and submit login"),
        ("Frontend", "Backend API", "POST /api/auth/login"),
        ("Backend API", "Auth", "Validate credentials + token"),
        ("Auth", "Backend API", "Return access token"),
        ("Backend API", "Frontend", "Login success + JWT"),
        ("User", "Frontend", "Create field + polygon"),
        ("Frontend", "Backend API", "POST /api/map/fields"),
        ("Backend API", "Graph Service", "Create field node"),
        ("Graph Service", "Neo4j", "Persist field graph relations"),
        ("Backend API", "Postgres", "Persist field/trap metadata"),
        ("Backend API", "Frontend", "Field created response"),
        ("User", "Frontend", "Upload trap images"),
        ("Frontend", "Backend API", "POST /api/analysis/upload-range"),
        ("Backend API", "Inference", "Run model inference"),
        ("Inference", "Backend API", "Detection list + confidence"),
        ("Backend API", "Postgres", "Persist uploads + detections"),
        ("Backend API", "Frontend", "Return analytics summary"),
        ("Frontend", "User", "Show detections + trends"),
    ]

    fig = go.Figure()
    for name, x in x_positions.items():
        fig.add_trace(
            go.Scatter(
                x=[x, x],
                y=[0, len(steps) + 1],
                mode="lines",
                line=dict(color="#CBD5E1", dash="dash"),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_annotation(x=x, y=len(steps) + 1.3, text=name, showarrow=False, font=dict(size=12))

    for idx_step, (src, dst, label) in enumerate(steps, start=1):
        y = len(steps) + 1 - idx_step
        fig.add_annotation(
            x=x_positions[dst],
            y=y,
            ax=x_positions[src],
            ay=y,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=3,
            arrowwidth=1.4,
            arrowcolor=COSMIC_PURPLE,
        )
        fig.add_annotation(
            x=(x_positions[src] + x_positions[dst]) / 2,
            y=y + 0.2,
            text=f"{idx_step}. {label}",
            showarrow=False,
            font=dict(size=10, color="#374151"),
        )

    fig.update_layout(
        title="Sequence Diagram (Upload + Inference Workflow)",
        xaxis=dict(visible=False, range=[-0.5, len(participants) - 0.5]),
        yaxis=dict(visible=False, range=[0, len(steps) + 1.8]),
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


def er_diagram_dot() -> str:
    return (
        _dot_header("LR")
        + '  users [label="users\\nPK id"];\n'
        + '  fields [label="field_maps\\nPK id\\nFK owner_user_id"];\n'
        + '  traps [label="trap_points\\nPK id\\nFK field_id"];\n'
        + '  uploads [label="trap_uploads\\nPK id\\nFK user_id\\nFK trap_id"];\n'
        + '  detections [label="detections\\nPK id\\nFK upload_id"];\n'
        + '  env_daily [label="environmental_daily\\nPK id\\nFK field_id"];\n'
        + '  env_source [label="environmental_source_daily\\nPK id\\nFK field_id"];\n'
        + "  users -> fields;\n"
        + "  users -> uploads;\n"
        + "  fields -> traps;\n"
        + "  fields -> uploads;\n"
        + "  traps -> uploads;\n"
        + "  uploads -> detections;\n"
        + "  fields -> env_daily;\n"
        + "  fields -> env_source;\n"
        + "}\n"
    )


def deployment_diagram_dot() -> str:
    return (
        _dot_header("LR")
        + '  browser [label="Browser\\n(User)"];\n'
        + '  frontend [label="Frontend Container\\n(React)"];\n'
        + '  backend [label="Backend Container\\n(FastAPI)"];\n'
        + '  inference [label="Inference Worker\\n(YOLO Runtime)"];\n'
        + '  k8s [label="Kubernetes Cluster"];\n'
        + '  db [label="Cloud Postgres"];\n'
        + '  neo4j [label="Cloud Neo4j"];\n'
        + '  storage [label="Object Storage\\n(Images/Artifacts)"];\n'
        + '  weather [label="Open-Meteo API"];\n'
        + "  browser -> frontend;\n"
        + "  frontend -> backend;\n"
        + "  backend -> inference;\n"
        + "  backend -> k8s;\n"
        + "  k8s -> db;\n"
        + "  k8s -> neo4j;\n"
        + "  k8s -> storage;\n"
        + "  k8s -> weather;\n"
        + "}\n"
    )


def postgres_data_model_diagram_dot() -> str:
    return (
        _dot_header("LR")
        + '  users [label="users"];\n'
        + '  field_maps [label="field_maps"];\n'
        + '  trap_points [label="trap_points"];\n'
        + '  trap_uploads [label="trap_uploads"];\n'
        + '  detections [label="detections"];\n'
        + '  environmental_daily [label="environmental_daily"];\n'
        + '  environmental_source_daily [label="environmental_source_daily"];\n'
        + "  users -> field_maps;\n"
        + "  users -> trap_uploads;\n"
        + "  field_maps -> trap_points;\n"
        + "  field_maps -> trap_uploads;\n"
        + "  trap_points -> trap_uploads;\n"
        + "  trap_uploads -> detections;\n"
        + "  field_maps -> environmental_daily;\n"
        + "  field_maps -> environmental_source_daily;\n"
        + "}\n"
    )


def graph_model_diagram_dot() -> str:
    return (
        _dot_header("LR")
        + '  user [label="(:User)"];\n'
        + '  field [label="(:Field)"];\n'
        + '  trap [label="(:Trap)"];\n'
        + '  upload [label="(:Upload)"];\n'
        + '  detection [label="(:Detection)"];\n'
        + '  weather [label="(:WeatherDay)"];\n'
        + '  user -> field [label=" OWNS"];\n'
        + '  field -> trap [label=" HAS_TRAP"];\n'
        + '  trap -> upload [label=" CAPTURED_AT"];\n'
        + '  upload -> detection [label=" CONTAINS"];\n'
        + '  field -> weather [label=" HAS_WEATHER"];\n'
        + "}\n"
    )


def backend_class_diagram_dot() -> str:
    return (
        _dot_header("LR")
        + '  User [label="User\\n+id\\n+email\\n+role"];\n'
        + '  FieldMap [label="FieldMap\\n+id\\n+owner_user_id\\n+polygon_geojson"];\n'
        + '  TrapPoint [label="TrapPoint\\n+id\\n+field_id\\n+code"];\n'
        + '  TrapUpload [label="TrapUpload\\n+id\\n+user_id\\n+field_id\\n+trap_id"];\n'
        + '  Detection [label="Detection\\n+id\\n+upload_id\\n+confidence"];\n'
        + '  EnvironmentalDaily [label="EnvironmentalDaily\\n+id\\n+field_id\\n+observation_date"];\n'
        + '  EnvironmentalSourceDaily [label="EnvironmentalSourceDaily\\n+id\\n+field_id\\n+provider"];\n'
        + '  User -> FieldMap [label="1..* owns"];\n'
        + '  FieldMap -> TrapPoint [label="1..* contains"];\n'
        + '  User -> TrapUpload [label="1..* uploads"];\n'
        + '  TrapPoint -> TrapUpload [label="1..* captured_by"];\n'
        + '  TrapUpload -> Detection [label="1..* detections"];\n'
        + '  FieldMap -> EnvironmentalDaily [label="1..* weather"];\n'
        + '  FieldMap -> EnvironmentalSourceDaily [label="1..* weather_raw"];\n'
        + "}\n"
    )


_require_dashboard_access()

token = _get_config("GITHUB_TOKEN", "")
owner = _get_config("GITHUB_OWNER", "")
repo = _get_config("GITHUB_REPO", "")
show_internal_errors = _get_config_bool("SHOW_INTERNAL_ERRORS", False)

if not token:
    st.error("Set GITHUB_TOKEN in 02_pm_analytics_dashboard/.env.")
    st.stop()
if not owner or not repo:
    st.error("Set GITHUB_OWNER and GITHUB_REPO in 02_pm_analytics_dashboard/.env.")
    st.stop()

header_left, header_mid, header_right = st.columns([4, 1, 1])
with header_left:
    st.caption(f"Repository: {owner}/{repo}")
with header_mid:
    if st.button("Refresh Data", key="refresh_data_top"):
        fetch_data.clear()
with header_right:
    if st.button("Logout", key="dashboard_logout"):
        st.session_state["dashboard_authenticated"] = False
        st.rerun()

try:
    data = fetch_data(owner=owner, repo=repo, token=token)
except Exception as exc:  # noqa: BLE001
    st.error("Unable to load GitHub data.")
    if show_internal_errors:
        st.exception(exc)
    st.stop()

issues_df = data["issues"]
prs_df = data["pulls"]
commits_df = data.get("commits", pd.DataFrame())
workflows_df = data.get("workflows", pd.DataFrame())
pr_reviews_df = data.get("pr_reviews", pd.DataFrame())
issue_events_df = data.get("issue_events", pd.DataFrame())
labels_df = data["labels"]
milestones_df = data["milestones"]

if issues_df.empty and prs_df.empty:
    st.warning("No issue or PR data found for this repository.")
    st.stop()

(
    pm_tab,
    architecture_tab,
    dev_tab,
    quality_tab,
    cicd_tab,
    defects_tab,
    perf_tab,
    collab_tab,
) = st.tabs(
    [
        "Project Management",
        "Architecture",
        "Development (Engineering Productivity)",
        "Quality",
        "CI/CD & Deployment",
        "Issues & Defects",
        "System Performance",
        "Collaboration",
    ]
)

with pm_tab:
    st.markdown("### Project Management")

    current_milestone = choose_current_milestone(milestones_df)

    min_date = date.today() - timedelta(days=180)
    max_date = date.today()
    if not issues_df.empty and issues_df["created_at"].notna().any():
        min_date = issues_df["created_at"].min().date()
        max_date = max(max_date, issues_df["created_at"].max().date())

    f1, f2, f3, f4, f5 = st.columns(5)

    milestone_options = ["Current milestone", "All", "No milestone"]
    if not milestones_df.empty:
        milestone_options += sorted(milestones_df["title"].dropna().unique().tolist())

    with f1:
        milestone_filter_raw = st.selectbox("Milestone", milestone_options, key="pm_filter_milestone")

    with f2:
        date_range = st.date_input(
            "Date range (created_at)",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="pm_filter_date_range",
        )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    with f3:
        label_options = ["All"]
        if not labels_df.empty:
            label_options += sorted(labels_df["name"].dropna().unique().tolist())
        label_filter = st.selectbox("Label", label_options, key="pm_filter_label")

    with f4:
        issue_state = st.selectbox("Issue state", ["all", "open", "closed"], index=0, key="pm_filter_state")

    with f5:
        timeframe_mode = st.selectbox(
            "Scope timeframe",
            ["Full scope", "Until now"],
            index=0,
            key="pm_scope_timeframe",
        )

    milestone_filter = milestone_filter_raw
    if milestone_filter_raw == "Current milestone":
        if current_milestone:
            milestone_filter = current_milestone
            st.caption(f"Current milestone inferred as: {current_milestone}")
        else:
            milestone_filter = "All"
            st.caption("No open milestone found. Falling back to All milestones.")

    filtered_issues = apply_issue_filters(
        issues_df,
        start_date=start_date,
        end_date=end_date,
        assignee="All",
        label=label_filter,
        milestone=milestone_filter,
        issue_state=issue_state,
    )
    filtered_prs = apply_pr_date_filter(prs_df, start_date=start_date, end_date=end_date)

    pm_overview = overview_metrics(filtered_issues, filtered_prs, milestones_df)
    pm_cycles = cycle_metrics(filtered_issues, filtered_prs)

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Open Issues", pm_overview["open_issues"])
    k2.metric("Closed Issues", pm_overview["closed_issues"])
    k3.metric("Open PRs", pm_overview["open_prs"])
    k4.metric("Closed PRs", pm_overview["closed_prs"])
    k5.metric("Avg Issue Close", fmt_days(pm_overview["avg_issue_close_days"]))
    k6.metric("Avg Cycle Time", fmt_days(pm_cycles["avg_cycle_days"]))

    use_size = True

    include_epics = milestone_filter == "All"
    heat_issues = filtered_issues.copy()
    heat_title_scope = "Whole Project"
    if milestone_filter == "No milestone":
        heat_title_scope = "No Milestone"
        include_epics = False
    elif isinstance(milestone_filter, str) and milestone_filter not in {"All"}:
        heat_title_scope = f"Milestone: {milestone_filter}"
        include_epics = False

    scope_issues = heat_issues.copy()
    if timeframe_mode == "Until now":
        now_utc = pd.Timestamp.now(tz="UTC")
        scope_issues = scope_issues[scope_issues["created_at"].notna() & (scope_issues["created_at"] <= now_utc)].copy()

    progress_blocks = _build_progress_hierarchy(
        scope_issues,
        use_size=use_size,
        include_epics=include_epics,
    )
    total_weight = int(progress_blocks["weight"].sum()) if not progress_blocks.empty else 0
    done_weight = int(progress_blocks.loc[progress_blocks["status"] == "done", "weight"].sum()) if not progress_blocks.empty else 0
    completion_pct = (done_weight / total_weight * 100) if total_weight > 0 else 0.0

    phase_start, phase_end = _delivery_window(scope_issues, milestones_df, milestone_filter)
    now_ts = pd.Timestamp.now(tz="UTC")
    phase_total_days = max((phase_end - phase_start).days, 1)
    elapsed_days = (min(max(now_ts, phase_start), phase_end) - phase_start).days
    time_elapsed_pct = max(0.0, min(100.0, (elapsed_days / phase_total_days) * 100))
    schedule_variance = completion_pct - time_elapsed_pct
    feature_delivery = _planned_vs_actual(scope_issues, "feature", phase_start, phase_end, now_ts)
    task_delivery = _planned_vs_actual(scope_issues, "task", phase_start, phase_end, now_ts)
    expected_pct = time_elapsed_pct
    actual_pct = completion_pct

    st.markdown("### Key Delivery Insights")
    i1, i2, i3, i4, i5 = st.columns(5)
    i1.metric("Features Done", f"{feature_delivery['done_total']}/{feature_delivery['total']}")
    i2.metric("Features Expected by Now", feature_delivery["expected_now"])
    i3.metric("Tasks Done", f"{task_delivery['done_total']}/{task_delivery['total']}")
    i4.metric("Tasks Expected by Now", task_delivery["expected_now"])
    i5.metric("Schedule Variance", f"{schedule_variance:+.1f} pts")

    st.markdown("### Milestone Plan Position")
    st.caption("Shows where progress should be by now vs where it actually is, including extra completed tasks not yet required by plan.")
    render_chart(
        milestone_plan_position_chart(
            expected_pct=expected_pct,
            actual_pct=actual_pct,
            phase_start=phase_start,
            phase_end=phase_end,
        ),
        key="pm_milestone_plan_position",
        brand_style=False,
    )

    st.markdown("### Delivery Progress Heatmap")
    st.caption("Color legend: Backlog (grey), In Progress (orange), Done (green)")
    st.caption("Whole project view shows Epic -> Feature -> Task. Milestone view shows Feature -> Task.")
    heat_event = render_chart(
        progress_heatmap_chart(
            progress_blocks,
            title=f"Progress Heatmap ({heat_title_scope})",
            include_epics=include_epics,
        ),
        key="pm_progress_heatmap",
        brand_style=False,
    )
    selected_custom = _extract_selected_task_customdata(heat_event)
    if selected_custom and len(selected_custom) >= 6:
        kind = str(selected_custom[0] or "")
        issue_number = selected_custom[4]
        body_markdown = str(selected_custom[5] or "").strip()
        if kind in {"task", "task_orphan"} and issue_number:
            st.markdown("#### Task Description")
            st.caption(f"Issue #{int(issue_number)}")
            st.markdown(body_markdown or "_No description provided._")

    st.markdown("### Delivery Breakdown")
    scope_label = "Whole Project" if milestone_filter == "All" else str(milestone_filter)
    b1, b2 = st.columns(2)
    with b1:
        render_chart(completed_hierarchy_chart(scope_issues), key="pm_completed_hierarchy")
    with b2:
        st.markdown("#### Completed Hierarchy Counts")
        st.dataframe(
            completed_hierarchy_counts(scope_issues).rename(columns={"level": "Level", "completed": "Completed"}),
            width="stretch",
            hide_index=True,
        )

    c1, c2 = st.columns(2)
    with c1:
        render_chart(
            hierarchy_vs_average_chart(
                scope_issues,
                issues_df,
                scope_label=scope_label,
            ),
            key="pm_hierarchy_vs_average",
        )
    with c2:
        render_chart(
            phase_progress_chart(time_elapsed_pct=time_elapsed_pct, work_completed_pct=completion_pct),
            key="pm_scope_progress_balance",
        )

    st.markdown("### Export")
    issue_csv = filtered_issues.to_csv(index=False).encode("utf-8")
    pr_csv = filtered_prs.to_csv(index=False).encode("utf-8")
    x1, x2 = st.columns(2)
    with x1:
        st.download_button(
            "Download filtered issues CSV",
            issue_csv,
            file_name="filtered_issues.csv",
            key="pm_download_issues_csv",
        )
    with x2:
        st.download_button(
            "Download filtered PRs CSV",
            pr_csv,
            file_name="filtered_prs.csv",
            key="pm_download_prs_csv",
        )

with quality_tab:
    st.markdown("### Quality")
    st.caption("Run backend (pytest) and frontend (vitest) tests with real line coverage for 03_application.")

    history = load_quality_history()
    q1, q2, q3 = st.columns([1, 1, 2])
    with q1:
        if st.button("Run Weekly Quality Snapshot", key="quality_run_snapshot"):
            snapshot = run_quality_snapshot(REPO_ROOT)
            history.append(snapshot)
            save_quality_history(history)
            st.success("Quality snapshot recorded.")
    with q2:
        if st.button("Clear Quality History", key="quality_clear_history"):
            history = []
            save_quality_history(history)
            st.info("Quality history cleared.")
    with q3:
        if history:
            st.caption(f"Latest snapshot: {history[-1].get('timestamp', 'N/A')}")
        else:
            st.caption("No quality snapshots yet.")

    latest = history[-1] if history else None
    runtime_rate = latest.get("runtime_tests_pass_rate_pct", 0.0) if latest else None
    coverage_rate = latest.get("application_coverage_pct", 0.0) if latest else None
    backend_cov = latest.get("backend_coverage_pct", 0.0) if latest else None
    frontend_cov = latest.get("frontend_coverage_pct", 0.0) if latest else None
    kq1, kq2, kq3, kq4 = st.columns(4)
    kq1.metric("Runtime Test Pass Rate", f"{runtime_rate:.1f}%" if runtime_rate is not None else "N/A")
    kq2.metric("Application Coverage", f"{coverage_rate:.1f}%" if coverage_rate is not None else "N/A")
    kq3.metric("Backend Coverage", f"{backend_cov:.1f}%" if backend_cov is not None else "N/A")
    kq4.metric("Frontend Coverage", f"{frontend_cov:.1f}%" if frontend_cov is not None else "N/A")

    g1, g2 = st.columns(2)
    with g1:
        render_chart(
            runtime_test_results_chart(history),
            key="quality_runtime_results",
        )
    with g2:
        render_chart(
            coverage_trend_chart(history),
            key="quality_coverage_trend",
        )

with dev_tab:
    st.markdown("### Development (Engineering Productivity)")
    st.caption("Lead time, cycle time, review speed, throughput, and code churn (scope-aligned with PM filters).")

    scoped_issues = filtered_issues.copy() if "filtered_issues" in locals() else issues_df.copy()
    scoped_prs = filtered_prs.copy() if "filtered_prs" in locals() else prs_df.copy()
    prs_with_review = _pr_with_first_review(scoped_prs, pr_reviews_df)

    merged = prs_with_review.dropna(subset=["created_at", "merged_at"]).copy()
    merged["lead_days"] = _delta_days(merged["merged_at"], merged["created_at"])
    lead_time_days = float(merged["lead_days"].median()) if not merged.empty else float("nan")

    reviewed = prs_with_review.dropna(subset=["created_at", "first_review_at"]).copy()
    reviewed["review_hours"] = _delta_hours(reviewed["first_review_at"], reviewed["created_at"])
    review_hours = float(reviewed["review_hours"].median()) if not reviewed.empty else float("nan")

    cycle_days = cycle_metrics(scoped_issues, scoped_prs).get("avg_cycle_days", float("nan"))
    merged_prs = int(scoped_prs["merged_at"].notna().sum()) if not scoped_prs.empty else 0
    commits_per_week = 0.0
    if not commits_df.empty:
        ctmp = commits_df.dropna(subset=["date"]).copy()
        if not ctmp.empty:
            ctmp["week"] = ctmp["date"].dt.tz_localize(None).dt.to_period("W").dt.start_time
            commits_per_week = float(ctmp.groupby("week").size().mean())

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Lead Time for Changes", fmt_days(lead_time_days))
    k2.metric("Avg Cycle Time", fmt_days(cycle_days))
    k3.metric("PR First Review Time", "N/A" if pd.isna(review_hours) else f"{review_hours:.1f} h")
    k4.metric("Merged PRs", merged_prs)
    k5.metric("Avg Commits / Week", f"{commits_per_week:.1f}")

    d1, d2 = st.columns(2)
    with d1:
        render_chart(weekly_pr_throughput(scoped_prs), key="dev_pr_weekly")
    with d2:
        render_chart(pr_merge_time_distribution(scoped_prs), key="dev_pr_merge_dist")
    d3, d4 = st.columns(2)
    with d3:
        render_chart(weekly_commit_activity(commits_df), key="dev_commit_weekly")
    with d4:
        render_chart(code_churn_by_week_chart(scoped_prs), key="dev_code_churn")

with cicd_tab:
    st.markdown("### CI/CD & Deployment")
    st.caption("Pipeline efficiency from GitHub Actions runs. Deployment KPIs show placeholder if no deploy runs exist yet.")

    wf = workflows_df.copy()
    if "start_date" in locals() and "end_date" in locals() and not wf.empty:
        sd = pd.Timestamp(start_date).tz_localize("UTC")
        ed = pd.Timestamp(end_date).tz_localize("UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        wf = wf[(wf["created_at"].notna()) & (wf["created_at"] >= sd) & (wf["created_at"] <= ed)].copy()

    completed = wf[wf["conclusion"].notna()].copy() if not wf.empty else pd.DataFrame()
    success_rate = float((completed["conclusion"].str.lower() == "success").mean() * 100.0) if not completed.empty else float("nan")
    failure_rate = float((completed["conclusion"].str.lower().isin(["failure", "timed_out", "startup_failure", "action_required"])).mean() * 100.0) if not completed.empty else float("nan")
    duration_min = float((_delta_hours(completed["updated_at"], completed["created_at"]) * 60.0).median()) if not completed.empty else float("nan")
    deploy_runs = wf[wf["name"].fillna("").str.lower().str.contains("deploy|release", regex=True)] if not wf.empty else pd.DataFrame()
    deploy_freq_week = 0.0
    if not deploy_runs.empty:
        tmp = deploy_runs.dropna(subset=["created_at"]).copy()
        tmp["week"] = tmp["created_at"].dt.tz_localize(None).dt.to_period("W").dt.start_time
        deploy_freq_week = float(tmp.groupby("week").size().mean())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Build Success Rate", fmt_pct(success_rate))
    c2.metric("Pipeline Failure Rate", fmt_pct(failure_rate))
    c3.metric("Median Pipeline Duration", "N/A" if pd.isna(duration_min) else f"{duration_min:.1f} min")
    c4.metric("Deployment Frequency", f"{deploy_freq_week:.2f} / week")

    w1, w2 = st.columns(2)
    with w1:
        render_chart(workflow_weekly_outcomes_chart(wf), key="cicd_weekly_outcomes")
    with w2:
        render_chart(workflow_duration_trend_chart(wf), key="cicd_duration_trend")

with defects_tab:
    st.markdown("### Issues & Defects")
    st.caption("Bug intake, closure speed, reopen behavior, and severity profile.")
    scoped_issues = filtered_issues.copy() if "filtered_issues" in locals() else issues_df.copy()
    defects = scoped_issues[
        scoped_issues["labels"].apply(
            lambda labels: isinstance(labels, list)
            and any("bug" in str(label).strip().lower() for label in labels)
        )
    ].copy() if not scoped_issues.empty else pd.DataFrame()
    open_bugs = int((defects["state"].str.lower() == "open").sum()) if not defects.empty else 0
    closed_bugs = int((defects["state"].str.lower() == "closed").sum()) if not defects.empty else 0
    bug_rate = (len(defects) / max(len(scoped_issues), 1) * 100.0) if not defects.empty else 0.0
    bug_ttr_days = (
        float(
            _delta_days(
                defects.dropna(subset=["created_at", "closed_at"])["closed_at"],
                defects.dropna(subset=["created_at", "closed_at"])["created_at"],
            ).median()
        )
        if not defects.empty
        else float("nan")
    )

    reopen_rate = float("nan")
    if not defects.empty and not issue_events_df.empty:
        defect_numbers = set(defects["number"].dropna().astype(int).tolist())
        reopened = issue_events_df[
            issue_events_df["issue_number"].isin(defect_numbers)
            & (issue_events_df["event"].fillna("").str.lower() == "reopened")
        ]
        reopen_rate = (reopened["issue_number"].nunique() / max(len(defect_numbers), 1)) * 100.0

    b1, b2, b3, b4, b5 = st.columns(5)
    b1.metric("Bug Rate", f"{bug_rate:.1f}%")
    b2.metric("Open Bugs", open_bugs)
    b3.metric("Closed Bugs", closed_bugs)
    b4.metric("Median Time to Resolution", fmt_days(bug_ttr_days))
    b5.metric("Reopen Rate", fmt_pct(reopen_rate))

    bl, br = st.columns(2)
    with bl:
        render_chart(bug_status_pie(scoped_issues), key="defects_status_pie")
    with br:
        render_chart(bug_open_close_trend(scoped_issues), key="defects_trend")
    bl2, br2 = st.columns(2)
    with bl2:
        render_chart(bug_severity_distribution_chart(defects), key="defects_severity_dist", brand_style=False)
    with br2:
        render_chart(issue_state_pie(defects), key="defects_state_split", brand_style=False)

with perf_tab:
    st.markdown("### System Performance")
    st.caption("Operational telemetry placeholders. Connect runtime metrics to populate these views.")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("API P95 Latency", "N/A")
    p2.metric("Inference P95 Latency", "N/A")
    p3.metric("Error Rate", "N/A")
    p4.metric("Throughput (req/min)", "N/A")
    pl, pr = st.columns(2)
    with pl:
        render_chart(deployment_placeholder_chart("API Latency Trend"), key="perf_api_latency")
    with pr:
        render_chart(deployment_placeholder_chart("Inference Latency Trend"), key="perf_inference_latency")

with collab_tab:
    st.markdown("### Collaboration")
    st.caption("Review participation, bus-factor proxy, and contribution distribution.")
    scoped_issues = filtered_issues.copy() if "filtered_issues" in locals() else issues_df.copy()
    scoped_prs = filtered_prs.copy() if "filtered_prs" in locals() else prs_df.copy()

    review_participants = pr_reviews_df["author"].dropna().nunique() if not pr_reviews_df.empty else 0
    pr_authors = scoped_prs["author"].dropna().nunique() if not scoped_prs.empty else 0
    review_participation_rate = (review_participants / max(pr_authors, 1)) * 100.0

    contribution = pd.concat(
        [
            scoped_issues["author"].dropna(),
            scoped_prs["author"].dropna(),
            commits_df["author"].dropna() if not commits_df.empty else pd.Series(dtype=object),
        ]
    )
    bus_factor = 0.0
    if not contribution.empty:
        dist = contribution.value_counts(normalize=True)
        bus_factor = float(dist.iloc[0] * 100.0)

    review_comments = int(scoped_prs["review_comments_count"].fillna(0).sum()) if "review_comments_count" in scoped_prs.columns else 0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Review Participants", review_participants)
    col2.metric("Review Participation", f"{review_participation_rate:.1f}%")
    col3.metric("PR Review Comments", review_comments)
    col4.metric("Bus Factor Risk", f"{bus_factor:.1f}% top-contributor share")

    c1, c2 = st.columns(2)
    with c1:
        render_chart(top_contributors_chart(scoped_issues, scoped_prs), key="collab_top_contributors")
    with c2:
        assignee_counts = scoped_issues.explode("assignees")["assignees"].dropna().value_counts().head(10) if not scoped_issues.empty else pd.Series(dtype=int)
        if assignee_counts.empty:
            render_chart(deployment_placeholder_chart("Top Assignees"), key="collab_top_assignees_empty")
        else:
            df = assignee_counts.reset_index()
            df.columns = ["assignee", "issues"]
            fig = px.bar(df, x="assignee", y="issues", title="Top Assignees by Issue Count")
            render_chart(fig, key="collab_top_assignees")
    c3, c4 = st.columns(2)
    with c3:
        render_chart(collaboration_distribution_chart(scoped_issues, scoped_prs, commits_df), key="collab_distribution", brand_style=False)
    with c4:
        commits_plot = commits_per_developer_chart(commits_df)
        commits_plot.update_layout(title="Commit Distribution by Developer")
        render_chart(commits_plot, key="collab_commits_per_dev", brand_style=False)

with architecture_tab:
    st.markdown("### Architecture")
    st.caption("Application-only architecture views (frontend, backend, inference, data stores).")

    st.markdown("#### C4 Container Diagram")
    st.graphviz_chart(c4_container_diagram_dot(), use_container_width=True)
    st.markdown("#### Component Diagram (Backend)")
    st.graphviz_chart(backend_component_diagram_dot(), use_container_width=True)
    render_chart(sequence_diagram_upload_workflow(), key="arch_sequence_workflow", brand_style=False)
    st.markdown("#### Class Diagram (Backend Domain)")
    st.graphviz_chart(backend_class_diagram_dot(), use_container_width=True)
    st.markdown("#### ER Diagram")
    st.graphviz_chart(er_diagram_dot(), use_container_width=True)
    st.markdown("#### Deployment Diagram")
    st.graphviz_chart(deployment_diagram_dot(), use_container_width=True)
    st.markdown("#### Databases")
    st.caption("Dedicated views for relational and graph data models.")
    db1, db2 = st.columns(2)
    with db1:
        st.markdown("##### Postgres")
        st.graphviz_chart(postgres_data_model_diagram_dot(), use_container_width=True)
    with db2:
        st.markdown("##### Graph (Neo4j)")
        st.graphviz_chart(graph_model_diagram_dot(), use_container_width=True)
