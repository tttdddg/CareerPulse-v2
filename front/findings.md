# Findings

## 现状
- 尚未检查项目现有结构与依赖（待任务执行时补充）。

## 假设
- 需要从当前项目根目录生成规划文件。
- 富文本编辑器尚未指定具体库。

## 待确认
- 是否已有现有页面或设计稿。
- 富文本编辑器偏好（如 `@wangeditor/editor`、`quill`、`tiptap`）。

## 阶段2统一 LLM Client（2026-08-09）

- 冻结架构明确 `backend/app/core/config.py` 与 `backend/app/core/llm_client.py` 为统一配置和统一 LLM 客户端位置；职责包括兼容 OpenAI provider、结构化输出校验、默认 30 秒超时。
- Agent 契约规定上层负责 LLM 失败后的重试 2 次及 fallback，因此 Client 应抛统一异常，不自行吞掉失败或实施业务降级。
- 当前仓库尚不存在 `backend/app/core/`，本任务需要新建目录及两个允许文件；也未检索到现有 OpenAI/LLM 调用实现。
- 当前 `backend/` 下未发现 requirements 文件；依赖与运行方式仍需继续从根目录和项目配置盘点。
- 文档用 PowerShell 默认读取时出现编码乱码，后续以 UTF-8 定向读取关键段落。
- Python 3.11、Pydantic 2 和 httpx 在当前后端运行环境可用；项目无依赖清单，采用 httpx 直连兼容接口，避免新增 OpenAI SDK 耦合。
- 现有 Agent 均为 async，统一 Client 采用异步调用；请求/响应原文不写日志，HTTP 错误仅保留状态码。
- `generate_json` 默认发送 OpenAI 兼容的 `response_format={"type":"json_object"}` 并以 Pydantic 本地校验；不支持该参数的兼容提供方可通过 `extra_parameters` 显式传入其支持的 response_format，但完全不兼容 chat/completions 的 provider 仍需适配。
- 按用户允许修改范围未新增持久化测试文件，采用本地 Mock Transport 最小调用测试完成验证。

## ProfileAgent 阶段2 Schema（2026-08-09）

- `04_API_CONTRACTS.md` 与 `05_AGENT_CONTRACTS.md` 均为 FROZEN；StudentProfile 固定字段为 `student_id/name/basic_info/abilities/competitiveness_score/completeness/missing_fields`。
- 固定范围：能力等级 1–5；confidence、completeness 为 0.0–1.0；competitiveness_score 为 0.0–100.0；abilities 为 3–30 项。
- 画像中的能力标签必须来自 §11 标签体系；画像 level 不允许 0（0 仅用于后续 Gap 计算）。
- 公共契约 §10 已明确 competitiveness_score “由能力等级加权计算得出”，虽然 ProfileAgent 输出中保留该字段，但不应由 LLM 自由编造；Schema 只能限制范围，不能保证来源确定性。
- 当前 `backend/app/schemas/` 不存在，因此需要创建 `profile_schema.py`；暂无统一导出文件可修改。
- 数据字典中的 `student_ability_records` 与公共契约一致：level 1–5、confidence 0–1、evidence 可持久化；当前能力标签 JSON 有 43 个非废弃标签，比冻结契约的最低 40 个更多。
- 当前 CareerState.student_profile 类型仍是 `dict[str, Any] | None`，因此 Schema 应通过 `model_dump()` 无损生成可直接赋值的字典，不修改冻结 State。
- ProfileAgent 当前 Mock 输出完整包含所有冻结字段且有 3 项合法标签，可直接用于 Schema 兼容测试。
- Schema 将拒绝未知/废弃标签、重复标签、额外字段，以及 evidence 中明显的邮箱、手机号和身份证号，落实标签与隐私契约。

## ProfileAgent Prompt V1（2026-08-09）

