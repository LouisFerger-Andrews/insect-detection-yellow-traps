from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import analysis as analysis_api


def test_detect_question_intents_finds_keywords() -> None:
    out = analysis_api._detect_question_intents(
        "Compare year 2025 vs 2026 with weather and trap differences"
    )
    assert out["compare"] is True
    assert out["weather"] is True
    assert out["trap"] is True


def test_line_scatter_bar_and_yearly_svg_helpers() -> None:
    no_data_line = analysis_api._line_chart_svg("T", [], [], "Y", "#111")
    assert "No data available" in no_data_line

    line_html = analysis_api._line_chart_svg(
        "Trend",
        ["01-01", "01-08", "01-15"],
        [1.0, 2.5, 1.8],
        "Avg",
        "#2563eb",
    )
    assert "<svg" in line_html
    assert "polyline" in line_html

    no_points = analysis_api._scatter_svg("Scatter", [])
    assert "No overlapping" in no_points

    scatter_html = analysis_api._scatter_svg(
        "Scatter",
        [
            {"week_start": "2026-01-01", "temp_avg": 10, "avg_population": 2},
            {"week_start": "2026-01-08", "temp_avg": 12, "avg_population": 3},
        ],
    )
    assert "<circle" in scatter_html

    no_data_bar = analysis_api._bar_chart_svg("Bars", [], [], "Y", "#333")
    assert "No data available" in no_data_bar
    bar_html = analysis_api._bar_chart_svg("Bars", ["A", "B"], [3.0, 5.0], "Count", "#333")
    assert "<rect" in bar_html

    insufficient = analysis_api._yearly_week_comparison_svg(
        "Year compare", [{"week_start": "2026-01-01", "avg_population": 2.0}]
    )
    assert "Not enough yearly series" in insufficient

    yearly_html = analysis_api._yearly_week_comparison_svg(
        "Year compare",
        [
            {"week_start": "2025-01-01", "avg_population": 1.0},
            {"week_start": "2025-01-08", "avg_population": 1.2},
            {"week_start": "2026-01-01", "avg_population": 2.0},
            {"week_start": "2026-01-08", "avg_population": 2.4},
        ],
    )
    assert "ISO week" in yearly_html
    assert "<polyline" in yearly_html


def test_render_exploratory_report_html_includes_expected_sections() -> None:
    context = {
        "field": {"name": "Demo Field"},
        "range": {
            "all_data": False,
            "year": 2026,
            "weeks": 10,
            "start_date": "2026-01-01",
            "end_date": "2026-03-01",
        },
        "weekly_population": [
            {"week_start": "2025-01-01", "avg_population": 1.2, "total_population": 8, "uploads": 4},
            {"week_start": "2025-01-08", "avg_population": 1.4, "total_population": 10, "uploads": 5},
            {"week_start": "2026-01-01", "avg_population": 2.1, "total_population": 12, "uploads": 6},
            {"week_start": "2026-01-08", "avg_population": 2.6, "total_population": 15, "uploads": 6},
        ],
        "weekly_weather": [
            {"week_start": "2025-01-01", "temp_avg": 8.2, "rain_sum": 2.0, "gdd_avg": 0.3, "deficit_avg": 0.1},
            {"week_start": "2025-01-08", "temp_avg": 9.0, "rain_sum": 3.1, "gdd_avg": 0.5, "deficit_avg": 0.2},
            {"week_start": "2026-01-01", "temp_avg": 10.5, "rain_sum": 1.5, "gdd_avg": 0.9, "deficit_avg": 0.2},
            {"week_start": "2026-01-08", "temp_avg": 11.8, "rain_sum": 1.0, "gdd_avg": 1.1, "deficit_avg": 0.3},
        ],
        "by_trap": [
            {"trap_code": "R01-P01", "detections": 25, "uploads": 10},
            {"trap_code": "R01-P02", "detections": 18, "uploads": 9},
        ],
    }
    html = analysis_api._render_exploratory_report_html(
        question="Compare 2025 and 2026 weather and trap behavior",
        answer="Summary here",
        context=context,
    )
    assert "Exploratory Analysis Report" in html
    assert "Population Trend by Week" in html
    assert "Year Comparison: Weekly Avg Detections per Image" in html
    assert "Detections vs Temperature (Weekly)" in html
    assert "Top Traps by Total Detections" in html
    assert "Weekly Data Table" in html


def test_exploratory_report_wrapper_uses_chat_result(monkeypatch) -> None:  # noqa: ANN001
    def fake_chat(payload, db, current_user):  # noqa: ANN001
        return {
            "answer": "ok",
            "used_openai": False,
            "provider_error": "",
            "context": {"totals": {"uploads": 1, "detections": 2, "avg_confidence": 0.5}},
            "full_context": {"field": {"name": "My Field"}, "range": {}, "weekly_population": [], "weekly_weather": [], "by_trap": []},
        }

    monkeypatch.setattr(analysis_api, "exploratory_chat", fake_chat)
    out = analysis_api.exploratory_report({"question": "Q"}, db=None, current_user=None)
    assert out["answer"] == "ok"
    assert out["filename"].startswith("exploratory-report-my-field-")
    assert "<html" in out["html"]


