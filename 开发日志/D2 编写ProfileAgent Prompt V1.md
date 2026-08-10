ProfileAgent Prompt V1 已完成。本轮业务修改仅位于 `prompts/profile_agent/**`，未修改 Agent、后端 Schema、数据库或前端，也未调用真实模型。

Prompt 文件：

- [system.txt](D:/vue/CareerPulse-Pro/prompts/profile_agent/system.txt)
- [user_template.txt](D:/vue/CareerPulse-Pro/prompts/profile_agent/user_template.txt)
- [PROMPT_V1_CHECK.md](D:/vue/CareerPulse-Pro/prompts/profile_agent/PROMPT_V1_CHECK.md)

其中 user template 预留：

```
{{resume_text}}
{{form_data}}
{{supplementary_info}}
```

System Prompt 已覆盖：

- 仅依据用户明确提供的信息。
- 禁止编造技能、经历、职责和成果。
- 不确定信息降低 `confidence`。
- 每项能力强制提供事实性 `evidence`。
- AI 项目不自动推断 RAG、Agent、MCP 等技能。
- 仅使用当前 43 个有效标准能力标签。
- 完整的 1–5 能力等级规则。
- 完整的 confidence 分段规则。
- evidence 匿名化与隐私规则。
- 3–30 项能力、标签唯一等 Schema 约束。
- 严格 JSON-only，无 Markdown 围栏或解释文字。
- 禁止匹配度、Gap、职业路径和录用概率。
- 防止简历或补充材料中的提示注入。

三份匿名样例人工模拟结果：

- 演示学生 A：支持 Python、数据分析、用户研究、沟通表达；不从 AI 产品经理目标推断产品规划、RAG、Agent 或 MCP。
- 演示学生 B：支持 Java、SQL/数据库、后端开发、Git/版本控制；不推断 Spring、Docker/K8s、云计算或 API 设计。
- 演示学生 C：支持 Python、SQL/数据库、数据分析、数据可视化、沟通表达；不从统计建模推断机器学习/深度学习，也不从目标行业推断电商行业知识。

静态检查：

- 三份模板输入组装成功，无残留占位符。
- 三份预期输出均通过当前 `StudentProfile` Schema。
- 能力数量分别为 4、4、5。
- Prompt 文件 UTF-8 检查通过。
- 未实际调用 LLM。

主要幻觉风险：

- “熟悉”“参与过”等模糊用词可能导致等级膨胀。
- 专业、目标岗位和行业名称可能被错误当作能力证据。
- 工具关键词共现可能导致能力过度映射。
- evidence 摘要过程中可能无意增加原文没有的职责或结果。
- 多来源冲突可能被模型擅自选择某一版本。
- 能力最少 3 项与极少信息输入存在契约冲突；Prompt 已要求不得为了凑数编造，上层应追问或 fallback。
- `completeness` 属于模型判断，跨模型可能有轻微波动。
- `competitiveness_score` 因公共 Schema 必填而固定输出 `0.0` 占位。后续确定性 Service 必须覆盖后才能展示或持久化，不能把占位值当作真实评分。

未自动提交 Git。