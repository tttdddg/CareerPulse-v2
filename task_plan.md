# CareerPulse 阶段4 MCP 仓库侧接入（2026-08-27）

## 当前目标

在保留阶段3四个 MCP 工具及 `server.py` 现有扁平参数改动的前提下，将已经完成的阶段4 Training / Resource / Feedback 内部 handler 以三个薄 MCP 适配器注册到现有 Server，使 `tools/list` 从 4 个增加到 7 个；同步严格协议测试、公开契约与服务元信息，并完成阶段4、阶段3及后端适用回归。仅完成代码仓库侧接入，不配置百宝箱、Cloudflare 或真实 Token。

## 当前阶段

1. **已完成** — 审计现有 MCP Server、阶段4 handler/Schema、阶段3与内部工具测试、公开契约和全部未提交差异。
2. **已完成** — 冻结三个公开 MCP 签名、工具描述、错误语义、元信息和文档更新范围。
3. **已完成** — 增量注册三个薄适配器并扩展 MCP 协议测试，保持原四工具不变。
4. **已完成** — 同步 MCP 工具目录、API 契约、集成说明和 stage/version/instructions 元信息。
5. **已完成** — 运行阶段4 MCP、阶段3 MCP、后端适用回归、compile/diff/tools-list 检查并汇总结果。

## 本轮约束

- 不创建第二套 MCP Server，不改变现有鉴权、部署或总体架构。
- MCP 层只做扁平协议参数到已有严格 Request Schema、再到 `CareerMCPToolService` handler 的适配。
- Training 保持一个合并工具，由现有字段区分 generate / score。
- 不修改或重写 TrainingService、ResourceService、FeedbackService 和三个既有 handler。
- 公开 Schema 不放宽；新增平台工具必须有成功与失败测试。
- 保留任务开始前所有未提交改动，不覆盖用户文件，不执行 Git commit。
- 不将仓库侧代码完成表述为百宝箱现场接入完成。

## 本轮错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| `planning-with-files/scripts/session-catchup.py` 不存在 | 1 | 与现有任务记录一致；改用三份规划文件、Git 状态和 diff 恢复上下文，不再重试。 |
| 文档检索向 `rg` 传入 Windows 不接受的 `backend/README*` 字面路径 | 1 | 指定的三个 MCP 文档和根 README 已正常读取；后续先用 `rg --files` 解析文件，不重复该 glob。 |
| 首轮 MCP 定向测试 1 项错误：把 `MCPServer.call_tool()` 的 `CallToolResult` 当列表下标访问 | 1 | 三个新增工具和其余 10 项均通过；改为官方 `Client.call_tool()` 后定向测试 11/11 通过。 |
| 第二次文档检索继续向 `rg` 传入 Windows 不接受的 `docs/a02/*.md` / `decisions/*.md` | 1 | 已改用 `rg --files docs/a02 decisions` 获取精确文件；后续不再向命令传裸 wildcard 路径。 |
| 从 `backend/` 复核 Service 时误用 `backend/app/...`，且把内部 `server.list_tools()` 的 list 当作 Client 包装对象 | 1 | 未产生文件变化；下次使用 `app/services/...` 和直接迭代返回 list，不重复错误形式。 |
| `python -m unittest discover -s app -t .` 为 6 failures / 1 error | 1 | 5 个 ProfileAgent 直接失败均由任务前已缺 `prompts/profile_agent/system.txt`/`user_template.txt` 导致，2 个旧 Mock 全链为同一原因级联；不越界猜写 prompt，另跑 Match/Path/Training/Feedback Agent 适用回归。 |
| 最终组合检查退出码 1 | 1 | 前置 MCP 11/11、JSON 解析、tools=7、diff check、hash 均成功；最后 `rg` 因没有找到任何过期活动声明按约定返回 1，不是测试/实现失败，不重复命令。 |

## 完成结论

- 现有唯一 MCP Server 已增量注册三个阶段4薄适配器，实际 `tools/list` 为 7；Training 保持合并工具。
- 原四工具、扁平 Profile/Job 参数、鉴权、Service/handler/Orchestrator 和 HTTP API 均未回归或被覆盖。
- 阶段4分组 29/29、阶段3分组 26/26、backend 顶层完整套件 180/180、相关 Agent 60/60、最终 MCP 11/11 均通过。
- `backend/app` 的 7 个既有 Profile prompt 缺失直接/级联失败仍在，已如实分类；不属于本次接入范围。
- 仓库侧代码和契约已完成；百宝箱、Cloudflare、固定 Token、公网与现场联调仍需人工完成。

---

# 当前任务：阿里云 ECS 第一阶段部署准备（2026-09-11）

## 目标

在不改变现有 Service/Agent 业务逻辑、公共 Schema、前端和旧表结构的前提下，以 Python 3.11 为基线补齐 FastAPI + MCP 的 Ubuntu 22.04 部署资产、配置化旧 PostgreSQL 连接、最小健康检查和生产依赖清单，并完成全量回归。

## 阶段

1. **已完成** — 复核工作树、现有配置、依赖、路由与相关测试，冻结最小修改边界。
2. **已完成** — 配置化旧 PostgreSQL、补 `/healthz`、整理 Python 3.11/Linux 生产依赖。
3. **已完成** — 新增 systemd、Nginx、环境模板、部署说明和 smoke test。
4. **已完成** — 新增/调整非业务测试，执行定向与完整测试、静态检查和部署文件校验。
5. **已完成** — 汇总修改文件、首次部署命令和仍未解决阻塞项。

