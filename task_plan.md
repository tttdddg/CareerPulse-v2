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
