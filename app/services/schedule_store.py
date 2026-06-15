from __future__ import annotations

import json
from pathlib import Path

from app.schemas import ScheduleSnapshot


class ScheduleStore:
    def __init__(self, cache_file: Path) -> None:
        self.cache_file = cache_file

    def load(self) -> ScheduleSnapshot | None:
        if not self.cache_file.exists():
            return None
        return ScheduleSnapshot.model_validate_json(self.cache_file.read_text(encoding="utf-8"))

    def save(self, snapshot: ScheduleSnapshot) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.cache_file.with_suffix(".tmp")
        temp_path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        temp_path.replace(self.cache_file)
