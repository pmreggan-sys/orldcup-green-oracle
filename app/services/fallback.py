from __future__ import annotations

from dataclasses import dataclass

from app.i18n import STAGE_LABELS
from app.repository import TournamentRepository
from app.schemas import (
    DataQualityPayload,
    EngineDetails,
    LocalizedAnalysis,
    LocalizedFactor,
    MatchContextPayload,
    NormalizedTeamOutcome,
    PlayerToWatch,
    PredictRequest,
    PredictionPayload,
)

BASE_TIER_RATINGS = {
    "夺冠热门档": 84,
    "一线强队档": 76,
    "二线 / 东道主档": 68,
    "中游 / 新军档": 60,
}

KNOCKOUT_STAGES = {"round_of_32", "round_of_16", "quarterfinal", "semifinal", "final"}

GROUP_BUCKETS = [
    (3, (35, 30, 35), "1-1", "low"),
    (7, (41, 30, 29), "2-1", "medium"),
    (11, (47, 29, 24), "2-1", "medium"),
    (17, (55, 27, 18), "2-0", "high"),
    (999, (63, 24, 13), "3-1", "high"),
]

KNOCKOUT_BUCKETS = [
    (3, (41, 18, 41), "1-1", "low"),
    (7, (47, 18, 35), "2-1", "medium"),
    (11, (53, 17, 30), "2-1", "medium"),
    (17, (60, 16, 24), "2-0", "high"),
    (999, (67, 15, 18), "3-0", "high"),
]


