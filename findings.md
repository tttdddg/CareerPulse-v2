# D4-2.6 阶段4最终端到端验证发现

## 初始基线

- D4-2.5 已有 14 项内部工具测试，分别覆盖四个动作、主要异常、session 隔离、幂等和 real/mock 区分，但尚需确认是否存在一条连续复用同一 State 的 Profile → Match → Path → Training → Resource → Feedback 验收测试。
- 上一步完整回归为 `236 passed / 96 subtests，5 failed`；5 项已知失败来自缺失的 ProfileAgent prompt 文件。D4-2.6 必须重新执行完整套件，并据事实分类，不能沿用旧结果代替本轮证据。
- 当前改动集中于 Agent、CareerState、CareerOrchestrator、内部 tool service、边界 Schema 和测试；三个冻结 Service 无 diff。
- 已知 session-catchup 脚本不存在，本轮按 planning skill 规则不重复调用。

## 待验证

- 阶段3 Profile/Match/Path 在当前完整工作树中能否全绿，以及如何用离线固定 Agent/Service 形成连续主链。
- 训练生成是否从真实 match_result 的有序 skill gaps 取值，评分是否由 mock LLM 只给 coverage/reason、数值全由 TrainingService 返回并写回 State。
- ResourceService 输出四类字段是否原样落 State，unknown tag 是否通过冻结逻辑产生 flag。
- FeedbackAgent 是否自动投影 session/user/skill gaps/training targets/overall score，并保存调权和 growth snapshot。
- 非法 coverage、数值字段、隐私、无上下文、新 session 的 fail-safe 是否都有端到端证据。

## 覆盖盘点（第一轮）

- `test_stage3_e2e.py` 已证明 Match/Path 的 HTTP 分步主链、Service 等值、持久化、日志隐私、幂等与 LLM 不覆盖数值；其 prepare 接口接收冻结的真实 student/job profile，并不执行 ProfileAgent。
- `test_stage4_internal_tools.py` 当前 14 项是按动作独立 seed State：已覆盖四动作、无 match、无 training、非法 type/rating、隐私、LLM 失败、ResourceService 异常、session 隔离和 real/mock；尚缺同一 session 上从真实 MatchService 输出连续流入全部阶段4动作的测试。
- TrainingAgent 单测已覆盖五档枚举、额外/缺失维度、非法数值字段、Service 数值来源和评语失败；TrainingService 单测已覆盖非法 coverage、数值字段 fallback、隐私和确定性。
- ResourceService 单测已覆盖 unknown tag、无资源、输出字段、顺序和确定性；FeedbackAgent/Service 已覆盖 rating、隐私、调权、growth snapshot 和确定性。
- D4-2.6 最小新增测试应聚焦“同一 State 连续接线”和“真实 MatchService 结果被 Training/Resource/Feedback 消费”，避免复制已有 Service 算法单测。

## 连续验收设计

- 连续测试将复用阶段3匿名 `student_profile()` / `job_profile()`，由真实 MatchAgent→MatchService 和 PathAgent→PathService 在同一 CareerState 中运行，再通过 D4-2.5 内部工具完成 Training、Resource、Feedback。
- Match/Path 使用永远离线失败的 LLM double，证明其确定性 Service/fallback 不依赖公网；Training 使用只返回合法 `TrainingAnalysis` 和解释 Schema 的 mock LLM，覆盖真实五档主路径。
- 对 `cross_role_communication`，应由真实 skill gaps 驱动 TrainingService 选择任务；测试不硬编码选题算法，而是用冻结 Service 对相同 gaps 的结果做等值比较，并额外要求 target abilities 与真实 gaps 有交集。
- 评分将把同一合法 coverage signal 独立传给冻结 TrainingService，逐字段比较 `dimension_scores`、`total_score`、`ability_updates`，从而证明 Agent 未重算。
- 反馈使用低 training rating，记录 FeedbackService 的真实调用参数和返回结果，核对 session/user、skill gaps、training targets、overall score 均由 State 自动补齐。
- ProfileAgent 的两个 prompt 文件仍缺失，这是 D4 之前的仓库问题；D4-2.6 不新增或猜测阶段3 prompt。阶段3 ProfileAgent 全套结果必须在最终完整回归中按既有失败如实分类。

## 实际确定性样本

- 阶段3匿名 fixture 经真实 MatchService 得到 `overall_score=82.92`，有序 skill gaps 为需求分析、产品规划、沟通表达、用户研究（终端中文编码显示异常，但 Python 数据本身正常）。
- 相同 gaps 下冻结 TrainingService 能确定性选择任务；连续测试将动态调用同一冻结 Service 生成 expected task，不硬编码具体 ID。
- ResourceService 对该真实 gaps 返回 3 条 learning resources，并产生 `no_resource_for_tag:用户研究` 与 `job_resources_unavailable`；这可同时验证真实资源、缺资源 flag 与顺序投影。
- TrainingAgent 对一般非法 coverage 会在 Agent Schema 边界将信号降为 `None` 后交给 Service fallback；对含数值字段的原始映射会保留给 Service 明确拒收并输出 `agent_analysis_rejected:numeric_field`。两种行为均需在工具级验证不抛异常且数值来自 Service。

## 新增连续验收结果

- 新增 `backend/tests/test_stage4_final_e2e.py` 共 4 项，首轮 `4 passed`，没有发现 D4 接线实现错误。
- 完整同 session 用例验证了阶段3 profile contract → Match → Path，再经内部工具完成 Training generate/score、Resource、Feedback；所有业务结果均与相同输入下的冻结 Service 输出等值。
- 合法 mock LLM 动态读取当前 task criteria，只返回 coverage/reason；测试逐字段证明 dimension scores、total score、ability updates 来自 TrainingService。
- 非法 coverage 在 Agent Schema 边界退为 Service fallback；数值污染由 Service 输出拒收 flag；两条工具调用均返回结构化成功结果，无未捕获异常。
- unknown tag 通过内部资源工具返回空资源和确定性 flag，且未发生任何 LLM 调用。
- 首次 feedback 返回 stable growth 和 `first_growth_snapshot`，低 training rating 的 priority 更新与 FeedbackService 原始结果完全一致。

## 定向回归

- D4-2.1～D4-2.6 相关 Agent、State、内部工具、最终 E2E 加三个冻结 Service：`130 passed / 25 subtests`。
- 阶段3 Match/Path Agent、stage3 E2E、TBox stage3 tools、MCP server：`40 passed`。
- 两组均只有当前环境 `.pytest_cache` 无写权限警告，不影响测试执行或业务持久化测试；没有未捕获异常或网络调用。

## 已知失败分类

