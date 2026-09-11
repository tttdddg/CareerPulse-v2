# 阶段4 MCP 仓库侧接入发现（2026-08-27）

## 初始边界与工作树

- 目标是把三个已经真实化的阶段4内部 handler 注册到现有 MCP Server，使 `tools/list` 为 7；不进入百宝箱、Cloudflare、固定 Token 或现场联调。
- 任务开始时 `backend/app/mcp/server.py`、`backend/tests/test_mcp_server.py`、`docs/a02/04_API_CONTRACTS.md`、`docs/a02/16_MCP_SERVER_INTEGRATION.md` 已有上一任务未提交的扁平参数兼容改动，必须原样保留并增量编辑。
- `docs/a02/17_STAGE5_INTERFACE清单.md` 和两份开发日志为任务开始前未跟踪文件，本轮不擅自覆盖。
- planning skill 的 session catchup 脚本缺失；已通过计划文件和 Git diff 恢复，不再重复失败命令。

## 待核查

- 三个内部 Request/Result Schema 的精确字段、联合校验和错误 envelope。
- 现有 MCP 测试的官方客户端、tools/list、连续会话、鉴权与业务失败测试模式。
- 公共 API 契约、MCP 工具目录和集成说明中所有“4 工具/阶段3/规划中”表述。
- `server.py` 元信息应如何从 stage3 更新为准确的阶段4 MCP 能力状态，同时避免声称平台现场已配置。

## 实现与 Schema 核查

- 现有唯一注册工厂为 `create_career_mcp_server()`；四个阶段3函数均使用 `@server.tool(..., structured_output=True)`，函数内构造严格 Request 后直接调用同一个 `CareerMCPToolService`。注册完成后统一把 SDK 动态参数模型改为 `extra="forbid"` 并重建 JSON Schema，因此新增工具只要放在该循环之前就自动获得同样的未知字段拒绝语义。
- `server.py` 当前扁平化改动只影响 Profile/Job 两个公开签名和适配构造；新增注册必须在其后增量添加，不能恢复嵌套 `StudentProfileInput` / `TargetJobInput` 参数。
- `GenerateAndScoreTrainingRequest` 已严格区分两种模式：无 `user_answer` 时要求 `training_type` 且禁止 `training_id`；有 `user_answer` 时要求 `training_id`，可选 `training_type` 仅用于与存储任务做一致性检查。
- `RecommendLearningAndJobResourcesRequest` 只有公共 `session_id/user_id/trace_id`，调用方不能覆盖 gaps 或 target job。
- `SaveGrowthFeedbackRequest` 要求 `satisfaction: Rating`，三个分项 rating 和最长 10000 字符 comments 可选。
- 三个 Result 均继承现有 `MCPToolResult` 成功/失败一致性 envelope；成功分别返回 Training task/score、ResourceService 四类结果、FeedbackAgent 完整结果，失败必须为 `data=None + error_code`。
- `CareerMCPToolService` 三个 handler 已完整实现状态加载、身份绑定、trace 幂等账本、安全错误 envelope 和持久化；MCP 注册层无需也不应复制任何前置、训练、资源或反馈逻辑。
- 现有内部工具测试已经覆盖 handler 的 generate、score、resource、feedback、非法 Schema、业务前置失败、隐私、LLM fallback、ResourceService 失败、session 隔离与幂等；新的 MCP 测试重点应验证官方协议适配，而不是重复 Service 算法。

## 现有 MCP 测试与文档核查

- `backend/tests/test_mcp_server.py` 使用官方 MCP `Client(..., mode="legacy")` 覆盖 initialize、tools/list/call、阶段3四步状态链、HTTP 等值、前置失败、未知字段、Streamable HTTP Bearer；当前本地 list 集合和远程 list 数量分别硬编码为 4。
- 当前测试 Orchestrator 只注入 Profile/Job/Match/Path 四个 Agent。要从 MCP 协议真正调用 Training/Feedback，测试 fixture 必须增量注入真实 `TrainingAgent` / `FeedbackAgent`（使用现有离线 LLM double 和真实 Service），不能 mock MCP handler。
- 阶段4 MCP 成功链可复用 `_run_chain()` 先建立同一 session 的真实 profile/job/match/path，再在同一个 `Client` 上执行 training generate → score → resources → feedback；这同时覆盖用户要求的连续发现和多工具调用。
- `docs/a02/13_MCP_TOOL_CATALOG.md` 顶部和总览明确声称只注册 4 个且阶段4未注册，§5 的 Training 输入还是旧 `student_id/job_id` 规划契约，§6 允许 caller 提供 gaps/target job；这些都必须改成真实 session-state 契约，不能只替换标题状态。
- `docs/a02/04_API_CONTRACTS.md §1.4` 当前只定义 `stage3-mcp-v1` 四工具；应以加法方式升级为阶段4七工具，保持 §1.3 HTTP `stage3-tool-v1` 不变。
- `docs/a02/16_MCP_SERVER_INTEGRATION.md` 工具表、四步措辞、测试覆盖和百宝箱 `tools/list` 数量均仍是 4；需要加入三个真实工具、请求样例、前置/业务错误和“代码已注册但平台未现场配置”边界。
- 文档检索命令包含 Windows 不接受的 `backend/README*` 字面路径，导致该单项报错；其他指定文档均成功读取，后续使用 `rg --files` 解析路径，不重复该形式。

## 冻结的公开 MCP 设计

