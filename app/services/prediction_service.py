from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from copy import deepcopy

from app.config import Settings
from app.i18n import CONFIDENCE_LABELS
from app.repository import TournamentRepository
from app.schemas import (
    DataQualityPayload,
    EngineDetails,
    KnockoutAdvancePayload,
    LocalizedAnalysis,
    LocalizedFactor,
    MatchContextPayload,
    NoticePayload,
    PlayerToWatch,
    PredictRequest,
    PredictionPayload,
    PredictionResponse,
    RawSkillPrediction,
    SourceInfo,
    TournamentPriorTeam,
    TournamentPriorsPayload,
    TranslationPayload,
)
from app.services.fallback import FallbackEngine
from app.services.green_oracle_engine import GreenOracleEngine, GreenOracleEngineError
from app.services.llm_client import LLMError, OpenAICompatibleClient
from app.services.prompt_builder import PromptBuilder
from app.services.schedule_service import ScheduleService

logger = logging.getLogger(__name__)


TRANSLATION_PROMPT = """
你是一个严格的中英双语体育翻译器。你将收到一份世界杯预测结果的中文字段。
请输出合法 JSON，结构必须为：
{
  "keyFactorsEn": ["...", "...", "..."],
  "analysisEn": "...",
  "playersToWatchEn": [
    {"playerEn": "...", "reasonEn": "..."},
    {"playerEn": "...", "reasonEn": "..."}
  ]
}

要求：
1. 不要遗漏字段，不要输出任何 JSON 以外的内容。
2. 保留足球解说语气，但不要夸张。
3. 球员英文名若已知请用常见英文名，不确定时可用拼音转写。
"""


