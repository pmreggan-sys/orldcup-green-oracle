from pathlib import Path

from app.services.prompt_builder import PromptBuilder


def test_prompt_builder_overrides_section_six(tmp_path: Path, sample_snapshot):
    skill_text = "## 一、header\nkeep\n\n## 六、最新情报（每日更新区）\nold"
    skill_file = tmp_path / "skill.md"
    skill_file.write_text(skill_text, encoding="utf-8")
    builder = PromptBuilder(skill_file)

    output = builder.build(sample_snapshot)

    assert "old" not in output
    assert "## 六、最新情报（每日更新区）" in output
    assert "赛程数据源：football-data.org" in output
    assert "墨西哥 vs 南非" in output
