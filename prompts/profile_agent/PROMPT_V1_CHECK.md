# ProfileAgent Prompt V1 人工模拟检查

检查方式：将 `students_demo.json` 中三份匿名画像反向整理为 `resume_text`、`form_data`、`supplementary_info`，组装 `user_template.txt`，再人工检查预期抽取边界。未调用真实 LLM。

## 演示学生 A

- 模拟 `form_data`：本科、信息管理（演示）、2027 年毕业、目标岗位 AI 产品经理、目标行业人工智能、无工作经验。
- 模拟 `resume_text`：匿名课程数据项目、演示数据分析任务、模拟用户访谈、课程展示。
- 模拟 `supplementary_info`：真实项目经历尚未提供。
- 可支持标签：Python、数据分析、用户研究、沟通表达。
- 不应推断：产品规划、需求分析、大模型应用、RAG、Agent、MCP。目标岗位和“AI”字样不是这些能力的实践证据。
- 预期结构：4 项能力均有 evidence；缺失项保留“真实项目经历”；`competitiveness_score` 为 `0.0` 占位。

## 演示学生 B

- 模拟 `form_data`：专科、软件技术（演示）、2026 年毕业、目标岗位后端开发工程师、目标行业企业服务/SaaS、无工作经验。
- 模拟 `resume_text`：匿名课程管理系统、数据库课程设计、模拟 API 项目、小组作业中的版本控制。
- 模拟 `supplementary_info`：实习经历尚未提供。
- 可支持标签：Java、SQL/数据库、后端开发、Git/版本控制。
- 不应推断：Spring、云计算、Docker/K8s、Linux/运维；仅“完成 API 项目”也不足以自动认定 API 设计能力。
- 预期结构：4 项能力均保守定级；实习经历列入缺失项；`competitiveness_score` 为 `0.0` 占位。

## 演示学生 C

- 模拟 `form_data`：硕士、统计学（演示）、2026 年毕业、目标岗位数据分析师、目标行业电子商务、0.5 年经验。
- 模拟 `resume_text`：匿名统计建模项目、模拟业务查询、公开演示数据研究、课程分析看板、匿名项目汇报。
- 模拟 `supplementary_info`：无额外缺失信息。
- 可支持标签：Python、SQL/数据库、数据分析、数据可视化、沟通表达。
- 不应推断：机器学习、深度学习、电子商务行业知识。统计建模和目标行业本身不足以证明这些标签。
- 预期结构：5 项能力均有 evidence；不增加额外标签；`competitiveness_score` 为 `0.0` 占位。

## 静态检查结果

- 三份 user template 均能完成占位符替换，无残留模板变量。
- 三份预期输出将冻结评分改为 `0.0` 占位后，均通过当前 `StudentProfile` Schema 校验。
- 能力项数量分别为 4、4、5，均满足 3–30 项约束。
- Prompt 明确包含 JSON-only、标准标签、等级、confidence、evidence、隐私、禁止匹配/Gap/路径/录用概率和提示注入防护规则。

## 阶段2封板测试基线（2026-08-10）

- 固定专项命令：`cd backend && python -m unittest app.agents.tests.test_profile_agent -v`。
- ProfileAgent 专项测试 7/7 通过，覆盖三份匿名样例、信息不完整、非法 JSON、Schema 失败、模型异常、fallback、CareerState 写回、隐私日志和 Prompt 数据块转义。
- 阶段1 Mock 套件直接运行时 5/7 通过；两个遗留断言仍假设 ProfileAgent 不依赖外部模型且总是成功。当前无 API Key 时真实 Agent 会正确返回 `partial`、`fallback_used=true`，TBox 映射为降级状态，因此不能通过伪造 success 修复旧断言。
- 当前仓库缺少 `backend/app/__init__.py`，不要使用 `python -m unittest discover -s app`；现阶段使用完整模块名执行测试。

## 已知语义风险与后续边界

- Pydantic 只能验证字段、类型、范围和标准标签，不能证明 evidence、证书、项目或工作年限确实来自用户输入。结构合法的幻觉仍可能进入 `CareerState.student_profile`。
- Prompt 规则属于行为约束，不是确定性事实校验。后续应增加输入事实 grounding：证书需显式原文证据，工作年限和基础表单字段应由确定性逻辑回填或核对，不能接受模型覆盖。
- 稀疏输入下的 `completeness` 仍可能被模型高估；更合理的实现是由 Service 按冻结维度确定性计算。`competitiveness_score` 同样继续保持 `0.0` 占位，等待确定性 Service 覆盖。
- 同一输入的核心能力稳定性尚无自动门禁。接入真实 provider 后，应固定模型版本和低 temperature，并增加多次运行的标签/等级漂移阈值测试。
- 规则 fallback 在证据不足三项时会使用阶段1 Demo 能力，保证流程可继续但不代表用户真实能力；上层展示必须依赖 `fallback_used`，不得把这类结果作为确定画像。
- JobAgent 可以复用统一 LLM Client、结构修复、fallback、隐私摘要和测试注入方式，但不能照搬 ProfileAgent 的能力抽取规则，也不能让 LLM 生成匹配分、Gap 或路径评分。
