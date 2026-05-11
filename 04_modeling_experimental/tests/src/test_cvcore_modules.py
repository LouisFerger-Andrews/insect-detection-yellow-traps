from __future__ import annotations

import importlib
import builtins
import sys
import types
from pathlib import Path

import cv2
import numpy as np
import pytest
from typer.testing import CliRunner

from cvcore.cli import app as cvcore_app
from cvcore.data import exporters as cv_exporters
from cvcore.data.loaders import build_coco_dataset, build_dataloader
from cvcore.eval.evaluator import Evaluator
from cvcore.eval.metrics import count_mae
from cvcore.models.classical import OpenCVDetector
from cvcore.models.pytorch import TorchDetectionModel
from cvcore.models.yolo import YoloModel
from cvcore.training.optim import build_optimizer
from cvcore.training.schedulers import build_scheduler
from cvcore.training.trainer import Trainer
from cvcore.utils.io import ensure_dir
from cvcore.utils.reproducibility import capture_env, set_seed


class _FakeLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, msg: str, *args) -> None:  # noqa: ANN001
        self.messages.append(msg % args if args else msg)


class _FakeTorchModule:
    def __init__(self) -> None:
        self._saved = None
        self._loaded = None
        self._seed = None
        self.cuda = types.SimpleNamespace(manual_seed_all=self._manual_seed_all)
        self.optim = types.SimpleNamespace(
            AdamW=lambda params, lr: ("adamw", params, lr),
            SGD=lambda params, lr, momentum: ("sgd", params, lr, momentum),
            lr_scheduler=types.SimpleNamespace(
                CosineAnnealingLR=lambda opt, T_max: ("cosine", opt, T_max)
            ),
        )
        self.__version__ = "fake-torch"

    def manual_seed(self, seed: int) -> None:
        self._seed = seed

    def _manual_seed_all(self, seed: int) -> None:
        self._seed = seed

    def save(self, state, path: str) -> None:  # noqa: ANN001
        self._saved = (state, path)

    def load(self, path: str, map_location: str = "cpu"):  # noqa: ANN001
        self._loaded = (path, map_location)
        return {"loaded": True}


def test_cvcore_cli_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr("cvcore.cli.setup_logging", lambda: None)
    monkeypatch.setattr("cvcore.cli.load_yaml", lambda _: {"x": 1})

    for cmd in ("prepare-data", "train", "evaluate", "predict", "export"):
        result = runner.invoke(cvcore_app, [cmd, "demo", "cfg.yml"])
        assert result.exit_code == 0
        assert "with {'x': 1}" in result.stdout


