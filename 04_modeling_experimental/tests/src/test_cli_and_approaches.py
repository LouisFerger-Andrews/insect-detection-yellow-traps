from __future__ import annotations

import importlib
import json
import types
from pathlib import Path

import click
import pytest
from typer.testing import CliRunner

import cli as app_cli
from approaches.classical_cv.approach import ClassicalCVApproach
from approaches.rtdetr.approach import RTDETRApproach
from approaches.yolo.approach import YoloApproach
from core.approach_base import RunContext


class _Logger:
    def __init__(self) -> None:
        self.entries: list[str] = []

    def info(self, msg: str, *args) -> None:  # noqa: ANN001
        self.entries.append(msg % args if args else msg)


def _ctx(tmp_path: Path, cfg: dict | None = None, approach: str = "yolo") -> RunContext:
    return RunContext(
        project="demo",
        approach=approach,
        run_dir=tmp_path / "run",
        config=cfg or {"project": "demo", "data": {}},
    )


def test_build_context_and_run_or_fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:  # noqa: ANN001
    monkeypatch.setattr(app_cli, "load_config", lambda path, project: {"project": project, "repro": {"seed": 7}})
    monkeypatch.setattr(app_cli, "set_seed", lambda seed: None)

    class _Dt:
        @staticmethod
        def now():
            class _N:
                @staticmethod
                def strftime(fmt: str) -> str:
                    return "20260101_120000"

            return _N()

    monkeypatch.setattr(app_cli, "datetime", _Dt)
    ctx = app_cli._build_context("p", "a", Path("x.yml"))
    assert str(ctx.run_dir).endswith("04_modeling_experimental/runs/p/a/20260101_120000")

    app_cli._run_or_fail(lambda: None)
    with pytest.raises(click.exceptions.Exit):
        app_cli._run_or_fail(lambda: (_ for _ in ()).throw(ValueError("boom")))
    assert "Error: boom" in capsys.readouterr().out


def test_cli_commands_list_and_wrappers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = CliRunner()

    class FakeImpl:
        def __init__(self, ctx) -> None:  # noqa: ANN001
            self.ctx = ctx
            self.seen = []

        def prepare_data(self) -> None:
            self.seen.append("prepare_data")

        def train(self) -> None:
            self.seen.append("train")

        def evaluate(self):
            self.seen.append("evaluate")
            return {"mAP": 0.1}

        def predict(self, image_path: Path):
            self.seen.append(f"predict:{image_path.name}")
            return [{"ok": True}]

        def export(self):
            self.seen.append("export")
            return self.ctx.run_dir / "export"

    impl_holder = {"impl": None}

    def _factory(ctx):  # noqa: ANN001
        impl_holder["impl"] = FakeImpl(ctx)
        return impl_holder["impl"]

    monkeypatch.setattr(app_cli, "_build_context", lambda *args, **kwargs: _ctx(tmp_path, {"project": "demo"}))
    monkeypatch.setattr(app_cli, "get_approach", lambda _: _factory)
    monkeypatch.setattr(app_cli, "_run_or_fail", lambda fn, *a, **k: fn(*a, **k))
    monkeypatch.setattr(app_cli, "get_logger", lambda name, run_dir=None: _Logger())
    monkeypatch.setattr(app_cli, "list_approaches", lambda: {"yolo": object, "rtdetr": object})

    list_res = runner.invoke(app_cli.app, ["list-approaches"])
    assert list_res.exit_code == 0
    assert "yolo" in list_res.stdout

    base_args = ["--project", "demo", "--approach", "yolo", "--config", "cfg.yml"]
    assert runner.invoke(app_cli.app, ["prepare-data", *base_args]).exit_code == 0
    assert runner.invoke(app_cli.app, ["train", *base_args]).exit_code == 0
    assert runner.invoke(app_cli.app, ["evaluate", *base_args]).exit_code == 0
    assert runner.invoke(app_cli.app, ["predict", *base_args, "--image", "a.jpg"]).exit_code == 0
    assert runner.invoke(app_cli.app, ["export", *base_args]).exit_code == 0


