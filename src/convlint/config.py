"""Optional .convlint.json config loading."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

DEFAULT_NAMES = (".convlint.json", "convlint.json")


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    if path:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    for name in DEFAULT_NAMES:
        if os.path.exists(name):
            with open(name, "r", encoding="utf-8") as fh:
                return json.load(fh)
    return {}
