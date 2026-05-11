"""Logging helpers."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional


def get_logger(name: str, run_dir: Optional[Path] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if run_dir is not None:
        run_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(run_dir / "run.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
