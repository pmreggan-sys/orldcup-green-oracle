import pytest

from app.config import Settings
from app.repository import TournamentRepository
from app.schemas import (
    MatchContextPayload,
    PredictRequest,
    RawDataQuality,
    RawEngineModel,
    RawKnockoutPayload,
    RawPlayerToWatch,
    RawSkillPrediction,
    RawTeamProbability,
    RawTournamentPriors,
)
from app.services.fallback import FallbackEngine
from app.services.green_oracle_engine import GreenOracleEngine
from app.services.llm_client import LLMError, OpenAICompatibleClient
from app.services.prediction_service import PredictionService
from app.services.prompt_builder import PromptBuilder
from app.services.schedule_service import ScheduleService


class StubClient(OpenAICompatibleClient):
    def __init__(self, payload):
        self.payload = payload
        self.settings = Settings()

    async def chat_json(self, system_prompt: str, user_prompt: str, *, model: str | None = None) -> dict:
        return self.payload


class StubScheduleService:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def load_snapshot(self):
        return self.snapshot

    def resolve_match_context(self, request, snapshot):
        return MatchContextPayload(
            fixtureId="fd-1",
            stage=request.stage,
            stageLabelZh="16 强",
            stageLabelEn="Round of 16",
            status="scheduled",
            venueZh="纽约",
            venueEn="New York",
            homeSide=None,
            sourceUpdatedAt=snapshot.fetchedAt,
            dataDelayNoteZh=snapshot.dataDelayNoteZh,
            dataDelayNoteEn=snapshot.dataDelayNoteEn,
        )


def make_engine_prediction():
    return RawSkillPrediction(
        teamA=RawTeamProbability(name="法国", winProb=41),
        draw=27,
        teamB=RawTeamProbability(name="英格兰", winProb=32),
        predictedScore="1-1",
        confidence="中",
        keyFactors=["[LLM填写]", "[LLM填写]", "[LLM填写]"],
        analysis="[LLM填写：150字以内，不得改动概率与比分]",
        playersToWatch=[
            RawPlayerToWatch(team="法国", player="姆巴佩", reason="[LLM填写]"),
            RawPlayerToWatch(team="英格兰", player="凯恩", reason="[LLM填写]"),
        ],
        engine=RawEngineModel(
            model="elo-dixon-coles-poisson v1",
            ratings={"法国": 2065, "英格兰": 2045},
            lambda90={"法国": 1.4, "英格兰": 1.2},
            rho=-0.12,
            homeAdv=None,
            capApplied=85,
        ),
        dataQuality=RawDataQuality(level="medium", sourcesUsed=["engine_ratings"], notes="ok"),
        tournamentPriors=RawTournamentPriors(source="Kimi", sourceDate="2026-06-05", teamA=None, teamB=None),
        safeUse="仅供球迷讨论，不构成任何决策建议。",
        stage="16强",
        knockout=RawKnockoutPayload(
            note="draw 表示90分钟战平进入加时/点球",
            advanceProb={"法国": 53, "英格兰": 47},
        ),
    )


@pytest.mark.asyncio
async def test_prediction_service_rejects_mutated_engine_fields(sample_snapshot):
    repository = TournamentRepository()
    engine_prediction = make_engine_prediction()
    mutated = engine_prediction.model_copy(deep=True)
    mutated.teamA.winProb = 99

    service = PredictionService(
        settings=Settings(openai_api_key="test", openai_model="gpt-4o-mini", openai_base_url="https://example.com/v1"),
        repository=repository,
        prompt_builder=PromptBuilder(repository.base_path.parent / "worldcup2026-green-oracle" / "SKILL.md"),
        fallback_engine=FallbackEngine(repository),
        llm_client=StubClient(mutated.model_dump()),
        green_oracle_engine=GreenOracleEngine(repository, repository.base_path.parent),
        schedule_service=StubScheduleService(sample_snapshot),
    )

    with pytest.raises(LLMError):
        service._assert_immutable_engine_fields(engine_prediction, mutated)


@pytest.mark.asyncio
async def test_prediction_service_normalizes_knockout_payload(sample_snapshot):
    repository = TournamentRepository()
    service = PredictionService(
        settings=Settings(),
        repository=repository,
        prompt_builder=PromptBuilder(repository.base_path.parent / "worldcup2026-green-oracle" / "SKILL.md"),
        fallback_engine=FallbackEngine(repository),
        llm_client=StubClient({}),
        green_oracle_engine=GreenOracleEngine(repository, repository.base_path.parent),
        schedule_service=StubScheduleService(sample_snapshot),
    )

    payload = await service._normalize_prediction(
        make_engine_prediction(),
        PredictRequest(teamA="france", teamB="england", stage="round_of_16", lang="zh"),
        service.schedule_service.resolve_match_context(PredictRequest(teamA="france", teamB="england", stage="round_of_16", lang="zh"), sample_snapshot),
        translate=False,
    )

    assert payload.knockout is not None
    assert payload.knockout.advanceProb["法国"] == 53
    assert payload.engine.model == "elo-dixon-coles-poisson v1"


@pytest.mark.asyncio
async def test_prediction_service_replaces_placeholder_copy(sample_snapshot):
    repository = TournamentRepository()
    service = PredictionService(
        settings=Settings(),
        repository=repository,
        prompt_builder=PromptBuilder(repository.base_path.parent / "worldcup2026-green-oracle" / "SKILL.md"),
        fallback_engine=FallbackEngine(repository),
        llm_client=StubClient({}),
        green_oracle_engine=GreenOracleEngine(repository, repository.base_path.parent),
        schedule_service=StubScheduleService(sample_snapshot),
    )

    payload = await service._normalize_prediction(
        make_engine_prediction(),
        PredictRequest(teamA="france", teamB="england", stage="round_of_16", lang="zh"),
        service.schedule_service.resolve_match_context(PredictRequest(teamA="france", teamB="england", stage="round_of_16", lang="zh"), sample_snapshot),
        translate=False,
    )

    assert all("[LLM填写]" not in factor.zh for factor in payload.keyFactors)
    assert "[LLM填写]" not in payload.analysis.zh
    assert all("[LLM填写]" not in player.reasonZh for player in payload.playersToWatch)


def test_prediction_service_repairs_overlong_live_payload():
    raw = make_engine_prediction().model_dump()
    raw["analysis"] = "这是一段" + "很长" * 120
    raw["keyFactors"] = ["一个非常非常长的关键因素文案", "第二个非常非常长的关键因素文案", "第三个非常非常长的关键因素文案"]
    repaired = PredictionService._repair_live_payload(raw)
    assert len(repaired["analysis"]) <= 150
    assert all(len(item) <= 15 for item in repaired["keyFactors"])
