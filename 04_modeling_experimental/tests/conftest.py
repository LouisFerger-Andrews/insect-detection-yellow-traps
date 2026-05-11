from __future__ import annotations

import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
BACKEND = REPO_ROOT / "03_application" / "backend"

for path in (SRC, BACKEND):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Backend defaults required for importing settings-dependent modules in tests.
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("POSTGRES_URL", "sqlite:///./test.db")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "test")
os.environ.setdefault("MODEL_WEIGHTS_PATH", "03_application/poc-model/swd_yolo_best.pt")