- ProfileAgent 单文件：`5 failed, 5 passed`。所有失败均由 `prompts/profile_agent/system.txt` 和 `user_template.txt` 不存在触发：4 项本应调用 mock LLM 的测试提前进入规则 fallback，1 项 prompt 安全测试直接报加载失败。
- 分类：既有阶段3实现资产缺失，不是 D4-2.1～D4-2.6 接线实现错误，也不是本轮测试脚本错误或规格歧义。
- 依据用户范围，本轮不补写未知业务 prompt、不改 ProfileAgent 测试预期；最终验收必须明确指出“阶段4内部链路全绿，但仓库完整套件仍因既有 Profile prompt 阻塞而非全绿”。
- 完整套件实际结果为 `245 passed / 96 subtests，7 failed`。新增的 2 项失败来自 `app/platform/tests/test_mock_career_flow.py`，其默认全链包含 ProfileAgent；prompt 加载失败令 final report 为 partial，旧 TBox mock envelope 随之返回 code=-4。
- 因而 7 项不是 7 个独立问题，而是两个 prompt 文件缺失产生的 5 个直接失败和 2 个级联失败；D4 阶段4真实内部链路测试全部通过。

## 全量与冻结基线

- 精确 deselect 上述 7 个既有阻塞节点后，适用全量为 `245 passed / 96 subtests`；通过数与完整运行相同，说明完整运行中的所有非阻塞节点均已成功执行。
- 三个冻结 Service 独立回归为 `61 passed / 14 subtests`，Training/Resource/Feedback 确定性边界无回归。
- D4 相关组合回归的 `130 passed / 25 subtests` 与适用全量共同覆盖 D4-2.1～D4-2.6 新增测试；没有通过修改预期消除失败。

## 编译、隐私与真实/mock 审计

- `python -m compileall -q app tests` 通过。
- `call_mock_tool`/`MOCK_TOOL_REGISTRY` 只存在于 `mock_tools.py` 和显式 real-vs-mock 测试；真实 MCP/API/内部工具没有引用旧 mock。
- 默认 CareerOrchestrator 注册真实 Profile/Job/Match/Path/Training/Feedback Agent；D4 内部方法位于 CareerMCPToolService，阶段4测试没有导入任何网络客户端。
- MCP server 仍只有 4 个阶段3 decorator 注册；阶段4三个名称尚未进入 tools/list，符合禁止平台接入范围。
- 训练答案/comments 仅作为 Orchestrator 临时 stage input；Agent 日志只记录“已提供”，调用账本只保存 hash fingerprint。连续 E2E 与既有隐私测试均断言原文不进入 CareerState。
- 受保护范围 diff 为空：三个冻结 Service、platform、API、MCP server、mock_tools、migration 均未修改；`git diff --check` 通过，仅有换行提示。
- 未发现 ResourceAgent；资源真实路径仍为内部 Tool → ResourceService，符合“不为对称新建 Agent”。

## 阶段4改动与测试规模

- D4-2.1～D4-2.6 当前业务改动集中在 TrainingAgent、FeedbackAgent、CareerState、CareerOrchestrator、CareerMCPToolService；新增三个 Agent/tool 边界 Schema 与三个 prompt 文件。
- 阶段4新增/重建测试文件共 5 个，测试函数合计 69：TrainingAgent 21、FeedbackAgent 20、CareerState 10、内部工具 14、最终连续 E2E 4。
- D4-2.6 本身只新增 `test_stage4_final_e2e.py` 和规划/开发日志，没有修改业务代码；首轮即全绿，说明未发现可明确归因于本阶段接线的实现错误。

## 与 D4-2.5 基线对比

- 按 D4-2.5 相同范围重跑 `tests + app/agents/tests`：`240 passed / 96 subtests，5 failed`。
- D4-2.5 为 `236 passed / 96 subtests，5 failed`；D4-2.6 恰好新增 4 个通过项，失败节点和根因完全不变，因此本轮没有新增回归。
- 将历史 platform tests 一并纳入更完整的仓库级套件后为 `245 passed / 96 subtests，7 failed`；多出的 2 个失败是历史 Mock 全链对同一 Profile prompt 缺失的级联反映，不是 D4 路径调用旧 mock。

---

# D4-2.5 Orchestrator 与内部工具链发现

## 待核查

- 阶段3 `run_stage`、共享 tool service、HTTP/MCP Schema、错误 envelope 与 session 持久化的真实复用边界。
- `mock_tools` 当前用途以及是否被任何生产入口调用。
- 冻结阶段4工具名称和参数 Schema，哪些仅是规划态、哪些适合本轮内部实现但不注册平台。
- 四个动作应调用 TrainingAgent、FeedbackAgent 还是冻结 Service，如何避免资源推荐依赖一次虚构训练评分。

## 第一轮命名与现状

- 冻结/规划工具名为 `generate_and_score_training`、`recommend_learning_and_job_resources`、`save_growth_feedback`；训练生成与评分共用第一个名称，不能拆成不兼容的外部名称。
- `docs/a02/13_MCP_TOOL_CATALOG.md` 明确这三个阶段4名称仍是“规划中，尚未注册”；本轮只能实现内部可调用能力，不得加入 MCP `tools/list` 或平台路由。
- `CareerOrchestrator.run_stage(state, agent_name)` 是阶段3分步执行与持久化入口；Match/Path 的 API 和 MCP 适配均复用它。
- `mock_tools.py` 仍包含同名阶段4 mock，必须确认其调用者；正式新链路不得经过这些函数，但不能删除阶段3/demo所需 mock。

## 阶段3成熟模式

- `CareerMCPToolService` 是 transport-neutral 应用层：负责加载/校验 session、身份绑定、调用 `orchestrator.run_stage()`、超时、持久化、结果 Schema 和安全失败；确定性计算仍留在 Agent/Service。
- `MCPToolResult` 固定 envelope 为 `success/error_code/message/missing_fields/retryable/trace_id/session_id/status/data`，非常适合作为阶段4内部调用结果；本轮可复用模型风格，但不能把新增方法注册到 MCP server。
- 阶段3工具会把调用写入 `platform_tool_calls` ledger，并以 trace_id 做幂等。D4-2.5 是“内部可被外部接入”而非平台调用，需判断是否复用 ledger；若复用同一类就会把未注册内部动作混入平台账本，倾向新增独立 transport-neutral 内部服务且仍通过 Orchestrator 持久化 AgentLog。
- 现有 `mcp_tool_schema.py` 只包含四个已注册阶段3工具；直接加入阶段4 Schema 容易让“尚未注册”语义混淆。更合适的是独立 `internal_tool_schema.py`，沿用相同基类/envelope 风格。

## Mock / 注册边界

- `mock_tools.py` 是完全独立的显式 `call_mock_tool()` 注册表，没有被真实 CareerAgent API、Platform API 或 MCP server 引用；其阶段4评分按答案长度硬算、反馈固定 `feedback_saved=false`，只能保留为明确 demo/mock，绝不能被新内部服务调用。
- MCP server 当前只装饰注册四个阶段3工具，且动态工具参数强制 extra-forbid；本轮不修改 `server.py` 即可保证阶段4能力不会提前出现在 `tools/list`。
- 阶段3 HTTP platform API 把网络鉴权、幂等 ledger、HTTP 状态映射放在 transport 层。D4-2.5 不新增公网/平台路由，内部接口应返回结构化对象而不是抛出输入或业务异常。
- CareerAgent API 的 Match/Path 分步接口直接 `run_stage()` 后检查 State；阶段4内部层应复用相同 Orchestrator 入口并集中封装输入写入/恢复，避免四处手工改 `student_input`。

