from app.repository import TournamentRepository
from app.schemas import PredictRequest
from app.services.fallback import FallbackEngine


def test_fallback_invariants_group_stage():
    repository = TournamentRepository()
    engine = FallbackEngine(repository)
    payload = engine.predict(PredictRequest(teamA="mexico", teamB="south-africa", stage="group", lang="zh"))

    assert payload.teamA.winProb + payload.drawProb + payload.teamB.winProb == 100
    assert payload.teamA.winProb <= 85
    assert payload.teamB.winProb <= 85
    assert "-" in payload.predictedScore
    assert payload.confidence in {"high", "medium", "low"}
    assert len(payload.playersToWatch) == 2


def test_fallback_knockout_newcomer_penalty():
    repository = TournamentRepository()
    engine = FallbackEngine(repository)
    payload = engine.predict(PredictRequest(teamA="spain", teamB="jordan", stage="round_of_16", lang="en"))

    assert payload.teamA.winProb > payload.teamB.winProb
    assert payload.drawProb < 20
    assert payload.knockout is not None
    assert "西班牙" in payload.knockout.advanceProb
