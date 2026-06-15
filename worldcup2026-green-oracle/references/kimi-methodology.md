# Kimi Report Methodology Notes

Use this reference when a prediction needs richer priors than the local rating baseline.

Source: `Kimi_2026_World_Cup_Report.pdf`, generated 2026-06-09, report release baseline 2026-06-05.

## Useful Data

- Chapter 2 defines a multi-source methodology: FIFA match data, World Football Elo, FIFA SUM ranking, event data, player data, environment data, and market consensus as a bias variable.
- Chapter 7 page 166 provides baseline title probabilities across Elo, Dixon-Coles, SPI, gradient boosting, ensemble consensus, confidence intervals, and confidence labels.
- Chapter 8 pages 177-178 provide 48-team title probability priors.
- Chapter 8 page 181 provides semifinal probability priors for the leading teams.
- Appendix A pages 201-202 defines future structured team fields: `elo_rating`, `fifa_rank`, `title_prob`, `final_prob`, `semi_prob`, `group_placement`, `squad_value_million`, `avg_age`, `win_rate_18m`, `xg_per_game`, `xga_per_game`, `ppda`, `travel_fatigue_level`, and more.
- Appendix B pages 203-204 describes Elo and multi-result football extensions.

## How To Use

- Treat `data/kimi_team_priors.json` as tournament-level priors, not single-match probabilities.
- Use priors to adjust confidence and context, not to override `tools/predict.py` match probabilities.
- If a strong team has low title probability because of bracket path, explain that distinction.
- Market-implied fields may only be used as consensus-bias context. Do not mention betting, odds, picks, staking, or wagering.
- When updating `data/ratings.json`, prefer verified Elo/FIFA/team-form sources over narrative text.

## Future Improvements

- Add `fifa_rank`, `elo_rank`, `squad_value_million`, `avg_age`, `xg_per_game`, and `travel_fatigue_level` as structured fields when reliable extracted tables are available.
- Add a tournament Monte Carlo script that uses match probabilities, official bracket rules, and finished-match locks.
- Add a calibration report using Brier score, log loss, Ranked Probability Score, and Expected Calibration Error.