## 约束与决定

- 不修改 Service/Agent 业务实现，不创建或猜测旧业务基础表，不补造缺失 Prompt，不修改前端。
- 不执行服务器部署，不写入真实密码、Token、数据库 URL 或个人信息。
- `/healthz` 仅返回固定最小状态，不探测或暴露数据库/外部服务配置。
- `requirements-prod.txt` 按直接运行依赖整理并固定 Python 包版本，不从 Windows 环境完整 freeze。
- 先保持单 Uvicorn worker，由 Nginx 只代理到 `127.0.0.1:8000`。

## 错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| `planning-with-files/scripts/session-catchup.py` 不存在 | 1 | 技能目录仅包含 `SKILL.md`；已读取 Git 状态及三份现有规划文件恢复上下文，不再重试。 |
| 首次探测 MCP 协议版本时导入不存在的 `mcp.shared.version` | 1 | 改从已安装 `mcp.types.LATEST_PROTOCOL_VERSION` 读取，确认固定 SDK 2.0.0 对应 `2026-07-28`，不重复错误导入。 |
| 首次组合补丁同时 Delete/Add `config.py` 被补丁工具拒绝 | 1 | 补丁未落盘；改为 Update File 替换原内容并拆分新增文件，不重复同一路径双操作。 |
| Windows 主机没有 `bash`，无法直接执行 `bash -n` | 1 | 不重复调用；改查找 WSL/sh 或使用静态内容校验，最终 Ubuntu 首次部署仍要求执行 `bash -n`。 |
| PowerShell 将 `backend/requirements*.txt` 原样传给 `rg` 导致路径语法错误 | 1 | 该段未完成；后续改用 `rg --glob 'requirements*.txt' backend`，不再使用 shell glob 路径。 |
| WSL 首次受沙箱拒绝，授权后又确认未安装 Linux 发行版 | 2 | 无可用 Linux 用户空间，停止本机 Bash/Nginx/systemd 原生语法尝试；保留静态测试并把目标机原生校验列为首次部署必做。 |

## 完成结论

- Python 3.11/Linux 生产依赖、旧 PostgreSQL 环境化、最小 `/healthz` 和完整 `deploy/` 资产已完成。
- 部署测试 9/9；最终后端全量回归 203 passed + 109 subtests，数据/迁移静态检查、compileall、pip check、敏感信息与 diff check 通过。
- 未修改 Service/Agent 业务逻辑、公共 Schema、旧表迁移、Prompt 或前端；未执行服务器部署或真实外部调用。
- Ubuntu 原生 `bash -n`、`nginx -t`、systemd 启动和公网 MCP smoke 必须在首次 ECS 部署时执行，当前 Windows 主机无 Linux 发行版，不能声称已验证。


# CareerPulse MCP 百宝箱入参兼容修复（2026-08-27）

## 当前目标

仅修复 `build_student_profile`、`analyze_target_job` 的 MCP 公开入参与服务端模型不一致问题：公开 Schema 使用百宝箱可识别的基础类型，在 MCP 适配层重建真实 Pydantic 输入；保持工具名、身份/追踪字段、Service、返回结构、HTTP API、部署和鉴权不变，并回归四个阶段3工具。

## 当前阶段

1. **已完成** — 定位 MCP 注册、真实输入模型、共享调用层与现有测试，核对工作区已有改动。
2. **已完成** — 冻结两个工具的扁平基础类型签名及预期 `tools/list` JSON Schema。
3. **已完成** — 最小修改 MCP 适配层并补充百宝箱普通 JSON 调用及四工具回归测试。
4. **已完成** — 运行定向测试、相关回归、Schema/隐私/差异检查。
5. **已完成** — 汇总根因、修改文件、新参数结构、测试结果和百宝箱测试参数。

## 本轮约束

- 不修改部署、鉴权、HTTP API、原有 Service 业务逻辑和返回结构。
- 不改变工具名称及 `user_id`、`session_id`、`trace_id`。
- 不把 Pydantic BaseModel 或嵌套对象直接暴露为 MCP 入参，不虚构模型字段。
- 保留并避开用户已有未提交文件，不自动提交 Git。

## 本轮错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| planning-with-files 的 `scripts/session-catchup.py` 不存在 | 1 | 已读取现有规划文件和 Git 状态恢复上下文，不再重复失败。 |
| 首次 `rg` 组合正则被 PowerShell 双引号误解析为模块名 | 1 | 改用单引号包裹正则后成功定位全部 MCP 测试调用点。 |
| 文档检索包含不存在的 `backend/README.md` | 1 | 其余目标文档已正常检索；移除该不存在路径，不重复调用。 |

## 完成结论

- 修复仅涉及 MCP 注册适配、对应测试和 MCP 公共契约/百宝箱样例；Service、HTTP API、部署、鉴权和输入模型定义均未修改。
- MCP 定向 `8/8`、HTTP 工具 `5/5`、阶段3 E2E `10/10`、backend 全套 `177/177` 全部通过。
- `tools/list` 已确认无目标工具的 `$ref/$defs` 或嵌套 object 入参；compileall 与 `git diff --check` 通过。

---

# CareerPulse A02：D4-2.6 阶段4最终端到端验证

## 2026-08-24 当前目标

