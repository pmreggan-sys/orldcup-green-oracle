#!/usr/bin/env python3
"""Advanced World Cup 2026 match predictor.

Method:
1. Team rating difference -> expected goals.
2. Poisson score grid with Dixon-Coles low-score correction.
3. Optional in-play conditioning from minute/current score/red card.
4. Integer probabilities with sum exactly 100.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

MAX_GOALS = 8
BASE_LAMBDA = 1.32
ELO_SLOPE = 0.0032
DC_RHO = -0.12
HOME_BONUS = 55
RED_CARD_SELF = 0.65
RED_CARD_OPP = 1.25
LATE_URGENCY = 1.08

PRE_MATCH_CAP = 85
IN_PLAY_CAP_60 = 92
IN_PLAY_CAP_LATE = 95
IN_PLAY_CAP_FT = 98


def load_teams() -> dict:
    path = Path(__file__).resolve().parent.parent / "data" / "ratings.json"
    return json.loads(path.read_text(encoding="utf-8"))["teams"]


def load_priors() -> dict:
    path = Path(__file__).resolve().parent.parent / "data" / "kimi_team_priors.json"
    if not path.exists():
        return {"source": None, "teams": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_team(name: str, teams: dict) -> str:
    if name in teams:
        return name
    normalized = name.strip().lower()
    for team, info in teams.items():
        aliases = [alias.lower() for alias in info.get("aliases", [])]
        if normalized in aliases:
            return team
    raise SystemExit(f"Unknown team: {name}")


def expected_goals(rating_a: int, rating_b: int, home: str | None) -> tuple[float, float]:
    bonus_a = HOME_BONUS if home == "A" else 0
    bonus_b = HOME_BONUS if home == "B" else 0
    diff = (rating_a + bonus_a) - (rating_b + bonus_b)
    lambda_a = BASE_LAMBDA * math.exp(ELO_SLOPE * diff)
    lambda_b = BASE_LAMBDA * math.exp(-ELO_SLOPE * diff)
    return clamp(lambda_a, 0.18, 4.4), clamp(lambda_b, 0.18, 4.4)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def poisson(k: int, lam: float) -> float:
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


def dc_tau(a: int, b: int, lam: float, mu: float) -> float:
    if a == 0 and b == 0:
        return max(0.0, 1 - lam * mu * DC_RHO)
    if a == 0 and b == 1:
        return max(0.0, 1 + lam * DC_RHO)
    if a == 1 and b == 0:
        return max(0.0, 1 + mu * DC_RHO)
    if a == 1 and b == 1:
        return max(0.0, 1 - DC_RHO)
    return 1.0


def score_grid(lambda_a: float, lambda_b: float, use_dc: bool) -> list[list[float]]:
    grid = [[0.0 for _ in range(MAX_GOALS + 1)] for _ in range(MAX_GOALS + 1)]
    total = 0.0
    for a in range(MAX_GOALS + 1):
        for b in range(MAX_GOALS + 1):
            prob = poisson(a, lambda_a) * poisson(b, lambda_b)
            if use_dc:
                prob *= dc_tau(a, b, lambda_a, lambda_b)
            grid[a][b] = prob
            total += prob
    for a in range(MAX_GOALS + 1):
        for b in range(MAX_GOALS + 1):
            grid[a][b] /= total
    return grid


def largest_remainder(probs: list[float]) -> list[int]:
    scaled = [p * 100 for p in probs]
    ints = [math.floor(p) for p in scaled]
    missing = 100 - sum(ints)
    order = sorted(range(len(probs)), key=lambda i: scaled[i] - ints[i], reverse=True)
    for index in order[:missing]:
        ints[index] += 1
    return ints


def apply_cap(win_a: float, draw: float, win_b: float, cap: int) -> tuple[float, float, float]:
    cap_value = cap / 100
    for _ in range(2):
        if win_a > cap_value:
            excess = win_a - cap_value
            win_a = cap_value
            share = draw + win_b
            draw += excess * draw / share
            win_b += excess * win_b / share
        if win_b > cap_value:
            excess = win_b - cap_value
            win_b = cap_value
            share = draw + win_a
            draw += excess * draw / share
            win_a += excess * win_a / share
    return win_a, draw, win_b


def pick_score(grid: list[list[float]], base_a: int, base_b: int, direction: str) -> str:
    best_score = (base_a, base_b)
    best_prob = -1.0
    for add_a in range(MAX_GOALS + 1):
        for add_b in range(MAX_GOALS + 1):
            final_a = base_a + add_a
            final_b = base_b + add_b
            result = "A" if final_a > final_b else "B" if final_b > final_a else "D"
            if result == direction and grid[add_a][add_b] > best_prob:
                best_prob = grid[add_a][add_b]
                best_score = (final_a, final_b)
    return f"{best_score[0]}-{best_score[1]}"


def probabilities_from_grid(grid: list[list[float]], base_a: int, base_b: int) -> tuple[float, float, float]:
    win_a = draw = win_b = 0.0
    for add_a in range(MAX_GOALS + 1):
        for add_b in range(MAX_GOALS + 1):
            final_a = base_a + add_a
            final_b = base_b + add_b
            prob = grid[add_a][add_b]
            if final_a > final_b:
                win_a += prob
            elif final_b > final_a:
                win_b += prob
            else:
                draw += prob
    return win_a, draw, win_b


def confidence(rating_gap: int, in_play: bool) -> str:
    if in_play:
        return "中"
    if rating_gap >= 180:
        return "高"
    if rating_gap <= 50:
        return "中"
    return "中"


def predict(args: argparse.Namespace) -> dict:
    teams = load_teams()
    priors = load_priors()
    team_a = resolve_team(args.teamA, teams)
    team_b = resolve_team(args.teamB, teams)
    rating_a = teams[team_a]["rating"]
    rating_b = teams[team_b]["rating"]
    lambda_a, lambda_b = expected_goals(rating_a, rating_b, args.home)

    in_play = args.minute is not None
    current_a, current_b = (0, 0)
    cap = PRE_MATCH_CAP
    use_dc = True
    lambda_a_used, lambda_b_used = lambda_a, lambda_b

    if in_play:
        current_a, current_b = parse_score(args.score)
        remaining = max(0, 90 - args.minute) / 90
        urgency = LATE_URGENCY if args.minute >= 75 else 1.0
        lambda_a_used = max(0.03, lambda_a * remaining * urgency)
        lambda_b_used = max(0.03, lambda_b * remaining * urgency)
        if args.red_card == "A":
            lambda_a_used *= RED_CARD_SELF
            lambda_b_used *= RED_CARD_OPP
        elif args.red_card == "B":
            lambda_b_used *= RED_CARD_SELF
            lambda_a_used *= RED_CARD_OPP
        use_dc = False
        if args.minute >= 90 and abs(current_a - current_b) >= 1:
            cap = IN_PLAY_CAP_FT
        elif args.minute >= 80 and abs(current_a - current_b) >= 2:
            cap = IN_PLAY_CAP_LATE
        elif args.minute >= 60:
            cap = IN_PLAY_CAP_60

    grid = score_grid(lambda_a_used, lambda_b_used, use_dc)
    win_a, draw, win_b = probabilities_from_grid(grid, current_a, current_b)
    win_a, draw, win_b = apply_cap(win_a, draw, win_b, cap)
    int_a, int_draw, int_b = largest_remainder([win_a, draw, win_b])

    direction = ["A", "D", "B"][[int_a, int_draw, int_b].index(max(int_a, int_draw, int_b))]
    score = pick_score(grid, current_a, current_b, direction)

    result = {
        "teamA": {"name": team_a, "winProb": int_a},
        "draw": int_draw,
        "teamB": {"name": team_b, "winProb": int_b},
        "predictedScore": score,
        "confidence": confidence(abs(rating_a - rating_b), in_play),
        "keyFactors": ["[LLM填写]", "[LLM填写]", "[LLM填写]"],
        "analysis": "[LLM填写：150字以内，不得改动概率与比分]",
        "playersToWatch": [
            {"team": team_a, "player": first_player(teams[team_a]), "reason": "[LLM填写]"},
            {"team": team_b, "player": first_player(teams[team_b]), "reason": "[LLM填写]"}
        ],
        "engine": {
            "model": "elo-dixon-coles-poisson v1",
            "ratings": {team_a: rating_a, team_b: rating_b},
            "lambda90": {team_a: round(lambda_a, 2), team_b: round(lambda_b, 2)},
            "rho": DC_RHO,
            "homeAdv": args.home,
            "capApplied": cap
        },
        "dataQuality": {
            "level": "medium",
            "sourcesUsed": ["engine_ratings", "kimi_team_priors"] + (["user_state"] if in_play else []),
            "notes": "评分为可维护基线；重大伤停、首发和天气需写入每日情报或调整评分后重跑。"
        },
        "tournamentPriors": {
            "source": priors.get("source"),
            "sourceDate": priors.get("source_date"),
            "teamA": compact_prior(priors.get("teams", {}).get(team_a)),
            "teamB": compact_prior(priors.get("teams", {}).get(team_b))
        },
        "safeUse": "仅供球迷讨论，不构成任何决策建议。"
    }

    if args.knockout or args.stage in {"32强", "16强", "8强", "半决赛", "决赛"}:
        edge_a = 1 / (1 + math.exp(-(rating_a - rating_b) / 360))
        advance_a = win_a + draw * edge_a
        result["knockout"] = {
            "note": "draw 表示90分钟战平进入加时/点球",
            "advanceProb": {team_a: round(advance_a * 100), team_b: round((1 - advance_a) * 100)}
        }

    if in_play:
        result["currentState"] = {
            "minute": "HT" if args.minute == 45 else str(args.minute),
            "score": args.score,
            "knownEvents": [f"red_card:{args.red_card}"] if args.red_card else []
        }
    result["stage"] = args.stage
    result["mode"] = "in_play" if in_play else "pre_match"
    return result


def parse_score(score: str) -> tuple[int, int]:
    try:
        left, right = score.split("-", 1)
        return int(left), int(right)
    except ValueError as exc:
        raise SystemExit("Score must look like 1-0") from exc


def first_player(team: dict) -> str:
    players = team.get("players", [])
    return players[0] if players else "[LLM填写]"


def compact_prior(prior: dict | None) -> dict | None:
    if not prior:
        return None
    return {
        "titleProb": prior.get("title_prob"),
        "titleCI": prior.get("title_ci"),
        "semiProb": prior.get("semi_prob"),
        "semiCI": prior.get("semi_ci"),
        "confederation": prior.get("confederation")
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teamA", required=True)
    parser.add_argument("--teamB", required=True)
    parser.add_argument("--stage", default="小组赛")
    parser.add_argument("--minute", type=int)
    parser.add_argument("--score", default="0-0")
    parser.add_argument("--red-card", choices=["A", "B"])
    parser.add_argument("--home", choices=["A", "B"])
    parser.add_argument("--knockout", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    print(json.dumps(predict(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
