# 《D4-2.3 FeedbackAgent实现完成报告》

## 1. 完成结论

D4-2.3 已在限定范围内完成：FeedbackAgent 已从读取 `student_input.ratings` 后返回占位结果的 mock，实现为真实消费冻结 `FeedbackService.save_feedback()` 的 Agent。

当前链路为：

```text
真实用户评分 + CareerState 真实上下文
  → FeedbackAgent 参数与来源投影
  → FeedbackService.save_feedback（校验、保存、调权、成长快照）
  → 完整 feedback_result
  → 可选 LLM 一句确认说明
  → state.feedback_result
```

本步骤没有修改 FeedbackService、TrainingService、ResourceService、CareerState、CareerOrchestrator 或平台工具，也没有重新实现 priority、growth_trend、competitiveness_score 或反馈存储算法。

## 2. 原 mock 行为如何移除

原 FeedbackAgent 存在以下占位行为，现已全部移除：

| 原行为 | 当前实现 |
| --- | --- |
| 只读取 `student_input.ratings` | 优先读取 `student_input.feedback`，兼容旧 `ratings` 和顶层反馈字段 |
| 没有 FeedbackService 调用 | 真实调用 `FeedbackService.save_feedback(**全部参数)` |
| satisfaction 缺失时默认 3 | 缺失或非法 satisfaction 直接失败，不补中性评分 |
| 硬编码 `updated_priorities=[]` | 完整使用 Service 返回的 priority 调整 |
| 硬编码 `growth_archive_updated=True/False` | 完整使用 Service 返回值 |
| path/training/resource rating 和 comments 永远为 None | 用户提供什么就按严格边界传什么，缺失则保持 None |
| fallback 虚构 satisfaction=3 | fallback 返回空结果，不声称反馈已保存 |
| `mock_save_growth_feedback` | 工具语义名改为 `save_growth_feedback` |
| 未设置 service_name | 设为 `FeedbackService` |

生产代码中不再存在 `feedback_saved=false`、默认中性满意度或本地 priority/trend 算法。

## 3. 每个参数的真实来源

| FeedbackService 参数 | 来源 | 处理规则 |
| --- | --- | --- |
| `session_id` | `state.session_id` | 不接受用户反馈 payload 覆盖 |
| `user_id` | `state.user_id` | 缺失时原样传 Service，由 Service 返回 missing_user_id |
| `satisfaction` | `student_input.feedback.satisfaction`；兼容旧 `ratings` | 必填、严格非 bool 的 1-5 整数 |
| `path_rating` | 用户反馈输入 | 可选 1-5 |
| `training_rating` | 用户反馈输入 | 可选 1-5；缺失时传 None，不调权 |
| `resource_rating` | 用户反馈输入 | 可选 1-5 |
| `comments` | 用户反馈输入 | Agent 只做类型/长度边界；隐私由 Service 最终校验 |
| `skill_gaps` | 最近 `state.match_result.skill_gaps` | 原样深拷贝，不筛选、不排序、不调权 |
| `training_target_abilities` | `training_plan.latest_score.training_id` 对应 TrainingTask 的 `target_abilities` | 找不到 latest_score 时取 trainings 最后一项；无训练任务传 None |
| `abilities` | 优先 `student_profile.abilities`，否则真实 `ability_dimensions` | 原样深拷贝，不补标签、等级或时间戳 |
| `completed_trainings` | 当前 State 无可靠累计字段 | 按冻结规格默认值传 0，不把 latest_score 虚构为累计次数 |
| `completed_phases` | 当前 State 无可靠完成字段 | 传 0；path phases 是计划，不视为已完成 |
| `overall_score` | 最近 `state.match_result.overall_score` | 缺失传 None，由 Service 输出 unavailable flag |

“最近一次 TrainingTask”优先以最近评分结果中的 `training_id` 定位，而不是简单取生成列表最后一题，避免多类型训练生成时关联错误题目。

## 4. Service / Agent 职责边界

### FeedbackService 独占职责