## 冻结契约与实现策略

- 工具目录的训练 Schema 是旧规划版本（要求 student_id/job_id），但当前阶段3真实模式已统一为 session_id/user_id + 后端 State。D4-2.5 作为未注册内部边界将保留冻结工具名，输入改为 session/user + 用户真正提供字段；不修改已冻结公开文档，平台接入阶段再做正式契约冻结。
- 生成与评分复用同一 `generate_and_score_training` 方法：生成只需 training_type；评分只需 training_id + user_answer，training_type 从 State 中对应 TrainingTask 自动取得。
- 独立资源动作不能新建 ResourceAgent。内部应用服务将直接调用冻结 ResourceService，从 State 提取有序 gap dimensions 和目标岗位，写入现有 `resource_result` 并持久化。
- TrainingAgent/FeedbackAgent 当前从 `student_input.training/feedback` 读请求；内部调用不应把 user_answer/comments 永久保存。最小 Orchestrator 扩展是在 `run_stage` 中临时注入 stage_input，Agent 完成后恢复原 student_input，再持久化结果和安全日志。
- 阶段4内部方法可加入现有 transport-neutral `CareerMCPToolService`，复用 session/identity/trace/幂等 ledger/超时/错误 envelope；只要不改 `mcp/server.py`，它们就不会被注册到 MCP。

## 实现结果

- 新增 `internal_tool_schema.py`，请求只暴露 session_id/user_id/trace_id 和用户动作字段；资源请求明确拒绝 ability_gaps/target_job 覆盖。
- `run_stage(..., stage_input=...)` 仅支持 TrainingAgent/FeedbackAgent；注入期间 Agent 日志仍能记录安全摘要，finally 恢复原 student_input，再持久化 State。
- `CareerMCPToolService` 新增三个未注册方法：训练方法覆盖 generate/score 两模式，资源方法直接调用 ResourceService，反馈方法调用 FeedbackAgent；统一复用阶段3的安全 envelope、trace 幂等账本和 session identity。
- 资源 action 的 ledger `agent_run_key=None`，明确它是 Tool→ResourceService 而不是伪造 ResourceAgent；结果指针仍是 `resource_result`。
- 首轮 13 项完全离线内部工具测试通过，覆盖四动作、缺上下文、非法边界、隐私、LLM/Service 失败、session 隔离和 real/mock 区分。

## 回归结果

- 内部工具测试最终 `14 passed`，新增 trace 幂等回放验证同一调用不重复执行 TrainingAgent。
- 阶段3 MCP/HTTP tool/E2E 回归 `21 passed`；`mcp/server.py` 未修改，tools/list 仍只有原四个阶段3工具。
- 三个冻结 Service 独立回归 `61 passed / 14 subtests`。
- 完整回归 `236 passed / 96 subtests，5 failed`；5 项仍全部为既有 ProfileAgent prompt 缺失，无新增失败。
- 排除既有 ProfileAgent 阻塞文件的适用全量 `231 passed / 96 subtests`。

---

# D4-2.4 CareerState 统一接入发现

## 待核查

- CareerState 已有阶段4字段的真实形状、默认值、序列化与恢复方式。
- Profile / Match / Path 如何通过 BaseAgent 和 Orchestrator 写入、读取状态。
- TrainingAgent / FeedbackAgent 当前对嵌套状态的重复解析点，以及能否用最小状态访问器统一。
- completed 统计和反馈调权 priority 是否存在可靠维护及后续消费者。

## 接入裁决

- 冻结 CareerState 已有 `training_plan`、`resource_result`、`feedback_result`，数据库保存完整 Pydantic 快照；无需增加顶层字段或数据库迁移。
- 当前训练题在 `training_plan.trainings`，最近评分与 ability_updates 分别在 `training_plan.latest_score` 及其子字段；growth_snapshot 在 `feedback_result.growth_snapshot`。新增同义顶层字段会违反“不重复存储”。
- `completed_trainings` / `completed_phases` 没有可靠维护来源，路径阶段是计划而非完成；本步骤不新增计数字段，继续使用冻结 Service 允许的 0 默认值。
- `updated_priorities` 已完整保存在 `feedback_result`，现有流程在 FeedbackAgent 后没有再次消费 priority 的节点；不另建会话 priority 副本，不反写冻结 `match_result`。
- CareerState 增加只读深拷贝访问器，统一最近训练任务、最近评分、ability_updates、skill_gaps、overall_score 和 growth_snapshot 的 fail-safe 读取；这些访问器不进入序列化公共字段。
- `apply_agent_data` 现有实现直接保存调用方对象，两个 State 若消费同一结果对象会共享嵌套可变数据；改为深拷贝写入，并对三个阶段4构造字段做入模前深拷贝，隔离 session。

## 最终验证

- 新增 CareerState 测试 `10 passed`；包含 SQLite 完整 State 往返恢复和两种跨 session 共享对象隔离场景。
- CareerState + Training/Feedback + Match/Path + stage3 E2E 定向回归 `80 passed / 11 subtests`。
- 三个冻结 Service 回归 `61 passed / 14 subtests`。
- 完整回归 `222 passed / 96 subtests，5 failed`；5 项均为前序已知 ProfileAgent prompt 缺失，无新增失败。
- 排除该已知 ProfileAgent 文件的适用全量回归 `217 passed / 96 subtests`。
- compileall 与 diff check 通过；冻结 Service、CareerOrchestrator、platform 无差异。

---

# D4-2.3 FeedbackAgent 真实化发现

## 待核查

- FeedbackService.save_feedback 的精确参数、默认值、错误返回、状态性行为和输出字段。
- 当前 FeedbackAgent 的 mock/硬编码路径及 BaseAgent fail-safe 行为。
- feedback 输入在 student_input 中的既有组织方式，以及 match/training/profile/path 的可靠上下文来源。
- README、Agent/API/工具契约是否要求 feedback_schema 和文字解释 prompt。

## 已知工作区状态

- D4-2.1 TrainingAgent 与 D4-2.2 ResourceService 接入成果尚未提交，必须原样保留。
- 完整回归已有 5 个 ProfileAgent prompt 缺失失败；后续只判断失败数是否增加，不越界修复。
- session-catchup 脚本已知缺失，本轮不重复调用。

## 第一轮实现现状

- 当前 FeedbackAgent 是完整占位：读取 `student_input.ratings`，无评分时 fallback；把 satisfaction 强制转 int 并默认 3；硬编码 `updated_priorities=[]`，不调用 FeedbackService；fallback 还虚构中性 satisfaction=3。
- FeedbackService.save_feedback 接收用户反馈、skill_gaps、abilities、completed 计数、training_target_abilities、overall_score；内部独占校验、内存保存、优先级调整、成长快照与 trend 判断。
- Service 错误以裸 dict `{error: "code:detail"}` 返回；Agent 必须识别并转为 BaseAgent 标准失败，不能把 error 当成功 feedback_result。
- comments 的邮箱/手机/身份证校验已在 Service 内实现；Agent Schema 不应复制隐私正则或提前吞掉该 Service 错误。
- Service 明确允许 path/training/resource rating 全部缺失，只要求 satisfaction；completed_trainings/completed_phases 的冻结缺省值均为 0。
- CareerState 已有 session_id、user_id、match_result、training_plan、student_profile、path/learning/career_roadmap、feedback_result，无需本轮增加字段。
- 当前尚无 feedback_schema；README §13.4 明确允许/要求补齐 `backend/app/schemas/feedback_schema.py`。