- `generate_and_score_training` 公开参数固定为 `session_id/user_id`、可选 `trace_id/training_type/training_id/user_answer`；`training_type` 使用现有三值 `TrainingType`。Request 的 model validator 是模式裁决唯一来源：generate 要求 `training_type`，score 要求 `training_id + user_answer`，不拆工具。
- `recommend_learning_and_job_resources` 公开参数只有 `session_id/user_id/trace_id`，确保能力缺口和目标岗位只能从同一 session 的 State 投影。
- `save_growth_feedback` 公开参数为 `session_id/user_id/satisfaction`、可选 `trace_id/path_rating/training_rating/resource_rating/comments`；四个 rating 均复用严格 1–5 `Rating` 类型。
- Server 元信息升级为 `stage4-mcp-v1`，描述七工具 session 流程；instructions 明确先画像/岗位/匹配/路径，再按需训练、资源、反馈。该版本只表示仓库侧 MCP 能力版本，不表示百宝箱现场发布。
- 协议测试将保留现有四工具断言并新增：7 名称/Schema、同一 Client 的阶段3+阶段4连续成功链、三个非法/缺失参数拒绝、阶段4业务失败安全 envelope、原有远程 Bearer list/call 数量回归。
- 测试 LLM 继续使用统一离线失败 double；TrainingService 的确定性 fallback 和 FeedbackAgent 的文字 fallback均为真实生产路径，不在 MCP 层造返回值。
- `Status` 已包含 `TRAINING_STARTED/COMPLETED` 和 `FEEDBACK_STARTED/COMPLETED`，无需扩展状态枚举。
- `04_API_CONTRACTS.md` 自身要求任何修改先在 `decisions/` 建 ADR。由于本次把三个规划工具改为真实公开注册并纠正旧入参，属于加法公共契约变化；将新增 `ADR-003-stage4-mcp-tool-registration.md`，记录不改 HTTP API、只激活现有 MCP Server、State 自动补齐上下文和未现场发布边界。
- 现有 ADR 风格为简洁的“背景/决策/影响”，状态 Accepted；ADR-003 将沿用该格式，不引入新的流程或架构。

## 首轮实现验证

- 三个 `@server.tool` 薄适配器已加入唯一 MCP Server 工厂；函数体仅构造对应 Request 并调用同名 `CareerMCPToolService` 方法。
- Server 元信息已更新为 `stage4-mcp-v1`；原 Profile/Job 扁平签名及其构造逻辑完整保留。
- MCP 测试 fixture 已加入真实 TrainingAgent/FeedbackAgent，原四工具仍走原路径；新增连续测试在同一 Client/session 中执行 tools/list、阶段3四步、Training generate/score、Resource、Feedback。
- 首次定向测试 10/11 通过，唯一错误为测试把 `CallToolResult` 当列表；改用官方 Client 后 `python -m unittest tests.test_mcp_server -v` 为 `11 passed`。
- 通过的协议测试已证明：tools/list 为 7、Training 两分支成功、Resource/Feedback 成功、非法 enum/extra/rating 与缺参被拒、业务失败返回安全 envelope、远程 Bearer 鉴权仍工作。

## 关联契约补充核查

- `05_AGENT_CONTRACTS.md` 与 `04_API_CONTRACTS.md`/工具目录声明捆绑；其 Training/Feedback 段仍保留旧规划措辞（LLM 生成训练题/分数、默认 60、Redis 补写等），与已经验收的真实 Agent/Service 不一致。
- 本轮将只在相关 Training/Feedback 段做事实纠正：列出真实 MCP 瞬时输入、数值归属确定性 Service、可选 LLM 仅做语义/文字、Service 失败使用安全错误而非虚构分数或保存成功；不改 Agent 公共输出字段。
- 文档检索再次因 Windows 裸 wildcard 路径单项报错；已用 `rg --files` 获得精确清单，后续不再重复该命令形式。

## 实际运行 Schema / Service 复核

- 直接调用唯一 Server 的实际 `list_tools()` 返回 `COUNT 7`，名称依次为原四工具加三个阶段4工具；三个新 input schema 均为根层 `additionalProperties=false`。
- Training 实际 tools/list 必填仅 `session_id/user_id`，三个模式字段为可空；三值 enum 正确。跨字段 generate/score 约束由适配器内现有 `GenerateAndScoreTrainingRequest` 二次严格验证。
- Resource 实际公开 properties 精确为 `session_id/user_id/trace_id`；Feedback 必填 `session_id/user_id/satisfaction`，四个 rating 的 JSON Schema 均带 1–5 边界。
- ResourceService 真实返回四字段：`learning_resources`（最多 10）、固定空 `job_resources`、`certificate_suggestions`、`data_quality_flags`；FeedbackService 返回保存标志、archive 标志、priority updates、growth snapshot 和 flags，Agent 只加自然语言摘要。文档已按这套形状更新。

## 分组回归结果

- 阶段4 MCP + 内部工具 + 最终 E2E：`python -m unittest tests.test_mcp_server tests.test_stage4_internal_tools tests.test_stage4_final_e2e -v`，29/29 通过。
- 阶段3 MCP + HTTP 平台工具 + E2E：`python -m unittest tests.test_mcp_server tests.test_tbox_stage3_tools tests.test_stage3_e2e -v`，26/26 通过。
- 两组均包含原四 MCP 工具回归；远程 Streamable HTTP 401/成功、tools/list=7、阶段3 HTTP OpenAPI 与确定性 Match/Path 均未回归。

## 完整回归结果与既有阻塞

- `python -m unittest discover -s tests -t .`：180/180 通过；这是仓库后端顶层完整测试集，较任务前 177 项增加 3 个 MCP 协议测试。
- 额外 `python -m unittest discover -s app -t .`：运行 77 项，70 通过、6 failures + 1 error。失败精确为 5 个 `ProfileAgentTests` 和 2 个 `MockCareerFlowTests`，根因是任务开始前已知缺失 `prompts/profile_agent/system.txt` 与 `user_template.txt`；与前序 D4 验收记录一致。
- 本轮未修改 ProfileAgent、prompt 或旧 Mock flow；不会为 MCP 接入猜写业务 prompt 或降低旧断言。将运行 Match/Path/Training/Feedback Agent 适用套件证明相关代码无回归。
- 排除上述已知 Profile/Mock 阻塞后，Match/Path/Training/Feedback Agent 适用回归 60/60 通过；三个阶段4真实 Agent/Service 边界无回归。

## 最终差异初审

- `python -m compileall -q app tests` 与 `git diff --check` 均通过；只有 Git 对工作树 LF/CRLF 的提示，无 whitespace error。
- `backend/app/services`、`backend/app/mcp/tool_service.py`、`backend/app/orchestrator`、`backend/app/main.py`、`backend/app/platform` 的 diff 均为空，证明未重写 Service/handler、总体架构、挂载或鉴权。
- `server.py` 相对 HEAD 的 diff 同时包含任务前扁平 Profile/Job 参数改动和本轮三个注册；逐段检查确认扁平字段、构造逻辑及原四工具完整保留。
- 实际业务差异集中于 `server.py`、阶段4 Schema 模块说明、MCP 协议测试；其余为 ADR/契约/接入文档和 planning skill 工作记录。
- `feedback_schema.py` 曾因本轮注释试改后恢复，`git diff` 已为空；Git status 仍受行尾/索引状态显示 M，但没有内容差异，不把它列为交付变更。

## 最终协议与文档证据

