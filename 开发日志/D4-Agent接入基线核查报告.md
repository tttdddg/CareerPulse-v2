# D4-2.0 Agent接入基线核查报告

## 一、核查结论

三个冻结 Service 可以直接被 Agent 消费，不需要重构。当前主要缺口在
TrainingAgent、FeedbackAgent、交互状态建模、多 Service 调用日志和分步
Orchestrator 调度。

仓库不存在 ResourceAgent，冻结架构和 Agent 合同也不要求新增。
ResourceService 应作为 TrainingAgent 的第二个确定性 Service 接入。

本次核查未修改业务代码。核查时仅新增本报告文件。

## 二、当前真实架构

当前真实内部调用方向为：

1. 内部工具或未来平台适配层校验参数并加载会话；
2. CareerOrchestrator.run_stage() 调用指定 Agent；
3. Agent 从 CareerState 投影 Service 全参数；
4. 确定性 Service 返回裸 dict；
5. Agent 组装结果并调用 CareerState.apply_agent_data()；
6. StateRepository 原子持久化 CareerState 和 AgentLog。

CareerOrchestrator 默认六 Agent 顺序为：

ProfileAgent → JobAgent → MatchAgent → PathAgent → TrainingAgent → FeedbackAgent

CareerOrchestrator 当前有两种执行方式：

- run(state)：重置为 INITIALIZED，无条件顺序执行六个 Agent，生成 final_report，
  最后统一持久化；
- run_stage(state, agent_name)：执行单个已配置 Agent，并立即持久化。

BaseAgent 当前统一处理依赖检查、状态流转、fallback、状态写入和 AgentLog，
但一次 Agent 运行只能自动生成一条 ToolCallLog。

三个阶段4 Service 的真实入口为：

| 能力 | 真实入口 | 当前特征 |
|---|---|---|
| 训练生成 | TrainingService.generate(training_type, ability_gaps) | 从真实题库确定性选题 |
| 训练评分 | TrainingService.score(training_id, user_answer, agent_analysis) | LLM 只提供五档语义信号，Service 计算数值 |
| 资源推荐 | ResourceService.recommend_resources(ability_gaps, target_job) | 内部复用 AbilityTagNormalizer |
| 反馈 | FeedbackService.save_feedback(...) | 一次完成保存、调权和成长快照 |

## 三、当前 mock 与占位点

### A. TrainingAgent

backend/app/agents/training_agent.py 当前仍是完整 Mock：

- 没有导入或调用 TrainingService、ResourceService、LLMClient；
- _execute() 和 _fallback() 调用相同的 _build()，没有真实成功与失败差异；
- tool_name 仍为 mock_generate_training；
- 未设置真实 service_name；
- 从旧兼容字段 match_result.ability_gaps[].tag 读取缺口；
- 验收接口要求使用 match_result.skill_gaps[].dimension；
- 缺口为空时硬编码“沟通表达”，属于无依据补值；
- 硬编码 mock-training-001、训练标题、场景、任务描述和评分维度；
- 硬编码 A02 Demo 学习资源，没有调用 ResourceService；
- generated_at 使用当前时间，同输入不能逐字节复现；
- 不支持评分模式；
- 不处理 training_id、user_answer 或 agent_analysis；
- 没有 LLM 五档 coverage/reason 语义判定；
- 没有识别 Service 裸 dict 的 error 返回；
- 没有 TrainingAgent 专属测试。

### B. FeedbackAgent

backend/app/agents/feedback_agent.py 当前仍是占位实现：

- 没有导入或调用 FeedbackService；
- tool_name 仍为 mock_save_growth_feedback；
- 未设置 service_name = FeedbackService；
- 从 student_input.ratings 读取反馈，混用了画像输入字段；
- 实际只读取 satisfaction；
- path_rating、training_rating、resource_rating、comments 永远返回 None；
- 没有传入 skill_gaps、training_target_abilities、overall_score；
- 没有传入 completed_trainings、completed_phases；
- updated_priorities 永远为空；
- growth_archive_updated=True 是硬编码，没有真实更新成长记录；
- fallback 会虚构中性满意度 3；
- 没有检查 user_id，但真实 FeedbackService 要求 user_id 非空；
- 没有 FeedbackAgent 专属测试。

## 四、ResourceService 接入位置

### C. 是否存在或需要 ResourceAgent

当前不存在 ResourceAgent，也不应为了结构对称新增。

