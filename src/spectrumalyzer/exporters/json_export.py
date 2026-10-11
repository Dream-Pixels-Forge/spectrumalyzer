"""Rich JSON — the complete analysis, one source of truth."""

from __future__ import annotations

import json
from typing import Any, Dict

from spectrumalyzer.model import AnalysisResult


def render(result: AnalysisResult) -> str:
    data: Dict[str, Any] = result.to_dict()
    return json.dumps(data, indent=2)