- 最终 `python -m unittest tests.test_mcp_server` 再次 11/11 通过。
- 直接运行时清单为 7：`build_student_profile, analyze_target_job, analyze_job_match, generate_career_path, generate_and_score_training, recommend_learning_and_job_resources, save_growth_feedback`。
- 工具目录阶段4范围内 8 个 `json` fenced blocks 均通过 `json.loads`；指定活动文档没有残留“只注册/阶段4规划未注册/读取四工具”的声明。
- `feedback_schema.py` 工作树 blob 与 HEAD blob 均为 `21779afd74f4a671576ecda17045b5f0e499ff5b`，确认无内容变化。
- 最终组合命令的退出码 1 仅来自末尾 `rg` 无匹配；此前所有实际检查均为成功输出。

---

# 2026-09-11 阿里云 ECS 第一阶段部署准备发现

- 前序只读审计确认生产入口为 `backend/` 下的 `app.main:app`，MCP 以 Streamable HTTP 挂载在同一 FastAPI 应用的 `/mcp`。
- 当前本机验证基线为 Python 3.11.15；生产依赖需按 Linux/Python 3.11 直接依赖整理，不能采用 Windows 全量 freeze。
- 旧 REST 数据库仍从 `app/config.py` 读取固定 PostgreSQL 参数；本轮只把连接参数迁移到环境变量并保留开发默认值，不创建旧表。
- `report_service.py` 运行时导入 `reportlab`，而现有 `requirements.txt` 未声明；生产依赖必须补齐。
- 当前仓库没有 `deploy/` 资产，也没有 `/healthz`；本轮新增最小部署边界，不改业务路由契约。
- `profile_agent/job_agent` Prompt 文件和旧业务基础表迁移仍缺失，本轮明确不虚构。
- `reportlab` 当前 PyPI 稳定发布 5.0.1 提供通用 Python wheel 且支持 Python 3.11，可作为生产直接依赖固定版本。
- 已安装 `mcp==2.0.0` 暴露的最新协议版本为 `2026-07-28`；smoke test 可使用该版本发送最小 initialize 请求。
- 现有测试没有 `/healthz` 或旧 PostgreSQL 环境配置测试；本轮将新增独立部署就绪测试，不修改既有业务测试断言。
- 配置实现保留 `POSTGRES_CONFIG` 历史符号以降低兼容风险，但 `db.get_db_conn()` 每次连接都会重新读取环境，并新增可配置的 1–60 秒连接超时。
- `/healthz` 已明确排除 OpenAPI，固定只返回 `{"status":"ok"}`；不会触发数据库、LLM、TBox 或 MCP 工具调用。
- 新增部署边界测试 5 项全部通过，`git diff --check` 仅报告仓库既有 Windows 行尾转换提示，无空白错误。
- 部署目录五类资产已齐全；扩展后的部署边界测试 8/8 通过，覆盖 Nginx 关键指令、systemd loopback/single-worker 和环境模板空密钥。
- 当前 Windows 执行环境没有 `bash`，因此无法在本机直接运行 `bash -n`；脚本仍需在 Ubuntu 目标机执行语法检查和真实 smoke。
- WSL 可执行文件存在但没有已安装发行版；即使授权也无法提供 Bash/Nginx/systemd 校验环境。smoke 脚本已确认 LF、正确 shebang、无 NUL，并由静态测试覆盖关键内容。
- smoke 使用的原始 MCP initialize 载荷已通过真实 ASGI lifespan 测试：无 Bearer 为 401，有 Bearer 为 200 且包含 result。
- 最终全量测试为 203 passed + 109 subtests；相较前序 194 项，新增 9 项全部纳入 discovery。
- 最终扫描未发现原硬编码 PostgreSQL 密码、猜测旧表 DDL、Prompt/前端变更或部署模板中的非空真实密钥。


# MCP 百宝箱入参兼容修复发现（2026-08-27）

## 初始边界

- 只处理 `build_student_profile` 与 `analyze_target_job` 的 MCP 注册/适配和测试。
- 已知 `analyze_job_match`、`generate_career_path` 在百宝箱调试通过，作为回归基线。
- `tools/list` 必须不再为这两个工具公开嵌套输入模型的 `$ref` / `$defs`。
- 当前尚未读取实现；真实字段和最小签名以代码中的 `StudentProfileInput`、`TargetJobInput` 为准。

## 第一轮代码核查

- 根因已定位在 `backend/app/mcp/server.py`：两个注册函数直接把 `student_input: StudentProfileInput`、`target_job_input: TargetJobInput` 放进 SDK 工具函数签名，SDK 因而把它们生成为嵌套 Pydantic object Schema；百宝箱侧却按 String 传入，SDK 在进入适配函数前即校验失败。
- `StudentProfileInput` 不是单一自然语言字段。真实字段为 `resume_text`、`form_fields`、`form_data`、`parsed_data`、`skills`、`education`、`projects`、`internships`、`work_experience`、`competitions`、`certificates`、`supplementary_info`，且要求至少一个非空证据。
- `TargetJobInput` 真实字段为 `job_id`、必填 `job_title`、`industry`、`city`、`job_description`、`trend_context`。
- 共享 `CareerMCPToolService` 当前只接收已构造好的 `BuildStudentProfileRequest` / `AnalyzeTargetJobRequest`，再原样调用 Agent/Service；因此兼容修复可完全限制在 MCP 注册适配层与 MCP 测试，不改业务 Service。
- 现有 MCP 测试仍用嵌套 `student_input` / `target_job_input`，`tools/list` 只断言嵌套参数名存在，没有阻止 `$ref/$defs`，正好解释为何本地通过而百宝箱失败。
- 相关实现和测试文件当前 `git diff` 为空，本轮可以做清晰的最小增量修改。

## 公开签名设计

- `build_student_profile` 公开模型/现有 Service 使用的基础字段：`resume_text`、教育与目标表单标量、字符串数组形式的技能/经历字段、`supplementary_info`；适配层把表单标量归入真实 `form_fields` 后构造 `StudentProfileInput`。仅接受 mapping 的 `form_data/parsed_data` 不再作为 MCP 入参暴露，HTTP/内部模型不变。
- `analyze_target_job` 将公开 `job_title: str`（必填）、`job_id: int | null`、`industry/city/job_description/trend_context: str | null`；适配层构造 `TargetJobInput`。`trend_context` 选择真实模型已经支持的字符串分支，不公开 object/任意元素列表分支。
- `session_id`、`user_id` 仍必填，`trace_id` 仍可选；后两个通过工具签名保留原名和语义。
- 新 Schema 测试需要递归断言两个输入 Schema 不含 `$ref` 或 `$defs`，并逐字段验证顶层类型；同时断言旧嵌套参数名不再出现。
- `docs/a02/04_API_CONTRACTS.md` 是 AGENTS 规定的公共 Schema 所有者，必须同步；`docs/a02/16_MCP_SERVER_INTEGRATION.md` 的百宝箱 JSON 样例也必须同步，避免现场继续填写旧嵌套对象。