@dataclass
class DummyUser:
    id: int
    role: str = "admin"


class _StaticQuery:
    def __init__(self, *, first=None, all_value=None, one=None, scalars=None):
        self._first = first
        self._all = all_value if all_value is not None else []
        self._one = one
        self._scalars = list(scalars or [])

    def filter(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def with_entities(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def group_by(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def order_by(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def limit(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def all(self):
        return self._all

    def first(self):
        return self._first

    def one(self):
        return self._one

    def scalar(self):
        return self._scalars.pop(0) if self._scalars else None


class _FakeDB:
    def __init__(self, queries):
        self._queries = list(queries)

    def query(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self._queries.pop(0)


def test_upload_range_validation_errors() -> None:
    with pytest.raises(HTTPException) as exc:
        analysis_api.upload_range(
            start_date=date(2026, 1, 2),
            end_date=date(2026, 1, 1),
            field_id="f1",
            trap_id=None,
            trap_code=None,
            images=[],
            db=None,  # type: ignore[arg-type]
            current_user=DummyUser(id=1),
        )
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc2:
        analysis_api.upload_range(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
            field_id="f1",
            trap_id=None,
            trap_code=None,
            images=[],
            db=None,  # type: ignore[arg-type]
            current_user=DummyUser(id=1),
        )
    assert exc2.value.status_code == 400


def test_model_stats_and_list_uploads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    metrics = tmp_path / "model_metrics.json"
    metrics.write_text('{"precision":0.9,"recall":0.8,"mAP50":0.7}')
    monkeypatch.setattr(
        analysis_api,
        "get_settings",
        lambda: SimpleNamespace(
            model_metrics_path=str(metrics),
            model_weights_path="03_application/poc-model/swd_yolo_best.pt",
            model_confidence=0.25,
            model_image_size=640,
        ),
    )
    totals = SimpleNamespace(uploads=3, detections=9, avg_confidence=0.66)
    uploads = [SimpleNamespace(id=1)]
    db = _FakeDB([_StaticQuery(one=totals), _StaticQuery(all_value=uploads)])

    stats = analysis_api.model_stats(db=db, current_user=DummyUser(id=1))
    assert stats["evaluation"]["precision"] == 0.9
    assert stats["production_observed"]["total_uploads"] == 3

    rows = analysis_api.list_my_uploads(db=db, current_user=DummyUser(id=1, role="admin"))
    assert len(rows) == 1


def test_exploratory_chat_full_fallback_and_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    selected_field = SimpleNamespace(id="field-1", name="Field 1", area_m2=100.0, owner_user_id=1)
    totals = SimpleNamespace(uploads=4, detections=10, avg_confidence=0.75)
    by_field = [SimpleNamespace(field_id="field-1", uploads=4, detections=10)]
    by_trap = [SimpleNamespace(trap_code="R01-P01", uploads=3, detections=8)]
    recent = [SimpleNamespace(id=1, field_id="field-1", trap_code="R01-P01", capture_date=date(2026, 1, 2), detection_count=3)]
    weekly_pop = [SimpleNamespace(week_start=date(2026, 1, 1), uploads=4, avg_population=2.5, total_population=10)]
    weekly_weather = [SimpleNamespace(week_start=date(2026, 1, 1), temp_avg=10.0, rain_sum=1.0, gdd_avg=0.5, deficit_avg=0.2, heat_stress_avg=0.0)]
    base_query = _StaticQuery(
        one=totals,
        all_value=recent,
        scalars=[date(2026, 1, 10), date(2026, 1, 1)],
    )
    db = _FakeDB(
        [
            _StaticQuery(first=selected_field),
            base_query,
            _StaticQuery(all_value=by_field),
            _StaticQuery(all_value=by_trap),
            _StaticQuery(all_value=weekly_pop),
            _StaticQuery(),
            _StaticQuery(all_value=weekly_weather),
        ]
    )
    monkeypatch.setattr(
        analysis_api,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="", openai_chat_model="gpt-4o-mini"),
    )
    out = analysis_api.exploratory_chat(
        {"question": "How are we doing?", "field_id": "field-1", "all_data": True},
        db=db,
        current_user=DummyUser(id=1, role="admin"),
    )
    assert out["used_openai"] is False
    assert out["context"]["totals"]["uploads"] == 4

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"output": [{"content": [{"text": "Model answer"}]}], "output_text": ""}

    db2 = _FakeDB(
        [
            _StaticQuery(one=totals, all_value=[], scalars=[None]),
            _StaticQuery(all_value=[]),
            _StaticQuery(all_value=[]),
            _StaticQuery(all_value=[]),
        ]
    )
    monkeypatch.setattr(
        analysis_api,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="x", openai_chat_model="gpt-4o-mini"),
    )
    monkeypatch.setattr(analysis_api.requests, "post", lambda *args, **kwargs: _Resp())
    out2 = analysis_api.exploratory_chat({"question": "status"}, db=db2, current_user=DummyUser(id=1, role="admin"))
    assert out2["used_openai"] is True
    assert "Model answer" in out2["answer"]