以离线端到端测试验证 Profile → Match → Path、训练生成/评分、资源推荐、反馈与成长快照、异常和确定性边界；只修复能够明确归因于 D4-2.1～D4-2.5 接线的问题，不新增业务需求、不重构冻结 Service。

## 当前阶段

1. **已完成** — 盘点现有端到端覆盖、测试入口、离线 LLM 与冻结基线。
2. **已完成** — 补齐一条完整阶段3+阶段4内部链路测试及缺失异常场景。
3. **已完成** — 运行定向测试，分类并只修复本阶段接线实现错误。
4. **已完成** — 运行全部测试、三个冻结 Service、compileall、隐私与真实/mock 静态审计。
5. **已完成** — 写入《D4 阶段4最终内部链路验收报告》并完成禁止范围审计。

## 当前约束

- 自动测试必须使用 mock/offline LLM，不依赖公网或百宝箱。
- 数值、ID、priority、flags、resources 必须来自确定性代码；不为文本逐字节稳定性写脆弱断言。
- 不修改 TrainingService、ResourceService、FeedbackService 的业务算法。
- 不通过修改测试预期掩盖实现失败；失败必须区分测试脚本、实现和规格歧义。
- 不注册百宝箱工具，不修改平台配置，不进行 ngrok、VM、域名或部署。
- 保留 D4-2.1～D4-2.5 未提交成果，不回退用户已有改动，不执行 Git commit。

## 本轮错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| planning-with-files 的 session-catchup 脚本已知不存在 | 0 | 遵循“不重复失败”，读取当前规划文件、Git 差异和测试清单恢复上下文。 |
| ProfileAgent 定向回归 5 项失败 | 1 | 根因是 D4 前已缺失的 `prompts/profile_agent/system.txt` 与 `user_template.txt`；分类为既有阶段3仓库实现/资产缺失，不修改测试预期、不在 D4-2.6 猜写 prompt。 |
| 完整套件 7 项失败 | 1 | 5 项是上述 ProfileAgent；另 2 项历史 Mock 全链因同一 ProfileAgent fallback 使最终状态为 partial/code=-4。分类为同一既有资产缺失的级联失败，保留真实结果。 |

---

# 历史任务：D4-2.5 Orchestrator 与内部工具链整合

## 2026-08-24 当前目标

严格复用阶段3的 Orchestrator、持久化、Schema 和错误 envelope 模式，为生成训练、训练评分、资源推荐、保存反馈四个阶段4动作提供稳定的内部调用接口；不注册百宝箱平台工具。

## 当前阶段

1. **已完成** — 核查阶段3 Orchestrator、内部工具、API/MCP、Schema、错误与 demo 模式。
2. **已完成** — 冻结四个阶段4内部动作的名称、输入、状态投影与返回 envelope。
3. **已完成** — 实现 Orchestrator / 内部工具链及最小 Schema 适配。
4. **已完成** — 新增离线工具链测试并运行阶段3/阶段4/全量回归。
5. **已完成** — 写入 D4-2.5 开发日志并完成禁止范围审计。

## 当前约束

- 冻结工具名称优先，不自行创造与文档不兼容的公开命名。
- ability gaps、skill gaps、训练 criteria、target abilities、overall score 等系统上下文由 State 自动补齐。
- 参数错误和 Agent/Service/LLM 失败必须返回稳定 fail-safe envelope，不使 Orchestrator 崩溃。
- 生产内部路径使用真实 Agent / Service；阶段3 mock 仅保留其既有测试/demo用途。
- 不修改三个冻结 Service，不注册百宝箱阶段4工具，不进入 ngrok/VM/域名/部署。
- 保留 D4-2.1/2.2 未提交成果，不回退用户已有改动，不执行 Git commit。

## 本轮错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| 清理首次失败测试留下的 `.runtime/tmpt1cv4y8_` 时被 Windows ACL 拒绝 | 1 | 该目录位于已忽略 runtime 且不进入 Git；停止扩大权限操作，不影响代码或测试结果。 |
| 改到 `.runtime` 后仍使用 `TemporaryDirectory`，Windows ACL 继续阻止 SQLite 访问 | 1 | 对齐仓库既有 stage3 测试，改为 `.runtime/tests` 下 UUID 数据库文件并在 finally 清理。 |
| 新持久化测试使用系统临时目录，受当前 workspace sandbox 限制而无法创建 SQLite | 1 | 代码未失败；将临时数据库移到项目已忽略的 `backend/.runtime` 后重跑。 |
| 首次切换 D4-2.4 的组合补丁与规划文件实际措辞不匹配 | 1 | 文件未变化；读取实际内容后使用精确补丁，不重复原补丁。 |
| planning-with-files 的 session-catchup 脚本已知不存在 | 0 | 遵循“不重复失败”，直接读取规划文件和 Git 状态恢复上下文。 |
| 整文件替换补丁同时 delete/add `feedback_agent.py` 被工具拒绝 | 1 | 文件未变化；拆成先删除、再新增的两个精确补丁，不重复组合形式。 |
| 完整回归保留 5 个 ProfileAgent 失败 | 1 | 与 D4-2.1/2.2 相同，仍由两个 Profile prompt 文件缺失导致；不越界修复，运行排除该已知项的适用全绿回归。 |

---

# 历史任务：D4-2.2 ResourceService 业务接入

## 2026-08-24 当前目标

