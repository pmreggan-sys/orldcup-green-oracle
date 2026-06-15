from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.schemas import (
    MatchScorePayload,
    ScheduleFixture,
    ScheduleSnapshot,
    ScoreSummary,
    StandingsGroup,
)


@pytest.fixture
def sample_snapshot(repository):
    mexico = repository.team_by_slug("mexico")
    south_africa = repository.team_by_slug("south-africa")
    france = repository.team_by_slug("france")
    england = repository.team_by_slug("england")
    return ScheduleSnapshot(
        source="football-data.org",
        competition="WC",
        fetchedAt=datetime(2026, 6, 13, 10, 0, tzinfo=UTC),
        dataFreshness="delayed_free_tier",
        dataDelayNoteZh="免费层可能延迟。",
        dataDelayNoteEn="Free tier may be delayed.",
        fixtures=[
            ScheduleFixture(
                fixtureId="fd-1",
                providerMatchId=1,
                stage="group",
                stageLabelZh="小组赛",
                stageLabelEn="Group Stage",
                status="scheduled",
                kickoffAt=datetime(2026, 6, 13, 12, 0, tzinfo=UTC),
                teamA=mexico,
                teamB=south_africa,
                score=None,
                venueZh="墨西哥城",
                venueEn="Mexico City",
                group="GROUP_A",
                predictionAvailable=True,
                knockout=False,
                homeSide="A",
                featured=True,
            ),
            ScheduleFixture(
                fixtureId="fd-2",
                providerMatchId=2,
                stage="round_of_16",
                stageLabelZh="16 强",
                stageLabelEn="Round of 16",
                status="scheduled",
                kickoffAt=datetime(2026, 6, 30, 18, 0, tzinfo=UTC),
                teamA=france,
                teamB=england,
                score=None,
                venueZh="纽约",
                venueEn="New York",
                group=None,
                predictionAvailable=True,
                knockout=True,
                homeSide=None,
                featured=True,
            ),
            ScheduleFixture(
                fixtureId="fd-3",
                providerMatchId=3,
                stage="group",
                stageLabelZh="小组赛",
                stageLabelEn="Group Stage",
                status="finished",
                kickoffAt=datetime(2026, 6, 12, 18, 0, tzinfo=UTC),
                teamA=repository.team_by_slug("canada"),
                teamB=repository.team_by_slug("bosnia-and-herzegovina"),
                score=MatchScorePayload(fullTime=ScoreSummary(home=2, away=1)),
                venueZh="多伦多",
                venueEn="Toronto",
                group="GROUP_B",
                predictionAvailable=True,
                knockout=False,
                homeSide="A",
                featured=False,
            ),
        ],
        standings=[
            StandingsGroup(
                group="A",
                rows=[],
            )
        ],
    )


@pytest.fixture
def repository():
    from app.repository import TournamentRepository

    return TournamentRepository()
