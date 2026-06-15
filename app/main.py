from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import Settings, get_settings
from app.i18n import CONFIDENCE_LABELS, LANGUAGE_TEXT, STAGE_LABELS, TIER_LABELS
from app.logging_utils import configure_logging
from app.repository import TournamentRepository
from app.schemas import PredictRequest, ScheduleResponse, SyncResponse
from app.time_utils import format_beijing
from app.services.fallback import FallbackEngine
from app.services.green_oracle_engine import GreenOracleEngine
from app.services.llm_client import OpenAICompatibleClient
from app.services.prediction_service import PredictionService
from app.services.prompt_builder import PromptBuilder
from app.services.rate_limit import InMemoryRateLimiter
from app.services.schedule_provider import FootballDataProvider
from app.services.schedule_service import ScheduleService
from app.services.schedule_store import ScheduleStore

configure_logging()
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Green Oracle 2026")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

repository = TournamentRepository(BASE_DIR / "app")


def get_rate_limiter(settings: Settings = Depends(get_settings)) -> InMemoryRateLimiter:
    return InMemoryRateLimiter(limit_per_minute=settings.rate_limit_per_minute)


rate_limiter = get_rate_limiter(get_settings())


def get_schedule_service(settings: Settings = Depends(get_settings)) -> ScheduleService:
    return ScheduleService(
        repository=repository,
        provider=FootballDataProvider(settings=settings, repository=repository),
        store=ScheduleStore(settings.schedule_cache_file),
    )


def get_prediction_service(
    settings: Settings = Depends(get_settings),
    schedule_service: ScheduleService = Depends(get_schedule_service),
) -> PredictionService:
    return PredictionService(
        settings=settings,
        repository=repository,
        prompt_builder=PromptBuilder(skill_path=BASE_DIR / "worldcup2026-green-oracle" / "SKILL.md"),
        fallback_engine=FallbackEngine(repository=repository),
        llm_client=OpenAICompatibleClient(settings=settings),
        green_oracle_engine=GreenOracleEngine(repository=repository, workspace_root=BASE_DIR),
        schedule_service=schedule_service,
    )


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "anonymous"


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "request_complete",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "client_ip": _client_ip(request),
        },
    )
    return response


def _fixture_view(fixture, lang: str) -> dict:
    return {
        "fixture_id": fixture.fixtureId,
        "kickoff": fixture.kickoffAt,
        "kickoff_display": format_beijing(fixture.kickoffAt),
        "stage": fixture.stage,
        "stage_label": fixture.stageLabelZh if lang == "zh" else fixture.stageLabelEn,
        "status": fixture.status,
        "status_label": LANGUAGE_TEXT[lang]["status_labels"][fixture.status],
        "team_a": fixture.teamA,
        "team_b": fixture.teamB,
        "venue": fixture.venueZh if lang == "zh" else fixture.venueEn,
        "score": fixture.score,
        "group": fixture.group,
        "prediction_available": fixture.predictionAvailable,
        "knockout": fixture.knockout,
        "featured": fixture.featured,
    }


def _language_context(lang: str, schedule_service: ScheduleService) -> dict:
    text = LANGUAGE_TEXT[lang]
    snapshot = schedule_service.load_snapshot()
    fixtures = schedule_service.homepage_fixtures(snapshot)
    standings = repository.standings_or_groups(snapshot)
    bullets = schedule_service.summary_bullets(snapshot, lang)
    lead_fixture = None
    for candidate in fixtures["live_upcoming"] + fixtures["knockout"] + fixtures["recent"]:
        lead_fixture = candidate
        if lead_fixture:
            break
    focus_groups = {"A", "C", "I", "L"}
    selected_group = "A"
    detailed_groups = []
    for bucket in standings:
        group_name = bucket.group if hasattr(bucket, "group") else bucket["group"]
        rows = bucket.rows if hasattr(bucket, "rows") else bucket["teams"]
        group_summary = {
            "group": group_name,
            "rows": rows,
            "is_focus": group_name in focus_groups,
        }
        detailed_groups.append(group_summary)
        if group_name in focus_groups and selected_group == "A":
            selected_group = group_name
    return {
        "lang": lang,
        "text": text,
        "teams": repository.options(),
        "group_tables": detailed_groups,
        "featured": [_fixture_view(fixture, lang) for fixture in fixtures["featured"]],
        "schedule_sections": {
            "live_upcoming": [_fixture_view(fixture, lang) for fixture in fixtures["live_upcoming"]],
            "knockout": [_fixture_view(fixture, lang) for fixture in fixtures["knockout"]],
            "recent": [_fixture_view(fixture, lang) for fixture in fixtures["recent"]],
        },
        "lead_fixture": _fixture_view(lead_fixture, lang) if lead_fixture else None,
        "schedule_snapshot": snapshot,
        "schedule_updated_display": format_beijing(snapshot.fetchedAt, "%Y-%m-%d %H:%M"),
        "schedule_bullets": bullets,
        "schedule_freshness_label": text["freshness_labels"].get(snapshot.dataFreshness, snapshot.dataFreshness),
        "stage_labels": {key: labels[lang] for key, labels in STAGE_LABELS.items()},
        "settings": get_settings(),
        "confidence_labels": {key: value[lang] for key, value in CONFIDENCE_LABELS.items()},
        "tier_labels": TIER_LABELS,
        "focus_groups": focus_groups,
        "selected_group": selected_group,
    }


