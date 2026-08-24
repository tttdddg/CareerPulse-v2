# 《D4-2.2 ResourceService业务接入完成报告》

## 1. 完成结论

D4-2.2 已在限定范围内完成：冻结的 `ResourceService` 已接入现有 TrainingAgent 评分业务链路。用户完成训练评分后，TrainingAgent 从真实 `match_result.skill_gaps[].dimension` 按当前列表顺序提取 `ability_gaps`，调用：

```python
ResourceService.recommend_resources(
    ability_gaps=ability_gaps,
    target_job=target_job,
)
```

Service 返回的 `learning_resources`、`job_resources`、`certificate_suggestions`、`data_quality_flags` 被完整写入既有 `state.resource_result`。

本步骤没有新增 ResourceAgent，没有调用 LLM 推荐资源，没有修改 ResourceService 或复制 AbilityTagNormalizer，也没有进入百宝箱、平台工具注册或公网部署。

## 2. 仓库核查结论

### 2.1 是否已有 ResourceAgent

仓库不存在 ResourceAgent，冻结架构也不要求新增：

- `backend/app/agents/__init__.py` 只导出六个既有 Agent；
- CareerOrchestrator 默认顺序为 Profile → Job → Match → Path → Training → Feedback；
- `docs/a02/05_AGENT_CONTRACTS.md §5.1` 明确把“调用 ResourceService 推荐资源”列为 TrainingAgent 职责；
- D4-2.0 基线核查也已验收 `ResourceService → TrainingAgent → resource_result` 的接入建议。

因此本步骤没有为了结构对称新建 ResourceAgent。

### 2.2 skill_gaps 结构与顺序责任

真实 `MatchResult.skill_gaps` 中每项是严格 `SkillGap`，至少包含：

- `dimension`；
- `student_level` / `required_level` / `gap`；
- `score` / `weight` / `priority`；
- `importance` / `difficulty` 及证据字段。

MatchService 已按确定性 priority score 排序，并依次写入 `priority=1..n`。本步骤只按现有列表顺序提取 `dimension`，不读取 priority 后重排，也不重新计算 priority。

### 2.3 当前推荐结果状态位置

CareerState 已有 `resource_result: dict | None`，CareerOrchestrator 的 final_report 也已包含该字段。因此本步骤直接复用现有状态位置，没有修改 CareerState 或进行状态字段统一重构。

## 3. 最终消费位置及选择理由

最终消费位置：**TrainingAgent 的训练评分成功分支**。

选择依据：

1. 冻结 Agent 契约与 README §13.4 均明确要求 TrainingAgent 调用 ResourceService；
2. API 状态流规定 training_plan 生成后，用户完成训练时产生 resource_result；
3. TrainingAgent 已持有真实 match_result、job_profile，并负责训练生成/评分的多轮业务入口；
4. MatchAgent 只应负责匹配，不应混入下游资源推荐副作用；
5. PathAgent 的 learning_plan 是阶段3兼容投影，把 ResourceService 四字段拆入其中会丢失 job_resources 和 data_quality_flags；
6. CareerOrchestrator 当前只统一调用 Agent，直接特判 Service 会破坏既有调用模式；
7. 独立 tool 是后续百宝箱阶段能力，本轮明确禁止提前注册。

当前时序为：

```text
真实 match_result + job_profile
  → TrainingAgent 评分模式
  → LLM 五档语义判断
  → TrainingService.score（全部评分数值）
  → ResourceService.recommend_resources（纯确定性资源推荐）
  → state.training_plan + state.resource_result
```

训练题 generate 分支仍只生成 `training_plan`；资源推荐不会在用户完成训练前提前执行。

## 4. ability_gaps 与 target_job 来源

### ability_gaps

固定来源：

```text
state.match_result.skill_gaps[].dimension
```

处理规则：

- 按 `skill_gaps` 当前列表顺序逐项提取；
- 不接受训练请求中的 ability_gaps 作为资源推荐来源；
- 不按 priority 再排序；
- 不重新归一标签；
- unknown/no-resource 判断继续由冻结 ResourceService 内部处理。

### target_job

固定读取 `state.job_profile.title`；缺少有效标题时传 `None`。当前冻结 ResourceService 接受该参数但暂不参与匹配，因此 Agent 不扩写岗位资源逻辑。

## 5. 输出透传方式

TrainingAgent 对 ResourceService 裸 dict 只做最低限度的边界检查：

- 返回值必须为 mapping；
- 不得是 `{error: ...}`；
- 必须包含四个冻结顶层字段。

校验通过后复制整个 Service 结果，不裁剪、不排序、不重新计算、不补造数据：

```json
{
  "learning_resources": [],
  "job_resources": [],
  "certificate_suggestions": [],
  "data_quality_flags": []
}
```

`resource_id` 和 `demo_only` 仍由 ResourceService 的既有输出白名单剔除；Agent 不重新读取资源数据文件，也不会把内部字段加回结果。

## 6. LLM 与 Service 职责边界

资源推荐不调用 LLM：

- LLM 仍只用于 D4-2.1 已验收的训练答案五档语义判断和评分后的文字解释；
- ResourceService 调用是同步、确定性的直接调用；
- 评分模式下 LLM 调用数仍为原有两次，没有新增第三次资源推荐调用；
- 学习资源、岗位资源、证书建议和质量 flags 全部来自 ResourceService。

