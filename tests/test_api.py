from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app, get_schedule_service
from app.schemas import ScheduleSnapshot


client = TestClient(app)


class StubScheduleService:
    def __init__(self, snapshot: ScheduleSnapshot):
        self.snapshot = snapshot

    def load_snapshot(self) -> ScheduleSnapshot:
        return self.snapshot

    async def load_or_sync(self) -> ScheduleSnapshot:
        return self.snapshot

    async def sync(self) -> ScheduleSnapshot:
        return self.snapshot

    def homepage_fixtures(self, snapshot: ScheduleSnapshot):
        return {"live_upcoming": snapshot.fixtures[:1], "knockout": snapshot.fixtures[1:2], "recent": snapshot.fixtures[2:], "featured": snapshot.fixtures[:2]}

    def summary_bullets(self, snapshot: ScheduleSnapshot, lang: str):
        return ["stub bullet"]

    def resolve_match_context(self, request, snapshot):
        fixture = next((item for item in snapshot.fixtures if item.teamA.slug == request.teamA and item.teamB.slug == request.teamB), None)
        if not fixture:
            return None
        from app.schemas import MatchContextPayload

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


def test_api_predict_engine_response(sample_snapshot):
    app.dependency_overrides[get_schedule_service] = lambda: StubScheduleService(sample_snapshot)
    try:
        response = client.post(
            "/api/predict",
            json={"teamA": "mexico", "teamB": "south-africa", "stage": "group", "lang": "zh"},
            headers={"x-forwarded-for": "198.51.100.10"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] in {"engine", "live"}
    assert data["prediction"]["teamA"]["slug"] == "mexico"
    assert data["prediction"]["engine"]["model"] == "elo-dixon-coles-poisson v1"
    assert data["prediction"]["teamA"]["winProb"] + data["prediction"]["drawProb"] + data["prediction"]["teamB"]["winProb"] == 100


def test_schedule_api_returns_snapshot(sample_snapshot):
    app.dependency_overrides[get_schedule_service] = lambda: StubScheduleService(sample_snapshot)
    try:
        response = client.get("/api/schedule")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["snapshot"]["source"] == "football-data.org"
    assert len(data["snapshot"]["fixtures"]) == 3


def test_internal_sync_requires_token(sample_snapshot):
    app.dependency_overrides[get_schedule_service] = lambda: StubScheduleService(sample_snapshot)
    try:
        response = client.post("/internal/sync")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_internal_sync_accepts_token(sample_snapshot):
    settings = get_settings()
    app.dependency_overrides[get_schedule_service] = lambda: StubScheduleService(sample_snapshot)
    try:
        response = client.post("/internal/sync", headers={"x-internal-sync-token": settings.internal_sync_token})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_rejects_duplicate_teams():
    response = client.post(
        "/api/predict",
        json={"teamA": "mexico", "teamB": "mexico", "stage": "group", "lang": "zh"},
        headers={"x-forwarded-for": "198.51.100.11"},
    )
    assert response.status_code == 422


def test_api_rate_limit_response(sample_snapshot):
    settings = get_settings()
    app.dependency_overrides[get_schedule_service] = lambda: StubScheduleService(sample_snapshot)
    headers = {"x-forwarded-for": "198.51.100.12"}
    try:
        for _ in range(settings.rate_limit_per_minute):
            response = client.post(
                "/api/predict",
                json={"teamA": "mexico", "teamB": "south-africa", "stage": "group", "lang": "zh"},
                headers=headers,
            )
            assert response.status_code == 200
        limited = client.post(
            "/api/predict",
            json={"teamA": "mexico", "teamB": "south-africa", "stage": "group", "lang": "zh"},
            headers=headers,
        )
    finally:
        app.dependency_overrides.clear()
    assert limited.status_code == 429
