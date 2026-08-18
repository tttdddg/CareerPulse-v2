阶段3第2步已完成：实现确定性人岗匹配、能力缺口、严格 Schema、集中配置和单元测试。未开发 MatchAgent、PathAgent、MCP/Tool、职业路径或前端，也未提交 Git。

### 1. 修改文件

核心代码：

- [match_schema.py](D:/vue/CareerPulse-Pro/backend/app/schemas/match_schema.py)：新增严格 MatchRequest、MatchResult、DimensionMatch、SkillGap、硬条件和证据 Schema
- [match_config.py](D:/vue/CareerPulse-Pro/backend/app/services/match_config.py)：集中管理阈值、置信度权重、算法版本和容差
- [match_service.py](D:/vue/CareerPulse-Pro/backend/app/services/match_service.py)：确定性匹配、Gap、硬条件、置信度与兼容投影
- [test_match_service.py](D:/vue/CareerPulse-Pro/backend/tests/test_match_service.py)：扩展至 23 项匹配测试

契约与决策：

- [ADR-001-stage3-match-result-extension.md](D:/vue/CareerPulse-Pro/decisions/ADR-001-stage3-match-result-extension.md)
- [03_ARCHITECTURE.md](D:/vue/CareerPulse-Pro/docs/a02/03_ARCHITECTURE.md)
- [04_API_CONTRACTS.md](D:/vue/CareerPulse-Pro/docs/a02/04_API_CONTRACTS.md)
- [05_AGENT_CONTRACTS.md](D:/vue/CareerPulse-Pro/docs/a02/05_AGENT_CONTRACTS.md)
- [13_MCP_TOOL_CATALOG.md](D:/vue/CareerPulse-Pro/docs/a02/13_MCP_TOOL_CATALOG.md)，仅同步输出契约，未实现 MCP/Tool

规划记录也按 `planning-with-files` 要求更新了 `task_plan.md`、`findings.md`、`progress.md`。用户提供的 `D3 stage1.md` 未修改。

### 2. 匹配公式

对学生画像中具有明确等级、且岗位权重大于零的维度集合 `Kobs`：

```
DimensionScore_k = min(StudentLevel_k / RequiredLevel_k, 1) × 100

OverallScore =
  Σ(k∈Kobs) Weight_k × DimensionScore_k
  / Σ(k∈Kobs) Weight_k

Gap_k = max(RequiredLevel_k - StudentLevel_k, 0)

GapPriorityScore_k = Gap_k × Weight_k / Difficulty_k
```

按 `GapPriorityScore` 降序、importance、标签名稳定排序，再生成整数 priority。

匹配等级：

- `≥80`：high
- `≥60`：good
- `≥40`：fair
- `≥20`：weak
- `<20`：low
- 可观测岗位权重 `<50%`：insufficient_data

结果 confidence：

```
0.6 × 证据加权置信度
+ 0.3 × 岗位能力可观测权重覆盖率
+ 0.1 × 学生画像完整度
```

缺失的 confidence 组件不会当作零，而是对现有组件权重重新归一化。

### 3. 缺失数据处理

- 未提供岗位要求能力：`student_level/gap/score/confidence = null`，状态为 `unknown`
- 未提供能力进入 `missing_skills`，但不进入新 `skill_gaps`
- 不把“未提供”判为 level 0，也不作为零分参与 observed score
- 可观测权重不足 50% 时不输出高低匹配结论
- 零权重维度标为 `excluded`，不参与分数、Gap、硬条件或 missing_skills
- 低置信度、低 completeness、声明缺失字段均进入 `data_quality_flags`
- 非法等级、confidence、weight、difficulty、importance、未知标签明确抛错
- 裸 dict 输入中的学生证据也会检查邮箱、手机号和身份证信息
- 旧 `ability_gaps.current_level=0` 仅保留在 `deterministic-v1` 兼容投影中
- 当前岗位 Schema 没有学历/经验门槛，因此硬条件仅确定性评估 `critical` 能力，输出 passed/failed/unknown

### 4. 测试结果

核心相关测试：

```
MatchService                 23/23 passed
AbilityTagNormalizer          5/5 passed
ProfileAgent阶段2回归         7/7 passed
合计                         35/35 passed
```

此外：

- 48 个统一能力标签校验通过
- 3 份学生、3 份岗位 Demo 校验通过
- 9 张数据库迁移表静态检查通过
- 隐私检查通过
- 7 个现有 Mock 工具成功/失败 envelope 检查通过
- `compileall` 通过
- `git diff --check` 通过

平台旧基线为 `5/7`：两个失败在开发前后完全一致，原因是未配置 LLM 时 Profile/Job 正确 fallback，但旧测试仍固定期待全链 `success` 和 TBox `code=0`。本步骤按范围未修改 Agent 或平台测试。

### 5. 匹配示例

使用仓库现有真实阶段2 Demo：`演示学生C × 数据分析师`。

```
{
  "overall_score": 90.42,
  "match_level": "high",
  "confidence": 0.8756,
  "matched_skills": ["数据分析", "Python", "数据可视化"],
  "missing_skills": [],
  "skill_gaps": [
    {
      "dimension": "SQL/数据库",
      "student_level": 3,
      "required_level": 4,
      "gap": 1,
      "weight": 0.25,
      "priority": 1
    },
    {
      "dimension": "沟通表达",
      "student_level": 2,
      "required_level": 3,
      "gap": 1,
      "weight": 0.1,
      "priority": 2
    }
  ],
  "calculation_version": "deterministic-match-v2"
}
```

已知后续边界：当前 Mock MatchAgent 尚未调用新版 MatchService；这是本步骤明确排除的内容，文档中已经显式标注，避免误称已经集成。