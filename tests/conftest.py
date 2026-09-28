"""Hypothesis profiles for the property-based tests.

Locally the default profile explores new random examples each run (and remembers failures in the
git-ignored `.hypothesis/` database). CI sets `HYPOTHESIS_PROFILE=ci`: derandomized, so every CI
run checks the same examples and a red run is reproducible rather than a flake.
"""

import os

from hypothesis import settings

settings.register_profile("ci", derandomize=True, database=None, print_blob=True)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))
