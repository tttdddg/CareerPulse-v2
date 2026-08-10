JobAgent Prompt V1 已完成，只新增 `prompts/job_agent/**`，未修改 Agent、Schema、前端或数据库。

Prompt 文件：

- [system.txt (line 1)](D:/vue/CareerPulse-Pro/prompts/job_agent/system.txt:1)
- [user_template.txt (line 1)](D:/vue/CareerPulse-Pro/prompts/job_agent/user_template.txt:1)
- [PROMPT_V1_CHECK.md (line 1)](D:/vue/CareerPulse-Pro/prompts/job_agent/PROMPT_V1_CHECK.md:1)

System Prompt 包含：

- JD 事实、趋势资料、模型归纳的明确分层
- 标准能力标签映射
- `required_level` 1–5 规则
- 权重范围及总和必须为 `1.0`
- `critical / important / nice_to_have` 定义
- JD evidence 来源和匿名化要求
- 空 JD、空趋势资料的保守处理
- 技能趋势、AI 风险、机会和风险的来源约束
- 完整 `JobAgentOutput` JSON 结构
- 禁止匹配度、Gap、路径、录用概率及额外说明

User Template 预留：

```
{{job_name}}
{{job_description}}
{{trend_context}}
```

三岗位检查：

- AI 产品经理：禁止从“大模型应用”扩展出 RAG、Agent、MCP、微调等未提供要求。
- 数据分析师：禁止从数据分析岗位推断机器学习、深度学习或具体增长率。
- 后端开发工程师：趋势资料中的 Docker/K8s、云计算不能进入当前 JD 的硬性能力要求。

静态验证结果：

- 三岗位输入组装：3/3 通过
- 三个占位符均正确替换
- 无残留模板变量
- 三个文件均为有效 UTF-8
- JobSchema 核心字段检查通过
- JSON-only、禁止 Markdown、禁止匹配/Gap/路径等约束存在
- 未调用真实 LLM

主要幻觉风险：

- 把岗位名称或行业常识扩展成 JD 未要求的技术栈。
- 把趋势热门技能伪装成当前岗位硬性要求。
- 为满足权重总和而补造能力和 evidence。
- 根据“高级”“精通”直接给出 level 4–5。
- 将定性资料改写成招聘增长率、薪资变化或 AI 替代比例。
- 仓库目前没有独立岗位趋势资料样例，因此无法验证真实趋势准确率。
- 当前 Schema 没有 `unknown` AI 风险枚举；缺少趋势资料时只能使用 `medium` 中性占位，并在 `ai_risk_detail` 和 `data_source` 中明确资料不足。

没有新增依赖，没有修改 JobAgent，也没有提交 Git。