def test_classical_cv_approach_flows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logger = _Logger()
    monkeypatch.setattr("approaches.classical_cv.approach.get_logger", lambda *a, **k: logger)
    monkeypatch.setattr("approaches.classical_cv.approach.parse_common_config", lambda cfg: types.SimpleNamespace(raw_dir=tmp_path, image_glob="*.jpg"))  # noqa: E501
    monkeypatch.setattr("approaches.classical_cv.approach.ensure_raw_images", lambda *a, **k: [tmp_path / "a.jpg"])

    ctx = _ctx(tmp_path, {"project": "demo", "data": {}}, approach="classical_cv")
    impl = ClassicalCVApproach(ctx)
    impl.prepare_data()
    impl.train()
    assert impl.evaluate()["mAP"] == 0.0

    missing = tmp_path / "missing.jpg"
    with pytest.raises(FileNotFoundError):
        impl.predict(missing)

    existing = tmp_path / "x.jpg"
    existing.write_bytes(b"x")

    monkeypatch.setattr(importlib, "import_module", lambda name: (_ for _ in ()).throw(ImportError("cv2 missing")))
    with pytest.raises(RuntimeError):
        impl.predict(existing)

    class _CV:
        @staticmethod
        def imread(path: str):  # noqa: ARG004
            return None

    monkeypatch.setattr(importlib, "import_module", lambda name: _CV())
    with pytest.raises(ValueError):
        impl.predict(existing)

    export_dir = impl.export()
    assert (export_dir / "README.txt").exists()


def test_rtdetr_approach_flows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logger = _Logger()
    monkeypatch.setattr("approaches.rtdetr.approach.get_logger", lambda *a, **k: logger)
    monkeypatch.setattr(
        "approaches.rtdetr.approach.parse_common_config",
        lambda cfg: types.SimpleNamespace(project="demo", raw_dir=tmp_path, processed_dir=tmp_path / "proc", image_glob="*.jpg"),
    )

    class _DS:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            self.kwargs = kwargs

        def export_coco(self):
            out = tmp_path / "proc" / "coco" / "annotations.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("{}", encoding="utf-8")
            return out

    monkeypatch.setattr("approaches.rtdetr.approach.Dataset", _DS)
    impl = RTDETRApproach(_ctx(tmp_path, {"project": "demo", "data": {}}, approach="rtdetr"))
    impl.prepare_data()

    monkeypatch.setattr(importlib, "import_module", lambda name: (_ for _ in ()).throw(ImportError("torch missing")))
    with pytest.raises(RuntimeError):
        impl.train()
    monkeypatch.setattr(importlib, "import_module", lambda name: object())
    impl.train()

    assert impl.evaluate()["count_error"] == 0.0

    missing = tmp_path / "none.jpg"
    with pytest.raises(FileNotFoundError):
        impl.predict(missing)

    existing = tmp_path / "img.jpg"
    existing.write_bytes(b"x")
    real_import = __import__

    def _patched_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: ANN001
        if name == "PIL":
            raise ImportError("pillow missing")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", _patched_import)
    with pytest.raises(RuntimeError):
        impl.predict(existing)

    export_dir = impl.export()
    assert (export_dir / "README.txt").exists()


