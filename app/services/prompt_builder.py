from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.schemas import MatchContextPayload, RawSkillPrediction, ScheduleSnapshot
from app.time_utils import format_beijing


SECTION_SIX_HEADING = "## 六、最新情报（每日更新区）"


@dataclass(slots=True)
class PromptBuilder:
    skill_path: Path

    def build(self, snapshot: ScheduleSnapshot) -> str:
        skill_text = self.skill_path.read_text(encoding="utf-8")
        generated_section = self.render_daily_brief_section(snapshot)
        if SECTION_SIX_HEADING not in skill_text:
            return f"{skill_text.rstrip()}\n\n{generated_section}\n"
        head, _, _tail = skill_text.partition(SECTION_SIX_HEADING)
        return f"{head.rstrip()}\n\n{generated_section}\n"

    def render_daily_brief_section(self, snapshot: ScheduleSnapshot) -> str:
        live = [fixture for fixture in snapshot.fixtures if fixture.status == "in_progress"]
        upcoming = [fixture for fixture in snapshot.fixtures if fixture.status == "scheduled"][:4]
        knockout = [fixture for fixture in snapshot.fixtures if fixture.knockout and fixture.predictionAvailable][:3]

        bullets = [
            f"赛程数据源：football-data.org（赛事代码 {snapshot.competition}），最近同步时间 {format_beijing(snapshot.fetchedAt, '%Y-%m-%d %H:%M')} 北京时间。",
            f"当前已同步比赛 {len(snapshot.fixtures)} 场；进行中 {len(live)} 场，已确认淘汰赛对阵 {len(knockout)} 场。",
        ]
        if upcoming:
            next_line = "；".join(
                f"{fixture.stageLabelZh}：{fixture.teamA.name_zh} vs {fixture.teamB.name_zh}"
                for fixture in upcoming
            )
            bullets.append(f"接下来重点赛程：{next_line}。")
        bullets.append(snapshot.dataDelayNoteZh)

        lines = "\n".join(f"- {line}" for line in bullets)
        return (
            "## 六、最新情报（每日更新区）\n\n"
            "> 本节由网站赛程同步流程覆盖更新。**当本节与第四节冲突时，以本节为准**。\n\n"
            f"**情报日期：{snapshot.fetchedAt:%Y-%m-%d}（赛程同步）**\n\n"
            f"{lines}"
        )

    def build_fill_prompt(
        self,
        engine_prediction: RawSkillPrediction,
        match_context: MatchContextPayload | None,
        lang: str,
    ) -> str:
        context_lines = []
        if match_context:
            context_lines.extend(
                [
                    f"- 比赛阶段：{match_context.stageLabelZh}",
                    f"- 场地：{match_context.venueZh or '待定'}",
                    f"- 状态：{match_context.status}",
                ]
            )
            if match_context.homeSide:
                context_lines.append(f"- 主场修正已作用于球队：{match_context.homeSide}")

        context_block = "\n".join(context_lines) if context_lines else "- 无额外赛程上下文"
        return (
            "你将收到一份已经由 Green Oracle 统计引擎生成好的世界杯比赛 JSON。"
            "你只能填写或改写以下字段：keyFactors、analysis、playersToWatch。"
            "严禁修改 teamA.winProb、draw、teamB.winProb、predictedScore、engine、dataQuality、tournamentPriors、knockout、stage、safeUse。"
            "输出必须仍然是完整合法 JSON。\n\n"
            "补全文案要求：\n"
            "1. keyFactors 保持 3 到 5 条，每条 15 字以内。\n"
            "2. analysis 150 字以内，像专业足球转播解说。\n"
            "3. playersToWatch 保持两名球员，每队各一名。\n"
            "4. 如果信息不足，就在 analysis 中承认不确定性，不要虚构伤停。\n"
            "5. 语言统一使用中文，英文页面后续由站点自行翻译。\n\n"
            f"赛程上下文：\n{context_block}\n\n"
            f"当前站点请求语言：{lang}\n\n"
            f"请补全这份 JSON：\n{engine_prediction.model_dump_json(indent=2)}"
        )