def test_evaluator_report_and_abstract_behavior(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ev = Evaluator()
    with pytest.raises(NotImplementedError):
        ev.evaluate(model=None, dataloader=[])

    ev.report({"mAP": 0.5})
    assert "{'mAP': 0.5}" in capsys.readouterr().out

    out_path = tmp_path / "metrics.txt"
    ev.report({"count_error": 1.0}, out_path=str(out_path))
    assert "count_error" in out_path.read_text(encoding="utf-8")


def test_count_mae_validates_lengths() -> None:
    assert count_mae([1, 3], [1, 1]) == 1.0
    with pytest.raises(ValueError):
        count_mae([1], [1, 2])


def test_cvcore_model_wrappers_and_io(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyTorchModel:
        def __init__(self) -> None:
            self.loaded = None

        def __call__(self, batch):  # noqa: ANN001
            return [{"ok": True, "n": len(batch)}]

        def state_dict(self):
            return {"weights": 1}

        def load_state_dict(self, data):  # noqa: ANN001
            self.loaded = data

    fake_torch = _FakeTorchModule()
    monkeypatch.setitem(__import__("sys").modules, "torch", fake_torch)

    torch_model = TorchDetectionModel(DummyTorchModel())
    assert torch_model.predict([1])[0]["ok"] is True
    with pytest.raises(NotImplementedError):
        torch_model.train([], [])
    torch_model.save(str(tmp_path / "torch.pt"))
    loaded = torch_model.load(str(tmp_path / "torch.pt"))
    assert isinstance(loaded, TorchDetectionModel)

    class DummyYolo:
        def __init__(self) -> None:
            self.saved = None
            self.loaded = None

        def __call__(self, batch):  # noqa: ANN001
            return [{"batch": len(batch)}]

        def save(self, path: str) -> None:
            self.saved = path

        def load(self, path: str) -> None:
            self.loaded = path

    yolo = DummyYolo()
    yolo_model = YoloModel(yolo)
    assert yolo_model.predict([1])[0]["batch"] == 1
    with pytest.raises(NotImplementedError):
        yolo_model.train([], [])
    yolo_model.save("x.bin")
    yolo_model.load("x.bin")
    assert yolo.saved == "x.bin"
    assert yolo.loaded == "x.bin"

    detector = OpenCVDetector(threshold=150)
    result = detector.train([], [])
    assert result["status"] == "no_train"
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    img[0:2, 0:2] = (255, 255, 255)
    pred = detector.predict([img])
    assert pred[0]["count"] in (0, 1)

    thr_path = tmp_path / "thr.txt"
    detector.save(str(thr_path))
    loaded_detector = detector.load(str(thr_path))
    assert isinstance(loaded_detector, OpenCVDetector)


def test_training_builders_and_trainer(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_torch = _FakeTorchModule()
    monkeypatch.setitem(__import__("sys").modules, "torch", fake_torch)

    opt1 = build_optimizer(params=[1], cfg={"optimizer": "adamw", "lr": 0.01})
    assert opt1[0] == "adamw"
    opt2 = build_optimizer(params=[1], cfg={"optimizer": "sgd", "lr": 0.02})
    assert opt2[0] == "sgd"
    with pytest.raises(ValueError):
        build_optimizer(params=[1], cfg={"optimizer": "unknown"})

    sched = build_scheduler(opt1, {"scheduler": "cosine", "epochs": 10})
    assert sched[0] == "cosine"
    assert build_scheduler(opt1, {"scheduler": "none"}) is None

    class DummyModel:
        def train(self, train_loader, val_loader=None):  # noqa: ANN001
            return {"ok": True, "n": len(train_loader)}

    trainer = Trainer(DummyModel())
    out = trainer.fit([1, 2], [3])
    assert out["ok"] is True


def test_cvcore_data_helpers_and_utils(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ann = tmp_path / "_annotations.coco.json"
    ann.write_text(
        '{"images":[{"id":1,"file_name":"a.jpg"}],"annotations":[],"categories":[]}',
        encoding="utf-8",
    )
    (tmp_path / "a.jpg").write_bytes(b"x")
    ds = build_coco_dataset(root=tmp_path, annotation_file=ann, transforms=None)
    assert len(ds) == 1

    fake_loader_class = lambda dataset, batch_size, shuffle: (dataset, batch_size, shuffle)
    torch_mod = types.ModuleType("torch")
    torch_utils_mod = types.ModuleType("torch.utils")
    torch_utils_data_mod = types.ModuleType("torch.utils.data")
    torch_utils_data_mod.DataLoader = fake_loader_class
    torch_utils_mod.data = torch_utils_data_mod
    torch_mod.utils = torch_utils_mod
    monkeypatch.setitem(sys.modules, "torch", torch_mod)
    monkeypatch.setitem(sys.modules, "torch.utils", torch_utils_mod)
    monkeypatch.setitem(sys.modules, "torch.utils.data", torch_utils_data_mod)
    dl = build_dataloader(ds, batch_size=4, shuffle=False)
    assert dl[1] == 4

    with pytest.raises(NotImplementedError):
        cv_exporters.export_coco([], "x")
    with pytest.raises(NotImplementedError):
        cv_exporters.export_yolo([], "x")

    new_dir = tmp_path / "nested" / "path"
    ensure_dir(str(new_dir))
    assert new_dir.exists()


def test_reproducibility_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_torch = _FakeTorchModule()
    fake_np = types.SimpleNamespace(random=types.SimpleNamespace(seed=lambda _: None))
    monkeypatch.setitem(__import__("sys").modules, "torch", fake_torch)
    monkeypatch.setitem(__import__("sys").modules, "numpy", fake_np)

    set_seed(123)
    env = capture_env()
    assert "python" in env
    assert env["torch"] == "fake-torch"

    # no-op path
    set_seed(0)


def test_classical_opencv_detector_import_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    detector = OpenCVDetector()
    real_import = builtins.__import__

    def _patched_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: ANN001
        if name == "cv2":
            raise ImportError("missing")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", _patched_import)
    with pytest.raises(RuntimeError):
        detector.predict([np.zeros((4, 4, 3), dtype=np.uint8)])


def test_classical_detector_file_flow(tmp_path: Path) -> None:
    detector = OpenCVDetector(threshold=101)
    path = tmp_path / "threshold.txt"
    detector.save(str(path))
    loaded = detector.load(str(path))
    assert isinstance(loaded, OpenCVDetector)
    assert loaded.threshold == 101
