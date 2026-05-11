from pathlib import Path

import typer

from cvcore.utils.config import load_yaml
from cvcore.utils.logging import setup_logging

app = typer.Typer(add_completion=False)


@app.command()
def prepare_data(project: str, config: str):
    setup_logging()
    cfg = load_yaml(config)
    typer.echo(f"Preparing data for {project} with {cfg}")


@app.command()
def train(project: str, config: str):
    setup_logging()
    cfg = load_yaml(config)
    typer.echo(f"Training for {project} with {cfg}")


@app.command()
def evaluate(project: str, config: str):
    setup_logging()
    cfg = load_yaml(config)
    typer.echo(f"Evaluating for {project} with {cfg}")


@app.command()
def predict(project: str, config: str):
    setup_logging()
    cfg = load_yaml(config)
    typer.echo(f"Predicting for {project} with {cfg}")


@app.command()
def export(project: str, config: str):
    setup_logging()
    cfg = load_yaml(config)
    typer.echo(f"Exporting for {project} with {cfg}")


if __name__ == "__main__":
    app()