在不修改冻结 ResourceService 算法、不新增仅为结构对称的 ResourceAgent、不重构 CareerState 的前提下，将真实 `match_result.skill_gaps[].dimension` 按原顺序传给 `ResourceService.recommend_resources()`，完整透传四类结果并完成离线测试、全量回归和开发日志。

## 当前阶段

1. **已完成** — 核查 ResourceAgent、Match/Path/Orchestrator/tool 消费层、skill_gaps 顺序及现有推荐状态位置。
2. **已完成** — 冻结最小接入设计和允许修改文件。
3. **已完成** — 实现 ResourceService 业务接入及必要边界 Schema。
4. **已完成** — 新增离线测试，运行 ResourceService 原测试和全量回归。
5. **已完成** — 写入 D4-2.2 开发日志，核对冻结文件与最终差异。

## 当前约束

- ability_gaps 只能来自真实 `match_result.skill_gaps[].dimension`，保持当前顺序。
- 不重新计算 priority、不归一标签、不复制 AbilityTagNormalizer、不调用 LLM 推荐资源。
- 完整保留 learning_resources、job_resources、certificate_suggestions、data_quality_flags。
- 不修改 TrainingService、ResourceService、FeedbackService、百宝箱平台、公网部署；CareerState 仅允许最小结果透传，不做统一重构。
- 保留 D4-2.1 未提交成果，不回退用户已有改动，不执行 Git commit。

## 本轮错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| `planning-with-files/scripts/session-catchup.py` 不存在 | 1 | 使用 Git 状态和现有三份规划文件恢复上下文，不再重试。 |
| 完整 `tests + app/agents/tests` 有 5 个 ProfileAgent 失败 | 1 | 失败仍由既有 `prompts/profile_agent/system.txt`、`user_template.txt` 缺失导致；D4-2.2 不越界修复，改跑排除该已知项的适用回归并在报告披露。 |
| 组合静态检查从 `backend/` 搜索不存在的相对 `docs` 目录，导致命令最终退出 1 | 1 | 前置适用回归 `187 passed` 和 compileall 均成功；已从仓库根重新检索，无 ResourceAgent 匹配。 |
| 更新三份规划文件的组合补丁上下文不匹配 | 1 | 业务代码未受影响；读取文件精确上下文后拆分为小补丁。 |

---

# 历史任务：CareerPulse A02 Hermes 提交前最小收尾

## 2026-08-24 当前目标

只修复阶段3测试的稳定导入、核清并显式处理 `httpx2` 测试依赖、校正 MCP 工具目录、完成 Token 与差异检查，然后从仓库根目录和 `backend/` 目录验证。禁止修改历史 Mock、`tbox_adapter.py`、算法、健康端点、全仓库换行配置、部署或提交。

## 当前阶段

1. **已完成** — 审计测试目录/导入、pytest 配置、MCP 客户端依赖元数据、工具目录与 Token 痕迹。
2. **已完成** — 通过测试包、共享辅助模块和 backend 级 pytest 配置修复导入；确认 `httpx2>=2.5.0` 是 `mcp==2.0.0` 的正式必需依赖，不重复锁第二套客户端。
3. **已完成** — 更新 `13_MCP_TOOL_CATALOG.md`，明确只有四个阶段3工具已注册，7 个旧名称均是历史/规划且尚未注册。
4. **已完成** — 从仓库根与 backend 运行定向/全量/阶段3测试、compileall、diff 和算法无差异检查。
5. **已完成** — 汇总文件、风险和是否可提交结论。

## 本轮错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| `planning-with-files/scripts/session-catchup.py` 不存在 | 1 | 使用现有计划文件、Git 状态和 diff 恢复上下文，不再重试。 |

---

# 历史任务：标准远程 MCP Server（已完成）

## 当前目标

在保留现有 HTTP Tool API 和确定性算法的前提下，使用固定版本的官方 MCP Python SDK 增加 Streamable HTTP `/mcp` 入口，复用现有 Agent、Service、Pydantic Schema、CareerState 持久化和调用日志，并完成官方客户端协议测试、状态串联、HTTP 一致性回归和接入文档。

## 当前阶段

1. **已完成** — 审计仓库规则、Python/依赖、现有 Agent/Service/状态/日志/HTTP Schema/测试与未提交改动；核对官方 MCP SDK 稳定版本和挂载方式。
2. **已完成** — 确定 MCP 工具名称映射、共享调用层、统一结果/错误模型、鉴权/配置和状态前置契约；同步公共契约文档。
3. **已完成** — 固定 SDK 依赖，实现 MCP Server、Streamable HTTP `/mcp`、真实工具注册和安全日志关联。
4. **已完成** — 新增 initialize、tools/list、tools/call、Schema、四工具串联、前置失败、鉴权、fallback、日志隐私和 HTTP 一致性测试。
5. **已完成** — 运行新增测试与现有 HTTP/后端回归，修复问题，核对未改算法，并完成 MCP 接入说明与最终结果清单。

## 当前约束

- 不修改 MatchService、PathService 的匹配、缺口、评分或路径算法。
- 不删除、不重命名现有 HTTP Tool API；优先抽取共享调用能力，避免 MCP 复制算法。
- 不以 `tbox_adapter.py` 的 Mock 返回替代真实 Agent/Service。
- 后续工具仅凭 `session_id` 读取持久化 CareerState，不让模型转传整份画像/岗位/匹配 JSON。
- 新公开字段同步 `docs/a02/04_API_CONTRACTS.md`；MCP 工具目录与实现保持一致。
- 不接真实付费 LLM；测试使用现有离线 double/fallback。
- 不写入真实 Token，不进入百宝箱配置，不执行 Git commit。
- 工作区已有改动属于前序成果；只做增量修改，不回退、不覆盖无关内容。

