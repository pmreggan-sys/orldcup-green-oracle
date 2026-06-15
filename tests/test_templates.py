from fastapi.testclient import TestClient

from app.main import app, get_schedule_service


client = TestClient(app)


class StubScheduleService:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def load_snapshot(self):
        return self.snapshot

    async def load_or_sync(self):
        return self.snapshot

    def homepage_fixtures(self, snapshot):
        return {"live_upcoming": snapshot.fixtures[:1], "knockout": snapshot.fixtures[1:2], "recent": snapshot.fixtures[2:], "featured": snapshot.fixtures[:2]}

    def summary_bullets(self, snapshot, lang):
        return ["stub summary"]

    def resolve_match_context(self, request, snapshot):
        return None


def test_homepage_renders_chinese(sample_snapshot):
    app.dependency_overrides[get_schedule_service] = lambda: StubScheduleService(sample_snapshot)
    try:
        response = client.get("/")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "绿茵神算 2026" in response.text
    assert "赛程主屏" in response.text
    assert "已确认淘汰赛" in response.text


def test_homepage_renders_english(sample_snapshot):
    app.dependency_overrides[get_schedule_service] = lambda: StubScheduleService(sample_snapshot)
    try:
        response = client.get("/en")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "Green Pitch Oracle 2026" in response.text
    assert "Fixture Board" in response.text
    assert "Confirmed Knockout Ties" in response.text