## 第二轮契约裁决

- 冻结工具输入明确要求 session_id、user_id、satisfaction，三个分项 rating 和 comments 可选；“至少一项评分”已由 FeedbackService 报告裁决为 satisfaction 本身即可。
- `docs/a02/05_AGENT_CONTRACTS.md` 旧文档写 FeedbackAgent 不调用 LLM，但本轮用户明确要求覆盖“LLM 文字解释失败不影响保存”；采用 **Service 成功后可选一句解释** 的加法实现，LLM 失败使用固定说明，绝不修改 Service 字段。
- FeedbackService 新输出比旧 API §7.1 更完整，且本轮用户明确要求五个字段全部保留；Agent 应以 Service 当前冻结输出为准整体透传到现有 `feedback_result`。
- completed_trainings / completed_phases 由调用方提供、Service 缺省 0；CareerState 没有可靠完成统计，path phases 是计划而非完成，因此本轮固定传冻结默认值 0，不从计划数量推断。
- growth_snapshot 直接放在 feedback_result 内，与 Service/工具冻结输出一致；不新增 CareerState 顶层成长字段。
- 平台工具 `save_growth_feedback` 仍是规划态且本轮禁止注册；只补可复用的严格工具参数 Schema。

## 第三轮参数来源与边界设计

- 用户反馈输入优先读取 `student_input.feedback`，兼容既有 `student_input.ratings` 和顶层同名评分字段；session_id/user_id 固定从 CareerState 读取，不能由请求覆盖。
- skill_gaps 原样深拷贝最近 `state.match_result.skill_gaps`，不筛选、不重排、不调权。
- training_target_abilities 优先用 `training_plan.latest_score.training_id` 找到已评分 TrainingTask；若还没有 latest_score，才取 trainings 列表最后一项；无训练任务传 None。
- overall_score 只读取 `match_result.overall_score`；没有则传 None，由 Service 写 0.0 和 competitiveness_unavailable flag。
- abilities 优先透传 student_profile.abilities；统一画像只有 ability_dimensions 时透传该真实列表，不补标签、等级或时间戳。
- completed_trainings/completed_phases 均传 0，因为当前 State 无完成历史字段，training_plan/path_plan 只证明生成/计划，不能当累计完成统计。
- Agent 内部用户反馈 Schema 严格校验评分形状；独立 FeedbackToolInput 额外包含 session/user 作为后续工具参数边界，但本轮不注册工具。
- comments Schema 只做类型/长度边界，不复制隐私规则；隐私违规必须到达 FeedbackService，并由其 error 触发 Agent 标准失败。
- Service 成功结果先用 Pydantic 验证但保留原 dict 五字段；可选 LLM 只返回单字段 message，prompt 不包含 comments、用户ID或能力证据。

## 实现落点

- 新增严格 feedback_schema：Agent 用户评分输入、未来工具完整参数、Service 结果验证、成长快照/优先级更新和 LLM 单句输出边界。
- FeedbackAgent 已改为真实依赖注入 FeedbackService，tool_name=`save_growth_feedback`、service_name=`FeedbackService`，fallback 返回空 dict，不再伪造中性反馈。
- Service 原始五字段经 Schema 验证后整体复制；`natural_language_summary` 是唯一加法文字字段，LLM 失败使用固定确认句。
- 解释 prompt 只接收 Service 结果，不接收 comments、session/user、画像或训练证据，因此不会把用户反馈隐私发给 LLM。
- Agent 日志摘要只记录各评分/评论是否提供和 gap 数，不记录 comments 文本。

## 首轮测试结果

- FeedbackService 原 20 项 + FeedbackAgent 新 19 项：`39 passed`，全部离线。
- 新测试覆盖真实 Service 保存、完整参数投影、最近已评分训练任务、差评升优先级、好评回落、低满意度抑制、无 training_rating/gaps/recent training、固定 Service 数值原样透传、Service error、缺 user、隐私、非法 satisfaction、工具 Schema、LLM 失败和日志隐私。
- 完整回归首轮为 `211 passed, 5 failed`；相比 D4-2.2 的 `192 passed, 5 failed` 新增 19 项均通过，失败数量和原因未变化。
- 补充缺 session_id 用例后，FeedbackAgent 共 20 项；FeedbackService + FeedbackAgent 定向为 `40 passed`。
- 排除既有 ProfileAgent 阻塞的适用回归为 `207 passed`，包含全部 Service、Match/Path/Training/Feedback Agent。
- 补测后的完整回归收集 217 项，结果 `212 passed, 5 failed`；与前序相同的 5 个 ProfileAgent 失败之外无新增回归。
- `compileall app tests` 通过，冻结 Service/Orchestrator/platform 目录无 diff，`git diff --check` 无 whitespace error。

---

# 历史：标准 MCP Server 发现记录

## 2026-08-24 Hermes 提交前收尾

- `backend/tests` 原先没有 `__init__.py`，`test_tbox_stage3_tools.py` 使用 `from tests.test_stage3_e2e ...`；从 backend 启动时会碰巧命中本地命名空间包，从仓库根启动则先因 `app` 不在导入根而收集失败，且同名第三方 `tests` 包可能产生歧义。
- 最小规范修复是把 tests 变成包，将 `OfflineLLMClient`、`student_profile`、`job_profile` 移至 `tests/stage3_fixtures.py`，两个测试使用包内相对导入；`backend/pytest.ini` 固定 backend 为 pytest 的相对源码根，无本机绝对路径或代码级 `sys.path` 修改。
- `test_mcp_server.py` 直接导入 `httpx2`，用于官方 MCP Streamable HTTP 客户端的 ASGITransport/Bearer 全链测试。
- 已安装的官方 `mcp==2.0.0` METADATA 明确声明必需依赖 `httpx2>=2.5.0`；隔离安装随 MCP 自动得到 `httpx2==2.12.0`，不是只靠 Hermes 手工额外安装。项目已固定 MCP 版本，因此不额外加入一套 `httpx/httpx2` 测试实现，也不重复固定 MCP 自身管理的传输依赖。
- 工具目录虽然已有 0.5 节说明只注册四个工具，但后续七节和总览仍像可运行目录；现已逐项标注历史语义/规划中/尚未注册，并在文件顶部声明 `tools/list` 只有四个当前名称。

## 当前已知基线

