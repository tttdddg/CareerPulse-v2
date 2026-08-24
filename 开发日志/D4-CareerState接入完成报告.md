# 《D4-CareerState接入完成报告》

## 1. 完成结论

D4-2.4 已按最小必要原则完成。阶段4真实结果继续使用冻结 CareerState 已有的三个顶层容器：

- `training_plan`
- `resource_result`
- `feedback_result`

本步骤没有新增同义顶层字段，也没有修改数据库表或公开 API 字段。当前训练题、最近评分、ability updates 与 growth snapshot 均从上述真实结果中投影读取，避免同一数据出现两份状态而失去一致性。

CareerState 新增了统一、fail-safe、返回深拷贝的读取接口；TrainingAgent 与 FeedbackAgent 已改为通过这些接口消费上下文。Agent 结果写入 State 时也会深拷贝，防止调用方对象或不同 session 共享嵌套可变数据。

## 2. 新增 / 修改字段

### 2.1 序列化字段

**没有新增序列化顶层字段。** 现有字段已经覆盖阶段4需求：

| 业务数据 | 实际存储位置 | 写入方 | 读取方 | 生命周期 | 无历史默认值 |
|---|---|---|---|---|---|
| 当前/最近训练题 | `training_plan.trainings` | TrainingAgent generate | TrainingAgent score、FeedbackAgent，经 CareerState 访问器读取 | 当前 session 快照并随 State 持久化 | `training_plan=None`，读取返回 `None` |
| 最近训练评分 | `training_plan.latest_score` | TrainingAgent score | CareerState/UI/后续节点 | 当前 session 最近一次评分 | 读取返回 `None` |
| 最近 ability updates | `training_plan.latest_score.ability_updates` | TrainingService 产出，TrainingAgent 原样写入 | CareerState/UI/后续节点 | 跟随最近评分 | 读取返回 `[]` |
| 当前资源推荐 | `resource_result` | TrainingAgent 调用 ResourceService 后写入 | Orchestrator final report、UI/后续节点 | 当前 session 最近一次推荐 | `None` |
| 最近反馈结果 | `feedback_result` | FeedbackAgent | Orchestrator final report、UI/后续节点 | 当前 session 最近一次反馈 | `None` |
| growth snapshot | `feedback_result.growth_snapshot` | FeedbackService 产出，FeedbackAgent 原样写入 | CareerState/UI/后续节点 | 跟随最近反馈结果 | 读取返回 `None` |
| completed 统计 | 不新增 State 字段 | 无可靠写入方 | FeedbackAgent 继续使用冻结规格默认值 | 不建立伪历史 | `0 / 0` 仅作为 Service 调用默认值 |
| 反馈调权 priority | `feedback_result.updated_priorities` | FeedbackService 产出，FeedbackAgent 原样写入 | 当前仅供结果展示/未来节点读取 | 跟随最近反馈 | 不反写 `match_result`，不建立副本 |

### 2.2 新增 CareerState 读取接口

- `get_skill_gaps()`：读取最近真实 `match_result.skill_gaps`。
- `get_training_task(training_id=None)`：显式 ID 时精确查找；未给 ID 时优先选择最近评分对应任务，否则选择当前列表最后一个任务。
- `get_latest_training_score()`：读取 `training_plan.latest_score`。
- `get_latest_ability_updates()`：从最近评分投影 ability updates。
- `get_latest_training_target_abilities()`：从最近训练上下文投影目标能力。
- `get_match_overall_score()`：读取 MatchService 已确定的 overall score，不重算。
- `get_growth_snapshot()`：从最近反馈结果投影成长快照。

所有返回可变对象的接口均返回深拷贝；读取方修改返回值不会污染 CareerState。

## 3. 写入与读取链路

```text
MatchAgent -> match_result
                  | skill_gaps / overall_score（CareerState 安全读取）
                  v
TrainingAgent -> TrainingService -> training_plan
                  | score 对应 task / target_abilities（CareerState 安全读取）
                  +-> ResourceService -> resource_result
                  v
FeedbackAgent -> FeedbackService -> feedback_result
                                      +-> growth_snapshot

CareerOrchestrator.persist -> 完整 CareerState JSON 快照
CareerOrchestrator.get_session -> CareerState.model_validate 恢复
```

Service 仍只接收完整参数，不读取 CareerState；CareerState 访问器不做评分、调权、趋势计算或标签归一化。

## 4. 多训练上下文规则

- 评分模式必须按 `training_id` 精确找到对应 TrainingTask，确保 evaluation criteria 与 target abilities 来自同一道真实题。
- 查询“最近训练上下文”时，如 `latest_score.training_id` 能匹配任务，则使用该已评分任务。
- 尚无评分时使用 `trainings` 中最后一个真实任务。
- 兼容旧状态：若旧快照中的 latest score 指向已不存在的任务，非精确查询会安全回退到最后一个可用任务；精确查询仍返回 `None`。