@dataclass(slots=True)
class FallbackEngine:
    repository: TournamentRepository

    def predict(self, request: PredictRequest, match_context: MatchContextPayload | None = None) -> PredictionPayload:
        team_a = self.repository.team_by_slug(request.teamA)
        team_b = self.repository.team_by_slug(request.teamB)
        strength_a = self._strength(team_a.name_zh, request.stage)
        strength_b = self._strength(team_b.name_zh, request.stage)
        if match_context and match_context.homeSide == "A" and team_a.host:
            strength_a += 4
        if match_context and match_context.homeSide == "B" and team_b.host:
            strength_b += 4
        gap = abs(strength_a - strength_b)
        stage_is_knockout = request.stage in KNOCKOUT_STAGES
        buckets = KNOCKOUT_BUCKETS if stage_is_knockout else GROUP_BUCKETS
        fav_prob, draw_prob, dog_prob, score, confidence = self._pick_bucket(buckets, gap)

        if strength_a > strength_b:
            probs = (fav_prob, draw_prob, dog_prob)
            analysis_focus = "A"
        elif strength_b > strength_a:
            probs = (dog_prob, draw_prob, fav_prob)
            analysis_focus = "B"
        else:
            probs = (fav_prob, draw_prob, dog_prob)
            analysis_focus = "even"
        if probs[0] > 85 or probs[2] > 85:
            raise ValueError("Fallback engine exceeded probability cap.")

        key_factors = self._key_factors(team_a.name_zh, team_b.name_zh, request.stage, strength_a, strength_b, match_context)
        analysis = self._analysis(team_a.name_zh, team_b.name_zh, request.stage, score, analysis_focus)
        knockout = None
        if stage_is_knockout:
            favored_slug = team_a.name_zh if probs[0] >= probs[2] else team_b.name_zh
            favored_prob = probs[0] + draw_prob // 2 if probs[0] >= probs[2] else probs[2] + draw_prob // 2
            knockout = {
                "note": "draw 表示90分钟战平进入加时/点球",
                "advanceProb": {
                    team_a.name_zh: favored_prob if favored_slug == team_a.name_zh else 100 - favored_prob,
                    team_b.name_zh: favored_prob if favored_slug == team_b.name_zh else 100 - favored_prob,
                },
            }

        return PredictionPayload(
            teamA=NormalizedTeamOutcome(slug=team_a.slug, nameZh=team_a.name_zh, nameEn=team_a.name_en, winProb=probs[0]),
            drawProb=probs[1],
            teamB=NormalizedTeamOutcome(slug=team_b.slug, nameZh=team_b.name_zh, nameEn=team_b.name_en, winProb=probs[2]),
            predictedScore=score,
            confidence=confidence,
            keyFactors=key_factors,
            analysis=analysis,
            playersToWatch=[
                PlayerToWatch(
                    teamSlug=team_a.slug,
                    playerZh=team_a.primary_player_zh,
                    playerEn=team_a.primary_player_en,
                    reasonZh=f"{team_a.primary_player_zh} 是 {team_a.name_zh} 最能改变节奏的爆点。",
                    reasonEn=f"{team_a.primary_player_en} is the player most likely to tilt the rhythm for {team_a.name_en}.",
                ),
                PlayerToWatch(
                    teamSlug=team_b.slug,
                    playerZh=team_b.primary_player_zh,
                    playerEn=team_b.primary_player_en,
                    reasonZh=f"{team_b.primary_player_zh} 的处理球质量决定 {team_b.name_zh} 的上限。",
                    reasonEn=f"{team_b.primary_player_en}'s execution will define the ceiling for {team_b.name_en}.",
                ),
            ],
            engine=EngineDetails(
                model="deterministic-fallback-v1",
                ratings={team_a.name_zh: strength_a, team_b.name_zh: strength_b},
                lambda90={team_a.name_zh: round(max(strength_a / 60, 0.5), 2), team_b.name_zh: round(max(strength_b / 60, 0.5), 2)},
                rho=-0.12,
                homeAdv=match_context.homeSide if match_context else None,
                capApplied=85,
            ),
            dataQuality=DataQualityPayload(
                level="fallback",
                sourcesUsed=["repo_team_tiers", "deterministic_rules"],
                notes="Green Oracle engine unavailable, so the site used a deterministic display-safe fallback.",
            ),
            tournamentPriors=None,
            knockout=knockout,
            safeUse="仅供球迷讨论，不构成任何决策建议。",
            matchContext=match_context,
        )

    def _strength(self, team_name_zh: str, stage: str) -> int:
        team = self.repository.team_by_zh(team_name_zh)
        strength = BASE_TIER_RATINGS[team.tier_zh]
        if stage in KNOCKOUT_STAGES and team.tier_zh == "夺冠热门档":
            strength += 2
        if stage in KNOCKOUT_STAGES and team.newcomer:
            strength -= 2
        return strength

    def _pick_bucket(self, buckets: list[tuple[int, tuple[int, int, int], str, str]], gap: int) -> tuple[int, int, int, str, str]:
        for max_gap, probs, score, confidence in buckets:
            if gap <= max_gap:
                return probs[0], probs[1], probs[2], score, confidence
        raise ValueError("No fallback bucket matched.")

    def _key_factors(
        self,
        team_a_name: str,
        team_b_name: str,
        stage: str,
        strength_a: int,
        strength_b: int,
        match_context: MatchContextPayload | None,
    ) -> list[LocalizedFactor]:
        team_a = self.repository.team_by_zh(team_a_name)
        team_b = self.repository.team_by_zh(team_b_name)
        factors = [
            (
                f"{team_a.name_zh} 档位值 {strength_a}",
                f"{team_a.name_en} carries a strength mark of {strength_a}",
            ),
            (
                f"{team_b.name_zh} 档位值 {strength_b}",
                f"{team_b.name_en} enters with a strength mark of {strength_b}",
            ),
            (
                "小组赛平局容忍更高" if stage == "group" else "淘汰赛压低平局权重",
                "Group stage keeps a larger draw lane" if stage == "group" else "Knockout play compresses the draw lane",
            ),
        ]
        if match_context and match_context.homeSide:
            host_team = team_a if match_context.homeSide == "A" else team_b
            factors.append(
                (
                    f"{host_team.name_zh} 享有东道主加成",
                    f"{host_team.name_en} receives the host-country bump",
                )
            )
        else:
            stronger = team_a if strength_a >= strength_b else team_b
            factors.append(
                (
                    f"{stronger.name_zh} 的档位更稳",
                    f"{stronger.name_en} owns the steadier tier profile",
                )
            )
        if stage in KNOCKOUT_STAGES:
            factors.append(
                (
                    "淘汰赛经验会放大细节处理",
                    "Knockout experience weighs heavily in late-game details",
                )
            )
        return [LocalizedFactor(zh=zh, en=en) for zh, en in factors[:5]]

    def _analysis(self, team_a_name: str, team_b_name: str, stage: str, score: str, analysis_focus: str) -> LocalizedAnalysis:
        team_a = self.repository.team_by_zh(team_a_name)
        team_b = self.repository.team_by_zh(team_b_name)
        if stage in KNOCKOUT_STAGES:
            if analysis_focus == "A":
                zh = f"{team_a.name_zh} 在档位和细节容错上略占先手，90分钟更像 {score} 的节奏；若拖入加时，{team_a.primary_player_zh} 的终结点更值得信任。"
                en = f"{team_a.name_en} holds the sharper edge in baseline quality, making {score} the likeliest 90-minute shape; if it stretches beyond regulation, {team_a.primary_player_en} still feels like the cleaner finisher."
            elif analysis_focus == "B":
                zh = f"{team_b.name_zh} 的结构稳定性更高，90分钟更像 {score} 的走势；若比赛进入加时，{team_b.primary_player_zh} 更可能成为分胜负的人。"
                en = f"{team_b.name_en} looks steadier across the full structure, so {score} fits the most likely 90-minute arc; if extra time arrives, {team_b.primary_player_en} is the likelier decider."
            else:
                zh = f"两队更像一场必须咬到最后的淘汰赛，{score} 的90分钟结果最顺理成章；若进入加时点球，微小处理球差距才会拉开晋级方向。"
                en = f"This profiles as a knockout match that runs deep into tension, with {score} as the most natural 90-minute script; only tiny execution margins would split the teams in extra time or penalties."
        else:
            if analysis_focus == "A":
                zh = f"{team_a.name_zh} 的整体档位和主场/节奏条件更顺手，{score} 是最自然的比赛形状；{team_b.name_zh} 仍有反击窗口，但需要效率极高。"
                en = f"{team_a.name_en} owns the cleaner tier profile and the friendlier game context, making {score} the most natural shape; {team_b.name_en} still has transition moments if the finishing is ruthless."
            elif analysis_focus == "B":
                zh = f"{team_b.name_zh} 的结构完整度更高，{score} 对它更友好；{team_a.name_zh} 想抢分，必须把前场冲击转化成更高质量的终结。"
                en = f"{team_b.name_en} brings the more coherent overall structure, so {score} leans its way; for {team_a.name_en} to take points, the front-foot bursts need much cleaner end product."
            else:
                zh = f"两队基础档位接近，这会更像一场拉扯很久的小组赛，{score} 是最合逻辑的落点；谁先把握定位球和二点球，谁就更接近改写剧本。"
                en = f"The sides are close enough on baseline strength for a long, tugging group match, with {score} the most logical landing spot; the first team to own set pieces and second balls could tilt the script."
        return LocalizedAnalysis(zh=zh[:150], en=en[:260])
