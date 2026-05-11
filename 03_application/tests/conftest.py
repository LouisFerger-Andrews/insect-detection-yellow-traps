from __future__ import annotations

import os
import sys
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parent
APP_ROOT = TEST_ROOT.parent
REPO_ROOT = APP_ROOT.parent
BACKEND = APP_ROOT / "backend"

for path in (BACKEND, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Defaults needed for importing backend settings in tests.
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("POSTGRES_URL", "sqlite:///./test.db")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "test")
os.environ.setdefault("MODEL_WEIGHTS_PATH", "03_application/poc-model/swd_yolo_best.pt")
