# 标准 MCP Server 执行日志

## 2026-08-24 Hermes 提交前最小收尾

- 已读取 planning-with-files 技能；catchup 脚本缺失，改由计划文件和 Git 状态恢复上下文并记录失败。
- 已复现仓库根运行 `test_tbox_stage3_tools.py` 时 `No module named 'app'`；backend 目录原本 5/5 通过，但其跨测试导入依赖启动目录的命名空间包行为。
- 已新增 backend 级 pytest 配置、测试包标记和共享 `stage3_fixtures.py`，两个阶段3测试改为包内相对导入。
- 已核对 `mcp==2.0.0` 本地包 METADATA：正式依赖 `httpx2>=2.5.0`；隔离安装版本为 2.12.0，因此不新增重复客户端或额外直接 pin。
- 已更新 MCP 工具目录：当前标准 MCP 只注册四个工具，七个旧名称逐项标为历史/规划且尚未注册。
- 修复后仓库根 `test_tbox_stage3_tools.py` 5/5 通过；backend 目录 5/5 通过。后续将用禁用 pytest cache provider 的固定配置重跑最终验证，避免受受限缓存目录警告干扰。
- 最终验证：MCP 定向 6/6、阶段3 E2E 10/10、HTTP Tool API 5/5、`backend/tests` 86/86（另 71 个 subtests）全部通过；`pip check` 无断裂依赖。
- `compileall app tests scripts` 通过，`git diff --check` 退出码 0；MatchService、PathService、`tbox_adapter.py` 无 diff。本轮未修改 MatchAgent/PathAgent，工作区中这两个文件仍有前序任务留下的既有小 diff。
- Token 扫描确认 `.env.example` 的 `MCP_API_TOKEN` 为空，文档仅含 `example-local-token(-change-me)`/占位符，测试仅含 `test-only-mcp-token`；暂存区为空且无 Token 匹配，测试输出未打印 Token，生产仍从环境变量读取。
- 未执行 Git commit、部署、健康端点、deprecated 目录或全仓库 `.gitattributes` 变更。

## 2026-08-21（当前任务）

- 已完整读取 `planning-with-files` 技能并启用文件化计划。
- 技能说明引用的 session catchup 脚本不存在；已记录错误，并通过 Git 状态与既有规划文件恢复上下文。
- 已确认工作区存在前序阶段3与 HTTP Tool API 的大量未提交成果；本任务不会回退或提交这些改动。
- 已建立本次 MCP Server 的分阶段计划、约束和待确认清单。
- 已读取 AGENTS、Python/依赖、后端目录、主应用工厂、CareerState 和 CareerOrchestrator。
- 已确认 Python 3.11.15、依赖文件未锁 MCP SDK、状态持久化和分阶段真实 Agent 调用入口可复用。
- 已审计 Base/Profile/Job/Match/Path Agent 及正式 HTTP 平台 Schema/测试符号，确认工具命名存在历史映射，但真实业务入口和确定性输出模型均可复用。
- 已审计本地分步 API、正式 HTTP 工具实现和持久化账本，决定 MCP 复用 Orchestrator/Agent 与现有平台调用日志，而不通过内部 HTTP 回环或修改 AgentLog 公共字段。
- 已核对官方 MCP Python SDK/PyPI/ASGI/客户端文档，选择稳定固定版 `mcp==2.0.0`，传输只实现 Streamable HTTP，不无依据增加 SSE。
- 已确认宿主预装 MCP 1.26.0；将使用项目隔离运行时验证 2.0.0，不直接升级共享环境。
- 已隔离安装并实查 MCP 2.0.0 源码/API，确认可使用官方 `MCPServer`、原生 TokenVerifier、Streamable HTTP ASGI 与官方 Client。
- 阶段1审计完成；已冻结四工具名称映射、共享 MCP tool service、trace/log 复用、状态/fallback、官方鉴权和 `/mcp` 精确挂载方案。
- 已新增 MCP 严格输入/结果 Schema、传输无关真实工具服务、官方 MCPServer 四工具注册和静态 Bearer ASGI 保护。
- 已将可选 MCP Server 集成到现有 FastAPI lifespan，默认关闭，启用时精确提供 `/mcp`；编译和初始化烟测通过。
- 已补充 MCP 开关、Token、host/port/path 与 DNS-rebinding allowlist 环境变量样例。
- 已确定用官方 Client legacy 模式验证 initialize，并通过 httpx2 ASGITransport 走完整 Streamable HTTP Bearer 线路。
- MCP 首轮测试 4/5 通过；唯一失败是 SDK 动态根参数模型未宣告 extra-forbid，已收紧运行时模型并增加未知 score 字段拒绝覆盖。
- 修正后 MCP 测试 5/5 通过：官方 initialize/list/call、四工具串联、Schema、HTTP 结果一致性、前置错误、未知字段拒绝、Bearer 和真实远程 ASGI 传输均已验证。
- 已审计 API 契约、架构、旧 MCP 工具目录、HTTP 接入指南和百宝箱需求状态，明确采用加法文档更新并保留平台现场未验证项。
- 完整 `backend/tests` 回归 85/85 通过；compileall 与 `git diff --check` 通过。首次 app discovery 命令 top-level 错误，已记录并将用正确包根重跑。
- 最终新增配置测试后 MCP 为 6/6；MCP + 正式 HTTP 定向联合测试 11/11 通过。
- 最终 `backend/tests` 全量回归 86/86 通过；compileall、迁移/静态数据 `--check`、隐私检查和 `git diff --check` 全部通过。
- 正确包根运行 `backend/app`：34 通过、2 个历史 Mock 基线失败，失败内容与本任务开始记录一致且不涉及 MCP/正式 HTTP。
- 已同步架构、API_CONTRACTS、MCP_TOOL_CATALOG、TBOX_REQUIREMENTS，并新增完整 MCP 启动/鉴权/工具/样例/测试/公网/百宝箱填写说明。
- 已确认 MatchService/PathService 无 diff、没有 SSE 实现、没有真实凭据、没有 Git commit。