## 第一轮验证

- `python -m unittest tests.test_mcp_server -v`：8 项全部通过。
- 两个新增普通 JSON 测试已通过，并验证适配层写入 State 的内部 `student_input.form_fields`、技能列表和 `target_job_input` 与扁平参数一致。
- 现有四工具完整链、Match/Path 与 HTTP 结果逐字段一致性、远程 Streamable HTTP 鉴权、前置错误和未知字段拒绝均通过。
- `tools/list` 测试已验证两个目标工具的 input schema 中没有 `$ref` / `$defs`，也没有旧的 `student_input` / `target_job_input` 属性；`job_title` 是顶层必填字符串。
- 直接打印 SDK 注册后的实际 Schema 再次确认：根层 `type=object`、`additionalProperties=false`；基础字段只出现 `string`、`integer`、`number`、`array(items=string)` 与可选 `null`，没有 object 类型的业务入参。
- 阶段3正式 HTTP 工具回归 `5/5` 通过，阶段3端到端 Match/Path 回归 `10/10` 通过；HTTP 鉴权/OpenAPI、匹配、路径、幂等、超时、持久化与确定性结果未回归。

## 最终验证与范围

- `python -m unittest discover -s tests -t .`：backend 全套 `177 passed`，无失败。
- `python -m compileall -q app tests`：通过。
- `git diff --check`：通过；只有仓库现有 LF/CRLF 提示。
- `backend/app/services`、`backend/app/platform`、`backend/app/main.py`、`backend/app/schemas/mcp_tool_schema.py` 均无差异，证明 Service、鉴权/HTTP 集成、应用挂载和真实输入模型定义没有被改动。
- Git 状态中的 3 个未跟踪文档为任务开始前已存在的用户文件，本轮未触碰。

---

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
# 当前任务发现：MCP Tool Calling 兼容性（2026-08-28）

- `planning-with-files` 的会话恢复脚本在当前安装目录不存在；已改用现有三份规划文件与 Git 状态恢复。
- 现有规划文件包含历史 MCP/百宝箱任务记录；本次以新的“当前任务”章节追加，不覆盖历史证据。
- Git 状态命令只返回 `backend/.pytest_cache/` 权限警告，尚需用更精确的 diff/status 命令核对已有改动。
- `backend/app/mcp/server.py` 是 7 Tool 的唯一 MCP 注册/扁平适配层；它在函数内重建严格 Request Model，适合实现“外宽内严”。
- 当前公开签名仍直接暴露 `list[str] | None`（profile 的 6 个多值字段）、`TrainingType | None` Literal，以及严格 `Rating` int，因此请求会在进入适配函数之前被 MCP SDK 动态 Pydantic 参数模型拒绝。
- `analyze_job_match` / `generate_career_path` / resource 只对外暴露 `session_id` / `user_id` / 可选 `trace_id` 三个字符串，无复杂输入；状态通过 `CareerMCPToolService` 从 repository 按 session 读取。
- 内部 `TrainingType` 为三值 Literal，`Rating` 为 `strict=True` 且 1..5 的 int；必须在 MCP 公开签名先接受基础类型并标准化，再构造两个严格内部 Request。
- 历史计划显示 2026-08-27 已有一轮“百宝箱入参兼容修复”，但当前 `server.py` 的 skills/projects 已回到/仍是 list；需读取该历史章节与 Git diff 确认演变，不盲目重复方案。
- 2026-08-27 历史结论声称 profile/job 公开 Schema 已基础类型化，当前 Git 对 `server.py` 无 diff，但现行基线测试明确断言 skills 为 array。本轮应以当前源码/运行 Schema/用户实测为准，不依赖历史结论。
- `StudentProfileInput` 内部实际允许 skills 为 list 或 string，其他 profile 多值字段也允许 list/string；但用户要求的严格列表重建应在 MCP Adapter 完成，并将 list 传入不改动的内部 model。
- `TrainingService` 和任务数据只有远程协作、AI 办公任务、跨角色沟通三类；任务数据无“面试自我介绍”。因此该自然语言不属于可安全映射的现有类型，必须返回清晰不支持错误，不能偷映射到“跨角色沟通”。
- 现有 MCP 主测试会校验 training_type 对外 enum 和 satisfaction 整数范围；本轮需按新的 Adapter 边界更新这些 MCP 专用预期，同时保留内部 Request/Service 的 Literal 和 strict Rating 测试。
- 修改前 MCP 基线主测试 `11/11` 通过；这说明当前错误是对外入参兼容性缺口，不是 MCP 连通或内部链路整体失效。
- 运行时 `tools/list` 审计确认所有输入根 Schema 均 `additionalProperties=false`，且对外无嵌套 model / `$ref` / `$defs`；复杂风险集中在 array、Literal enum 和严格数字。
- fallback 是明确设计：`BaseAgent` 在主执行的依赖、Prompt、外部 LLM、JSON/Schema 校验等任何异常后标记 `fallback_used=True`并运行 Agent 专属 fallback。MCP 测试主动使用永远失败的 `OfflineLLMClient`，所以 profile/job 的 fallback 标记是预期演示行为。
- 真实环境中出现 fallback 表示 Agent 主路确实异常后自动降级（如模型未配置/请求失败、Prompt 资产缺失、模型输出校验失败），并非主逻辑“正常成功”的同义标记；但是当 fallback 产出经严格 Schema 验证时，工具仍可安全返回 partial/可用结果。
- 新 Adapter Schema 已通过编译和运行时生成检查：profile 多值字段的 `anyOf` 以 string 为首选并保留 array；training_type 不再暴露 enum；feedback 评分接受 string/integer；所有对外参数已有 description，无 `$ref/$defs`。
- 其他五工具中，match/path/resource 只有 session/user/trace 字符串；job 只有 `job_id` 的数字字符串风险；feedback 只有四个评分的数字字符串风险。对外无 bool/dict/嵌套 Model，因此未引入无用 bool/dict 转换。
- session/user 在 7 Tool 中继续是必填基础字符串；`CareerMCPToolService._load_or_create/_load_required/_check_identity` 继续保证同 session 状态串联和 user 所有权，本次未改 session mapper。
- 路径结果中的 `fallback_target` 是 PathService 对职业图未命中目标岗位时的可解释确定性降级；TrainingService 的 fallback 评分是 LLM 分析缺失/无效时的确定性文本覆盖算法；ResourceService 的 unknown-tag flag 是知识资源未命中标记。这些都是正常设计触发，本次未改逻辑。
- 但 ProfileAgent/JobAgent 的 Agent-level fallback 在当前仓库还有具体主路异常原因：根目录对应 Prompt 资产缺失。这不是本次 MCP 参数兼容修复的回归，也不应在 Adapter 中掩盖。