依据：

- docs/a02/03_ARCHITECTURE.md 只定义六个 Agent；
- docs/a02/05_AGENT_CONTRACTS.md 明确把调用 ResourceService 列为
  TrainingAgent 的职责；
- backend/app/agents/__init__.py 没有 ResourceAgent；
- CareerOrchestrator 默认链路没有 ResourceAgent。

建议接入关系：

| Service | Agent | State 输出 |
|---|---|---|
| TrainingService.generate/score | TrainingAgent | training_plan；评分结果字段待裁决 |
| ResourceService.recommend_resources | TrainingAgent | resource_result |
| FeedbackService.save_feedback | FeedbackAgent | feedback_result；成长快照字段待裁决 |

ResourceService 的 ability_gaps 应直接来自已按 priority 排序的
match_result.skill_gaps[].dimension。Agent 不再自行实现标签归一化，
AbilityTagNormalizer 继续由 ResourceService 内部复用。

## 五、CareerState 核查

### D. 当前字段

backend/app/orchestrator/career_state.py 当前包含：

- 会话：session_id、platform_session_id、user_id；
- 状态：status、error_type；
- 输入：student_input、target_job_input；
- 画像：student_profile、job_profile、trend_result；
- 匹配路径：match_result、path_plan、learning_plan、career_roadmap；
- 偏好：career_preferences、desired_city；
- 阶段4：training_plan、resource_result、feedback_result；
- 聚合日志：final_report、agent_logs。

其中 career_preferences 和 desired_city 已存在于代码，但没有出现在
docs/a02/04_API_CONTRACTS.md 的冻结 CareerState 清单中，属于既有代码与
契约的漂移。本步骤不处理该问题。

### E. 真实结果仍缺少的状态位置

现有字段已经能够承载：

- 训练题生成结果：training_plan；
- 资源推荐结果：resource_result；
- FeedbackResult 对外投影：feedback_result。

仍存在以下缺口：

1. 没有独立 TrainingScore 状态字段。
   TrainingService.score() 返回的 total_score、dimension_scores、
   ability_updates 没有明确持久化位置。不能未经契约批准将其塞进
   training_plan。

2. 没有完整成长快照状态字段。
   FeedbackService 返回 growth_snapshot，但冻结 feedback_result 只定义评分、
   优先级更新和 growth_archive_updated。

3. 没有干净的阶段4交互输入。
   当前没有 training_input/training_request 或 feedback_input。继续将 ratings
   放入 student_input 不合理。

技术负责人必须先裁决：

- TrainingScore 和 growth_snapshot 仅作为内部工具调用响应返回，不进入
  CareerState；或
- 为 CareerState 加法新增字段，并同步 docs/a02/04_API_CONTRACTS.md。

在裁决前不应擅自新增或命名公共字段。

## 六、CareerOrchestrator 当前行为

### F. 当前如何调用 Agent

- 构造器默认直接实例化六个 Agent；
- run() 对六个 Agent 逐个执行，不根据“等待用户回答”或“等待反馈”暂停；
- run_stage() 通过 Agent 名称查找并执行；
- Agent 通过 state.apply_agent_data() 修改状态；
- run_stage() 完成后持久化完整 State 和 AgentLog；
- 任一 Agent fallback 或失败都会使最终状态成为 PARTIAL。

阶段4交互存在两个结构问题：

1. 训练生成、用户作答、训练评分、反馈是多轮流程，不能由一次无条件 run()
   完成；
2. AgentLog 的数据库 run_key 固定为 session_id:agent_name。同一会话多次执行
   TrainingAgent 时，持久化日志会覆盖，不能证明每次调用都已留痕。

## 七、当前工具层组织方式

### G. Profile、Match、Path 等能力如何注册

当前有三套并存形态：

1. 历史 Mock 注册表

   backend/app/tools/mock_tools.py 使用 MOCK_TOOL_REGISTRY 字典注册七个旧名称。
   阶段4的训练、资源、反馈仍全部调用 Mock handler。

2. 正式 HTTP 平台工具

   backend/app/api/platform_tool_api.py 使用 FastAPI 路由静态注册，目前只有：

   - analyze_job_match；
   - generate_career_path。

   该层包含 Bearer 鉴权、固定 Pydantic Schema、请求指纹、幂等、超时和
   platform_tool_calls 持久化账本。