## 当前错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| `planning-with-files/scripts/session-catchup.py` 不存在 | 1 | 技能目录当前没有该脚本；已用 Git 状态和三份规划文件恢复上下文，不再重试。 |
| 当前宿主环境预装 `mcp==1.26.0`，`pip index versions mcp` 未从受限索引解析包且 pip 输出触发 GBK 编码噪声 | 1 | 不覆盖宿主环境；将固定 `mcp==2.0.0` 到项目依赖，并在项目忽略的运行时目录安装隔离副本用于测试。 |
| `main.py` 首行带 UTF-8 BOM，组合补丁无法匹配首行 | 1 | 保留原文件编码，改从第二行插入 import，再用精确小补丁完成集成。 |
| 一行 `python -c` MCP 客户端烟测被 PowerShell/嵌套引号截断 | 1 | 不重复复杂内联脚本；改为编写正式 unittest 后运行官方 Client 测试。 |
| MCP 首轮 5 项测试中 tools/list 根 Schema 未声明 `additionalProperties: false` | 1 | 固定 SDK 2.0 的动态参数模型默认为 extra-ignore；已在注册后统一改为 extra-forbid 并重建 Schema，同时增加未知分数字段拒绝测试。 |
| `unittest.discover('app')` 未设置 top-level，导致 app 子包被错误当成顶级包并出现相对导入错误 | 1 | 这不是代码失败；改用 `discover('app', top_level_dir='.')` 以 `app.*` 包名重跑。 |

---

## 历史任务：百宝箱最小 HTTP 接入（已完成）

## 目标

仅为百宝箱暴露阶段3匹配与职业路径能力：固定工具契约、结果/状态查询、鉴权/超时/错误/幂等、OpenAPI/平台描述、脱敏调用日志关联、Mock样例和平台配置说明；不重写 MatchService、PathService、MatchAgent、PathAgent，不接入阶段4。

## 阶段

1. **已完成** — 审计现有阶段3 API、Schema、持久化/日志、文档、测试与未提交改动。
2. **已完成** — 设计并同步固定工具请求/响应、错误、状态、鉴权、超时和幂等契约。
3. **已完成** — 实现百宝箱最小适配接口、OpenAPI工具描述、日志关联与隐私保护。
4. **已完成** — 添加平台工具成功/失败/幂等/鉴权/超时/日志接口测试和完整 Mock 样例。
5. **已完成** — 运行阶段3与平台接口回归，核对 OpenAPI，完成接入说明和平台配置清单。

## 约束与决定

- 保留并复用现有 MatchService、PathService、MatchAgent、PathAgent；不修改确定性分数归属。
- 工具输入不得包含任何可覆盖后端分数、缺口或路径评分的字段。
- 不暴露数据库；仅通过固定 API/工具 Schema 查询状态和结果。
- 日志仅保存脱敏元数据/摘要，并关联 AgentRunLog。
- 不接入阶段4工具，不自动提交 Git。
- 公开契约字段如变化，同步 `docs/04_API_CONTRACTS.md`（以仓库实际路径为准）。
- 工作区已有改动属于上一阶段成果，先审计再增量修改，不回退。

## 错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| `planning-with-files/scripts/session-catchup.py` 不存在 | 1 | 技能安装仅含 `SKILL.md`；已停止重试，改用 Git 状态、diff 和现有规划文件恢复。 |
| 单个补丁删除并新增同一路径被拒绝 | 1 | 已拆成独立补丁操作，不重复同一失败形式。 |
| 跨 3 个文件的集成补丁未匹配 `main.py` 上下文 | 1 | 已读取精确上下文，拆分为逐文件小补丁。 |
| 规划日志组合补丁使用了不完整行上下文 | 1 | 已读取文件尾部并用精确行重新应用，内容无丢失。 |
| 最终组合检查从仓库根执行 backend 相对命令 | 1 | `compileall app/tests/scripts` 与 `scripts/init_a02_data.py` 路径错误；已确认不是代码失败，将从 `backend/` 精确重跑。 |
# 当前任务：蚂蚁百宝箱 Tool Calling 兼容性统一修复（2026-08-28）

## 目标

在 `backend/app/mcp/` 及 MCP 专用测试内完成 7 个工具的对外 Schema/描述审计，建立可复用的宽输入标准化适配，修复 profile 多值字段、training_type 自然语言兼容和数字输入，保持内部 Pydantic 模型与业务层严格不变。

## 阶段

1. **已完成** — 审计 7 Tool 注册、JSON Schema、参数描述、适配路径、session/user 使用和现有测试。
2. **已完成** — 设计统一标准化函数，决定 7 Tool 对外基础类型与 training_type 有限别名/错误策略。
3. **已完成** — 仅修改 MCP Adapter/描述并新增兼容测试，不修改 Agent/Service/HTTP API/核心模型/算法。
4. **已完成** — 运行 MCP 单测、7 Tool Schema/adapter 测试、阶段3/4回归与可行的全量回归，分析 fallback。
5. **已完成** — 复核 diff/隐私/边界，整理 7 Tool 审计表和百宝箱重新联调步骤。

## 约束