- Prompt 目标字段必须与 StudentProfile 完全一致；当前 Schema 严格禁止额外字段，abilities 要求 3–30 项、标签唯一且来自 43 个有效标准标签。
- 三份匿名学生样例分别覆盖产品/AI方向、Java 后端方向、数据分析方向；均包含 basic_info、4–5 项 evidence-backed abilities、完整度和缺失字段。
- Prompt 必须把 resume_text/form_data/supplementary_info 视为不可信数据，防止其中的指令覆盖 system 约束。
- `competitiveness_score` 是冻结必填字段但应由确定性权重计算。Prompt V1 将要求固定输出 `0.0` 占位且禁止 LLM 估算；后续 Agent/Service 必须在入库或展示前覆盖，避免制造伪确定性分数。
- Schema 的 abilities 至少 3 项与“不得编造”在极少信息输入下可能冲突。Prompt 将明确不得为了凑数补标签；如果证据不足，应保守抽取并依赖上层校验失败后的追问/重试/fallback，而不是幻觉补齐。
- 当前 `prompts/profile_agent/` 不存在，需要在允许范围内新建 `system.txt` 和 `user_template.txt`。
- 三份匿名样例静态组装均无残留占位符，预期输出（竞争力评分改为 0.0 占位）全部通过当前 StudentProfile Schema；能力项分别为 4、4、5。
- 人工幻觉边界：A 不从 AI 产品目标推断产品规划/RAG/Agent/MCP；B 不从 Java/API 项目推断 Spring/云/Docker/API设计；C 不从统计建模和目标电商行业推断机器学习/深度学习/电商行业知识。

## ProfileAgent 真实 LLM 升级（2026-08-10）

- BaseAgent 已负责统一 envelope、真实 duration、fallback_used、error 摘要和 CareerState.apply_agent_data；ProfileAgent 可复用该流程，但 BaseAgent 的 success/fallback summary 文案仍含“Mock”。为避免扩大修改范围，优先复用基类并通过 ProfileAgent 的安全摘要/真实 tool_name 保持行为正确；是否需要统一去除 Mock 文案应在后续获准修改 BaseAgent 时处理。
- 统一 Client 的 `generate_json(..., response_model=StudentProfile)` 已同时完成 JSON 解析和 Pydantic 校验，并将两类失败统一为不含模型原文的 LLMValidationError，适合安全重试。
- 重试策略应为首次请求 + 最多 2 次结构修复请求；仅 JSON/Schema 校验失败进入修复重试，provider/超时/配置等模型异常直接抛给 BaseAgent 进入 fallback。
- 修复 Prompt 不包含失败输出或简历原文副本，只在同一安全用户 Prompt 后附加“上一响应结构校验失败”的明确修复指令，避免日志/异常泄露和自由改写。
- Prompt V1 要求 competitiveness_score 固定 0.0 占位；ProfileAgent 不应自行产生匹配分或实现 Match 逻辑。该占位值仍需未来确定性 Service 覆盖。
- Agent 侧会再次强制 competitiveness_score=0.0，即使 provider 忽略 Prompt 也不会让 LLM 分数进入 CareerState；fallback Schema 异常也会转换为不含原始输入值的安全摘要，避免 Pydantic 错误回显隐私。
- 三个 Prompt 数据块在渲染时转义 XML 控制字符，防止简历/表单/补充经历伪造闭合标签实施结构注入；原始内容仍只发送给 LLM，不进入普通日志。

## ProfileAgent 独立验证（2026-08-10）

- 当前环境未配置 A02_LLM_API_KEY/BASE_URL，因此正常样例与稳定性使用受控模拟 LLM；这验证 Agent/Schema/State/日志链路，不能代表真实 provider 的幻觉率。
- 必测 6 组全部执行：正常样例 3 组（各重复 2 次）、信息不完整 1 组、模型异常 1 组、非法 JSON 1 组。所有最终画像均通过 Pydantic，level/confidence 合法，统一 envelope 与 CareerState 更新正确，日志未出现完整简历哨兵、邮箱或手机号。
- 正常样例能力数 4/4/5，controlled repeat 核心标签与等级一致；不完整样例能力数 3、completeness=0.35，低于正常样例 0.68–0.80。
- 模型异常真实进入 ProfileAgent fallback：status=partial、fallback_used=true、仅调用模型 1 次；非法 JSON 前两次失败、第二次允许修复后成功，总调用 3 次且 repair prompt 使用正确。
- fallback evidence 仅为“输入中明确提及{tag}”，标签与输入对应但没有保留项目级事实，质量弱；该 fallback completeness 得到 1.0，明显高于原匿名样例 0.68，补充信息中的“实习经历缺失”没有反映到 missing_fields。
- 对抗探针确认当前存在语义校验缺口：伪造 PMP、5 年经验、completeness=1.0 的结构化输出可通过 Schema 并被 Agent 接受；同一输入的两个完全不同但 Schema 合法的能力核心也都会被接受，Agent 不检测漂移。
- 根因是 ProfileSchema 只校验结构/范围，Prompt 规则不等于可执行事实约束；ProfileAgent 未将 basic_info 与表单做确定性回填，也未验证 evidence/tag 是否能在输入中找到事实依据。
- 未修改任何业务逻辑。建议下一任务在获准范围内增加输入事实 grounding、表单字段确定性覆盖、证书显式证据门槛、确定性 completeness，以及真实 provider 多次运行测试。

