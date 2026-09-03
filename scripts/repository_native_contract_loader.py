#!/usr/bin/env python3
"""Load scripts/repository-native-contract-check.py for callers that cannot import its hyphenated filename."""

from __future__ import annotations

import importlib.util
from pathlib import Path

CONTRACT = Path(__file__).resolve().parent / "repository-native-contract-check.py"


def load_contract():
    spec = importlib.util.spec_from_file_location("repository_native_contract", CONTRACT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
