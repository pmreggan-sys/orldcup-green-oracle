from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.repository import TournamentRepository
from app.schemas import MatchContextPayload, PredictRequest, RawSkillPrediction


STAGE_TO_SKILL = {
    "group": "小组赛",
    "round_of_32": "32强",
    "round_of_16": "16强",
    "quarterfinal": "8强",
    "semifinal": "半决赛",
    "final": "决赛",
}


class GreenOracleEngineError(RuntimeError):
    """Raised when the bundled Green Oracle engine cannot produce a prediction."""


@dataclass(slots=True)
class GreenOracleEngine:
    repository: TournamentRepository
    workspace_root: Path

    def predict(self, request: PredictRequest, match_context: MatchContextPayload | None = None) -> RawSkillPrediction:
        team_a = self.repository.team_by_slug(request.teamA)
        team_b = self.repository.team_by_slug(request.teamB)
        command = [
            "python3",
            str(self.workspace_root / "worldcup2026-green-oracle" / "tools" / "predict.py"),
            "--teamA",
            team_a.name_zh,
            "--teamB",
            team_b.name_zh,
            "--stage",
            STAGE_TO_SKILL[request.stage],
        ]
        if request.stage != "group":
            command.append("--knockout")
        if match_context and match_context.homeSide:
            command.extend(["--home", match_context.homeSide])

        result = subprocess.run(
            command,
            cwd=str(self.workspace_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise GreenOracleEngineError(result.stderr.strip() or result.stdout.strip() or "Green Oracle engine failed.")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise GreenOracleEngineError("Green Oracle engine returned invalid JSON.") from exc
        return RawSkillPrediction.model_validate(payload)