def _build_prediction_view(response, lang: str) -> dict:
    text = LANGUAGE_TEXT[lang]
    payload = response.prediction
    translation_notice = None
    if lang == "en" and payload.analysis.en == payload.analysis.zh and response.mode == "live":
        translation_notice = text["translation_notice"]

    def _format_percent(value):
        if value is None:
            return "未公开" if lang == "zh" else "n/a"
        return f"{value:.2f}".rstrip("0").rstrip(".")

    engine_summary = None
    quality_summary = None
    priors_summary = None
    if lang == "zh":
        if payload.knockout:
            sorted_adv = sorted(payload.knockout.advanceProb.items(), key=lambda item: item[1], reverse=True)
            result_headline = f"{sorted_adv[0][0]} 晋级倾向更强"
            result_subheadline = "90 分钟内仍要提防僵持，但晋级天平已经略微倾向一侧。"
        else:
            gap = payload.teamA.winProb - payload.teamB.winProb
            if abs(gap) <= 6:
                result_headline = "这场更像五五开"
                result_subheadline = "胜负差距很窄，比分和临场效率会决定谁先把局面撬开。"
            elif gap > 0:
                result_headline = f"{payload.teamA.nameZh} 略占上风"
                result_subheadline = f"{payload.teamA.nameZh} 的胜面更大，但仍不是一场可以轻松带走的比赛。"
            else:
                result_headline = f"{payload.teamB.nameZh} 略占上风"
                result_subheadline = f"{payload.teamB.nameZh} 的胜面更大，但比赛仍保留足够波动。"
    else:
        if payload.knockout:
            sorted_adv = sorted(payload.knockout.advanceProb.items(), key=lambda item: item[1], reverse=True)
            result_headline = f"{sorted_adv[0][0]} holds the advance edge"
            result_subheadline = "Regulation still looks tight, but the wider qualification balance leans one way."
        else:
            gap = payload.teamA.winProb - payload.teamB.winProb
            if abs(gap) <= 6:
                result_headline = "This projects as a near coin flip"
                result_subheadline = "The teams are close enough that finishing and match rhythm will decide the swing moments."
            elif gap > 0:
                result_headline = f"{payload.teamA.nameEn} carries the slight edge"
                result_subheadline = f"{payload.teamA.nameEn} rates better, but not by enough to make this comfortable."
            else:
                result_headline = f"{payload.teamB.nameEn} carries the slight edge"
                result_subheadline = f"{payload.teamB.nameEn} rates better, though the match still carries real volatility."
    if payload.engine:
        team_a_rating = payload.engine.ratings.get(payload.teamA.nameZh)
        team_b_rating = payload.engine.ratings.get(payload.teamB.nameZh)
        team_a_lambda = payload.engine.lambda90.get(payload.teamA.nameZh)
        team_b_lambda = payload.engine.lambda90.get(payload.teamB.nameZh)
        if lang == "zh":
            engine_summary = [
                text["model_sheet_engine_blurb"],
                f"{payload.teamA.nameZh} 基线强度 {team_a_rating}，{payload.teamB.nameZh} 基线强度 {team_b_rating}。",
                f"预估进球倾向约为 {team_a_lambda:.2f} 比 {team_b_lambda:.2f}，因此比分落点更集中在当前结果附近。",
            ]
        else:
            engine_summary = [
                text["model_sheet_engine_blurb"],
                f"{payload.teamA.nameEn} sits on a base strength of {team_a_rating}, while {payload.teamB.nameEn} opens at {team_b_rating}.",
                f"The expected goal tilt is roughly {team_a_lambda:.2f} to {team_b_lambda:.2f}, which keeps the scoreline clustered near the displayed result.",
            ]
    if payload.dataQuality:
        if lang == "zh":
            level_label = {"fallback": "站内保底模式", "medium": "常规赛程判断", "high": "高置信赛程判断"}.get(payload.dataQuality.level, "常规判断")
            quality_summary = [
                text["model_sheet_quality_blurb"],
                f"当前属于 {level_label}，会优先参考已知赛程、球队基线和单场走势。",
                payload.dataQuality.notes,
            ]
        else:
            level_label = {"fallback": "safe fallback mode", "medium": "standard match read", "high": "high-confidence match read"}.get(payload.dataQuality.level, "standard read")
            quality_summary = [
                text["model_sheet_quality_blurb"],
                f"This result is currently in {level_label} and leans on known schedule context, team baselines, and match shape.",
                payload.dataQuality.notes,
            ]
    if payload.tournamentPriors and (payload.tournamentPriors.teamA or payload.tournamentPriors.teamB):
        if lang == "zh":
            priors_summary = [
                f"{payload.teamA.nameZh} 的赛事级先验夺冠概率约 {_format_percent(payload.tournamentPriors.teamA.titleProb if payload.tournamentPriors.teamA else None)}%。",
                f"{payload.teamB.nameZh} 的赛事级先验夺冠概率约 {_format_percent(payload.tournamentPriors.teamB.titleProb if payload.tournamentPriors.teamB else None)}%。",
            ]
        else:
            priors_summary = [
                f"{payload.teamA.nameEn} carries a tournament-title prior of about {_format_percent(payload.tournamentPriors.teamA.titleProb if payload.tournamentPriors.teamA else None)}%.",
                f"{payload.teamB.nameEn} carries a tournament-title prior of about {_format_percent(payload.tournamentPriors.teamB.titleProb if payload.tournamentPriors.teamB else None)}%.",
            ]
    else:
        priors_summary = [text["model_sheet_priors_empty"]]
    return {
        "mode": response.mode,
        "source": response.source,
        "generated_at": response.generatedAt,
        "generated_at_display": format_beijing(response.generatedAt, "%Y-%m-%d %H:%M"),
        "prediction_request": response.request,
        "prediction": payload,
        "notice": response.notice,
        "lang": lang,
        "text": text,
        "confidence_label": CONFIDENCE_LABELS[payload.confidence][lang],
        "translation_notice": translation_notice,
        "result_source_label": text["result_source_labels"][response.mode],
        "result_headline": result_headline,
        "result_subheadline": result_subheadline,
        "engine_summary": engine_summary,
        "quality_summary": quality_summary,
        "priors_summary": priors_summary,
    }