3. 标准 MCP

   backend/app/mcp/server.py 使用 server.tool 注册：

   - build_student_profile；
   - analyze_target_job；
   - analyze_job_match；
   - generate_career_path。

   CareerMCPToolService 负责校验参数、加载 CareerState、调用
   orchestrator.run_stage()、校验结果 Schema 并写调用账本。

实际仓库没有 docs/a02/03_ARCHITECTURE.md 中规划的动态 tool_registry.py。

### H. 阶段4应沿用的模式

内部接入应沿用真实 MatchAgent/PathAgent 模式：

- Agent 构造器支持注入 Service 和离线 LLM client；
- Agent 从 CareerState 提取 Service 全参数；
- Service 不读取 CareerState；
- LLM 输出使用 Pydantic 校验；
- LLM 只输出 coverage 和 reason，禁止数值；
- LLM 失败时将 agent_analysis=None 交给 TrainingService 的确定性 fallback；
- Service 继续返回裸 dict；
- Agent 判断 error 并完成 State 投影；
- Orchestrator 负责分步执行和持久化；
- 内部工具调用 Orchestrator，不绕过 Agent 直接调用 Service；
- 本阶段不修改 HTTP、MCP 或百宝箱注册。

mock_tools.py 只能作为旧名称和 Demo 语义参考，不能作为真实实现模板。

## 八、预计修改文件

### I. 必需修改

- backend/app/agents/training_agent.py
- backend/app/agents/feedback_agent.py
- 新增 backend/app/agents/tests/test_training_agent.py
- 新增 backend/app/agents/tests/test_feedback_agent.py

### 后续很可能需要修改

- backend/app/agents/base_agent.py
  - 用于准确记录 TrainingService 和 ResourceService 两条 ToolCallLog；
  - 若 TrainingAgent 可以局部实现，则避免扩大 BaseAgent 修改。

- backend/app/orchestrator/career_orchestrator.py
  - 支持生成、评分、资源、反馈的多轮分步执行；
  - 修正重复调用日志语义。

- backend/app/orchestrator/career_state.py
  - 仅在技术负责人批准新增公共字段后修改。

- 阶段4运输协议无关的内部工具适配及其测试
  - 应在 State/Agent 合同确定后再定文件名；
  - 不应现在预建空壳。

### 条件性文件

- backend/app/schemas/training_schema.py
- backend/app/schemas/feedback_schema.py
- 训练语义判定 Prompt

这些文件当前均不存在。内部 LLM 判定模型可以参考 MatchAgent，先作为
TrainingAgent 私有 Pydantic 模型；公共 Tool Schema 必须经技术负责人确认。

## 九、明确不修改文件

阶段4后半段应冻结：