- 阶段3本地核心能力和正式 HTTP Tool API 已完成，现有工作区包含未提交成果，必须增量开发。
- 正式 HTTP 平台层当前至少提供 `analyze_job_match`、`generate_career_path`、调用状态与结果查询，并具备 Bearer、超时、幂等和平台调用日志。
- `tbox_adapter.py` 是旧 Mock HTTP 入口，不能作为 MCP 真实业务实现。
- 仓库目前没有 `backend/app/mcp/`、MCP Server 入口或官方 MCP SDK 依赖。
- 架构文档允许 MCP 或 HTTP；百宝箱实际支持的传输/控制台字段仍需与平台现场能力区分。

## 当前待确认

- ProfileAgent、JobAgent 的可复用业务入口及其状态写入方式。
- CareerState 的状态字段、持久化行为、AgentRunLog/ToolCallLog 字段和 trace 关联能力。
- 现有 HTTP 平台 Schema 是否仅覆盖阶段3后两工具，以及前两工具应复用哪些已有 Schema。
- 官方 MCP Python SDK 与仓库 Python 版本兼容的当前稳定固定版本、FastAPI ASGI 挂载和鉴权方式。
- 官方客户端对 Streamable HTTP `initialize`、`tools/list`、`tools/call` 的测试 API。

## 基线审计（一）

- 运行时为 CPython 3.11.15；项目只有 `backend/requirements.txt`，其中现有依赖均未锁版本，也没有 MCP SDK。
- 主应用使用 `create_app()` 工厂并注入 `CareerOrchestrator`，这是挂载 MCP ASGI 应用和测试离线 Orchestrator 的合适入口。
- `CareerState` 当前状态名是 `PROFILE_COMPLETED`、`JOB_COMPLETED`、`MATCH_COMPLETED`、`PATH_COMPLETED`，不是需求文字中的 `PROFILE_READY`/`JOB_READY`；为保持公共状态契约，应把前两者作为 MCP 前置语义的现有等价状态，而不新增另一套状态枚举。
- `CareerState` 已统一携带 `session_id`、`platform_session_id`、`user_id`，并保存画像、岗位、匹配和路径结果；后续 MCP 工具可仅用 session 读取状态。
- `CareerOrchestrator.run_stage()` 会调用真实 Agent 并持久化状态和 AgentRunLog；`get_session()` 支持跨进程持久化读取。
- 现有 AgentLog 没有独立 `trace_id` 字段；平台调用日志可能已有 tool call ID/关联键，需要继续审计后决定复用方式，不能贸然改公共 AgentLog 字段。

## Agent 与 HTTP 契约审计（二）

- `ProfileAgent` 真实工具名现为 `analyze_student_profile`，但用户要求阶段3至少支持 `build_student_profile`；`JobAgent` 名为 `analyze_job_and_trend`，用户目标名为 `analyze_target_job`。需在最终映射表中明确 MCP 名称与既有内部 Agent 工具名的关系。
- `MatchAgent`/`PathAgent` 内部工具名仍为冻结旧名 `calculate_job_match`/`recommend_career_path`，正式 HTTP API 已使用 `analyze_job_match`/`generate_career_path`。为避免新增第三套主名称，MCP 应与正式 HTTP API 对齐后两者，并保留内部 Agent 名称映射说明。
- 四个 Agent 都通过 `BaseAgent.run()` 写隐私安全 AgentLog；Profile/Job 有规则或 Demo fallback，Match/Path 的 Service 计算在 LLM 增强失败时仍保留。
- 当前正式 HTTP Schema 只覆盖匹配、路径与查询；匹配请求要求客户端传完整 `StudentProfile`/`JobProfile`，而 MCP 新流程要求前两步写入 session、后两步从 session 读取，因此不能直接把 HTTP 请求模型原样作为 MCP 匹配工具输入。
- `platform_tool_schema.py` 已复用 `MatchResult`/`PathResult` 且 `extra=forbid`；MCP 结果应继续复用这些确定性模型，新增的只应是 MCP 专用薄输入和统一调用结果 envelope。
- 现有 HTTP 平台测试覆盖真实 Agent/Service、结果一致性、持久化、鉴权、固定 Schema、幂等、前置、超时、日志隐私和 OpenAPI，是 MCP 回归的核心基线。

## 状态与平台调用审计（三）

- 本地 HTTP `career_agent_api` 已有 prepare/match/path 的前置校验，但没有分别运行 ProfileAgent/JobAgent 的公开分步入口；MCP 需要新增自己的前两步薄调用逻辑并直接复用 `CareerOrchestrator.run_stage()`。
- 正式 HTTP `analyze_job_match` 当前允许首次调用时写入完整已验证画像和岗位，这与新 MCP 的 session 串联契约不同；必须保持 HTTP 行为不变，MCP 则从持久状态读取后再调用同一个 MatchAgent。
- `StateRepository.platform_tool_calls` 已保存工具名、session、用户哈希、状态、结果字段指针、Agent run key 和时长，不保存原始输入或 Token。MCP 可复用这一日志账本，把 `tool_call_id` 作为需求中的 `trace_id`，无需修改 AgentLog 公共字段或数据库迁移。
- 平台调用账本对 `(tool_name, idempotency_key)` 唯一；MCP SDK 单次 call 没有项目自定义 idempotency 元数据时，可由 MCP 输入明确要求/生成 trace_id。为满足统一 user/session 与调用日志，MCP 四个写工具输入应包含 `trace_id` 或可选由服务端生成。
- HTTP 后两工具的具体实现包含大量 API/HTTP 异常适配，直接从 MCP 调 HTTP 会破坏依赖注入且多一层网络；更适合抽取/新增一个与传输无关的 MCP application service，直接运行相同 Orchestrator Agent，并继续用 `MatchResult`/`PathResult` 验证确定性输出。

## 官方 MCP SDK 核对（四）

- 官方 PyPI 当前稳定线是 v2，最新稳定版为 `mcp==2.0.0`（2026-07-28 发布），要求 Python >=3.10，因此兼容仓库 Python 3.11.15；不是预览版。
- 官方 v2 `MCPServer.streamable_http_app()` 可作为 ASGI 应用挂载到 FastAPI；默认内部路径 `/mcp`，若挂载前缀本身就是 `/mcp`，应设置 `streamable_http_path="/"`。
- 挂载子应用不会自动运行其 lifespan；宿主 FastAPI lifespan 必须进入 `mcp.session_manager.run()`，否则首次请求失败。
- 官方明确 Streamable HTTP 是新部署首选，SSE 已被取代，因此当前没有百宝箱仅支持 SSE 的证据时不实现 `/sse`。
- 官方 v2 客户端支持 `Client(server)` 内存协议测试以及 URL Streamable HTTP；带 Authorization 时需通过自定义 HTTP 客户端传 Header。
- Streamable HTTP 浏览器客户端需要允许 `Mcp-*` 请求头并暴露 `Mcp-Session-Id`；现有 CORS `allow_headers=["*"]` 已满足请求侧，但 expose headers 需补充且不能影响现有接口。
- 当前 Codex/Hermes 宿主 venv 预装旧 `mcp==1.26.0`，不能代表项目依赖；必须用隔离的 2.0.0 运行时执行新增测试，避免修改共享宿主环境。

## SDK 2.0 实际 API 核对（五）

