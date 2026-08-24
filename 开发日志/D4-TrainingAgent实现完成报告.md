# 《D4-2.1 TrainingAgent实现完成报告》

## 1. 完成结论

D4-2.1 已在限定范围内完成：`TrainingAgent` 已从 mock / 硬编码实现改为真实消费冻结的 `TrainingService`，训练题生成、答案语义判定、确定性评分和自然语言反馈四段链路均已接通。

本步骤未修改 `TrainingService`、`ResourceService`、`FeedbackService`、`CareerState`、`CareerOrchestrator`、百宝箱配置或公网部署配置，也未重新实现任何评分算法。

## 2. 修改文件

| 文件 | 变更内容 |
| --- | --- |
| `backend/app/agents/training_agent.py` | 移除 mock 训练题与硬编码评分，接入 `TrainingService.generate()` / `score()`、结构化 LLM 判定、自然语言反馈及 fail-safe |
| `backend/app/schemas/training_schema.py` | 新增 Agent 输入、训练题、五档语义判定、Service 评分结果和自然语言反馈边界 Schema |
| `prompts/training_agent/score.txt` | 新增训练答案五档覆盖度判定 prompt |
| `prompts/training_agent/feedback.txt` | 新增确定性评分结果的自然语言解释 prompt |
| `backend/app/agents/tests/test_training_agent.py` | 新增 15 项离线 TrainingAgent 测试 |

## 3. Agent 新链路

### 3.1 训练题生成

```text
training_type + ability_gaps
  -> TrainingAgent 参数校验
  -> TrainingService.generate(training_type, ability_gaps)
  -> TrainingTask Schema 边界校验
  -> state.training_plan
```

- Agent 不生成题目、不复制 Service 选题逻辑。
- `ability_gaps` 原样透传给 Service。
- 兼容当前完整流程：未提供显式训练请求时，Agent 按冻结的 `TRAINING_TYPES` 逐类调用 Service，生成真实训练题，不再返回旧 mock 数据。

### 3.2 训练评分

```text
training_id + user_answer + 当前 training task
  -> LLM 对 evaluation_criteria 做五档语义判断
  -> TrainingService.score(training_id, user_answer, agent_analysis)
  -> TrainingScore Schema 边界校验
  -> 可选 LLM 自然语言点评
  -> state.training_plan.latest_score
     + state.training_plan.natural_language_feedback
```

- `agent_analysis` 是 LLM 的语义判定信号，Agent 不把它转换成分数。
- `dimension_scores`、`total_score`、`ability_updates` 均直接取自 Service 返回值。
- Agent 不二次计算、修正或覆盖 Service 数值。

## 4. Prompt 输入输出格式

### 4.1 五档语义判定 prompt

输入包含：

- 当前训练题；
- 用户答案；
- 当前任务的 `evaluation_criteria`；
- 每个合法 `dimension` 及其判定标准。

LLM 唯一允许的结构化输出为：

```json
{
  "dimensions": [
    {
      "dimension": "来自当前 evaluation_criteria 的维度",
      "coverage": "fully|mostly|partial|barely|missing",
      "reason": "简短且不含隐私信息的理由"
    }
  ]
}
```

约束如下：

- 禁止输出额外维度；
- 禁止输出 `score`、`total`、`total_score`、`level`、`probability`、`percentage` 或任何业务数值评分；
- `reason` 必填，最大 200 字符；
- Schema 拒绝额外字段、重复维度、超长理由及可识别的邮箱、手机号或身份证号。

### 4.2 自然语言反馈 prompt

输入包含：题目、用户答案、Service 返回的 `dimension_scores`、`total_score`、`improvement_suggestions` 和 `ability_updates`。

输出仅包含：

```json
{
  "commentary": "总体点评",
  "strengths": ["已有表现"],
  "next_steps": ["下一步建议"]
}
```

该 prompt 明确要求 LLM 只能解释既有结果，不得重算、修改或覆盖任何 Service 数值。

## 5. LLM / Service 数值职责边界

| 能力 | LLM | TrainingService |
| --- | --- | --- |
| 训练题生成 | 不参与 | 唯一生成来源 |
| 答案理解 | 对每个既有维度输出五档覆盖度和文字理由 | 校验并消费判定信号 |
| 维度分数 | 禁止输出 | 唯一计算来源 |
| 总分 | 禁止输出 | 唯一计算来源 |
| 能力更新 | 禁止计算 | 唯一计算来源 |
| 用户点评 | 解释 Service 已有结果 | 提供确定性评分和改进建议基础数据 |

Service 继续返回裸 `dict`；新增 Pydantic Schema 仅用于 Agent / LLM 边界和 Service 返回值的消费校验，没有倒逼修改 Service Schema。

## 6. Fail-safe

