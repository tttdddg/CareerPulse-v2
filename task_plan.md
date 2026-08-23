# CareerPulse A02：Hermes 提交前最小收尾

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