- 已将 `mcp==2.0.0` 及依赖安装到 Git 忽略的 `backend/.runtime/mcp2`，共享宿主包保持不变；测试命令将把该目录置于 `sys.path` 首位。
- v2 高层类为 `mcp.server.MCPServer`，工具使用 `@server.tool()`，可从类型注解/Pydantic 自动生成输入和结构化输出 Schema。
- `MCPServer` 原生接受 `AuthSettings` + `TokenVerifier`，可用项目静态 Bearer token 验证器获得协议入口级 401，无需自行包一层重复 ASGI 鉴权中间件。
- `AuthSettings` 需要 issuer/resource URL；本项目可用配置的 `MCP_PUBLIC_URL` 作为 resource server URL，并使用同源基础 URL 作为静态部署元数据占位。这里只验证固定 Bearer，不声称实现 OAuth 授权服务器。
- `streamable_http_app(streamable_http_path="/")` 创建 session manager；宿主 lifespan 必须运行它。`Context.request_id` 可读取 MCP JSON-RPC 请求 ID，但业务日志仍应生成固定格式 `tool-...` trace_id，避免外部请求 ID 不符合现有数据库长度/字符约束。
- v2 官方认证会从 Authorization Bearer Header 调用 TokenVerifier；无效或缺失 token 的拒绝可通过真实 Streamable HTTP 测试验证。

# D4-2.2 ResourceService 业务接入发现

## 待核查

- 是否已有 ResourceAgent，冻结契约是否要求独立 Agent。
- Match/Path/Orchestrator/tool 哪一层已拥有真实 match_result 与 target_job。
- skill_gaps 的字段模型、排序责任和当前推荐结果保存位置。
- 最小实现与测试落点，避免触碰冻结 Service 和 D4-2.4 State 集中处理范围。

## 已知工作区状态

- D4-2.1 TrainingAgent、training schema、prompt、测试和开发日志仍是未提交成果，必须保留。
- planning-with-files 的 session-catchup 辅助脚本缺失；已停止重试，使用 Git 状态与本文件恢复。

## 第一轮架构发现

- 仓库文件与符号检索未发现 `ResourceAgent`；现有 Agent 为 Profile、Job、Match、Path、Training、Feedback。
- `ResourceService.recommend_resources(ability_gaps, target_job)` 已完整封装标签归一、资源命中、排序、限制、证书提取和质量 flag；接入层只能准备参数并透传结果。
- `MatchResult.skill_gaps` 使用严格 `SkillGap` Schema，包含 `dimension` 和已有 `priority`；接入无需也不得重算 priority。
- `PathAgent` 同时持有真实 `state.match_result`、`state.job_profile`，并已经负责生成和写入 `learning_plan`；其现有 `learning_plan` 中 resources 与 certificate_suggestions 仍是空占位，因此是首要候选消费层。
- `MatchAgent` 负责确定性匹配结果及可选文本增强；在该层接资源会把下游推荐副作用混入匹配职责。ResourceService 不需要 LLM。

## 第二轮契约与状态发现

- `CareerState` 已有专用 `resource_result: dict | None`，最终报告也会完整带出该字段；D4-2.2 无需新增或重构 State 字段。
- CareerOrchestrator 当前只按顺序调用六个 Agent，不直接调用 Service；让 Orchestrator 特判 ResourceService 会破坏其统一 Agent 调用模式。
- MatchService 在构造 `skill_gaps` 时已按确定性 priority score 排序，并依次写入 `priority=1..n`；消费层必须按列表现有顺序取 `dimension`，不得再排序。
- 冻结 `05_AGENT_CONTRACTS.md §5.1` 明确规定 TrainingAgent 职责包含“调用 ResourceService 推荐资源”；README §13.4 同样明确 TrainingAgent 调用 ResourceService。
- `03_ARCHITECTURE.md` 还描述后续独立平台工具 `recommend_learning_and_job_resources`，但用户已限定本轮不接百宝箱/平台，因此不能在 tool 层提前实现。
- 综上，最终消费位置应从初步候选 PathAgent 调整为 **现有 TrainingAgent**：符合冻结职责，沿用 Agent→Service→State 模式，输出写入既有 `state.resource_result`；不新增 ResourceAgent，不改 Orchestrator。
- PathAgent 的 `learning_plan` 空资源槽是阶段3兼容投影，不应在本步骤把 ResourceService 四字段拆散塞入其中，否则会丢失 job_resources/data_quality_flags 并改变 LearningPlan 契约。

## 第三轮 TrainingAgent 接入时机发现

- D4-2.0 已明确建议 `ResourceService -> TrainingAgent -> resource_result`，并明确不新增 ResourceAgent；本轮应沿用已验收结论。
- API 状态流写明先由 TrainingAgent 产生 training_plan，再在“用户完成训练”后产生 resource_result；因此资源推荐应接在 **score 成功分支**，而不是生成训练题时提前推荐。
- 当前 TrainingAgent 的 generate 与 score 分支清晰，输出字段目前仅含 training_plan；最小改动是在 score 成功后调用 ResourceService，并同时返回 training_plan 与 resource_result。
- 推荐输入必须忽略显式训练请求里的 `ability_gaps`：资源 ability_gaps 固定从真实 `state.match_result.skill_gaps[].dimension` 按原列表顺序重建，避免调用者覆盖真实匹配缺口。
- `target_job` 应从真实 `state.job_profile` 取岗位标题；需继续核对冻结 ResourceService 报告对 title/normalized_title 的约定。
- ResourceService 输出不能拆分或重组；以原始四字段整体写入 `state.resource_result`，这样内部字段过滤 `resource_id/demo_only` 仍由冻结 Service 保证。

## 实现落点

- TrainingAgent 构造器增加可注入 `resource_service`，生产默认使用冻结 `ResourceService()`，测试可记录精确参数。
- score 成功后同步调用 `_recommend_resources(state)`；generate 分支保持只生成 training_plan，符合“用户完成训练后产生资源结果”的状态流。
- `_recommend_resources` 只做三件事：按现有顺序提取 dimension、读取 job_profile.title、调用并完整复制 Service 裸 dict；不接触 LLM、priority 或标签归一。
- Agent 只检查 Service 结果是否为 mapping、是否有 error、是否缺少四个必需顶层字段；不会裁剪或改写 Service 返回内容。
- BaseAgent `output_fields` 仅加法允许 `resource_result`，CareerState 已有同名字段，因此无需 State/Orchestrator/Schema 修改。

## 首轮测试结果

- ResourceService 原 12 项 + TrainingAgent 21 项：`33 passed`。
- 完整 `backend/tests + backend/app/agents/tests`：`192 passed, 5 failed`；相比 D4-2.1 的 `186 passed, 5 failed` 新增 6 项全通过，失败数和失败原因未变化。
- 5 个失败仍全部来自 ProfileAgent 缺失 `prompts/profile_agent/system.txt` 与 `user_template.txt`，与 ResourceService 接入无关且不在本步骤授权范围。
- 排除既有 ProfileAgent 阻塞项后的适用回归为 `187 passed`；MatchAgent、PathAgent、TrainingAgent 与全部 Service 测试全绿。
- `compileall app tests` 通过；仓库根检索确认不存在 ResourceAgent，TrainingAgent 生产代码中不存在 AbilityTagNormalizer 引用。
- 冻结 `backend/app/services/**`、`backend/app/orchestrator/**`、`backend/app/platform/**` 均无本轮 diff。

