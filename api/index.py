"""Vercel FastAPI entrypoint."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.main import app  # noqa: E402