- 保留用户已有未提交改动，不回退无关内容，不自动 commit。
- 公开 Schema 如需调整必须核对 `API_CONTRACTS.md`，但优先保持修改范围在 MCP 专属路径。
- 未知 training_type 不静默映射，非法数字不伪造默认值。
- 不改 fallback 业务逻辑，仅根据实现与测试报告触发原因。

## 错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| `planning-with-files/scripts/session-catchup.py` 不存在 | 1 | 使用现有规划文件、Git 状态和当前源码恢复上下文，不再重试。 |
| 首次 fallback 检索向 `rg` 传入 Windows 不支持的 `backend/app/llm*` 路径，并误读不存在的 `agents/base.py` | 1 | 不再使用该 glob；改读精确的 `agents/base_agent.py` 和 `core/llm_client.py`，已成功完成 fallback 审计。 |
| 当前 Python 环境未安装 `black`，且 `ruff` 命令不存在 | 1 | 不为格式化额外安装依赖；使用手工行长检查、`py_compile`、测试和 `git diff --check` 验证。 |
| 增强数字错误测试的首个组合补丁把 test 上下文误放到 `server.py` 段 | 1 | 未产生部分修改；拆成精确的 server/test 文件块后成功应用。 |
| 最终 Schema 内联检查的 PowerShell/Python 引号导致 `SyntaxError` | 1 | 编译和 diff check 已执行；Schema 检查改用 `chr(36)` 构造 `$ref/$defs` 键后通过。 |
| 首次检索最终行号的 `rg` 正则被 PowerShell 双引号截断 | 1 | 改用单引号原样正则后成功，未修改任何文件。 |

## 完成结论

- 修改仅限 MCP Adapter、MCP 专用测试与本轮规划记录；未修改 Agent、Service、CareerState、Orchestrator、HTTP API、核心 Request/Response 或算法。
- 最终 MCP 定向 `18/18`、阶段3/4+服务 `104/104`、backend tests 全量 `187/187`、相关 Agent `60/60` 通过；编译、diff check、7 Tool 描述和无 `$ref/$defs` 检查通过。
- 当前仓库根 `prompts/profile_agent/*` 和 `prompts/job_agent/*` 缺失；Profile/Job 主路会因 Prompt 加载异常进入设计内 fallback。本次按范围要求只报告，未扩大修复。

## 当前追加任务：Profile/Feedback 外层 Arguments 兼容复核（2026-08-28）

### 目标

仅复核并修复 `build_student_profile` 多值字段和
`save_growth_feedback` 评分字段的 MCP 外层兼容；新增 JSON 数组字符串支持，
并确认本地运行时 Schema 是否已允许 string。不修改 Service、HTTP API、
业务 Request Schema 或其他五个工具的业务行为。

### 阶段

1. **已完成** — 核对当前 `server.py`、normalization、运行时 tools/list 和部署缓存可能性。
2. **已完成** — 补充 JSON 数组字符串解析，对六个同类多值字段统一生效。
3. **已完成** — 补充 MCP Server 回归：字符串/真实 list、字符串/真实 int 和 resource_rating。
4. **已完成** — 运行 MCP 定向与相关全量回归，复核修改边界和重新获取 Schema 要求。

### 完成结论

- MCP 定向回归 `19/19`、`backend/tests` 全量回归 `188/188` 通过，`git diff --check` 无 whitespace error。
- 本地运行时 `tools/list` 已确认 profile 多值字段为 string/array，feedback 评分为 string/integer；现场仍出现旧类型错误时必须重启/重新部署 MCP 并让百宝箱刷新已发布工具 Schema。
- 未修改 Service、HTTP API、内部业务 Request Schema 或另外五个工具的业务行为。

### 约束

- 保留前一轮未提交的 MCP Adapter/测试改动，不回退。
- 内部 StudentProfileInput、SaveGrowthFeedbackRequest 和 strict Rating 不改。
- 不修改另外五个工具的业务处理。

---
# CareerPulse 百宝箱对话适配层（2026-09-03）

## 当前目标

审查现有 FastAPI、MCP 与平台配置，依据可核验的蚂蚁百宝箱企业版正式智能体 API，实现 `backend/app/platform/tbox/` 适配层和 `POST /api/tbox/chat`。入口负责服务端凭据、CareerPulse session 到百宝箱会话映射、普通/流式响应归一、超时与安全错误；不修改 Vue、MCP、阶段3/4算法或现有 Service。

## 当前阶段

1. **已完成** — 审查应用工厂、配置、既有平台/MCP实现、测试模式和工作区差异。
2. **已完成** — 核对百宝箱企业版实际 API 文档，冻结请求、会话与流式协议。
3. **已完成** — 实现配置、Schema、session mapper、client、chat service 和 FastAPI 路由。
4. **已完成** — 增加成功、失败、超时、会话映射、流式协议和凭据隐私测试。
5. **已完成** — 运行定向/全量回归、编译、OpenAPI、Token 与差异检查并交付。

## 本轮约束

- 不把百宝箱 API Key、Token 或上游内部错误暴露给浏览器或日志。
- 不虚构百宝箱能力、URL、字段或流式事件；实际文档无法核实时必须显式配置/阻断。
- 公开 Schema 若新增需同步 `docs/a02/04_API_CONTRACTS.md`。
- 测试使用传输 double，不调用真实付费 API，不写真实凭据。
- 保留当前未提交的前端整改和用户开发日志，不自动提交 Git。