AbilityTagNormalizer 仍只由 ResourceService 内部复用；TrainingAgent 没有导入、复制或调用该实现。

## 7. 修改文件

### 业务实现与测试

| 文件 | 变更 |
| --- | --- |
| `backend/app/agents/training_agent.py` | 注入 ResourceService；在 score 成功后调用推荐；允许输出 resource_result；增加最低限度 Service 结果校验 |
| `backend/app/agents/tests/test_training_agent.py` | 新增 6 项完全离线的 ResourceService 业务接入测试 |

### 开发记录

| 文件 | 变更 |
| --- | --- |
| `开发日志/D4-ResourceService业务接入完成报告.md` | 本完成报告 |
| `task_plan.md` / `findings.md` / `progress.md` | planning-with-files 过程计划、核查发现和测试记录；不包含业务实现 |

本步骤未新增 Resource Schema 或 Prompt，因为资源推荐没有 LLM 边界，Service 继续返回裸 dict，CareerState 也已有承载字段。

## 8. 测试覆盖与结果

新增测试均为离线测试，不依赖真实 LLM 或网络。

### 8.1 验收项覆盖

| 验收项 | 覆盖方式 |
| --- | --- |
| ability_gaps 来自真实 skill_gaps.dimension | 使用真实 MatchService 结果，逐项对比传给 ResourceService 的 dimension |
| 顺序不被打乱 | 构造与 priority 数值不一致的列表，断言仍按列表原顺序传入 |
| 空 gaps | 断言传入空数组，并保留 Service 的全量推荐与上限行为 |
| 已知标签命中 | 数据分析命中真实演示资源 |
| unknown_tag | 完整保留 `unknown_tag:未知标签XYZ` |
| no_resource_for_tag | 完整保留 `no_resource_for_tag:机器学习` |
| job_resources_unavailable | 断言 job_resources 为空且 flag 保留 |
| resource_id / demo_only 不暴露 | 对最终 resource_result 序列化断言内部字段不存在 |
| 不调用 LLM 推荐资源 | score 流仍只有原两次训练 LLM 调用；资源调用没有额外 LLM |
| 不复制 normalizer | 静态断言 TrainingAgent 不包含 AbilityTagNormalizer |
| 原 ResourceService 测试 | 原 12 项全部通过 |
| 全量无新增回归 | 新增 6 项全部通过；既有 ProfileAgent 失败数不变 |

### 8.2 执行结果

| 测试范围 | 结果 |
| --- | --- |
| ResourceService 原测试 + TrainingAgent 测试 | `33 passed`（12 + 21） |
| 排除既有 ProfileAgent 阻塞项的适用全量回归 | `187 passed` |
| 完整 `backend/tests + backend/app/agents/tests` | `192 passed, 5 failed` |
| `python -m compileall -q app tests` | 通过 |

完整回归中的 5 个失败仍全部来自既有 ProfileAgent：仓库缺少 `prompts/profile_agent/system.txt` 和 `prompts/profile_agent/user_template.txt`。D4-2.1 完整回归为 `186 passed, 5 failed`；本步骤增加 6 个通过项后为 `192 passed, 5 failed`，失败数量与原因均未增加。该问题不属于本步骤授权范围，因此没有越界修复。

## 9. 冻结范围确认

以下目录和文件没有本步骤差异：

- `backend/app/services/resource_service.py`；
- `backend/app/services/training_service.py`；
- `backend/app/services/feedback_service.py`；
- AbilityTagNormalizer 所在模块；
- `backend/app/orchestrator/career_state.py`；
- `backend/app/orchestrator/career_orchestrator.py`；
- `backend/app/platform/**`；
- 百宝箱配置与公网部署配置。

## 10. 已知边界

1. ResourceService 当前没有岗位资源数据源，因此 `job_resources` 必然为空，并返回 `job_resources_unavailable`；Agent 不补造岗位资源。
2. `target_job` 当前只是预留输入，冻结 Service 暂不用于匹配。
3. 资源推荐仅在训练 score 成功后执行；generate 分支不会提前写入 resource_result。
4. BaseAgent 当前每个 Agent run 只自动生成一条 ToolCallLog，TrainingAgent 日志的主 service_name 仍为 TrainingService；若后续要求分别记录 TrainingService / ResourceService 两条内部调用，需要在统一日志和多轮 Orchestrator 阶段集中处理，不能在本步骤私建第二套日志模型。
5. ResourceService 异常会沿用现有 BaseAgent 标准失败/fallback 机制，不会由 Agent 生成假资源；当前 BaseAgent 的原子应用方式意味着该次 score 与 resource_result 不会部分写入。
6. CareerState 字段集中整理、训练评分历史、独立资源平台工具和百宝箱注册均留待后续步骤。

## 11. 验收结论

D4-2.2 已完成 ResourceService 的最小真实业务接入：消费层选择符合冻结契约，ability_gaps 来源真实且顺序不变，四类 Service 输出完整透传，无 ResourceAgent、无 LLM 假资源、无 normalizer 复制、无冻结 Service 改动。新增测试全部通过；完整回归仅保留此前已知的 5 个 ProfileAgent prompt 缺失失败。
