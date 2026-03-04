# receipts/429-floor/receipts_429_floor_import.py
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
POLICY_PATH = HERE / "policy.py"

MODULE_NAME = "pitstop_receipt_429_floor_policy"

spec = importlib.util.spec_from_file_location(MODULE_NAME, POLICY_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to create import spec for {POLICY_PATH}")

policy_module = importlib.util.module_from_spec(spec)

# Critical: register before exec so dataclasses can resolve cls.__module__
sys.modules[MODULE_NAME] = policy_module

spec.loader.exec_module(policy_module)