## 本轮错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| `planning-with-files/scripts/session-catchup.py` 不存在 | 1 | 已读取现有三份规划文件和 Git 状态恢复上下文；不再重复。 |
| `npm view tbox-nodejs-sdk` 受 only-if-cached 策略拒绝 | 1 | 未获得包内容；改用官方 registry tarball URL，不重复 npm view。 |
| `curl` 访问 registry.npmjs.org 被本机代理拒绝 | 1 | 不重复同一下载；使用网页可访问的 npm README/官方 Ant Design X 文档作为已核验边界，HTTP endpoint 改为强制环境配置而非猜测。 |
| 按先前摘要中的 `backend/app/orchestrator/db_state.py` 与 `backend/.env.example` 路径读取失败 | 1 | 未修改文件；改用 `rg --files` 定位仓库实际文件，不重复错误路径。 |
| Windows 下 `python -m py_compile backend\\app\\platform\\tbox\\*.py` 不展开通配符 | 1 | 路由导入/OpenAPI 已成功；后续使用 `compileall` 或显式文件列表，不重复该命令。 |
| `python -m unittest discover -s tests -v` 将 tests 当顶层目录，3 个既有相对 import 模块加载失败 | 1 | 其余 175 项通过；改用 package-aware `-s tests -t .` 或显式 `tests.*` 模块，不修改测试导入。 |
| 最终 SSE 小补丁使用了损坏的 patch 文本且上下文未匹配 | 1 | 工具未修改文件；读取精确代码后确认目标逻辑（exclude_none、流前配置校验和测试）已在当前文件中，不重复该补丁。 |

## 已知既有测试失败

- `app.platform.tests.test_mock_career_flow` 当前 7 项中 2 项失败：旧全链 Mock 预期 `success/0`，现有 Agent fallback 实际为 `partial/-4`。该失败在本任务开始前的历史回归中已记录，本轮正式 chat 路由不调用旧 Mock，因此不扩大范围修改。

## 完成结论

- 正式 `POST /api/tbox/chat` 已挂载主 FastAPI，支持普通 JSON 与规范化 SSE、持久会话映射、总超时、安全错误、HMAC 匿名 userId 和隐私安全调用账本。
- `backend/tests` package-aware 全量回归 194/194；Chat 定向 6/6，Chat+既有阶段3平台工具 11/11；compileall、迁移/数据 check、OpenAPI 双 content-type、凭据扫描与 diff check 通过。
- 未修改 Vue、MCP、Agent、Service、评分算法或数据库 Schema；未配置/调用真实百宝箱租户，因此交付状态是“后端协议与传输联调完成，待部署凭据进行线上 smoke test”。

---

# 当前任务：CareerPulse Vue 成长闭环前端（2026-09-06）

## 目标

严格继承现有 CareerPulse 前端的布局、卡片、字体、色彩、间距、图表与交互语言，增量完成学习计划/资源推荐、职场训练、成长档案三项能力；所有页面只显示真实 API 数据或明确的 loading/empty/unavailable/error，不以 Mock 冒充成功。

## 阶段

1. **已完成** — 审查现有真实页面、布局、导航、组件、全局样式、API/Store 与后端 Training HTTP 能力，输出 UI 继承策略。
2. **已完成** — 改造现有 `GrowthPlan.vue`，加入结构化任务、学习资源、岗位资源并保留报告功能。
3. **已完成** — 新增 Training 页面与前端 API Adapter，覆盖完整页面状态且不伪造训练结果。
4. **已完成** — 增量改造 `Profile.vue` 为成长档案，保留真实历史快照与成长曲线。
5. **已完成** — 更新 Router/Sidebar，补充必要组件与响应式约束。
6. **已完成** — 运行 typecheck、现有测试、production build、diff check，并进行浏览器视觉一致性检查。

## 约束与决定

- 不改全局主题、Sidebar/Header 结构或现有路由体系，不引入新 UI 框架。
- 不修改后端、MCP、Match/Path/Training 算法或 Dashboard。
- 保留工作区既有未提交改动，只对本轮前端相关文件做增量修改。
- 不创建固定评分、固定进度、假资源、假历史、假成长曲线或自动 Mock fallback。
- 公共字段保持不变；如发现现有公开契约不足，优先做前端 unavailable/empty，不扩大后端范围。

## 错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| `planning-with-files/scripts/session-catchup.py` 不存在 | 1 | 已使用 Git 状态与现有三份规划文件恢复上下文，不再重试。 |
| 首次向三份规划文件追加记录时 `findings.md` 上下文不匹配 | 1 | 补丁未落盘；改为按各文件真实尾部逐一追加，不重复组合补丁。 |
| 使用 `backend/app/**/*.py` 做 PowerShell 路由检索时报 Windows 路径语法错误 | 1 | 同一命令的 `rg backend/app` 已返回完整路由；后续只用目录参数，不再传 shell glob。 |
| GrowthPlan 首个超大模板补丁未匹配文件上下文 | 1 | 补丁未落盘；已拆成页面头、任务/资源、报告区等小块并成功应用，不重复整段替换。 |
| GrowthPlan 首轮 typecheck 报联合类型中不存在 `suggestion/status` | 1 | 将 fallback gap 列表显式标注为 `MatchingGap[]` 后重跑，typecheck 通过。 |
| Profile overview 一次补丁文本包含无效 hunk 标记 | 1 | 补丁被完整拒绝、未落盘；立即使用纯净小补丁重新应用。 |
| Profile 首轮 typecheck 发现三个 overview computed 重复声明 | 1 | 读取精确区段后删除重复块，保留函数声明后的单一实现；重跑 typecheck 通过。 |
| 并行执行 typecheck/build 时 Vite 与 vue-tsc 同时写 `components.d.ts`，build 报 `UNKNOWN open` | 1 | 判定为生成声明文件并发锁冲突；typecheck 已结束后单独重跑 build 成功，不修改代码规避。 |
| node_repl 中导入 `playwright`/`playwright-core` 报包导出错误 | 1 | 未取得浏览器实例；停止重复同一导入，改用本机 Chrome/Edge headless CDP 路径进行视觉检查。 |
| 首次 Vite 视觉预览命令把 `127.0.0.1` 误解释为项目 root，页面返回 404 | 1 | 停止错误服务，改用 Vite CLI 显式 `--host 127.0.0.1`；CDP 二次渲染成功。 |