@dataclass(slots=True)
class PredictionService:
    settings: Settings
    repository: TournamentRepository
    prompt_builder: PromptBuilder
    fallback_engine: FallbackEngine
    llm_client: OpenAICompatibleClient
    green_oracle_engine: GreenOracleEngine
    schedule_service: ScheduleService

    async def predict(self, request: PredictRequest) -> PredictionResponse:
        snapshot = self.schedule_service.load_snapshot()
        match_context = self.schedule_service.resolve_match_context(request, snapshot)

        try:
            engine_prediction = self.green_oracle_engine.predict(request, match_context)
            if self.settings.live_mode_enabled:
                try:
                    return await self._predict_live(request, engine_prediction, match_context, snapshot)
                except Exception:  # noqa: BLE001
                    logger.exception("Live explanation pass failed; returning engine-only result.")
            payload = await self._normalize_prediction(engine_prediction, request, match_context, translate=request.lang == "en")
            return PredictionResponse(
                mode="engine",
                source=SourceInfo(provider="worldcup2026-green-oracle", model="elo-dixon-coles-poisson v1"),
                generatedAt=datetime.now(UTC),
                request=request,
                prediction=payload,
                notice=NoticePayload(
                    zh="当前结果由 Green Oracle 本地统计引擎直接生成，数值未经过模型改写。",
                    en="This prediction comes directly from the local Green Oracle engine, with all numeric fields kept intact.",
                ),
            )
        except GreenOracleEngineError:
            logger.exception("Green Oracle engine failed; considering deterministic fallback.")
            if not self.settings.demo_fallback_enabled:
                raise

        payload = self.fallback_engine.predict(request)
        if match_context:
            payload.matchContext = match_context
            payload.safeUse = "仅供球迷讨论，不构成任何决策建议。"
        return PredictionResponse(
            mode="fallback",
            source=SourceInfo(provider="demo", model="deterministic-fallback-v1"),
            generatedAt=datetime.now(UTC),
            request=request,
            prediction=payload,
            notice=NoticePayload(
                zh="Green Oracle 引擎暂时不可用，站点已切到确定性兜底结果以保持可访问。",
                en="The Green Oracle engine was unavailable, so the site returned a deterministic fallback result to stay online.",
            ),
        )

    async def _predict_live(
        self,
        request: PredictRequest,
        engine_prediction: RawSkillPrediction,
        match_context: MatchContextPayload | None,
        snapshot,
    ) -> PredictionResponse:
        system_prompt = self.prompt_builder.build(snapshot)
        fill_prompt = self.prompt_builder.build_fill_prompt(engine_prediction, match_context, request.lang)
        raw_result = await self.llm_client.chat_json(system_prompt, fill_prompt)
        repaired = self._repair_live_payload(raw_result)
        validated = RawSkillPrediction.model_validate(repaired)
        self._assert_immutable_engine_fields(engine_prediction, validated)
        normalized = await self._normalize_prediction(validated, request, match_context, translate=request.lang == "en")
        return PredictionResponse(
            mode="live",
            source=SourceInfo(
                provider=self.settings.openai_base_url or self.settings.anthropic_base_url,
                model=self.settings.openai_model if self.settings.openai_api_key.strip() else self.settings.anthropic_model,
            ),
            generatedAt=datetime.now(UTC),
            request=request,
            prediction=normalized,
            notice=NoticePayload(
                zh="Green Oracle 引擎先计算概率与比分，模型仅补充解说文案。",
                en="Green Oracle computed the probabilities first, and the model only filled the explanatory copy.",
            ),
        )

    async def _normalize_prediction(
        self,
        prediction: RawSkillPrediction,
        request: PredictRequest,
        match_context: MatchContextPayload | None,
        *,
        translate: bool,
    ) -> PredictionPayload:
        prediction = self._sanitize_prediction_placeholders(prediction, request)
        team_a = self.repository.team_by_zh(prediction.teamA.name)
        team_b = self.repository.team_by_zh(prediction.teamB.name)
        confidence = next(key for key, labels in CONFIDENCE_LABELS.items() if labels["zh"] == prediction.confidence)
        translation_failed = False
        translated = None
        if translate:
            try:
                translated = await self._translate_prediction(prediction)
            except LLMError:
                translation_failed = True
                logger.exception("Translation pass failed.")

        key_factors = []
        for index, factor in enumerate(prediction.keyFactors):
            factor_en = translated.keyFactorsEn[index] if translated and index < len(translated.keyFactorsEn) else factor
            key_factors.append(LocalizedFactor(zh=factor, en=factor_en))

        players = []
        for index, item in enumerate(prediction.playersToWatch):
            team = self.repository.team_by_zh(item.team)
            translated_player = translated.playersToWatchEn[index] if translated and index < len(translated.playersToWatchEn) else None
            players.append(
                PlayerToWatch(
                    teamSlug=team.slug,
                    playerZh=item.player,
                    playerEn=translated_player.playerEn if translated_player else team.primary_player_en,
                    reasonZh=item.reason,
                    reasonEn=translated_player.reasonEn if translated_player else item.reason,
                )
            )

        analysis = LocalizedAnalysis(
            zh=prediction.analysis,
            en=translated.analysisEn if translated else prediction.analysis,
        )
        if translation_failed:
            analysis = LocalizedAnalysis(zh=prediction.analysis, en=prediction.analysis)

        priors = TournamentPriorsPayload(
            source=prediction.tournamentPriors.source,
            sourceDate=prediction.tournamentPriors.sourceDate,
            teamA=self._prior_team(prediction.tournamentPriors.teamA),
            teamB=self._prior_team(prediction.tournamentPriors.teamB),
        )

        knockout = None
        if prediction.knockout:
            knockout = KnockoutAdvancePayload(
                note=prediction.knockout.note,
                advanceProb=prediction.knockout.advanceProb,
            )

        return PredictionPayload(
            teamA={"slug": team_a.slug, "nameZh": team_a.name_zh, "nameEn": team_a.name_en, "winProb": prediction.teamA.winProb},
            drawProb=prediction.draw,
            teamB={"slug": team_b.slug, "nameZh": team_b.name_zh, "nameEn": team_b.name_en, "winProb": prediction.teamB.winProb},
            predictedScore=prediction.predictedScore,
            confidence=confidence,
            keyFactors=key_factors,
            analysis=analysis,
            playersToWatch=players,
            engine=EngineDetails(**prediction.engine.model_dump()),
            dataQuality=DataQualityPayload(**prediction.dataQuality.model_dump()),
            tournamentPriors=priors,
            knockout=knockout,
            safeUse=prediction.safeUse,
            matchContext=match_context,
        )

    def _sanitize_prediction_placeholders(self, prediction: RawSkillPrediction, request: PredictRequest) -> RawSkillPrediction:
        team_a = self.repository.team_by_zh(prediction.teamA.name)
        team_b = self.repository.team_by_zh(prediction.teamB.name)
        sanitized = prediction.model_copy(deep=True)

        sanitized.keyFactors = [
            self._clean_factor(factor, team_a.name_zh, team_b.name_zh, index, request.stage)
            for index, factor in enumerate(sanitized.keyFactors)
        ]

        if self._looks_like_placeholder(sanitized.analysis):
            if request.stage == "group":
                sanitized.analysis = (
                    f"{team_a.name_zh} 在基础强度和比赛节奏上更占先手，比分更像朝着 {sanitized.predictedScore} 这一类走势收拢；"
                    f"{team_b.name_zh} 若想抢分，必须把有限的反击窗口打出更高质量的终结。"
                )[:150]
            else:
                sanitized.analysis = (
                    f"这会是一场更看细节执行的淘汰赛，90 分钟走势更接近 {sanitized.predictedScore}；"
                    f"如果比赛被拖进加时，双方核心球员的临门处理将决定晋级方向。"
                )[:150]

        fixed_players = []
        for item in sanitized.playersToWatch:
            team = self.repository.team_by_zh(item.team)
            player_name = item.player if not self._looks_like_placeholder(item.player) else team.primary_player_zh
            reason = item.reason
            if self._looks_like_placeholder(reason):
                if team.slug == team_a.slug:
                    reason = f"{player_name} 是 {team.name_zh} 最可能把优势转成进球的人。"
                else:
                    reason = f"{player_name} 的处理球质量会直接决定 {team.name_zh} 能不能把比赛拖住。"
            fixed_players.append(item.model_copy(update={"player": player_name, "reason": reason}))
        sanitized.playersToWatch = fixed_players
        return sanitized

    @staticmethod
    def _repair_live_payload(raw_result: dict) -> dict:
        repaired = deepcopy(raw_result)
        analysis = repaired.get("analysis")
        if isinstance(analysis, str):
            repaired["analysis"] = analysis.strip()[:150]
        factors = repaired.get("keyFactors")
        if isinstance(factors, list):
            trimmed = [str(item).strip()[:15] for item in factors if str(item).strip()]
            repaired["keyFactors"] = trimmed[:5] if trimmed else ["比赛节奏关键", "终结效率关键", "防线站位关键"]
            while len(repaired["keyFactors"]) < 3:
                repaired["keyFactors"].append(["比赛节奏关键", "终结效率关键", "防线站位关键"][len(repaired["keyFactors"])])
        players = repaired.get("playersToWatch")
        if isinstance(players, list):
            repaired_players = []
            for item in players[:2]:
                if not isinstance(item, dict):
                    continue
                player_item = dict(item)
                if isinstance(player_item.get("reason"), str):
                    player_item["reason"] = player_item["reason"].strip()[:80]
                repaired_players.append(player_item)
            repaired["playersToWatch"] = repaired_players
        return repaired

    @staticmethod
    def _looks_like_placeholder(value: str) -> bool:
        return "[LLM填写]" in value or value.startswith("[LLM填写")

    @staticmethod
    def _clean_factor(value: str, team_a_name: str, team_b_name: str, index: int, stage: str) -> str:
        if not PredictionService._looks_like_placeholder(value):
            return value
        group_defaults = [
            f"{team_a_name} 控球更稳",
            f"{team_b_name} 反击看效率",
            "开局节奏很关键",
            "定位球可能改命",
            "平局窗口仍存在",
        ]
        knockout_defaults = [
            f"{team_a_name} 经验更足",
            f"{team_b_name} 韧性不差",
            "淘汰赛容错更低",
            "加时可能介入",
            "细节处理定胜负",
        ]
        defaults = group_defaults if stage == "group" else knockout_defaults
        return defaults[min(index, len(defaults) - 1)]

    async def _translate_prediction(self, prediction: RawSkillPrediction) -> TranslationPayload:
        user_prompt = (
            "请把以下字段翻译成英文并返回 JSON：\n"
            f"keyFactors: {prediction.keyFactors}\n"
            f"analysis: {prediction.analysis}\n"
            f"playersToWatch: {[item.model_dump() for item in prediction.playersToWatch]}"
        )
        raw_translation = await self.llm_client.chat_json(
            TRANSLATION_PROMPT.strip(),
            user_prompt,
            model=self.settings.translation_model,
        )
        return TranslationPayload.model_validate(raw_translation)

    @staticmethod
    def _prior_team(payload) -> TournamentPriorTeam | None:
        if payload is None:
            return None
        return TournamentPriorTeam(**payload.model_dump())

    @staticmethod
    def _assert_immutable_engine_fields(original: RawSkillPrediction, candidate: RawSkillPrediction) -> None:
        original_fixed = {
            "teamA": original.teamA.model_dump(),
            "draw": original.draw,
            "teamB": original.teamB.model_dump(),
            "predictedScore": original.predictedScore,
            "engine": original.engine.model_dump(),
            "dataQuality": original.dataQuality.model_dump(),
            "tournamentPriors": original.tournamentPriors.model_dump(),
            "knockout": original.knockout.model_dump() if original.knockout else None,
            "stage": original.stage,
            "safeUse": original.safeUse,
        }
        candidate_fixed = {
            "teamA": candidate.teamA.model_dump(),
            "draw": candidate.draw,
            "teamB": candidate.teamB.model_dump(),
            "predictedScore": candidate.predictedScore,
            "engine": candidate.engine.model_dump(),
            "dataQuality": candidate.dataQuality.model_dump(),
            "tournamentPriors": candidate.tournamentPriors.model_dump(),
            "knockout": candidate.knockout.model_dump() if candidate.knockout else None,
            "stage": candidate.stage,
            "safeUse": candidate.safeUse,
        }
        if original_fixed != candidate_fixed:
            raise LLMError("Live model attempted to mutate immutable engine fields.")
