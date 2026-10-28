"""The I3 checker (`harness/v08/i3/checker.py`), loaded by path: I4 reuses its broker-tool parsers
and verdict helpers unchanged."""

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "i3" / "checker.py"
_spec = importlib.util.spec_from_file_location("v08_i3_checker", _PATH)
assert _spec is not None and _spec.loader is not None
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)