## 完成结论

- GrowthPlan 已形成“真实概览 → Gap 学习任务 → `/recommendations` 学习资源 → 岗位资源 empty → 原成长报告”结构，未补假进度或假资源。
- Training 新页面与 Adapter 已覆盖三种真实类型和完整生命周期；因无专用 HTTP API，当前明确 unavailable，不返回任何假任务或评分。
- Profile 已升级为成长档案，保留 histories/snapshot 与真实匹配分曲线；学习、训练、反馈记录均为明确 empty/unavailable。
- Router/Sidebar 保持原壳层和单层结构，新增 `/app/training` 与岗位入口并统一导航名称。
- 最终 `npm run typecheck`、`npm run build`、`git diff --check` 通过；package.json 无其他前端测试脚本。
- Headless Chrome 以 1440px 渲染三页并以 760px 复核，三页均无横向溢出，panel 圆角/边框为现有 16px/1px 语言。

---

# 当前任务：CareerPulse Vue 全站响应式适配（2026-09-06）

## 目标

在不改变 CareerPulse 既有视觉、业务结构、数据链路和交互语言的前提下，使全部当前注册路由在 Desktop、Tablet/Small Desktop、Mobile 和 320px 极小屏正常使用；重点消除非预期横向溢出，补全移动导航、弹窗和图表 resize，并以真实浏览器视口验证。

## 阶段

1. **已完成** — 审查全部当前注册路由、主布局、共享组件、图表、弹窗与固定尺寸，建立响应式问题清单。
2. **已完成** — 完善 Layout 的 PC 保持、Tablet 收窄和 Mobile Drawer 导航。
3. **已完成** — 适配 Landing、认证页与全部真实业务页的 Grid/Flex/Form/Button/长文本。
4. **已完成** — 适配 Radar/ECharts/Growth/PathGraph、RichText、Dialog/Drawer 和 AI 职业伙伴。
5. **已完成** — 运行 typecheck、build、diff check 与已有相关测试，复核不改业务/Mock/API。
6. **已完成** — 使用真实浏览器按 8 组指定尺寸检查核心路由并修复回归。

## 约束与决定

- 断点优先统一为 `>=1200px` Desktop、`768–1199px` Tablet、`<768px` Mobile、`<=480px` Small Mobile；仅在 320px 确有问题时增加极小屏规则。
- PC Sidebar/Header/页面结构和现有主题保持不变；移动端仅增加轻量菜单开关与 Element Plus Drawer。
- 不修改 API、Store 业务逻辑、后端、MCP、Agent、算法、Mock 策略或数据契约。
- 不用 `body { overflow-x: hidden }` 掩盖问题；逐一修复宽度、min-width、nowrap、图表与弹窗溢出源。
- 只适配 Router 当前真实挂载页面及其共享组件，不处理未挂载旧原型。

## 错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| `planning-with-files/scripts/session-catchup.py` 在前序任务中已确认不存在 | 1（历史） | 本轮直接读取现有规划文件与 Git 状态恢复上下文，不重复执行缺失脚本。 |
| 首次浏览器矩阵中 `npm run dev -- --host 127.0.0.1` 的参数被当前 PTY 解析为 Vite root | 1 | 结果全为浏览器错误页，未计入验收；已停止该服务，改用 Vite CLI 显式 `--host 127.0.0.1` 并将审计 URL 固定为回环 IP。 |

## 完成结论

- Desktop 保持 240px Sidebar、74px Header 和原页面视觉；Tablet 收窄内容 padding 并按页面降为双列/单列；Mobile 使用同一导航数据的 Drawer/Hamburger、12px 主内容边距和单列业务内容。
- Landing、Login/Register 及 7 个核心 app 路由均完成 Grid/Flex/Form/Button/长文本适配；没有复制页面或引入新 UI 框架。
- Radar、Growth、Analysis ECharts 改为容器级 ResizeObserver；PathGraph 在窄容器使用 X6 zoomToFit；富文本、AI 面板和 Dialog 均有明确的窄屏滚动/换行边界。
- 8 个指定视口共 62 个主组合通过，375/320 全 10 路由补跑通过；横向溢出、无效页面、Layout 断点失败均为 0。
- `npm run typecheck`、`npm run build`、`git diff --check` 全部通过；build 仅保留既有的大 chunk 警告，package.json 无额外测试脚本。
- 本轮未修改 Router、API、Store 业务逻辑、后端、MCP、Agent、算法或 Mock 策略；仅 DataInput 增加 descriptions 响应列数状态，Layout 增加移动菜单状态。

---
