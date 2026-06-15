from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from app.data.catalog import DEFAULT_FEATURED_TEAM_SLUGS, HOST_TEAMS, TEAM_SUPPLEMENT
from app.i18n import TIER_LABELS
from app.schemas import ScheduleFixture, ScheduleSnapshot, StandingsGroup, TeamProfile


class TournamentRepository:
    def __init__(self, base_path: Path | None = None) -> None:
        self.base_path = base_path or Path(__file__).resolve().parent
        ratings_path = self.base_path / "data" / "ratings.json"
        ratings_data = json.loads(ratings_path.read_text(encoding="utf-8"))["teams"]
        self._teams_by_zh: dict[str, TeamProfile] = {}
        self._teams_by_slug: dict[str, TeamProfile] = {}
        self._teams_by_alias: dict[str, TeamProfile] = {}
        self._teams_by_code: dict[str, TeamProfile] = {}

        for name_zh, info in ratings_data.items():
            supplement = TEAM_SUPPLEMENT[name_zh]
            alias_source = info.get("aliases", [])
            fifa_code = next(
                (alias for alias in alias_source if len(alias) == 3 and alias.isupper()),
                supplement.slug[:3].upper(),
            )
            team = TeamProfile(
                slug=supplement.slug,
                name_zh=name_zh,
                name_en=supplement.name_en,
                fifa_code=fifa_code,
                group=info["group"],
                tier_zh=info["tier"],
                tier_en=TIER_LABELS[info["tier"]]["en"],
                rating=info["rating"],
                host=name_zh in HOST_TEAMS,
                newcomer=supplement.newcomer,
                primary_player_zh=supplement.primary_player_zh,
                primary_player_en=supplement.primary_player_en,
            )
            self._teams_by_zh[name_zh] = team
            self._teams_by_slug[team.slug] = team
            self._teams_by_code[team.fifa_code.upper()] = team

            aliases = set(alias_source) | set(supplement.provider_aliases) | {supplement.name_en, name_zh}
            for alias in aliases:
                self._teams_by_alias[self._normalize_alias(alias)] = team

    def all_teams(self) -> list[TeamProfile]:
        return sorted(self._teams_by_zh.values(), key=lambda team: (team.group, team.rating * -1, team.name_en))

    def team_by_slug(self, slug: str) -> TeamProfile:
        return self._teams_by_slug[slug]

    def team_by_zh(self, name_zh: str) -> TeamProfile:
        return self._teams_by_zh[name_zh]

    def team_by_code(self, code: str) -> TeamProfile | None:
        return self._teams_by_code.get(code.upper())

    def resolve_team(self, *, name: str | None = None, code: str | None = None) -> TeamProfile:
        if code:
            team = self.team_by_code(code)
            if team:
                return team
        if not name:
            raise KeyError("Either team name or FIFA code is required.")
        normalized = self._normalize_alias(name)
        if normalized in self._teams_by_alias:
            return self._teams_by_alias[normalized]
        raise KeyError(f"Unknown team alias: {name}")

    def group_tables(self) -> list[dict[str, object]]:
        grouped: dict[str, list[TeamProfile]] = defaultdict(list)
        for team in self.all_teams():
            grouped[team.group].append(team)
        return [{"group": group, "teams": grouped[group]} for group in sorted(grouped)]

    def standings_or_groups(self, snapshot: ScheduleSnapshot | None) -> list[StandingsGroup | dict[str, object]]:
        if snapshot and snapshot.standings:
            return snapshot.standings
        return self.group_tables()

    def options(self) -> list[dict[str, str]]:
        return [
            {"slug": team.slug, "name_zh": team.name_zh, "name_en": team.name_en, "group": team.group}
            for team in self.all_teams()
        ]

    def featured_team_slugs(self) -> tuple[str, ...]:
        return DEFAULT_FEATURED_TEAM_SLUGS

    def featured_fixtures(self, snapshot: ScheduleSnapshot | None) -> list[ScheduleFixture]:
        if not snapshot:
            return []
        featured = [fixture for fixture in snapshot.fixtures if fixture.teamA.slug in self.featured_team_slugs()]
        featured.sort(key=lambda fixture: (fixture.kickoffAt or 0, fixture.providerMatchId))
        return featured[:8]

    @staticmethod
    def _normalize_alias(value: str) -> str:
        return value.strip().lower().replace(".", "").replace("’", "'")