## 当前追加任务发现（2026-08-28）

- 用户现场仍看到 skills=array-only 和 satisfaction=integer-only 错误；需将本地当前源码/运行时 Schema 与现场已发布 Schema 分开验证。
- 前一轮 normalizer 已支持逗号字符串和真实 list，但尚未支持形如 `["Python", "Vue3"]` 的 JSON 数组字符串；这是本轮明确要求的新增兼容点。
- 当前工作区 `server.py` 已将六个多值字段声明为 `str | list[str] | None`，四个评分字段声明为 `str | int [| None]`；适配函数也已调用统一 list/int normalizer。
- 从 `D:\vue\CareerPulse-Pro\backend\app\mcp\server.py` 实际 import 并生成的本地运行时 Schema 显示：skills/projects/competitions 均含 string+array 分支，satisfaction/resource_rating 均含 string+integer 分支。
- 因此用户现场引用的 array-only/integer-only 报错不可由当前工作区代码复现；高概率是运行中后端/MCP 仍为旧进程、未部署当前改动，或百宝箱仍缓存旧 tools/list。本轮仍需补足 JSON 数组字符串和明确回归。
- `parse_optional_list` 现在对以 `[` 开头的字符串先做 JSON 解析；只接受数组且每项必须是字符串，保留 JSON 元素内部的逗号，无效 JSON/非字符串元素明确报错。
- 六个 profile 多值字段共享同一 normalizer，因此 skills/projects/internships/work_experience/competitions/certificates 同步获得逗号文本、JSON 数组文本和真实 list 支持。
- MCP Server 精确回归覆盖 skills 的分隔字符串、JSON 数组字符串和真实 list，以及 satisfaction/resource_rating 的数字字符串和原生整数，`19/19` 通过。
- `backend/tests` 全量回归 `188/188` 通过；未发现另外五个 MCP 工具的行为回归。

---
# 2026-09-03 百宝箱对话适配层发现

- 工作区当前仅有上一轮前端真实数据整改和两份用户开发日志未提交；`backend/` 开始时无差异。
- 仓库已有标准 MCP Server、`CareerMCPToolService`、平台工具 HTTP API 和旧 `platform/tbox_adapter.py` Mock；新对话适配不能复用旧 Mock 冒充正式智能体 API。
- 当前规划技能的 session catchup 脚本缺失，已按既有记录改用规划文件和 Git 状态恢复。
- `create_app()` 已集中注入运行配置并支持测试参数覆盖；适配层应继续走 `application.state`/依赖注入，避免模块级读取密钥。
- 现有 `A02_TBOX_API_TOKEN` 是“百宝箱调用 CareerPulse 工具”的入站 Bearer，不应复用于“CareerPulse 调用百宝箱智能体”的出站凭据；需新增语义独立的配置名。
- 旧 `platform/tbox_adapter.py` 只是独立 Mock 全链端点，没有挂到主应用；不能作为新 `/api/tbox/chat` 的实现。
- 现有项目未直接声明 `httpx`；实现出站普通/流式 HTTP 前需核对环境依赖与可锁定版本。
- 平台工具异常处理仅覆盖 `/api/platform/v1/tools` 的校验错误；新 chat 入口应有独立安全错误模型/处理，不改变已有工具错误契约。
- 可公开核验的官方 Ant Design X TBox 集成文档确认：Node SDK 以 `authorization: 'Tbox-...'` 初始化；`client.chat()` 的稳定示例入参至少包含 `appId`、`query`、`userId`，返回事件流并提供 data/end/error 事件。
- 官方页面链接到百宝箱开放平台、授权管理和 OpenAPI 语雀文档，但当前浏览器无法直接打开这些语雀/开放平台 URL；尚未从官方公开页核实底层 HTTP endpoint、原始请求字段、会话字段和 SSE 事件结构。
- 因此不能根据第三方博客或演示代理端点写死生产 URL/协议；下一步应检查官方 SDK 包的元数据/源码，或让底层 endpoint 可配置并在缺配置时 fail closed。
- npm 当前公开的 `tbox-nodejs-sdk` 最新可见版本为 `0.0.19`，README 同时确认 `chat()` 流式与 `chatSync()` 非流式两种调用；SDK README 标注的 GitHub 仓库当前返回 404。
- PyPI 存在非官方/来源待核验的 `tboxsdk`，不能仅凭同名包作为企业版正式协议依据。
- 官方 SDK 的 CDN/registry 详情不能通过网页读取；可在受控临时目录下载 npm tarball，检查其实际 URL、headers、payload 和事件解析，不向项目添加 Node 运行时依赖。
- 本机 npm 被配置为只读缓存且无该包缓存，registry 下载又被不可用代理阻断，无法从 tarball 补充核验底层 endpoint。
- 当前可证明的正式公共契约只到 SDK 层：`TBox-...` authorization、`appId/query/userId`、流式 `chat` 与同步 `chatSync`。后端适配应将上游 URL 作为必填部署配置，并把 body/header 字段限制在这些已核验字段；会话延续字段需保持可配置/按真实响应提取，不能猜固定平台字段。
- 阿里云开发者社区转载的百宝箱开放平台文档给出正式 OpenAPI：`POST https://api.tbox.cn/api/chat`，请求头 `Authorization`、`Content-Type: application/json`，流式使用 `Accept: text/event-stream`。
- 请求字段：`appId/query/userId` 必填，`conversationId/files/searchEngine/stream` 可选；`stream` 默认 true。多轮应把前次返回的 `conversationId` 传回。
- 流式是标准 SSE：`id/event/data`；`data` JSON 中 `type=header|chunk|meta|thinking|end`，其 `payload` 又是 JSONString。header payload 的 `sessionId` 即 conversationId；chunk payload 包含 `text/conversationId/messageId`；结束事件为 `event:end`、`data:{"type":"end"}`。
- 非流式成功体外层为 `errorCode/errorMsg/data/traceId`，文档示例也可能直接展示单个 ChatResponse；ChatResponse 具有 `requestId/conversationId/messageId/result[]`，文本答案位于 `result[].mediaType=text` 的 `chunk`。
- 本轮前端统一响应应只暴露普通文本、CareerPulse session id、TBox conversation/message/request id；不向 Vue 透传 thinking/meta 原始节点数据，避免内部工作流和潜在敏感内容泄露。
- 当前运行环境已安装 Python 3.11.15、FastAPI 0.133.1、Pydantic 2.13.4 和 httpx 0.28.1；实现无需升级现有依赖，但应把直接运行依赖 `httpx` 写入 requirements。
- `backend/app/main.py` 已将 `A02_TBOX_API_TOKEN` 用作“百宝箱调用 CareerPulse 工具”的入站 Bearer；正式智能体出站 Token 必须使用独立配置名，不能复用。
- 仓库实际持久化模块是 `backend/app/db_state.py`，环境样例也不在 `backend/.env.example`；后续只按 `rg --files` 的实际结果定位。
- `CareerState.platform_session_id` 已是冻结契约中的百宝箱会话字段，StateRepository 会将其同时写入状态 JSON 和列；本轮无需新增映射表或数据库迁移。
- session mapper 将复用 CareerOrchestrator 持久化，并对同一 CareerPulse session 的对话调用做进程内串行化；首次上游返回的 conversationId 持久化后，后续请求必须带回。
- `platform_tool_calls` 可复用为出站对话调用的隐私安全账本：每次生成独立 `chat-*` 调用 ID，request fingerprint 只存 SHA-256，result_data 只存模式/是否映射等元数据，不保存 prompt 或 answer。
- 新浏览器契约采用严格 `session_id/user_id/message/stream` 请求；普通响应为固定 envelope，流式统一成 `session/delta/done/error` SSE。上游 `thinking/meta` 不透传。
- 自动重试可能导致非幂等聊天重复执行；本轮对超时/5xx采取显式可重试错误，不在适配器内盲目重试。
- 出站百宝箱 `userId` 不使用 CareerPulse 明文 user_id；适配层用独立 `TBOX_USER_ID_SECRET` 做 HMAC-SHA256，发送稳定的 `cp_<digest>`，密钥缺失时同样 fail closed。