- `TrainingService.generate()` / `score()` 返回 `{error: ...}` 或抛出异常时，转换为现有 `BaseAgent` 标准失败结果，不伪造训练题或评分。
- LLM 语义判定调用失败、结构不可用或维度越界时，Agent 将 `None` 交给 Service，由冻结 Service 执行自身 fallback；Agent 不复制 fallback 算法。
- LLM 返回数值字段时，不由 Agent 清洗后继续评分，而是将原始污染信号交给 Service；Service 按冻结契约拒收并进入 fallback，同时保留拒收标记。
- LLM 遗漏维度时，保留已提供维度，缺失维度由 Service 按自身规则处理。
- 自然语言反馈失败时，评分仍然成功；文字部分使用 Service 的 `overall_comment` 和 `improvement_suggestions` 形成安全回退，不影响任何分数。
- Agent 日志摘要不记录 `user_answer` 原文，避免训练回答中的隐私信息进入工具调用日志。

## 7. 测试结果

全部 TrainingAgent 测试使用本地 mock LLM，无真实网络依赖。

| 测试范围 | 命令结果 |
| --- | --- |
| TrainingService 原单测 + TrainingAgent 新测试 | `44 passed`（29 + 15） |
| 当前适用回归：Service 测试 + Match / Path / Training Agent | `181 passed` |
| MatchAgent 原测试 | 10 项通过，包含在上述 181 项中 |
| PathAgent 原测试 | 9 项通过，包含在上述 181 项中 |
| 用户要求的完整 `tests + app/agents/tests` | `186 passed, 5 failed` |

新增 15 项测试覆盖：

1. `generate` 确实调用 `TrainingService`；
2. `ability_gaps` 正确透传；
3. 训练题完全来自 Service，不再使用硬编码题目；
4. LLM 五档信号及严格结构化输出；
5. 缺失维度交由 Service 正确处理；
6. 数值污染字段由 Service 拒收并 fallback；
7. 所有评分数值来自 Service；
8. LLM feedback 失败不影响评分；
9. Service error 转为 Agent 标准失败结果；
10. 相同输入在 mock LLM 下业务结构稳定；
11. 旧完整流程改用三个真实 Service 训练类型；
12. 日志不泄露用户答案；
13. 训练 Schema 的五档、长度、隐私和额外字段约束。

完整命令中的 5 个失败全部来自既有 `ProfileAgent`：仓库缺少 `prompts/profile_agent/system.txt` 与 `prompts/profile_agent/user_template.txt`。该问题在 D4-2.0 核查时已存在，当时为 `171 passed, 5 failed`；本步骤新增 15 项均通过，失败数量和失败原因没有增加。由于 Profile 文件不在 D4-2.1 允许范围内，本步骤未越界修复。

## 8. 冻结 Service 改动确认

- `backend/app/services/training_service.py`：未修改；
- `backend/app/services/resource_service.py`：未修改；
- `backend/app/services/feedback_service.py`：未修改；
- AbilityTagNormalizer：未修改、未重新实现；
- Service 评分与 fallback 算法：未复制到 Agent。

同时未修改 `CareerState`、`CareerOrchestrator`、平台工具注册、百宝箱或部署配置。

## 9. 已知边界与后续注意事项

1. 当前冻结的 `CareerState` 只有 `training_plan`，没有独立 `training_score` 字段。因此本步骤把最新评分和自然语言反馈增量放入 `training_plan.latest_score` 与 `training_plan.natural_language_feedback`；后续若形成公共字段，需由技术负责人确认并同步 `API_CONTRACTS.md`，不能在本步骤擅自改 State。
2. 显式训练请求目前通过 `student_input.training`（兼容顶层同名字段）进入 Agent，这是在不修改 State / Orchestrator 前提下的最小接入方式；后续内部工具链阶段应统一入口。
3. 当前只保存最新一次评分，不维护训练评分历史；历史存储属于后续状态与持久化契约范围。
4. `generated_at` 属于运行元数据，因此不同运行时间会变化；在相同 mock LLM 下，训练题和评分业务结构保持稳定。
5. 旧完整流程会为冻结的三个训练类型各调用一次 Service；当前 `BaseAgent` 仍记录一次 Agent 工具调用日志。若后续要求逐次 Service 调用审计，需要在统一日志架构阶段处理，不能仅为 TrainingAgent 私建日志机制。
6. 仓库既有 Profile prompt 缺失会阻止全量测试全绿，也会使平台 mock 完整链路停在 ProfileAgent；该问题与本次 TrainingAgent 变更无关，但应在对应 Profile / prompt 任务范围内修复后重新执行全量验收。

## 10. 验收结论

D4-2.1 的 TrainingAgent 真实化链路已完成，冻结 Service 未被改动，新增测试全部通过，Match / Path Agent 未发生回归。仓库全量回归的唯一未清零项仍是 D4-2.0 已知的 ProfileAgent prompt 文件缺失，不属于本步骤授权修改范围。