- session/user/ratings/comments 最终校验；
- comments 隐私识别；
- feedback 内存保存；
- 差评升优先级、好评回落、中性不调；
- satisfaction≤2 时禁止硬调权；
- competitiveness_score；
- completed 数值合成；
- improving/stable/declining 判断；
- growth snapshot 保存；
- 所有 data_quality_flags。

### FeedbackAgent 仅负责

- 从用户输入读取评分；
- 从 State 投影真实上下文；
- 调用 Service；
- 识别 Service 裸 dict error；
- 验证 Service 成功结果结构并完整透传；
- 在成功结果之后生成可选的一句自然语言确认。

测试使用固定 Service 返回了与输入推导无关的 priority 和 growth 数值，Agent 输出逐字段保持一致，证明 Agent 没有二次计算或覆盖。

## 5. 输出透传

以下五个 Service 字段完整保留在 `state.feedback_result`：

```json
{
  "feedback_saved": true,
  "growth_archive_updated": true,
  "updated_priorities": [],
  "growth_snapshot": {
    "competitiveness_score": 0.0,
    "completed_trainings": 0,
    "completed_phases": 0,
    "growth_trend": "stable"
  },
  "data_quality_flags": []
}
```

Agent 只加法加入：

```json
{
  "natural_language_summary": "一句确认说明"
}
```

该字段不能携带或替换任何 priority/growth 业务字段。

## 6. Schema 与 Prompt

新增 `feedback_schema.py`，包含：

- `FeedbackAgentInput`：Agent 用户评分输入边界；
- `FeedbackToolInput`：含 session_id/user_id 的未来工具参数边界，本步骤没有注册工具；
- `FeedbackServiceResult`：冻结 Service 裸 dict 的消费校验；
- `PriorityUpdate` / `GrowthSnapshot`：确定性结果结构；
- `FeedbackNaturalLanguageExplanation`：LLM 仅允许输出 `{"message":"..."}`；
- `FeedbackAgentResult`：五个 Service 字段加一句说明。

新增 `prompts/feedback_agent/explain.txt`。Prompt 只接收 Service 成功结果，不包含 comments、session_id、user_id、画像、训练答案或能力证据；LLM 只能写一句确认，不得重算或修改 priority、competitiveness_score、growth_trend 和 completed 数值。

## 7. 隐私与 fail-safe

- comments 不发送给 LLM，也不写入 AgentLog 摘要；
- comments 隐私违规会到达 FeedbackService，由 Service 返回 `privacy_violation`；
- Service `{error: ...}` 被转换为 `FeedbackServiceError`，由 BaseAgent 返回标准 failed 结果，不把 error dict 当成功结果；
- missing user_id 到达 Service 并返回标准失败；
- missing/invalid satisfaction 在严格 Agent 输入边界失败，Service 不被误调用；
- 正常 CareerState 构造已阻止 missing session_id；隔离测试绕过模型边界验证 Agent 仍不吞 Service 的 missing_session_id error；
- LLM 解释失败时，真实反馈已经保存，五个 Service 字段保持不变，仅使用固定文字“反馈已保存，成长档案已更新。”；
- Service 或输入失败时 fallback 返回空 dict，不虚构保存成功、满意度或成长结果。

## 8. 修改文件

### 业务实现

| 文件 | 变更 |
| --- | --- |
| `backend/app/agents/feedback_agent.py` | 从 mock 替换为真实 FeedbackService 消费、状态投影、结果验证、可选说明和安全 fallback |
| `backend/app/schemas/feedback_schema.py` | 新增反馈输入、工具参数、Service 输出和 LLM 边界 Schema |
| `prompts/feedback_agent/explain.txt` | 新增一句式反馈确认 prompt |
| `backend/app/agents/tests/test_feedback_agent.py` | 新增 20 项完全离线 FeedbackAgent 测试 |

### 开发记录

