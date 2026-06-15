from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

StageSlug = Literal["group", "round_of_32", "round_of_16", "quarterfinal", "semifinal", "final"]
LangCode = Literal["zh", "en"]
ConfidenceValue = Literal["high", "medium", "low"]
FixtureStatus = Literal["scheduled", "in_progress", "finished"]
HomeSide = Literal["A", "B"]


class PredictRequest(BaseModel):
    teamA: str
    teamB: str
    stage: StageSlug
    lang: LangCode = "zh"
    fixtureId: str | None = None

    @model_validator(mode="after")
    def validate_teams(self) -> "PredictRequest":
        if self.teamA == self.teamB:
            raise ValueError("teamA and teamB must be different.")
        return self


class RawTeamProbability(BaseModel):
    name: str
    winProb: int = Field(ge=0, le=98)


class RawPlayerToWatch(BaseModel):
    team: str
    player: str
    reason: str


class RawEngineModel(BaseModel):
    model: str
    ratings: dict[str, int]
    lambda90: dict[str, float]
    rho: float
    homeAdv: str | None = None
    capApplied: int


class RawDataQuality(BaseModel):
    level: str
    sourcesUsed: list[str]
    notes: str


class RawTournamentPriorTeam(BaseModel):
    titleProb: float | None = None
    titleCI: list[float] | None = None
    semiProb: float | None = None
    semiCI: list[float] | None = None
    confederation: str | None = None


class RawTournamentPriors(BaseModel):
    source: str | None = None
    sourceDate: str | None = None
    teamA: RawTournamentPriorTeam | None = None
    teamB: RawTournamentPriorTeam | None = None


class RawKnockoutPayload(BaseModel):
    note: str
    advanceProb: dict[str, int]


class RawSkillPrediction(BaseModel):
    teamA: RawTeamProbability
    draw: int = Field(ge=0, le=98)
    teamB: RawTeamProbability
    predictedScore: str
    confidence: Literal["高", "中", "低"]
    keyFactors: list[str] = Field(min_length=3, max_length=5)
    analysis: str = Field(min_length=1, max_length=150)
    playersToWatch: list[RawPlayerToWatch] = Field(min_length=2, max_length=2)
    engine: RawEngineModel
    dataQuality: RawDataQuality
    tournamentPriors: RawTournamentPriors
    safeUse: str
    stage: str | None = None
    mode: str | None = None
    knockout: RawKnockoutPayload | None = None
    currentState: dict[str, Any] | None = None

    @field_validator("predictedScore")
    @classmethod
    def validate_score(cls, value: str) -> str:
        left, sep, right = value.partition("-")
        if not sep or not left.isdigit() or not right.isdigit():
            raise ValueError("predictedScore must look like 2-1.")
        return value

    @model_validator(mode="after")
    def validate_total(self) -> "RawSkillPrediction":
        total = self.teamA.winProb + self.draw + self.teamB.winProb
        if total != 100:
            raise ValueError("Probabilities must sum to 100.")
        return self


class TranslationChunk(BaseModel):
    playerEn: str
    reasonEn: str


class TranslationPayload(BaseModel):
    keyFactorsEn: list[str]
    analysisEn: str
    playersToWatchEn: list[TranslationChunk]

    @field_validator("keyFactorsEn")
    @classmethod
    def validate_factors(cls, value: list[str]) -> list[str]:
        if not 3 <= len(value) <= 5:
            raise ValueError("Translated key factors must include 3 to 5 items.")
        return value


class TeamProfile(BaseModel):
    slug: str
    name_zh: str
    name_en: str
    fifa_code: str
    group: str
    tier_zh: str
    tier_en: str
    rating: int
    host: bool
    newcomer: bool
    primary_player_zh: str
    primary_player_en: str


class LocalizedFactor(BaseModel):
    zh: str
    en: str


class LocalizedAnalysis(BaseModel):
    zh: str
    en: str


class NormalizedTeamOutcome(BaseModel):
    slug: str
    nameZh: str
    nameEn: str
    winProb: int = Field(ge=0, le=98)


class PlayerToWatch(BaseModel):
    teamSlug: str
    playerZh: str
    playerEn: str
    reasonZh: str
    reasonEn: str


