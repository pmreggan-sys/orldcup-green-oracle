from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.config import Settings
from app.data.catalog import HOST_CITY_CODES, HOST_CITY_LOCALIZED, HOST_COUNTRY_BY_SLUG
from app.i18n import STAGE_LABELS
from app.repository import TournamentRepository
from app.schemas import (
    FixtureStatus,
    HomeSide,
    MatchScorePayload,
    ScheduleFixture,
    ScheduleSnapshot,
    ScoreSummary,
    StandingsGroup,
    StandingsRow,
)

FREE_DATA_DELAY_NOTE_ZH = "当前赛程与比分来自 football-data.org 免费层，可能存在延迟；淘汰赛对阵以官方发布后同步到站点为准。"
FREE_DATA_DELAY_NOTE_EN = "Schedule and score data currently come from football-data.org's free tier and may be delayed; knockout pairings appear after the provider publishes them."

MATCH_STAGE_MAP = {
    "GROUP_STAGE": "group",
    "LAST_32": "round_of_32",
    "ROUND_OF_32": "round_of_32",
    "LAST_16": "round_of_16",
    "ROUND_OF_16": "round_of_16",
    "QUARTER_FINALS": "quarterfinal",
    "QUARTER_FINAL": "quarterfinal",
    "SEMI_FINALS": "semifinal",
    "SEMI_FINAL": "semifinal",
    "FINAL": "final",
}

STATUS_MAP: dict[str, FixtureStatus] = {
    "TIMED": "scheduled",
    "SCHEDULED": "scheduled",
    "LIVE": "in_progress",
    "IN_PLAY": "in_progress",
    "PAUSED": "in_progress",
    "FINISHED": "finished",
}


@dataclass(slots=True)
class FootballDataProvider:
    settings: Settings
    repository: TournamentRepository

    async def fetch_schedule_snapshot(self) -> ScheduleSnapshot:
        matches_payload, standings_payload = await self._fetch_provider_data()
        fixtures = self._normalize_fixtures(matches_payload.get("matches", []))
        standings = self._normalize_standings(standings_payload.get("standings", []))
        fetched_at = datetime.now(UTC)
        return ScheduleSnapshot(
            source="football-data.org",
            competition=self.settings.football_data_competition_code,
            fetchedAt=fetched_at,
            dataFreshness="delayed_free_tier",
            dataDelayNoteZh=FREE_DATA_DELAY_NOTE_ZH,
            dataDelayNoteEn=FREE_DATA_DELAY_NOTE_EN,
            fixtures=fixtures,
            standings=standings,
        )

    async def _fetch_provider_data(self) -> tuple[dict, dict]:
        headers = {"X-Auth-Token": self.settings.football_data_api_key} if self.settings.football_data_api_key else {}
        timeout = httpx.Timeout(self.settings.request_timeout_s)
        async with httpx.AsyncClient(timeout=timeout) as client:
            matches = await client.get(
                f"{self.settings.football_data_base_url.rstrip('/')}/competitions/{self.settings.football_data_competition_code}/matches",
                headers=headers,
            )
            standings = await client.get(
                f"{self.settings.football_data_base_url.rstrip('/')}/competitions/{self.settings.football_data_competition_code}/standings",
                headers=headers,
            )
        matches.raise_for_status()
        standings.raise_for_status()
        return matches.json(), standings.json()

    def _normalize_fixtures(self, items: list[dict]) -> list[ScheduleFixture]:
        fixtures: list[ScheduleFixture] = []
        for item in items:
            stage = self._map_stage(item.get("stage"))
            if not stage:
                continue
            home_team = item.get("homeTeam") or {}
            away_team = item.get("awayTeam") or {}
            home_name = home_team.get("name") or home_team.get("shortName")
            away_name = away_team.get("name") or away_team.get("shortName")
            if not home_name or not away_name:
                continue
            try:
                team_a = self.repository.resolve_team(
                    name=home_name,
                    code=home_team.get("tla"),
                )
                team_b = self.repository.resolve_team(
                    name=away_name,
                    code=away_team.get("tla"),
                )
            except KeyError:
                continue
            venue_en = item.get("venue")
            venue_zh = HOST_CITY_LOCALIZED.get(venue_en, {}).get("zh") if venue_en else None
            venue_en = HOST_CITY_LOCALIZED.get(venue_en, {}).get("en", venue_en) if venue_en else None
            status = STATUS_MAP.get(item.get("status", ""), "scheduled")
            group = item.get("group")
            home_side = self._resolve_home_side(team_a.slug, team_b.slug, venue_en)
            fixtures.append(
                ScheduleFixture(
                    fixtureId=f"fd-{item['id']}",
                    providerMatchId=item["id"],
                    stage=stage,
                    stageLabelZh=STAGE_LABELS[stage]["zh"],
                    stageLabelEn=STAGE_LABELS[stage]["en"],
                    status=status,
                    kickoffAt=self._parse_datetime(item.get("utcDate")),
                    teamA=team_a,
                    teamB=team_b,
                    score=self._score_payload(item.get("score")),
                    venueZh=venue_zh,
                    venueEn=venue_en,
                    group=group,
                    predictionAvailable=status in {"scheduled", "in_progress", "finished"},
                    knockout=stage != "group",
                    homeSide=home_side,
                    featured=team_a.slug in self.repository.featured_team_slugs(),
                )
            )
        fixtures.sort(key=lambda fixture: ((fixture.kickoffAt or datetime.max.replace(tzinfo=UTC)), fixture.providerMatchId))
        return fixtures

    def _normalize_standings(self, items: list[dict]) -> list[StandingsGroup]:
        groups: list[StandingsGroup] = []
        for block in items:
            if block.get("type") != "TOTAL":
                continue
            group_name = block.get("group")
            if not group_name:
                continue
            rows: list[StandingsRow] = []
            for row in block.get("table", []):
                try:
                    team = self.repository.resolve_team(
                        name=row.get("team", {}).get("name") or row.get("team", {}).get("shortName"),
                        code=row.get("team", {}).get("tla"),
                    )
                except KeyError:
                    continue
                rows.append(
                    StandingsRow(
                        position=row["position"],
                        team=team,
                        points=row["points"],
                        playedGames=row["playedGames"],
                        goalDifference=row["goalDifference"],
                        goalsFor=row["goalsFor"],
                        goalsAgainst=row["goalsAgainst"],
                    )
                )
            groups.append(StandingsGroup(group=group_name.split(" ")[-1], rows=rows))
        groups.sort(key=lambda group: group.group)
        return groups

    @staticmethod
    def _map_stage(stage: str | None) -> str | None:
        if not stage:
            return None
        if stage == "THIRD_PLACE":
            return None
        return MATCH_STAGE_MAP.get(stage)

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    def _score_payload(score: dict | None) -> MatchScorePayload | None:
        if not score:
            return None
        full_time = score.get("fullTime") or {}
        if full_time.get("home") is None and full_time.get("away") is None:
            return None
        return MatchScorePayload(
            fullTime=ScoreSummary(
                home=full_time.get("home"),
                away=full_time.get("away"),
            )
        )

    def _resolve_home_side(self, team_a_slug: str, team_b_slug: str, venue_en: str | None) -> HomeSide | None:
        if not venue_en:
            return None
        host_country = HOST_CITY_CODES.get(venue_en)
        if not host_country:
            return None
        if HOST_COUNTRY_BY_SLUG.get(team_a_slug) == host_country:
            return "A"
        if HOST_COUNTRY_BY_SLUG.get(team_b_slug) == host_country:
            return "B"
        return None