async def _enforce_rate_limit(request: Request, settings: Settings) -> None:
    allowed, retry_after = await rate_limiter.allow(_client_ip(request))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": "Rate limit exceeded.", "retryAfter": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


def _internal_sync_authorized(token: str | None, settings: Settings) -> bool:
    return bool(token and token == settings.internal_sync_token)


@app.on_event("startup")
async def startup_sync() -> None:
    schedule_service = get_schedule_service(get_settings())
    await schedule_service.load_or_sync()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, schedule_service: ScheduleService = Depends(get_schedule_service)):
    context = _language_context("zh", schedule_service)
    return templates.TemplateResponse(request, "index.html", {"request": request, **context})


@app.get("/en", response_class=HTMLResponse)
async def home_en(request: Request, schedule_service: ScheduleService = Depends(get_schedule_service)):
    context = _language_context("en", schedule_service)
    return templates.TemplateResponse(request, "index.html", {"request": request, **context})


@app.post("/predict", response_class=HTMLResponse)
async def predict_partial(
    request: Request,
    teamA: str = Form(...),
    teamB: str = Form(...),
    stage: str = Form(...),
    lang: str = Form(...),
    fixtureId: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    prediction_service: PredictionService = Depends(get_prediction_service),
):
    await _enforce_rate_limit(request, settings)
    try:
        prediction_request = PredictRequest(teamA=teamA, teamB=teamB, stage=stage, lang=lang, fixtureId=fixtureId)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = await prediction_service.predict(prediction_request)
    context = _build_prediction_view(response, lang)
    return templates.TemplateResponse(request, "partials/prediction_result.html", {"request": request, **context})


@app.post("/api/predict")
async def predict_api(
    request: Request,
    payload: PredictRequest,
    settings: Settings = Depends(get_settings),
    prediction_service: PredictionService = Depends(get_prediction_service),
):
    await _enforce_rate_limit(request, settings)
    response = await prediction_service.predict(payload)
    return JSONResponse(response.model_dump(mode="json"))


@app.get("/api/schedule")
async def schedule_api(schedule_service: ScheduleService = Depends(get_schedule_service)):
    snapshot = schedule_service.load_snapshot()
    return JSONResponse(ScheduleResponse(snapshot=snapshot).model_dump(mode="json"))


@app.post("/internal/sync")
async def internal_sync(
    settings: Settings = Depends(get_settings),
    schedule_service: ScheduleService = Depends(get_schedule_service),
    x_internal_sync_token: str | None = Header(default=None),
):
    if not _internal_sync_authorized(x_internal_sync_token, settings):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    snapshot = await schedule_service.sync()
    return JSONResponse(
        SyncResponse(
            status="ok",
            updatedAt=snapshot.fetchedAt,
            source=snapshot.source,
            fixtureCount=len(snapshot.fixtures),
            standingsCount=len(snapshot.standings),
        ).model_dump(mode="json")
    )


@app.get("/healthz")
async def health(settings: Settings = Depends(get_settings), schedule_service: ScheduleService = Depends(get_schedule_service)):
    snapshot = schedule_service.load_snapshot()
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
        "liveModeEnabled": settings.live_mode_enabled,
        "fallbackEnabled": settings.demo_fallback_enabled,
        "scheduleSource": snapshot.source,
        "scheduleUpdatedAt": snapshot.fetchedAt,
        "fixturesSynced": len(snapshot.fixtures),
    }
