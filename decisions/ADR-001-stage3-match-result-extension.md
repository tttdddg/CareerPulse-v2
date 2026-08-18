# ADR-001：阶段3 MatchResult 加法扩展与未知能力语义

- 状态：Accepted
- 日期：2026-08-13
- 范围：阶段3第2步（人岗匹配与能力缺口分析）

## 背景

D2 冻结契约只包含 `overall_score`、`dimensions`、`ability_gaps`、
`gap_analysis`、`strengths` 和 `matching_algorithm_version`。阶段3需要补充每项
能力的原始等级、证据、置信度、硬性条件结论、匹配等级和缺失信息表达。

D2 使用 `current_level=0` 表达能力未出现在画像中，但学生画像的合法能力等级为
1–5。阶段3必须避免将“未提供”解释为“已测得为零”。

## 决策

1. 保留 D2 顶层字段及 `matching_algorithm_version=deterministic-v1`，作为兼容投影。
2. 新增 `dimension_matches` 等阶段3结构化字段，Service 输出统一经
   `schemas/match_schema.py::MatchResult` 校验。
3. `dimension_matches.student_level/gap/score/confidence` 在学生画像未提供该能力时
   为 `null`，状态为 `unknown`；`skill_gaps` 只包含有明确学生等级的不足项。
4. `overall_score` 只对有明确学生等级且岗位权重大于零的维度计算，并按这些维度的
   权重重新归一化。可观测权重低于 0.5 时 `match_level=insufficient_data`。
5. D2 `ability_gaps.current_level=0` 仅在兼容投影中保留，不参与阶段3 Gap 结论。
6. 岗位权重继续来自阶段2 `JobProfile.required_abilities[].weight`；阈值、容差、
   confidence 组合权重集中在 `services/match_config.py`。
7. 当前 JobProfile 没有学历/经验硬门字段，所以硬性条件只评估
   `importance=critical` 的能力，并允许 `unknown`。

## 影响

- 已完整提供岗位所需能力的输入，`overall_score` 与 D2 冻结公式相同。
- 部分画像不会因未知能力被虚假扣成 0 分；结果可靠度由 `confidence`、
  `missing_skills`、`data_quality_flags` 和 `match_level` 共同表达。
- 老消费者仍可读取原字段；新消费者应优先使用阶段3字段。
- 本 ADR 不授权开发 MatchAgent、Tool/MCP、职业路径或前端。