## ProfileAgent 审查反馈核验（2026-08-10）

- 报告问题1的代码位置属实：ProfileAgent.run 事后修改 result.summary 和最后一条 AgentLog。但 Pydantic BaseModel 默认可变，当前赋值实测成功；BaseAgent 当前顺序执行且有 agent_name guard，因此这是技术债/未来脆弱点，不是当前 P1 运行时 Bug，建议降为 P2。
- 报告问题2部分属实：repair 文本没有逐项写出手机号/邮箱/身份证号，也没有明确“能力不足不得补齐”。但 repair 仍与完整 system prompt 同时发送，且自身已有“不要添加新事实”，system 又明确禁止凑能力，所以“模型不知道敏感规则”不准确；建议作为 P2 Prompt hardening，而非已证实 P1。
- 报告问题3属实且是当前最重要质量缺口：仓库只有 platform/tests/test_mock_career_flow.py，没有持久化 ProfileAgent 专项测试；此前隔离测试均未落盘。
- 问题4属实但仅文案准确性；问题5属实，探针确认 A & B 被改成 A &amp; B，可能污染模型输出；问题6属实但微秒级、低优先级。
- 问题7文件确实缺失，但“import app.core 会失败”不成立：Python namespace import 实测成功。属于工程约定/IDE 兼容问题，非运行时 Bug。
- 问题8已经解决：StudentProfile 当前 docstring 明确警告 LLM score 不可信、应由确定性计算提供，因此该条不再存在。
- 审查报告遗漏了独立验证已确认的更重要问题：Agent 不做语义 grounding，Schema 合法的虚构证书、工作年限、完整度可进入 CareerState；fallback completeness 可能虚高，少于3项规则标签时会注入 Demo 能力。
- 报告关于旧 Mock 测试“无 Key 仍能通过”不准确：当前直接运行 7 项有 2 项失败，分别是 final_report 期望 success 实为 partial、TBox code 期望 0 实为 -4。这是升级后 fallback 语义与旧断言冲突。
- 推荐测试落盘位置遵循现有 app/platform/tests 风格：新增 backend/app/agents/tests/__init__.py 与 test_profile_agent.py；使用 unittest.IsolatedAsyncioTestCase、可注入 QueueClient，测试公开 run 行为为主、私有 helper 为辅。
- 测试应分两层：当前必须全绿的结构/重试/fallback/隐私回归；以及 grounding 合同测试（虚构 PMP、改写年限、完整度膨胀），在修复前明确 expectedFailure 或单独质量门禁，避免把 Prompt 当作事实校验。

## ProfileAgent 阶段2封板（2026-08-10）

- 已将 7 项专项测试持久化到 `backend/app/agents/tests/test_profile_agent.py`，三份匿名样例、稀疏输入、JSON/Schema repair、provider fallback、状态写回和隐私日志均纳入回归。
- Prompt 数据块只依赖尖括号形成控制标签边界；保留普通 `&` 不会恢复闭合标签注入。修复后 `A & B` 原样保留，伪造的 `</resume_text>` 会转成 `&lt;/resume_text&gt;`。
- 专项测试命令 `python -m unittest app.agents.tests.test_profile_agent -v` 已通过 7/7。

## JobAgent 阶段2 Schema（2026-08-10）