- backend/app/services/training_service.py
- backend/app/services/resource_service.py
- backend/app/services/feedback_service.py
- backend/tests/test_training_service.py
- backend/tests/test_resource_service.py
- backend/tests/test_feedback_service.py
- backend/app/services/ability_normalization.py
- backend/app/data/ability_tags.json
- backend/app/data/ability_tag_aliases.json
- backend/app/data/training_tasks.json
- backend/app/data/resources.json
- Profile、Job、Match、Path Agent 与 Service
- backend/app/tools/mock_tools.py
- backend/app/api/**
- backend/app/mcp/**
- backend/app/platform/**
- backend/app/main.py
- backend/app/routers.py
- 数据库迁移
- 前端和公网部署文件

冻结契约文档也不由 Agent 实现步骤直接修改。如需新增公共字段，应先由技术负责人
更新契约。

## 十、风险点

1. Feedback 合同与验收 Service 有真实差异。
   Agent 合同写的是 FeedbackService.save/update_priorities/
   update_growth_archive 三步，实际验收入口是 save_feedback(...)。Agent 应适配
   真实接口，不能重构 Service。

2. 训练 fallback 文档已经过时。
   文档仍写默认分数60，但验收 Service 使用确定性文本窗口 fallback。固定60会违反
   数值归 Service 和不虚构红线。

3. 训练生成职责描述冲突。
   文档称题目标题和场景由 LLM 生成，真实 TrainingService 已从冻结题库确定性生成。
   Agent 不应重新生成题目内容。

4. BaseAgent 只能自动记录一个内部调用。
   TrainingAgent 同时调用 TrainingService 和 ResourceService，需要两条准确日志。

5. 重复 Agent 日志会覆盖。
   当前 run_key=session_id:AgentName 不支持同一会话的 TrainingAgent 生成和评分
   分别留痕。

6. FeedbackService 是进程内内存状态。
   服务重启后反馈和上一成长快照丢失。这是已验收边界，本轮不能擅自改数据库。

7. ResourceService 没有岗位资源数据。
   job_resources 必然为空并返回 job_resources_unavailable，Agent 不得补造岗位资源。

8. 当前完整回归无法复现155基线。

   本次只读运行结果：

   - 三个冻结 Service：61 passed；
   - tests + app/agents/tests：171 passed / 5 failed。

   5项失败均来自既有 ProfileAgent。仓库当前没有跟踪
   prompts/profile_agent/system.txt 和 user_template.txt，导致 ProfileAgent 转入
   fallback 或 Prompt 测试失败。该问题与三个阶段4 Service 无关，本步骤未修复，
   但进入阶段4集成前需要单独确认正确基线快照。

## 十一、百宝箱接入前最小完整链路

### J. 最小闭环

1. 会话中已有 student_profile、job_profile、match_result；
2. 内部训练生成请求经过参数校验；
3. Orchestrator.run_stage("TrainingAgent")；
4. TrainingAgent 从 skill_gaps[].dimension 读取能力缺口；
5. TrainingService.generate() 生成真实题库任务；
6. training_plan 持久化并记录真实日志；
7. 用户提交 training_id 和 user_answer；
8. TrainingAgent 调用离线可替换 LLM，只生成五档 coverage/reason；
9. TrainingService.score() 计算全部数值；
10. ResourceService.recommend_resources() 生成 resource_result；
11. TrainingScore 按技术负责人裁决的位置持久化或作为调用响应返回；
12. 用户提交真实 ratings；
13. FeedbackAgent 调用 FeedbackService.save_feedback()；
14. feedback_result 及成长快照按裁决写入；
15. CareerState、AgentLog、ToolCallLog 均可查询。

最低离线验收范围：

- 三种训练类型；
- 生成与评分两种模式；
- LLM 成功、无 LLM、非法 LLM 结构；
- Service error 裸 dict；
- 无资源和未知标签；
- 反馈好评、差评、中性和隐私拒绝；
- 同一 session 多轮状态连续更新；
- 每次 Agent/Service 调用日志真实且不覆盖；
- 全量回归不破坏冻结 Service；
- 不依赖真实外部 LLM；
- 不注册百宝箱、HTTP平台工具或新增 MCP 工具。

## 十二、D4-2.1 至 D4-2.5 推荐顺序

### D4-2.1：State 与内部调用合同裁决

- 明确训练交互输入如何进入 Agent；
- 明确 TrainingScore、growth_snapshot 是否进入 CareerState；
- 明确同一 Agent 多轮执行的日志身份规则；
- 如需公共字段，由技术负责人先更新 API_CONTRACTS。

### D4-2.2：TrainingAgent 真实化

- 接入 TrainingService；
- 完成生成与评分模式；
- 实现五档 LLM 语义判定；
- LLM 失败走 TrainingService 确定性 fallback；
- 增加完全离线单元测试。

### D4-2.3：ResourceService 接入 TrainingAgent

- 使用 skill_gaps[].dimension；
- 写入 resource_result；
- 记录 TrainingService、ResourceService 两条真实调用日志；
- 明确不新增 ResourceAgent。

### D4-2.4：FeedbackAgent 真实化

- 接入 FeedbackService.save_feedback()；
- 完成 ratings、skill_gaps、training_target_abilities、overall_score 投影；
- 完成 feedback_result 和成长快照处理；
- 增加完全离线单元测试。

### D4-2.5：Orchestrator 与内部工具闭环

- 完成生成、评分、资源和反馈的分步调度；
- 完成多轮状态持久化；
- 解决重复 AgentLog 覆盖；
- 增加离线端到端测试；
- 执行完整回归；
- 仍不接百宝箱、不注册平台工具、不做公网部署。

## 十三、本次核查验证

执行的冻结 Service 测试：

python -m pytest -p no:cacheprovider tests/test_training_service.py
tests/test_resource_service.py tests/test_feedback_service.py

结果：

61 passed

执行的当前 Agent/Service 全量核查：

python -m pytest -p no:cacheprovider tests app/agents/tests

结果：

171 passed, 5 failed

失败范围仅为既有 ProfileAgent Prompt 缺失问题。本报告不包含任何业务修复。