class EngineDetails(BaseModel):
    model: str
    ratings: dict[str, int]
    lambda90: dict[str, float]
    rho: float
    homeAdv: str | None = None
    capApplied: int


class DataQualityPayload(BaseModel):
    level: str
    sourcesUsed: list[str]
    notes: str


class TournamentPriorTeam(BaseModel):
    titleProb: float | None = None
    titleCI: list[float] | None = None
    semiProb: float | None = None
    semiCI: list[float] | None = None
    confederation: str | None = None


class TournamentPriorsPayload(BaseModel):
    source: str | None = None
    sourceDate: str | None = None
    teamA: TournamentPriorTeam | None = None
    teamB: TournamentPriorTeam | None = None


class KnockoutAdvancePayload(BaseModel):
    note: str
    advanceProb: dict[str, int]


class MatchContextPayload(BaseModel):
    fixtureId: str | None = None
    stage: StageSlug
    stageLabelZh: str
    stageLabelEn: str
    status: FixtureStatus = "scheduled"
    kickoffAt: datetime | None = None
    venueZh: str | None = None
    venueEn: str | None = None
    homeSide: HomeSide | None = None
    sourceUpdatedAt: datetime | None = None
    dataDelayNoteZh: str | None = None
    dataDelayNoteEn: str | None = None


class PredictionPayload(BaseModel):
    teamA: NormalizedTeamOutcome
    drawProb: int = Field(ge=0, le=98)
    teamB: NormalizedTeamOutcome
    predictedScore: str
    confidence: ConfidenceValue
    keyFactors: list[LocalizedFactor]
    analysis: LocalizedAnalysis
    playersToWatch: list[PlayerToWatch]
    engine: EngineDetails | None = None
    dataQuality: DataQualityPayload | None = None
    tournamentPriors: TournamentPriorsPayload | None = None
    knockout: KnockoutAdvancePayload | None = None
    safeUse: str | None = None
    matchContext: MatchContextPayload | None = None

    @model_validator(mode="after")
    def validate_total(self) -> "PredictionPayload":
        total = self.teamA.winProb + self.drawProb + self.teamB.winProb
        if total != 100:
            raise ValueError("Normalized probabilities must sum to 100.")
        return self


class SourceInfo(BaseModel):
    provider: str
    model: str


class NoticePayload(BaseModel):
    zh: str
    en: str


class PredictionResponse(BaseModel):
    mode: Literal["live", "engine", "fallback"]
    source: SourceInfo
    generatedAt: datetime
    request: PredictRequest
    prediction: PredictionPayload
    notice: NoticePayload


class ScoreSummary(BaseModel):
    home: int | None = None
    away: int | None = None


class MatchScorePayload(BaseModel):
    fullTime: ScoreSummary | None = None


class ScheduleFixture(BaseModel):
    fixtureId: str
    providerMatchId: int
    stage: StageSlug
    stageLabelZh: str
    stageLabelEn: str
    status: FixtureStatus
    kickoffAt: datetime | None = None
    teamA: TeamProfile
    teamB: TeamProfile
    score: MatchScorePayload | None = None
    venueZh: str | None = None
    venueEn: str | None = None
    group: str | None = None
    predictionAvailable: bool = True
    knockout: bool = False
    homeSide: HomeSide | None = None
    featured: bool = False


class StandingsRow(BaseModel):
    position: int
    team: TeamProfile
    points: int
    playedGames: int
    goalDifference: int
    goalsFor: int
    goalsAgainst: int


class StandingsGroup(BaseModel):
    group: str
    rows: list[StandingsRow]


class ScheduleSnapshot(BaseModel):
    source: str
    competition: str
    fetchedAt: datetime
    dataFreshness: str
    dataDelayNoteZh: str
    dataDelayNoteEn: str
    fixtures: list[ScheduleFixture]
    standings: list[StandingsGroup]


class ScheduleResponse(BaseModel):
    snapshot: ScheduleSnapshot


class SyncResponse(BaseModel):
    status: Literal["ok"]
    updatedAt: datetime
    source: str
    fixtureCount: int
    standingsCount: int