- 冻结 `JobProfile` 字段为 `job_id/title/normalized_title/industry/required_abilities/soft_skills/salary_range/job_description`；冻结 `TrendResult` 字段为 `job_title/industry/trend_summary/hot_skills/rising_skills/declining_skills/ai_risk_assessment/ai_risk_detail/development_opportunities/development_risks/data_source`。
- CareerState 将 `job_profile` 与 `trend_result` 分别存为两个 dict，因此 Schema 应分别提供 `JobProfile`、`TrendResult`，并可提供仅用于一次结构化响应校验的 `JobAgentOutput` 包装模型。
- 用户本次要求的独立 `job_type`、能力 `evidence`、`job_summary` 与冻结契约存在差异。为避免未同步 API 文档的顶层字段漂移，使用 `normalized_title` 表达归一化岗位类型、`job_description` 承载自然语言岗位摘要；`evidence` 作为明确要求的最小嵌套扩展，并允许在无 JD 的 fallback 场景为 null。
- `jobs_demo.json` 是现有三份岗位和权重样例，权重和均为 1.0；仓库不存在 `job_type_profiles.json`，数据字典只描述预期数据形态。
- required abilities 和趋势技能应复用 `ability_tags.json` 的有效标准标签；required_level 限制 1–5、weight 限制 0–1，并在 JobProfile 层校验标签唯一和总权重为 1.0。
- 最终 Schema 额外禁止未知字段，可直接分别 `model_dump()` 写入两个 CareerState 字段；组合模型还校验岗位名称和行业一致。
- 三份 `jobs_demo.json` 均通过；合法组合输出通过；required_level=6、权重总和不为1、未知趋势标签、额外 match_score、非法 AI 风险枚举均被拒绝。

## JobAgent Prompt V1（2026-08-10）

- Prompt 输出必须是 `JobAgentOutput`：顶层严格分为 `job_profile` 与 `trend_result`，二者岗位名和行业必须一致；不得直接输出合并对象。
- 三份岗位样例存在于 `backend/app/data/jobs_demo.json`，但这些是结构化 Demo 岗位画像，不是原始 JD；人工检查时只能据其 `job_description` 和能力项反向组成匿名模拟 JD，不能声称是真实招聘信息。
- 仓库没有独立的岗位趋势资料样例文件；只有冻结 TrendResult 字段和 TBox 趋势知识库建设要求。Prompt 必须把空 `trend_context` 作为事实缺口，使用保守措辞、空技能趋势列表和明确的数据来源限制，不能编造招聘量、增长率或年份。
- `required_abilities[].evidence` 在当前 Schema 可为 null，用于没有原始 JD 的 fallback；正常提供 JD 时 Prompt 应要求每项能力都有 JD 事实证据，且行业趋势不得进入该字段。
- 权重不是市场统计值，而是当前岗位能力要求的归一化相对重要性；必须在 0–1 且总和为 1.0。等级同样只能依据 JD 的职责强度、独立程度和资历措辞保守判定。
- 最终三份样例模板组装均无残留占位符；三个 Prompt 文件为严格 UTF-8；关键 Schema 字段、JSON-only、Markdown 禁止、匹配/Gap/路径禁令均通过静态检查。未调用真实模型，因此结论不代表真实 provider 的趋势准确率或幻觉率。

## JobAgent 真实 LLM 升级（2026-08-10）