## 5. completed 与 priority 裁决

当前仓库没有可靠的 completed trainings / completed phases 维护机制。`training_plan` 表示题目生成/最近评分，`path_plan` 表示计划，不等价于完成次数，因此本步骤没有虚构计数或新增字段，FeedbackAgent 继续传入冻结 FeedbackService 允许的 `0` 默认值。

`updated_priorities` 已完整存在于 `feedback_result`。当前执行顺序中 FeedbackAgent 后没有继续消费 priority 的业务节点，本步骤不另建 priority 状态，也不修改或反写冻结的 `match_result.skill_gaps`。

## 6. 兼容性与隔离

- 旧 CareerState 快照缺少阶段4结果时仍可正常初始化；三个已有字段默认为 `None`。
- Profile / Match / Path 原有字段名、写入方式和 Orchestrator final report 聚合未改变。
- `apply_agent_data()` 仍只允许声明过的 State 字段，但现在写入深拷贝，避免 Agent 返回对象被外部继续修改。
- `training_plan`、`resource_result`、`feedback_result` 在 CareerState 初始化时进行深拷贝，避免两个 session 由同一嵌套对象构造时相互污染。
- SQLite 持久化往返验证了 task、score、ability updates、resource、feedback、growth snapshot 均可随完整 State 恢复。
- 没有保存 LLM reasoning、chain-of-thought 或 prompt 中间数据。

## 7. 修改文件

- `backend/app/orchestrator/career_state.py`
  - 增加阶段4安全读取接口。
  - 增加阶段4容器入模深拷贝及 Agent 写入深拷贝。
- `backend/app/agents/training_agent.py`
  - skill gaps 和 training task 改从 CareerState 统一接口读取。
- `backend/app/agents/feedback_agent.py`
  - skill gaps、最近训练目标能力、overall score 改从 CareerState 统一接口读取。
- `backend/tests/test_career_state_stage4.py`
  - 新增 10 项状态兼容、读写、持久化和 session 隔离测试。
- `task_plan.md`、`findings.md`、`progress.md`
  - 记录本步骤计划、架构裁决与验证过程。
- `开发日志/D4-CareerState接入完成报告.md`
  - 本报告。

## 8. 明确未修改

- `backend/app/services/training_service.py`
- `backend/app/services/resource_service.py`
- `backend/app/services/feedback_service.py`
- `backend/app/orchestrator/career_orchestrator.py`
- ProfileAgent / MatchAgent / PathAgent
- 数据库 Schema / migration
- 百宝箱配置、平台工具注册、MCP 注册与公网部署

## 9. 测试结果

### 9.1 D4-2.4 新增状态测试

- `backend/tests/test_career_state_stage4.py`
- 结果：`10 passed`

覆盖：旧 State 初始化、Profile/Match/Path 既有字段写法、training task/score/ability updates、resource、feedback、growth snapshot、空历史、多训练最近上下文、旧悬空 score 兼容、跨 session 隔离、SQLite 恢复。

### 9.2 阶段4与既有 Match/Path 定向回归

- CareerState + TrainingAgent + FeedbackAgent + MatchAgent + PathAgent + stage3 E2E
- 结果：`80 passed / 11 subtests`

### 9.3 冻结 Service 回归

- TrainingService + ResourceService + FeedbackService
- 结果：`61 passed / 14 subtests`

### 9.4 全量回归

- 完整收集结果：`222 passed / 96 subtests，5 failed`
- 5 项失败均位于既有 `test_profile_agent.py`，原因仍为仓库缺少 `prompts/profile_agent/system.txt` 与 `user_template.txt`；与 D4-2.1～D4-2.3 的已知基线相同，本步骤未扩大范围修复。
- 排除该已知 ProfileAgent 阻塞文件后的适用全量回归：`217 passed / 96 subtests`。
- `python -m compileall -q app tests`：通过。
- `git diff --check`：通过，仅有现有 LF/CRLF 提示。

## 10. 已知边界

- CareerState 只保存“当前计划/最近结果”，没有在本步骤引入完整训练历史表或累计完成统计。
- FeedbackService 的历史归档实现仍遵循其冻结实现；CareerState 仅保留最近 feedback result 与 growth snapshot。
- 反馈调权结果尚无 FeedbackAgent 之后的消费者，因此只保留 Service 返回，不修改 match gap 顺序或 priority。
- 本步骤未做阶段4平台工具/API 注册；这些能力仍只存在于内部 Agent / Service / State 链路。
- 当前测试环境无法写 pytest cache，出现 `PytestCacheWarning`，不影响测试执行结果。

## 11. 冻结范围确认

三个冻结 Service 均无差异；CareerOrchestrator、platform 与百宝箱配置均无差异。未执行 Git commit、平台注册或部署。
