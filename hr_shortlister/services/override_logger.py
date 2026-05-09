from __future__ import annotations

import json
from pathlib import Path

from hr_shortlister.core.schemas import OverrideLogEntry, OverrideRequest, ScoringResult
from hr_shortlister.core.utils import ensure_dir


DEFAULT_LOG_PATH = Path("data") / "overrides" / "log.json"


def apply_override(result: ScoringResult, request: OverrideRequest) -> tuple[ScoringResult, OverrideLogEntry]:
    score_item = getattr(result.scores, request.dimension)
    original_score = score_item.score
    score_item.score = request.new_score

    updated = ScoringResult.model_validate(result.model_dump())
    entry = OverrideLogEntry(
        candidate=request.candidate,
        dimension=request.dimension,
        original_score=original_score,
        new_score=request.new_score,
        reason=request.reason,
    )
    return updated, entry


def append_override_log(entry: OverrideLogEntry, path: str | Path = DEFAULT_LOG_PATH) -> None:
    log_path = Path(path)
    ensure_dir(log_path.parent)
    entries = load_override_log(log_path)
    entries.append(entry.model_dump(mode="json"))
    log_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def load_override_log(path: str | Path = DEFAULT_LOG_PATH) -> list[dict]:
    log_path = Path(path)
    if not log_path.exists():
        return []
    try:
        return json.loads(log_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
