"""Entry-point CLI for insect detection approaches."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from core.approach_base import RunContext
from core.config import load_config
from core.registry import get_approach, list_approaches
from utils.logging import get_logger
from utils.repro import set_seed

app = typer.Typer(help="Insect on Yellow Paper CV CLI.")


def _build_context(project: str, approach: str, config_path: Path) -> RunContext:
    cfg = load_config(config_path, project)
    seed = cfg.get("repro", {}).get("seed")
    set_seed(seed)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path("04_modeling_experimental") / "runs" / project / approach / timestamp
    return RunContext(project=project, approach=approach, run_dir=run_dir, config=cfg)


def _run_or_fail(fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
    except Exception as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc


@app.command("list-approaches")
def list_approaches_cmd() -> None:
    """List available approaches."""
    for name in list_approaches().keys():
        typer.echo(name)


@app.command()
def prepare_data(
    project: str = typer.Option(..., "--project"),
    approach: str = typer.Option(..., "--approach"),
    config: Path = typer.Option(Path("04_modeling_experimental/configs/base.yaml"), "--config"),
) -> None:
    """Prepare datasets for the selected approach."""
    ctx = _build_context(project, approach, config)
    impl = get_approach(approach)(ctx)
    _run_or_fail(impl.prepare_data)


@app.command()
def train(
    project: str = typer.Option(..., "--project"),
    approach: str = typer.Option(..., "--approach"),
    config: Path = typer.Option(Path("04_modeling_experimental/configs/base.yaml"), "--config"),
) -> None:
    """Train the selected approach."""
    ctx = _build_context(project, approach, config)
    impl = get_approach(approach)(ctx)
    _run_or_fail(impl.train)


@app.command()
def evaluate(
    project: str = typer.Option(..., "--project"),
    approach: str = typer.Option(..., "--approach"),
    config: Path = typer.Option(Path("04_modeling_experimental/configs/base.yaml"), "--config"),
) -> None:
    """Evaluate the selected approach."""
    ctx = _build_context(project, approach, config)
    impl = get_approach(approach)(ctx)
    logger = get_logger("evaluate", ctx.run_dir)

    def _eval() -> None:
        metrics = impl.evaluate()
        logger.info("Metrics: %s", metrics)

    _run_or_fail(_eval)


@app.command()
def predict(
    project: str = typer.Option(..., "--project"),
    approach: str = typer.Option(..., "--approach"),
    config: Path = typer.Option(Path("04_modeling_experimental/configs/base.yaml"), "--config"),
    image_path: Path = typer.Option(..., "--image"),
) -> None:
    """Run inference on a single image."""
    ctx = _build_context(project, approach, config)
    impl = get_approach(approach)(ctx)
    logger = get_logger("predict", ctx.run_dir)

    def _predict() -> None:
        detections = impl.predict(image_path)
        logger.info("Detections: %s", detections)

    _run_or_fail(_predict)


@app.command()
def export(
    project: str = typer.Option(..., "--project"),
    approach: str = typer.Option(..., "--approach"),
    config: Path = typer.Option(Path("04_modeling_experimental/configs/base.yaml"), "--config"),
) -> None:
    """Export artifacts for deployment."""
    ctx = _build_context(project, approach, config)
    impl = get_approach(approach)(ctx)
    logger = get_logger("export", ctx.run_dir)

    def _export() -> None:
        export_path = impl.export()
        logger.info("Exported to %s", export_path)

    _run_or_fail(_export)


if __name__ == "__main__":
    app()