---

## 历史任务执行日志（百宝箱最小 HTTP 接入）

## 2026-08-21

- 已完整读取 `planning-with-files` 技能说明并启用文件化计划。
- session catchup 脚本缺失，命令失败；已记录在 `task_plan.md`，不再重复。
- 已读取上一阶段规划/发现/进度，恢复阶段3验收基线。
- 已将三份规划文件切换为本次百宝箱最小接入任务。
- 已检查 Git 状态/diff、后端与文档文件清单、平台/日志/鉴权/超时相关符号。
- 确认上一阶段大量改动仍未提交；本次将只做增量适配，不修改或回退其核心计算实现。
- 已完整读取阶段3 API、CareerState/AgentLog、StateRepository、CareerOrchestrator、应用工厂与现有配置。
- 初步决定新增独立薄适配层和平台调用记录，而不是把现有内部 `CareerState` 接口直接当作冻结工具契约。
- 已读取匹配/路径/阶段2严格 Schema、Agent 调用日志实现、阶段3 E2E 固定数据、V003 和迁移脚本。
- 确认新增 V004 平台工具调用表是最小且边界清晰的持久化方案。
- 已读取百宝箱需求、智能体配置、Prompt、旧工具目录、旧 TBox Mock 适配器、主路由和环境样例。
- 已识别旧冻结文档与本次最小工具命名/范围不一致；将保留旧历史文档，新增阶段3正式接入说明并同步 API 契约。
- 尝试通过官方语雀域名核对平台工具字段；公开搜索无结果、项目内具体链接无法打开，已停止重试并记录不可验证边界。
- 已对照 Agent 执行/日志实现、严格业务输出 Schema、公共 API 契约和数据字典，确定平台层 envelope、错误码与 AgentRunLog 关联方式。
- 已新增冻结平台 Schema、Bearer 鉴权、两个阶段3工具、状态/结果查询、超时与幂等逻辑、平台调用持久化表及 V004。
- 已将平台路由挂入主应用，并加入平台专用验证错误 envelope 和环境配置。
- 编译检查通过；阶段3 E2E 回归 `10/10` 通过。
- 新增平台接口测试，首轮 `4/4` 通过；覆盖匹配/路径、状态/结果、重放/冲突、鉴权、Schema、超时、日志隐私、持久化和 OpenAPI。
- 已同步 API 契约、架构、V004 数据字典并新增百宝箱阶段3配置说明。
- 已生成一套完整匿名 `analyze_job_match` Mock 请求/响应，并新增 Schema 校验测试。
- 平台接口测试增强后 `5/5` 通过，完整 Mock 文件也通过冻结 Pydantic Schema 校验。
- V001-V004 与静态数据检查通过；未配置生产 PostgreSQL，因此只运行 `--check`，未执行 `--apply`。
- `backend/tests` 全量回归：80/80 通过。
- `backend/app` 回归：34 通过、2 个上一阶段已存在的旧全链 TBox Mock 失败；失败项与基线完全一致（full chain partial、旧 Mock code=-4），本次正式阶段3工具测试均不受影响。
- 一组组合检查误从仓库根运行 backend 相对命令，compile/migration 子命令未实际执行；已记录并准备从正确目录重跑。`git diff --check` 未报告 whitespace error。
- 已从正确 `backend/` 目录重跑 compileall 和 V001-V004 `--check`，均通过；`git diff --check` 通过。
- 最终代码复核修正“前置失败却写入不存在 AgentRunLog 关联”的边界，并收紧 schema_version/tool_call_id；平台测试仍为 5/5 通过。
- 隐私复核将平台调用表的完整结果改为 CareerState 字段指针；结果查询仍从鉴权后的 CareerState 返回，平台+阶段3联合测试 15/15 通过。
- 最终 `backend/tests` 全量回归 80/80 通过；compileall、V001-V004 静态检查和 `git diff --check` 均通过。

## 最终接入结论

- CareerPulse 侧 `stage3-tool-v1` 已具备两个正式工具、状态/结果查询、固定 Schema、Bearer、超时、稳定错误码、持久幂等、隐私安全调用日志和 AgentRunLog 关联。
- OpenAPI 由主应用 `/openapi.json` 提供，只需在百宝箱选择 4 个阶段3 operation；完整配置字段、Mock 和未验证平台项已写入 `docs/a02/15_TBOX_STAGE3_MINIMAL_INTEGRATION.md`。
- 未接入任何阶段4工具，未修改 MatchService、PathService、MatchAgent 或 PathAgent 的计算逻辑，未提交 Git。