def test_yolo_approach_core_flows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logger = _Logger()
    monkeypatch.setattr("approaches.yolo.approach.get_logger", lambda *a, **k: logger)
    monkeypatch.setattr(
        "approaches.yolo.approach.parse_common_config",
        lambda cfg: types.SimpleNamespace(processed_dir=tmp_path / "proc"),
    )

    impl = YoloApproach(_ctx(tmp_path, {"project": "demo", "data": {}}, approach="yolo"))
    with pytest.raises(ValueError):
        impl.prepare_data()

    cfg_no_splits = {"project": "demo", "data": {"coco": {}}, "approach": {}}
    impl_no_splits = YoloApproach(_ctx(tmp_path, cfg_no_splits, approach="yolo"))
    with pytest.raises(ValueError):
        impl_no_splits.prepare_data()

    out_data_yaml = tmp_path / "proc" / "yolo" / "data.yaml"
    out_data_yaml.parent.mkdir(parents=True, exist_ok=True)

    calls = {"splits": 0}
    monkeypatch.setattr("approaches.yolo.approach.convert_coco_split_to_yolo", lambda split, output_dir, mask_cfg: calls.__setitem__("splits", calls["splits"] + 1) or ["insect"])  # noqa: E501
    monkeypatch.setattr("approaches.yolo.approach.write_yolo_dataset_yaml", lambda *a, **k: out_data_yaml)
    cfg_ok = {
        "project": "demo",
        "data": {
            "coco": {
                "train": {"images_dir": str(tmp_path), "annotations_path": str(tmp_path / "train.json")},
                "val": {"images_dir": str(tmp_path), "annotations_path": str(tmp_path / "val.json")},
            }
        },
        "approach": {},
    }
    (tmp_path / "train.json").write_text("{}", encoding="utf-8")
    (tmp_path / "val.json").write_text("{}", encoding="utf-8")
    impl_ok = YoloApproach(_ctx(tmp_path, cfg_ok, approach="yolo"))
    impl_ok.prepare_data()
    assert calls["splits"] == 2

    # resolve weights and candidates
    run_weights = impl_ok.ctx.run_dir / "train" / "weights"
    run_weights.mkdir(parents=True, exist_ok=True)
    (run_weights / "best.pt").write_text("", encoding="utf-8")
    assert impl_ok._resolve_weights().endswith("best.pt")
    (run_weights / "best.pt").unlink()
    (run_weights / "last.pt").write_text("", encoding="utf-8")
    assert impl_ok._resolve_weights().endswith("last.pt")
    (run_weights / "last.pt").unlink()
    impl_ok.ctx.config["approach"] = {"weights": "custom.pt"}
    assert impl_ok._resolve_weights() == "custom.pt"
    impl_ok.ctx.config["approach"] = {"model": "yolo11n.pt"}
    assert impl_ok._resolve_weights() == "yolo11n.pt"
    assert impl_ok._resolve_model_candidates() == ["yolo11n.pt"]
    impl_ok.ctx.config["approach"] = {"model_candidates": ["a.pt", "b.pt"]}
    assert impl_ok._resolve_model_candidates() == ["a.pt", "b.pt"]

    # resolve train model
    class _UMod:
        class YOLO:
            def __init__(self, candidate: str) -> None:
                if candidate == "a.pt":
                    raise RuntimeError("bad")
                self.candidate = candidate

    impl_ok.ctx.config["approach"] = {"model_candidates": ["a.pt", "b.pt"]}
    selected = impl_ok._resolve_train_model(_UMod)
    assert selected.candidate == "b.pt"
    impl_ok.ctx.config["approach"] = {"model_candidates": ["a.pt"]}
    with pytest.raises(RuntimeError):
        impl_ok._resolve_train_model(_UMod)

    # count error and metrics file writing
    split = types.SimpleNamespace(
        annotations_path=tmp_path / "ann.json",
        images_dir=tmp_path,
    )
    split.annotations_path.write_text(
        json.dumps(
            {
                "images": [{"id": 1, "file_name": "img.jpg"}],
                "annotations": [{"image_id": 1}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "img.jpg").write_bytes(b"x")

    class _Boxes:
        def __len__(self) -> int:
            return 2

    class _Pred:
        boxes = _Boxes()

    class _Model:
        def predict(self, **kwargs):  # noqa: ANN003
            return [_Pred()]

    ce = impl_ok._compute_count_error(_Model(), split, imgsz=640, conf=0.25, max_images=5)
    assert ce == 1.0
    impl_ok._write_metrics_file({"mAP50": 0.3})
    assert (impl_ok.ctx.run_dir / "model_metrics.json").exists()

    impl_ok.ctx.config["eval"] = {"metrics_output_path": str(tmp_path / "custom_metrics.json")}
    impl_ok._write_metrics_file({"mAP50": 0.5})
    assert (tmp_path / "custom_metrics.json").exists()


def test_yolo_train_evaluate_predict_export(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logger = _Logger()
    monkeypatch.setattr("approaches.yolo.approach.get_logger", lambda *a, **k: logger)
    monkeypatch.setattr(
        "approaches.yolo.approach.parse_common_config",
        lambda cfg: types.SimpleNamespace(processed_dir=tmp_path / "proc"),
    )

    data_yaml = tmp_path / "proc" / "yolo" / "data.yaml"
    data_yaml.parent.mkdir(parents=True, exist_ok=True)
    data_yaml.write_text("path: x", encoding="utf-8")

    class _BoxMetric:
        map = 0.4
        map50 = 0.6
        p = [0.8]
        r = [0.5]

    class _ValResult:
        box = _BoxMetric()

    class _Box:
        def __init__(self):
            self.xyxy = [types.SimpleNamespace(tolist=lambda: [1.0, 2.0, 3.0, 4.0])]
            self.conf = [0.9]
            self.cls = [2]

    class _PredResult:
        boxes = [_Box()]

    class _FakeYOLO:
        def __init__(self, weights: str) -> None:
            self.weights = weights
            self.trained = None

        def train(self, **kwargs):  # noqa: ANN003
            self.trained = kwargs

        def val(self, **kwargs):  # noqa: ANN003
            return _ValResult()

        def predict(self, **kwargs):  # noqa: ANN003
            return [_PredResult()]

        def export(self, **kwargs):  # noqa: ANN003
            return {"exported": kwargs}

    fake_ultra = types.SimpleNamespace(YOLO=_FakeYOLO)

    def _import_ultra(name: str):  # noqa: ANN001
        if name == "ultralytics":
            return fake_ultra
        raise ImportError("unexpected")

    cfg = {
        "project": "demo",
        "approach": {"model_candidates": ["m.pt"], "img_size": 320, "conf": 0.1, "export_format": "onnx"},
        "training": {"epochs": 1, "batch_size": 2, "device": None},
        "eval": {"compute_count_error": True},
        "data": {"coco": {"val": {"images_dir": str(tmp_path), "annotations_path": str(tmp_path / "val.json")}}},
    }
    (tmp_path / "val.json").write_text("{}", encoding="utf-8")
    impl = YoloApproach(_ctx(tmp_path, cfg, approach="yolo"))

    monkeypatch.setattr(importlib, "import_module", lambda name: (_ for _ in ()).throw(ImportError("missing")))
    with pytest.raises(RuntimeError):
        impl.train()

    monkeypatch.setattr(importlib, "import_module", _import_ultra)
    impl.train()

    monkeypatch.setattr(impl, "_compute_count_error", lambda *a, **k: 1.25)
    metrics = impl.evaluate()
    assert metrics["mAP50"] == 0.6
    assert metrics["count_error"] == 1.25
    assert "precision" in metrics and "recall" in metrics and "f1" in metrics

    missing = tmp_path / "missing.jpg"
    with pytest.raises(FileNotFoundError):
        impl.predict(missing)

    image_path = tmp_path / "img.jpg"
    image_path.write_bytes(b"x")
    preds = impl.predict(image_path)
    assert preds[0]["class_id"] == 2

    export_dir = impl.export()
    assert (export_dir / "export_result.txt").exists()

    monkeypatch.setattr(importlib, "import_module", lambda name: (_ for _ in ()).throw(ImportError("missing")))
    with pytest.raises(RuntimeError):
        impl.evaluate()
    with pytest.raises(RuntimeError):
        impl.export()
