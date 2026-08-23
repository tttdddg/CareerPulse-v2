# 标准 MCP Server 发现记录

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

## 实施设计决定（六）

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