---

# 2026-09-06 CareerPulse Vue 成长闭环发现

- 当前前端相关页面和 API/Store 已有大量未提交改动，必须先按 diff 区分既有成果，再做最小增量，不回退任何已有真实数据整改。
- 根目录与 `front/` 均存在历史规划文件；本轮沿用根目录规划记录，不覆盖前序任务内容。
- `planning-with-files` 安装目录只有 `SKILL.md`，会话恢复脚本缺失；已改用 Git 状态和现有规划文件恢复。
- 主布局固定为 240px 浅灰 Sidebar、74px Header、`#f2f4f8` 主背景和 26/30px 内容边距；Sidebar 菜单是扁平 54px 行高、无圆角、靛青 active 背景，不能另造后台壳层。
- 全局设计变量以 `#6366f1` 为 primary、`#8b5cf6` 为 secondary，正文 `#0f172a`、弱文案 `#475569`、边框 `#e2e8f0`；字体为 Noto Sans SC + Manrope，Element Plus base radius 10px。
- 现有业务页通常以白色、1px 浅边框、16px 圆角、无全局卡片阴影的 `el-card` 作为 panel；局部强调区域使用现有淡靛青背景/渐变，不应引入玻璃拟态或新渐变体系。
- `GrowthPlan.vue` 当前只有报告编辑器和简化学习建议侧栏；其资源项将 `/recommendations` 的字符串映射为“学习建议 N”，丢失了潜在结构化字段，需要先审查 API 契约再决定真实展示字段。
- `Profile.vue` 已真实调用 histories/snapshot，保留历史卡片、详情 Dialog 与 `GrowthChart`；当前 growth 数据完全来自历史接口，不能用静态点补齐。
- 现有小屏基础只在约 900/1150/1200px 将壳层或双栏改为单栏；本轮延续 CSS Grid 自动换行和流式 Dialog 宽度，不进行全站移动端重构。
- 六个业务页的稳定页面结构是：页面级 flex column + 16/18px gap、`.page-head` 标题/说明、`.panel` `el-card`、面板内 `.panel-head`、真实加载 `v-loading`、错误 `el-alert`、无数据 `el-empty`；新页面应直接复刻这套节奏。
- 数据输入页主标题为 28px，常规页多用 22px 左右 section heading；正文/元信息集中在 13–14px，颜色约 `#5d6780`/`#667089`，卡片内边框项用 12–14px 圆角。
- 岗位库的资源型卡片最适合作为新学习资源/训练类型卡片基准：`repeat(auto-fill,minmax(280px,1fr))`、1px `#dde4ef` 边框、12px 圆角、12px padding、10px 内部 gap，按钮沿用 Element Plus primary/plain。
- 分析页统一使用 `el-tag` 表达分类/状态、内联空值显示“待补充/待分析”，图表仅在真实数据存在时渲染；成长页将沿用同样的数据诚实性与状态词汇。
- Path 页面局部比其他页面更强的 20px 圆角/阴影属于图谱语境，不适合作为三项新能力的默认；本轮以 GrowthPlan/Profile/JobLibrary 的 16px panel 与 12px content card 为主。
- 现有页面标题语言偏直接业务名 + 一行解释；训练页可按指定标题与说明直接置于 `.page-head`，不增加 hero、游戏化计分或独立视觉壳。
- 前端 API 目前集中在单一 `career.ts`，采用 `unknown` 入参 + 类型守卫/normalizer + 明确错误的 Adapter 方式；新增 Training Adapter 应保持同一层次与严格类型，不让 View 解析后端原始结构。
- 当前 Analysis store 只保留当前 session 内真实匹配上下文（目标关键词、岗位、分数、gaps、student/job/report id）；可用于成长计划顶部概览，但刷新丢失时必须显示“暂无”，不能补默认岗位或分数。
- History store 的本地存储只是服务端真实 histories 的缓存；Profile onMounted 会以 `/users/{userId}/histories` 覆盖，因此成长概览可使用其 `reports/growthSeries`，不能把本地缓存当成新学习/训练事实来源。
- `career.ts` 的 `/recommendations` Adapter 当前把结构化响应压扁成 `string[]`，甚至拼为“标题：URL”；为了展示资源类型、能力、理由、链接、来源，需要把 Adapter 返回类型增量升级为结构化 `LearningResource[]`，同时兼容字符串响应但不推断缺失字段。
- 共享图表组件均在 mount/watch 渲染并监听 `window.resize`、unmount dispose，满足新增档案页 resize 要求；无需新增图表实现。
- `RichTextEditor` 与 `ExportButton` 已承载原报告的润色/检查/导出交互，GrowthPlan 必须继续复用，不能以新卡片替换或删除。
- 后端阶段4 Training/Resource/Feedback 的正式实现目前集中在 Agent/Service/MCP tool service；首次路由检索未发现对应 Vue HTTP Router，Training 页面应先按“服务接入中” unavailable 交付，除非后续精确路由审计发现现有 HTTP 入口。
- 当前工作区 diff 证明前序前端任务已经主动删除了默认报告、本地导出 fallback、固定学习资源、假 growth 曲线、假用户名/邮箱/会员等级和 API 失败后的本地历史成功展示；本轮必须保住这些数据诚实性整改。
- GrowthPlan/Profile 是未提交前序成果，后续修改采用整页增量但必须保留现有真实 API、错误处理与 empty 路径；不得恢复 diff 中已删除的 Mock/fallback。
- 精确路由清单确认 Vue 当前只有 jobs/students/matching/reports/histories/recommendations 等业务 HTTP API；没有 Training、ResourceService 阶段4或 Feedback 的专用 HTTP API。`/api/career-agent/run` 是整条 Agent 输入入口，不是可安全复用的训练生成/评分接口，且当前前端没有其 session id，因此本轮 Training 保持 unavailable。
- `/recommendations` 当前真实 HTTP 返回规则型资源对象：至少含 `type/title/url`；它调用旧 `recommendation_service`，不是阶段4 `ResourceService`，不返回 `target_ability/description/source/job_resources`。前端应保留其真实字段，缺失字段显示“暂无/未提供”，岗位资源展示 empty。
- 后端阶段4正式 Training schema 已核验：任务包含 id/type/title/scenario/task_description/evaluation_criteria/target_abilities/reference_answer；评分包含 total、dimension scores、overall comment、improvement suggestions、ability updates。前端 Adapter 可按该冻结契约定义类型，但不能发起不存在的 HTTP 请求。
- 三种 TrainingType 严格为 `remote_collaboration`、`ai_office_task`、`cross_role_communication`；前端只展示对应的远程协作、AI 办公任务、跨角色沟通，不扩展面试、群面、薪资谈判等能力。
- 成长档案的后端 `GrowthArchive` 契约存在于阶段4 Agent/MCP，但 Vue HTTP 无查询入口；学习记录、训练记录、Feedback 面板只能保留正式 empty/unavailable 结构，不能从其他字段臆造。
- histories Adapter 实际把真实历史报告的非空分数按日期构造成 GrowthChart 数据，因此档案页应将该图明确命名为“匹配分变化”，避免把匹配分误称成全能力成长分。
- Vite 开发代理会将 `/api/*` 重写到后端根路由；career Adapter 中 `url: '/recommendations'` 是现有正确调用方式。生产仍通过 `VITE_API_BASE_URL` 或 `/api`，本轮不改请求基础设施。
- 前端 TypeScript 为 strict + isolatedModules；新增 Adapter/页面需要避免不受控 `any`，保持所有后端结果经 `unknown` 和 normalizer 进入 View。
- GrowthPlan 新结构已按现有组件语言落入：页面标题、四项概览、基于真实 gap 的学习任务、真实 recommendations 资源、岗位资源 empty、原报告编辑/导出区域；下一步完成 computed/API 类型与现有样式收口。
- GrowthPlan 顶部阶段/完成数因 HTTP 无持久字段明确显示“暂无”；学习任务 topic/gap/objective/status 只来自 Analysis store 的真实 gap/gapDetails，建议动作和预计投入缺失时明确显示暂无。
- 资源链接只允许 http/https 后再渲染，类型仅做确定性中文标签转换；target ability/reason/source 没有 API 字段时显示未提供，不从 gap 或域名推断。
- Training Adapter 已定义与后端冻结 Schema 对齐的 task/score/type/lifecycle 类型，但 capability 固定为 unavailable 且方法只会抛明确错误；View 会在实际调用前检查 capability，不发送假请求。
- Training 页面完整承载 idle/generating/ready/scoring/completed/error/unavailable 分支，当前用户选择三种真实训练类型后进入 unavailable，不会显示任务、评分或历史假数据。
- Profile 已转为成长档案结构：真实概览、用户信息、真实历史匹配分曲线、学习/训练/Feedback empty 面板、原历史分析列表与 snapshot Dialog；原 histories/snapshot 调用保持不变。
- 档案概览优先显示当前 Analysis store 的真实目标岗位，缺失时退到最新服务端历史标题；最近匹配分优先最新历史，缺失时才使用当前会话真实 matchScore，不生成零分。
- Sidebar 保持单层结构，只新增现有岗位页与职场训练两个入口，并将已有“职业分析/成长规划/历史记录”统一为“职业路径/成长计划/成长档案”；没有新增分组、折叠菜单或壳层。
- Router 延续 `/app/{noun}` 命名，以 `/app/training` 新增职场训练；`/app/plan`、`/app/profile` 路径完全复用，只更新页面标题 metadata。
- 最终 typecheck 与 diff check 已通过；首次并行 build 只因 `components.d.ts` 并发写锁失败，顺序重跑 production build 成功。
- build 仍有项目既有单 chunk >500k 警告（主 JS 约 3.49MB、gzip 约 1.15MB）；本轮禁止大规模架构/路由懒加载重构，记录为已知非阻断风险。
- Mock 关键词审计在本轮页面/Adapter 未发现固定评分、固定进度、假成长数据或自动成功 fallback；命中仅为 `career.ts` 的通用转换函数 fallback 参数，不是 UI Mock。
- 本机 Chrome/Edge 可用，但 node_repl 的预装 Playwright 包当前无法导入；准备使用 headless Chrome CDP 注入临时视觉检查登录态并截取页面，不改应用认证代码。
- Headless Chrome 最终实测三页 1440px desktop 均成功渲染正确 title/heading，首个 panel 均为 16px radius + 1px border；760px 复核时 `bodyWidth === viewportWidth`，无明显横向溢出。
- 视觉检查中的 Profile 因本地 histories API 不可用显示全局 error 与“历史数据暂不可用”，符合 error 状态要求；GrowthPlan 的 `/recommendations` 正常返回两项真实资源，缺失 reason/source/ability 明确显示未提供。
- 临时视觉脚本、Vite 服务与 Chrome debug 进程均已清理；仅保留三张视觉验收截图在 Codex visualization 输出目录。