- BaseAgent 已负责 duration、统一 AgentResult、tool call、fallback_used/error 和 CareerState.apply_agent_data；JobAgent 只需返回严格的 `job_profile`/`trend_result` 两键数据。
- 结构失败策略与 ProfileAgent 一致：首次请求 + 最多 2 次 `LLMValidationError` repair；provider、配置和超时异常不做结构修复，直接进入 fallback。
- 输入兼容 `job_title/job_name/title`、`job_description/jd_text/jd/description`、`trend_context/trend_data/trend_material/knowledge_context`；原始 JD 和趋势上下文只进入 Prompt，不进入普通日志。
- 成功输出确定性回填输入 job_id/title/industry，防止 LLM 改写目标身份；正常提供 JD 时，任何 required ability 的 evidence 为 null 都会转为结构校验失败并进入 repair。
- 规则 fallback 只扫描 JD 中明确出现的标准标签/谨慎别名，等权归一化并提取包含标签的 JD 句子作为脱敏 evidence；没有标签时使用最接近的 `jobs_demo.json` 向量，并明确标记 Demo 描述。
- fallback 趋势永不根据行业常识填充 hot/rising/declining；有趋势上下文也只说明规则无法可靠判断方向，空上下文明确资料缺失，AI risk 使用 Schema 约束下的 medium 中性占位。
- 最终隔离测试 7/7 通过：正常 JD、信息少、空趋势、非法 JSON 两次修复、Schema 修复、provider 异常规则 fallback、三次结构失败后的 Demo fallback；验证 CareerState 双字段、duration、fallback_used、调用次数和 JD 联系方式不进入日志。
- 现有 ProfileAgent 专项 7/7、compileall 通过；无 Key 直接跑旧 platform suite 仍为已知 5/7（旧断言期待 success/code=0），同时注入受控 ProfileAgent+JobAgent LLM 后 platform suite 7/7 通过。
- 当前 evidence 仅保证非空和 Schema 合法，无法确定性证明 LLM 摘要完全忠实于 JD；规则 fallback evidence 有句子级原文支撑并脱敏。真实 provider grounding 仍需独立质量验证。
- 按用户白名单未持久化 JobAgent 测试文件；七类测试通过隔离脚本执行。后续若允许修改 `backend/app/agents/tests/**`，应把这些用例落盘为持续回归资产。

## JobAgent 独立验证（2026-08-10）

- 当前进程未配置 A02_LLM_API_KEY/BASE_URL，仓库也没有独立岗位趋势资料文件；正常场景采用受控 Fake LLM 和由三份 Demo 标签整理的匿名 JD/趋势上下文，仅验证 Agent/Schema/State/日志与事实边界，不代表真实 provider 或市场趋势准确率。
- 独立验证将额外探测结构合法的语义幻觉：JD 未出现的证书/技能、无法回溯的 evidence、趋势上下文未出现的趋势技能、未提供的百分比。Schema 的 extra=forbid 已能拦截 match/gap 等额外字段，但未必能拦截合法字段内的虚构内容。
- 对抗探针在修复前证实：7 项结构合法能力、伪造 evidence、未提供趋势技能和“增长38%”可被 success 接受。已仅修改 job_agent.py 增加 grounding：JD evidence/薪资可回溯、趋势技能来源、趋势数字来源和空趋势保守约束；grounding 失败不做结构 retry，直接 fallback。
- 修复后独立执行 8 个主场景全部达到预期：正常三岗位能力数 7/5/6，稀疏 JD 1 项，空趋势、非法 JSON、模型异常、综合对抗均通过；另外三个独立趋势探针分别拦截未支持技能、未支持数字和空趋势确定性陈述。
- 所有主场景 JobProfile/TrendResult 均通过 Pydantic，level/weight/总和合法，结果分别写入 CareerState；AgentResult、AgentLog 状态/fallback 一致，模型异常只调用一次，非法 JSON 调用三次。
- 平台受控双 LLM 链路 7/7、ProfileAgent 回归 7/7、compileall 和 JD 日志/规则 evidence 隐私探针通过。
- 剩余语义风险：非数字趋势摘要、机会/风险和 data_source 的机构名称仍无法完全做确定性语义验证；grounding 使用保守字符串/标签匹配，真实模型的忠实意译可能被误判而进入 fallback。需真实 provider 与真实趋势语料评估误拒率/漏检率。

## 逐页检查发现（2026-03-09）
- 路由当前实际使用页面为：
  - `/` -> `views/home/HomeLanding.vue`
  - `/login`、`/register` -> `views/login/Login.vue`
  - `/app/*` -> `views/input|analysis|path|plan|profile`
- 关键缺口：
  - 登录页未根据 `/register` 路由自动切换到注册模式。
  - 首页 CTA 固定跳转登录，未按登录态直达业务页。
  - 应用启动未主动 hydrate 用户 store，刷新后显示名/档案信息不稳定。
  - 图谱页在未完成分析时仅提示错误，不引导回输入页。
  - 个人中心加载历史时会覆盖本地刚生成的报告，存在数据回退风险。