---

## 历史实施设计决定（六）

- 公开 MCP 主工具名固定为 `build_student_profile`、`analyze_target_job`、`analyze_job_match`、`generate_career_path`；其中后两者与正式 HTTP 名称一致，前两者映射现有 Agent 工具 `analyze_student_profile`、`analyze_job_and_trend`。
- 新增传输无关 `CareerMCPToolService`：负责 session identity、状态前置、运行真实 Agent、Pydantic 输出验证、统一结果/错误 envelope 与现有 `platform_tool_calls` 日志；不实现任何匹配/路径计算。
- 每个 MCP 输入统一要求 `session_id`、`user_id`，并接受可选 `trace_id`；缺省时服务端生成 `tool-<uuid>`，该值同时作为平台账本 tool_call_id/idempotency key 和返回 trace_id。
- Profile/Job 原始输入目前没有可直接复用的严格模型，因此新增薄输入 Schema；输出直接嵌入现有 `StudentProfile`、`JobProfile`、`TrendResult`、`MatchResult`、`PathResult`。
- Profile/Job 的规则 fallback 若生成了可验证结构化结果，将把 CareerState 纠正为现有 `PROFILE_COMPLETED`/`JOB_COMPLETED` 并再次持久化；AgentLog 仍保留 `fallback_used=true`，不掩盖模型失败。
- MCP 以 `success=false` 的结构化结果返回业务前置错误，不泄露堆栈；SDK/Pydantic 层非法参数继续由协议 `tools/call` 拒绝。
- MCP 开关默认关闭；启用后通过官方 TokenVerifier 校验静态 Bearer。测试可显式关闭 MCP auth，但这不改变现有 HTTP `A02_TBOX_API_TOKEN` 鉴权。
- 为获得无重定向的精确 `/mcp`，把官方 MCP ASGI 应用挂在宿主根路径 `/`，其内置 `/mcp` route 位于所有既有 FastAPI 路由之后；既有 API 路由优先匹配，HTTP 接口不受影响。

## 测试设计发现（七）

- 官方 v2 `Client(..., mode="legacy")` 会显式发送 `initialize`，随后同一客户端可执行 `tools/list` 和 `tools/call`；这能直接覆盖用户要求的三类协议验证。
- `httpx2` 提供 `ASGITransport`，官方 `streamable_http_client` 可接收配置 Authorization Header 的 `httpx2.AsyncClient`，因此可在进程内走完整 Streamable HTTP/鉴权线路，无需启动真实端口或使用非官方协议模拟。
- 测试 Orchestrator 将注入 Profile/Job/Match/Path 四个真实 Agent 和统一离线失败 double：Profile/Job 验证 fallback 结构化结果，Match/Path 验证 LLM 失败不影响 Service 确定性结果，全程不调用付费模型。
- `jobs_demo.json` 含 AI产品经理的固定 required abilities，适合 JobAgent 离线 fallback 后继续匹配/路径；画像输入使用匿名证据，使 ProfileService 生成可匹配的能力维度。

## 文档审计（八）

- `04_API_CONTRACTS.md` 当前只有正式 HTTP `stage3-tool-v1`，需要加法新增 `stage3-mcp-v1`，明确 MCP 与 HTTP 后两工具的相同确定性结果和不同输入编排。
- `03_ARCHITECTURE.md` 的 MCP 目录仍是计划态单文件 `mcp_server.py`，实际实现是 `mcp/server.py + mcp/tool_service.py`，需要同步；旧协议段还写 HTTP `/api/tbox/<tool_name>` 和 `X-API-Key`，与现有正式 HTTP 路径/Bearer 不一致。
- `13_MCP_TOOL_CATALOG.md` 冻结历史名仍是 `analyze_student_profile`、`analyze_job_and_trend`、`calculate_job_match`、`recommend_career_path`；应保留历史目录并新增“阶段3远程 MCP 运行映射”，不能静默改名。
- `10_TBOX_REQUIREMENTS.md` 平台是否支持远程 MCP、超时/大小/并发等仍是待现场验证；本次只能把 CareerPulse Server 实现标为完成，不能勾选百宝箱配置或宣称已发布。
- 新接入说明应与现有 HTTP 指南并列，记录 SDK 2.0.0、Streamable HTTP `/mcp`、静态 Bearer、环境变量、官方 Client 测试、公网 HTTPS/DNS allowlist 和百宝箱待填逻辑字段。

## 最终验证结论（九）

- 官方 MCP Client legacy 模式完成 initialize，tools/list 实际列出四个预期工具；每个根输入 Schema 都是 `additionalProperties=false`，并准确标记必填字段。
- MCP 测试 6/6 通过；与现有 HTTP Tool API 联合定向测试 11/11 通过。
- `backend/tests` 全量 86/86 通过，包含现有阶段3 HTTP、正式平台 HTTP、MCP、Service、Schema、持久化和隐私测试。
- compileall、V001-V004/静态数据 `--check`、隐私检查和 `git diff --check` 均通过。
- `backend/app` 正确包根 discovery 为 34 通过、2 个旧 Mock 全链断言失败；与任务开始基线相同（期待 success/code=0，但默认离线 LLM 触发 partial/code=-4），本次未修改 `tbox_adapter.py` 或这些测试。
- `git diff --name-only` 确认 MatchService/PathService 无变更；未实现 SSE，未进入百宝箱，未提交 Git。
- CareerPulse 侧已经具备标准远程 MCP 地址契约；尚缺公网 HTTPS 部署、真实域名 allowlist 和目标百宝箱租户的远程 MCP/控制台字段现场验证。

---

## 历史任务发现（百宝箱最小 HTTP 接入）

## 来自阶段3验收的已知基线

- 已有分步链路：prepare → match → path，以及 session 和 Agent 日志查询。
- MatchService/PathService 负责确定性匹配、缺口、路径和评分；Agent 只编排/解释。
- 阶段3已有 SQLite/PostgreSQL 持久化、状态机、AgentRunLog 和应用工厂。
- 已有固定匿名 AI 产品经理案例可产生匹配结果、3条路径候选、2条备选及3/5年路线。
- 阶段3验收时后端 tests 全部通过；app 测试有2个早于本任务的 TBox Mock 基线失败。
- 目标环境 PostgreSQL V003 尚需部署验证；本地 SQLite 已验证跨应用实例读取。

## 本次待确认

- 当前 Git 改动范围及平台适配相关现有模块。
- 是否已有 ToolCallLog、鉴权中间件、统一错误 envelope、请求幂等存储和超时策略。
- 百宝箱支持的工具描述格式与 OpenAPI 暴露细节。
- 阶段3分步接口能否直接作为工具底层，或需新增稳定的 `/api/platform/tools/...` 适配层。
- 现有 API/Agent 契约文档的准确路径及公共字段。

