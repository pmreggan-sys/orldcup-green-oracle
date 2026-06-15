from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import datetime as dt

from app.data.catalog import OFFLINE_PREVIEW_FIXTURES
from app.time_utils import format_beijing
from app.repository import TournamentRepository
from app.schemas import MatchContextPayload, MatchScorePayload, PredictRequest, ScheduleFixture, ScheduleSnapshot, ScoreSummary, StandingsGroup
from app.services.schedule_provider import FREE_DATA_DELAY_NOTE_EN, FREE_DATA_DELAY_NOTE_ZH, FootballDataProvider
from app.services.schedule_store import ScheduleStore
from app.i18n import STAGE_LABELS

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ScheduleService:
    repository: TournamentRepository
    provider: FootballDataProvider
    store: ScheduleStore

    def load_snapshot(self) -> ScheduleSnapshot:
        cached = self.store.load()
        if cached:
            return cached
        return self.empty_snapshot()

    async def sync(self) -> ScheduleSnapshot:
        snapshot = await self.provider.fetch_schedule_snapshot()
        self.store.save(snapshot)
        return snapshot

    async def load_or_sync(self) -> ScheduleSnapshot:
        cached = self.store.load()
        if cached:
            return cached
        try:
            return await self.sync()
        except Exception:  # noqa: BLE001
            logger.exception("Initial schedule sync failed; using empty snapshot.")
            return self.empty_snapshot()

    def empty_snapshot(self) -> ScheduleSnapshot:
        now = datetime.now(UTC)
        fixtures = [self._preview_fixture(item) for item in OFFLINE_PREVIEW_FIXTURES]
        return ScheduleSnapshot(
            source="football-data.org",
            competition="WC",
            fetchedAt=now,
            dataFreshness="offline_preview",
            dataDelayNoteZh="当前未接入实时赛程 API，首页先展示站内离线预览赛程以便浏览和试跑预测。",
            dataDelayNoteEn="A live schedule API is not connected yet, so the homepage is showing a built-in offline preview slate for browsing and prediction testing.",
            fixtures=fixtures,
            standings=[],
        )

    def homepage_fixtures(self, snapshot: ScheduleSnapshot) -> dict[str, list[ScheduleFixture]]:
        live_or_upcoming = [fixture for fixture in snapshot.fixtures if fixture.status in {"scheduled", "in_progress"} and not fixture.knockout]
        knockout = [fixture for fixture in snapshot.fixtures if fixture.knockout and fixture.predictionAvailable]
        recent = [fixture for fixture in snapshot.fixtures if fixture.status == "finished"][-6:]
        featured = self.repository.featured_fixtures(snapshot)
        return {
            "live_upcoming": live_or_upcoming[:12],
            "knockout": knockout[:12],
            "recent": list(reversed(recent)),
            "featured": featured,
        }

    def summary_bullets(self, snapshot: ScheduleSnapshot, lang: str) -> list[str]:
        live = [fixture for fixture in snapshot.fixtures if fixture.status == "in_progress"]
        upcoming = [fixture for fixture in snapshot.fixtures if fixture.status == "scheduled"]
        knockout = [fixture for fixture in snapshot.fixtures if fixture.knockout and fixture.predictionAvailable]
        bullets: list[str] = []
        if lang == "zh":
            bullets.append(f"当前首页可用比赛 {len(snapshot.fixtures)} 场，数据源更新时间 {format_beijing(snapshot.fetchedAt, '%Y-%m-%d %H:%M')} 北京时间。")
            if live:
                bullets.append(f"进行中比赛 {len(live)} 场，首页优先显示实时或即将开球对阵。")
            elif upcoming:
                first = upcoming[0]
                bullets.append(f"下一场重点对阵：{first.teamA.name_zh} vs {first.teamB.name_zh}，阶段为 {first.stageLabelZh}。")
            if knockout:
                bullets.append(f"已确认淘汰赛对阵 {len(knockout)} 场，预测会同时展示 90 分钟结果与晋级倾向。")
            bullets.append(snapshot.dataDelayNoteZh)
            return bullets[:4]

        bullets.append(f"{len(snapshot.fixtures)} World Cup fixtures are currently available on the homepage, last refreshed at {format_beijing(snapshot.fetchedAt, '%Y-%m-%d %H:%M')} Beijing time.")
        if live:
            bullets.append(f"{len(live)} matches are in progress and appear at the top of the schedule board.")
        elif upcoming:
            first = upcoming[0]
            bullets.append(f"Next highlighted fixture: {first.teamA.nameEn} vs {first.teamB.nameEn} in the {first.stageLabelEn}.")
        if knockout:
            bullets.append(f"{len(knockout)} confirmed knockout fixtures already expose both 90-minute odds and advance probability.")
        bullets.append(snapshot.dataDelayNoteEn)
        return bullets[:4]

    def resolve_match_context(self, request: PredictRequest, snapshot: ScheduleSnapshot) -> MatchContextPayload | None:
        fixture = None
        if request.fixtureId:
            fixture = next((item for item in snapshot.fixtures if item.fixtureId == request.fixtureId), None)
        if fixture is None:
            fixture = next(
                (
                    item
                    for item in snapshot.fixtures
                    if item.teamA.slug == request.teamA and item.teamB.slug == request.teamB and item.stage == request.stage
                ),
                None,
            )
        if fixture is None:
            return None
        return MatchContextPayload(
            fixtureId=fixture.fixtureId,
            stage=fixture.stage,
            stageLabelZh=fixture.stageLabelZh,
            stageLabelEn=fixture.stageLabelEn,
            status=fixture.status,
            kickoffAt=fixture.kickoffAt,
            venueZh=fixture.venueZh,
            venueEn=fixture.venueEn,
            homeSide=fixture.homeSide,
            sourceUpdatedAt=snapshot.fetchedAt,
            dataDelayNoteZh=snapshot.dataDelayNoteZh,
            dataDelayNoteEn=snapshot.dataDelayNoteEn,
        )

    def _preview_fixture(self, item: dict) -> ScheduleFixture:
        team_a = self.repository.team_by_slug(item["team_a"])
        team_b = self.repository.team_by_slug(item["team_b"])
        score = None
        if item.get("score_home") is not None and item.get("score_away") is not None:
            score = MatchScorePayload(
                fullTime=ScoreSummary(home=item["score_home"], away=item["score_away"])
            )
        return ScheduleFixture(
            fixtureId=item["fixture_id"],
            providerMatchId=item["provider_match_id"],
            stage=item["stage"],
            stageLabelZh=STAGE_LABELS[item["stage"]]["zh"],
            stageLabelEn=STAGE_LABELS[item["stage"]]["en"],
            status=item["status"],
            kickoffAt=dt.fromisoformat(item["kickoff"]),
            teamA=team_a,
            teamB=team_b,
            score=score,
            venueZh=item["venue_zh"],
            venueEn=item["venue_en"],
            group=item["group"],
            predictionAvailable=True,
            knockout=item["stage"] != "group",
            homeSide=item["home_side"],
            featured=item["featured"],
        )