---

# 2026-09-06 CareerPulse Vue 全站响应式适配发现

- 本轮继承前一轮已完成的成长计划、职场训练和成长档案页面，不回退其真实 API/empty/unavailable 数据原则。
- Router 当前真实页面为 Landing、Login、Register、DataInput、AnalysisBoard、JobLibrary、PathGraph、GrowthPlan、TrainingPage、Profile；`/app/recommend` 仅重定向，不单独适配已删除原型页。
- 已知主壳层当前以 240px 固定 Sidebar + 74px Header 为 Desktop 基准，但既有 900px 规则把 Sidebar 直接变为整行宽度，无法作为合格手机导航；需改成保持 PC Sidebar、手机 Drawer/Hamburger。
- 前序视觉检查只覆盖成长计划/训练/档案的 1440px 与 760px，不足以证明全站 375/320px 可用；本轮必须重做完整视口矩阵。

- Landing 在 1100px 已降为单列，但没有 `<768px` 规则；手机下仍保留 520px hero visual、四项 metrics 两列、64px/46px 标题过渡与较大的图文间距，320px 高度和密度不理想。
- 当前登录/注册页在 700px 隐藏品牌 panel 并将表单居中，基础方向正确；但短信验证码行的 118px 按钮和输入会在 320px 挤压，需要 <=480px 纵向或更紧凑布局，且表单垂直居中时注册内容在 568px 高度可能越界。
- DataInput 在 1200px 即把双栏字段降为单列、900px 将底部操作降单列；需把 tablet 保留双栏到 768px、手机统一按钮宽度，并让 `el-descriptions` 在手机降为单列（需要响应式 `column` 属性而不只是 CSS）。
- AnalysisBoard 的 summary 两栏直到 720px 才切换，导致 768–900px 在扣除 240px Sidebar 后内容宽度不足；应在 tablet 阶段提前单列。岗位卡 `minmax(240px)`、标题动作栏、rank 标题、目标岗位 pill 和 560px 词云都需手机收口。
- JobLibrary 查询栏在 980px 已单列，岗位 grid 的 `minmax(280px)` 在 320px 主内容扣除 padding/card body 后会产生溢出；手机应显式单列 `minmax(0,1fr)`，卡片头和操作按钮允许换行/纵向。