| 文件 | 变更 |
| --- | --- |
| `开发日志/D4-FeedbackAgent实现完成报告.md` | 本报告 |
| `task_plan.md` / `findings.md` / `progress.md` | planning-with-files 过程记录，不包含业务逻辑 |

## 9. 测试结果

所有 FeedbackAgent 测试均使用本地 mock LLM，无真实网络调用。

### 覆盖清单

1. 不再返回硬编码 `feedback_saved=false`；
2. 调用真实 FeedbackService 并可读取保存记录；
3. skill_gaps 原样来自 match_result；
4. training_target_abilities 来自最近已评分 TrainingTask；
5. overall_score 来自 match_result；
6. 差评 priority 调整来自 Service；
7. 好评回落来自 Service；
8. satisfaction≤2 不硬调权；
9. growth_snapshot 原样透传；
10. Service error 转为 Agent 标准失败；
11. 固定 Service 数值证明 Agent 不计算 trend/priority；
12. LLM 解释失败不影响真实反馈保存；
13. missing session_id/user_id/invalid satisfaction/privacy_violation；
14. 无 training_rating、无 skill_gaps、无 recent training；
15. tools 参数 Schema；
16. comments 不进入 LLM 或日志；
17. 旧 `student_input.ratings` 兼容；
18. 全部离线、结构稳定。

### 执行结果

| 测试范围 | 结果 |
| --- | --- |
| FeedbackService 原测试 + FeedbackAgent 新测试 | `40 passed`（20 + 20） |
| 排除既有 ProfileAgent 阻塞项的适用回归 | `207 passed` |
| 完整 `backend/tests + backend/app/agents/tests` | `212 passed, 5 failed` |
| `python -m compileall -q app tests` | 通过 |

完整回归中的 5 个失败仍全部来自既有 ProfileAgent：仓库缺少 `prompts/profile_agent/system.txt` 和 `prompts/profile_agent/user_template.txt`。D4-2.2 完整回归为 `192 passed, 5 failed`；本步骤新增 20 项通过后为 `212 passed, 5 failed`，失败数量与原因没有增加。该问题不属于本步骤授权范围，因此未越界修复。

## 10. 冻结范围确认

以下文件或目录没有本步骤差异：

- `backend/app/services/feedback_service.py`；
- `backend/app/services/training_service.py`；
- `backend/app/services/resource_service.py`；
- `backend/app/orchestrator/career_state.py`；
- `backend/app/orchestrator/career_orchestrator.py`；
- `backend/app/platform/**`；
- 百宝箱与公网部署配置。

## 11. 已知边界

1. FeedbackService 的 feedback/growth 存储仍是进程内实例字典；进程重启后历史丢失，这是冻结 Service 的已验收边界。
2. 当前没有可靠 completed_trainings/completed_phases 历史，因此均传 0；不能用生成题数或计划阶段数冒充完成数。
3. 当前只保存 FeedbackService 最新增长快照，没有新增 CareerState 顶层 GrowthArchive 字段；完整状态统一仍留给 D4-2.4。
4. `abilities` 当前只由 Service 暂存、不参与计算；统一画像时原样传 ability_dimensions，不在 Agent 转换为另一套能力模型。
5. LLM 一句说明是本轮用户要求下的可选加法；旧 Agent 合同写“纯确定性不调用 LLM”，实际业务结果仍完全确定性，LLM 失败不影响保存。
6. `FeedbackToolInput` 只是严格参数边界，本步骤没有注册 `save_growth_feedback` 平台/MCP 工具。
7. BaseAgent 会为本次 Agent 调用记录一条隐私安全 ToolCallLog；多轮日志身份和统一内部工具链仍属于后续 Orchestrator 阶段。

## 12. 验收结论

D4-2.3 已完成 FeedbackAgent 真实化：所有输入均来自用户或真实 State，Service 五字段完整透传，priority/trend/growth/storage 均由冻结 FeedbackService 独占，错误不被吞掉，LLM 失败不影响真实保存，新增测试全部通过。完整回归只保留此前已知的 5 个 ProfileAgent prompt 缺失失败。