## 初步设计原则

- 百宝箱只传业务输入和调用元数据；不接受 score/gaps/path_score 等计算输出字段。
- 工具调用返回稳定 envelope，异步或超时时可凭 request/run 标识查询状态与结果。
- 工具日志与具体 AgentRunLog 建立显式关联，不记录完整简历、姓名、邮箱、电话或令牌。

## 仓库审计（第一轮）

- 现有改动均为上一阶段未提交成果；核心新增为 `career_agent_api.py`、`db_state.py`、V003 和 `test_stage3_e2e.py`，必须增量演进。
- 目前只有内部阶段3 prepare/match/path、session 查询和 Agent 日志查询；尚无 `analyze_job_match` / `generate_career_path` 平台工具入口。
- 当前代码未见 API Key 鉴权、平台级稳定错误 envelope、ToolCallLog 独立持久化或平台幂等请求表。
- `docs/a02/10_TBOX_REQUIREMENTS.md` 中工具超时仍标为待填写；`13_MCP_TOOL_CATALOG.md` 有 Bearer 示例但需核对是否属于阶段4/MCP，不能直接接入。
- `CareerState.agent_logs` 与独立 `agent_logs` 表已具备 AgentRunLog 基线；平台调用日志需要新增显式关联字段/记录，而非把原始请求塞进 Agent 日志。
- 工作区含未跟踪 `backend/.idea/`，与本任务无关，保持不动。

## 阶段3实现边界（第二轮）

- 内部 `stage3/match` 和 `stage3/path` 返回整个 `CareerState`，且错误依赖 FastAPI `detail`；不适合作为百宝箱的冻结工具契约，宜新增薄适配层并复用 Orchestrator。
- `CareerState` 持久化仅按 `session_id`，AgentRunLog 幂等键为 `session_id:agent_name`；尚不能表达平台 `tool_call_id`、请求摘要、关联 run_key、超时或重放状态。
- 阶段3接口已有 payload 冲突防护，但没有跨重启的工具级 idempotency key + 请求指纹语义。
- `main.create_app()` 可注入 Orchestrator，适合接口测试；平台配置应在应用构建时读取环境变量且测试可覆盖。
- 新平台层应返回裁剪后的 `match_result` / `career_roadmap` 与状态，不返回学生完整画像或数据库信息。
- 仓库旧 `backend/app/config.py` 含硬编码本地数据库口令；虽非本次平台配置入口，但任何新日志/文档不得复制或暴露该值。

## Schema/迁移审计（第三轮）

- `MatchResult` 与 `PathResult` 已是严格 `extra=forbid` 的确定性输出模型，可直接嵌入平台响应，不重复定义业务计算字段。
- 阶段2输入应继续使用统一 `career_profile_schema.StudentProfile` 和 `job_schema.JobProfile`；平台输入模型必须显式复用这两类并 `extra=forbid`。
- PathService 需要 `match_result`，但平台的 `generate_career_path` 不应接收它；应只接收上一次匹配的 session/tool call 标识，并从后端持久化状态读取。
- V003 仅覆盖阶段3 CareerState/AgentRunLog；平台工具调用表应使用独立加法迁移 V004，避免混入阶段3已验收迁移。
- `init_a02_data.py` 按 V001→V002→V003 应用迁移，可增量加入 V004 的静态契约检查与 apply 顺序。
- BaseAgent 已生成隐私安全的 service tool summary；平台日志可以关联该 AgentRunLog 的 `run_key=session_id:agent_name`，无需复制 Agent 输入/输出正文。

## 百宝箱文档现状（第四轮）

- 现有 D2 冻结文档仍列 7 个未来工具和旧名称 `calculate_job_match` / `recommend_career_path`；本次用户明确只接阶段3，并指定 `analyze_job_match` / `generate_career_path`，不能启用其余阶段4工具。
- `10_TBOX_REQUIREMENTS.md` 明确平台接入方式、超时、返回大小、并发限制仍待实际验证；因此接入说明需区分“CareerPulse 侧固定值”和“平台控制台待现场确认字段”。
- 旧 `tbox_adapter.py` 是全链 Mock 且无鉴权/持久幂等/稳定查询，不满足本次要求；可保留用于旧基线，新增正式阶段3适配层。
- 主路由聚合器是挂载新平台路由的正确位置；`.env.example` 是新增 token、timeout 和 base URL 配置的正确位置。
- 现有匿名 E2E fixture 可复用到新的完整 Mock 请求/响应文档与平台接口测试，避免引入真实简历信息。

## 官方资料核对

- 官方语雀域名的公开搜索没有返回工具配置资料，项目内记录的具体语雀链接也无法由当前浏览环境安全打开。
- 因此不能验证百宝箱控制台的精确字段名称、超时上限、响应大小或并发限制；本次只承诺 CareerPulse 侧 OpenAPI/HTTP 契约，并把平台现场项明确列为“待控制台验证”。

## 最终接口设计输入

- 现有 API 契约已有统一 envelope 与错误码 `0/-1/-2/-3/-4/-5/-6`，新工具层应严格复用并补全 HTTP 状态映射。
- `MatchAgent.tool_name`/`PathAgent.tool_name` 仍是旧内部名称；本次不改 Agent，只让平台工具日志记录外部名称并关联对应 AgentRunLog。
- 平台调用记录的最小字段：`tool_call_id`、`idempotency_key`、`request_fingerprint`、`tool_name`、`session_id`、`platform_session_id`、`user_id_hash`、`status`、`result_data`、`error_code/type`、`agent_run_key`、`duration_ms`、timestamps；不保存原始请求或 token。
- 响应查询需要按 `tool_call_id` 提供状态和结果，且必须校验 token；session 查询可保留内部接口，但百宝箱应只使用平台查询接口。
- 固定成功数据建议：匹配工具返回 `session_id/status/match_result/agent_run_id`；路径工具返回 `session_id/status/career_roadmap/agent_run_id`。两者都不返回画像原文。

## 实现与首轮验证

- 主应用 OpenAPI 已只增加 4 个阶段3平台 operation，并自动生成 `TBoxBearerAuth` HTTP bearer security scheme。
- 实际接口验证确认：匹配结果与 MatchService 逐字段一致；路径返回独立 3/5 年 roadmap；重复调用不新增 AgentRunLog。
- 平台调用表只含 user_id 哈希、请求指纹、CareerState 结果字段指针和关联 run_key；测试证明不含明文 user_id、token、画像姓名或证据文本。
- 完整 Mock 采用最小匿名单能力数据，仍是由真实 MatchAgent/MatchService 接口输出并能通过冻结请求/响应 Pydantic Schema。
- 最终代码复核后，前置条件阶段被拒绝的工具调用不再伪造 `agent_run_key`；只有实际存在 AgentRunLog 时才建立关联，超时则显式生成安全失败 AgentRunLog。
- `schema_version` 现为真正必填的 const 字段，tool/agent run 标识也有固定长度与字符约束；status/result 两个查询均验证 tool_call_id。