- PathGraph 页面在 1200px 已把详情与左右路径图降单列，手机指标也会单列；但 Panel header actions 未纵向收口，X6 在 ResizeObserver 中只 resize 画布而不重新 fit，且 auto layout 将安全宽度强制至少 360px，320px 内容区可能裁切节点。当前 X6 版本明确支持 `zoomToFit({ padding, minScale, maxScale })`，可用最小改动实现手机 fit view，并保留 pan/ctrl+wheel。
- GrowthPlan 的任务/资源 grid 在 720px 已单列，但与统一 `<768px` 断点不一致，且报告编辑器工具栏与富文本内图片/表格没有手机溢出处理；需在共享 RichTextEditor 统一修正。
- Training 在 1100px 过早把三类训练卡改成单列；应按 `768–1199px` 两列、`<768px` 单列，并在手机让开始/提交按钮可占满、评分头和长反馈安全换行。
- Profile 固定 Dialog 已使用 `min(560px, calc(100vw - 32px))`，基础宽度安全；仍需统一手机 margin/body max-height、单列 `minmax(0,1fr)`、信息行/历史标题换行以及 chart 容器观察尺寸变化。
- RadarChart/GrowthChart 目前只监听 window resize；Layout 宽度、Drawer 或卡片重排未必触发正确时机，应改为 ResizeObserver，并在窄容器调整 legend/grid/axis label。Analysis 内嵌 gauge/wordcloud 同样只有 window resize，需要观察自身容器。
- AI Assistant 当前宽度 `min(420px, 100vw - 20px)` 基本安全，但手机应贴近 12px 边距、限制短屏高度，并为 header 长标题、消息/Markdown/链接等 slot 内容统一 `overflow-wrap` 和横向滚动边界。

- 有效浏览器矩阵发现全局 `box-sizing` 选择器原本缺少逗号，导致登录表单的 `width:100% + padding` 实际超出容器；虽然 Login 自身 `overflow:hidden` 遮住了 body 横滚，元素仍越过视口。已修正为标准的 `*, *::before, *::after`，解决真实宽度源而非继续遮盖。
- 有效矩阵的全部核心业务路由在 1280、1024、768、430、390、375、320 下 `body/root scrollWidth <= viewport`；手机 Sidebar 为 none、Hamburger 为 flex，768px 边界保持 PC Sidebar。需在修正 box-sizing 后再跑终验，并补跑因 Vite首次预热而空白的 1440 截图。

- 最终浏览器矩阵共检查 62 个主组合，覆盖 1440×900、1280×800、1024×768、768×1024、430×932、390×844、375×812、320×568；另对 375 和 320 各补跑全部 10 个真实路由。最终 invalid、overflow、layout failure 均为 0。
- 移动导航实测包含 7 个核心入口，Drawer 打开正常，点击“岗位”后自动关闭并切换到 `#/app/jobs`；AI 职业伙伴面板在 375px 下为 351px 宽，左右各 12px，未超屏。
- 320×568 注册页首次截图暴露移动切换动画期间登录/注册表单重叠；手机端已关闭该桌面切换延迟，并让登录表单垂直居中、注册表单在自身容器滚动。复测截图显示注册字段与按钮正确单列，无横向越界。
- PathGraph 的真实接口在本地检查环境返回 unavailable，因此浏览器检查覆盖了正式错误/空图状态；X6 有数据时的 `zoomToFit` 与 ResizeObserver 由代码路径和类型检查覆盖，未注入假图谱到页面结果。

---
