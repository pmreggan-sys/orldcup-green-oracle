from app.config import Settings
from app.repository import TournamentRepository
from app.services.schedule_provider import FootballDataProvider


def test_provider_maps_round_of_32_and_skips_third_place():
    provider = FootballDataProvider(settings=Settings(), repository=TournamentRepository())
    assert provider._map_stage("LAST_32") == "round_of_32"
    assert provider._map_stage("ROUND_OF_16") == "round_of_16"
    assert provider._map_stage("THIRD_PLACE") is None


def test_provider_resolves_home_side_by_host_country():
    provider = FootballDataProvider(settings=Settings(), repository=TournamentRepository())
    assert provider._resolve_home_side("mexico", "south-africa", "Mexico City") == "A"
    assert provider._resolve_home_side("south-africa", "mexico", "Mexico City") == "B"
    assert provider._resolve_home_side("france", "england", "New York") is None
