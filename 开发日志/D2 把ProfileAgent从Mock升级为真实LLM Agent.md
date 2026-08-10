ProfileAgent 已升级为真实 LLM Agent，业务代码仅修改：

- [profile_agent.py](D:/vue/CareerPulse-Pro/backend/app/agents/profile_agent.py)
- `task_plan.md`、`findings.md`、`progress.md`：任务跟踪记录

未修改 JobAgent、Service、Orchestrator、公共 API、Match、数据库或前端，未提交 Git。

关键 diff：

- 接入统一 `llm_client.generate_json()`。
- 加载 Profile Prompt V1 的 system/user template。
- 支持 `resume_text`、`form_fields`/`form_data` 及三种补充经历字段。
- 使用 `StudentProfile` 完成 JSON 与 Schema 校验。
- 输出通过 `model_dump()` 写入 `CareerState.student_profile`。
- tool name 从 Mock 名称改为 `analyze_student_profile`。
- 保留 BaseAgent 统一返回、计时、日志和状态处理。
- 修正 ProfileAgent 的 Mock summary 文案。
- 强制覆盖 `competitiveness_score=0.0`，不接受 LLM 生成的非确定性评分。
- 未生成匹配分、Gap 或职业路径。

Retry 逻辑：

```
首次调用
  ↓ JSON/Schema 错误
第 1 次结构修复
  ↓ 仍错误
第 2 次结构修复
  ↓ 仍错误
fallback
```

修复 Prompt 明确要求只修正：

- JSON 语法
- 必填字段和字段类型
- 数值范围
- 标准能力标签
- 重复标签
- evidence 隐私问题

它同时要求不添加新事实、不重新解释任务、不自由扩写。provider、超时或配置异常不会进行无意义的结构重试，而是直接 fallback。

Fallback 逻辑：

1. 从简历及补充经历中匹配有效标准能力标签。
2. 至少匹配三项时生成保守的 `level=2`、`confidence=0.5` 规则画像。
3. 证据不足三项时使用阶段1 Demo 能力数据。
4. fallback 结果再次经过 `StudentProfile` 校验。
5. fallback 成功返回 `partial`、`fallback_used=true`。
6. fallback 也失败时返回标准 `failed` 结果，并保持 `student_profile=None`。

隐私处理：

- 普通日志只记录是否提供简历、表单字段数量、是否提供补充经历。
- 不记录简历正文、Prompt、手机号、邮箱或身份证号。
- fallback evidence 使用通用摘要，不复制原始文本。
- Pydantic fallback 错误会转换为安全摘要，避免回显输入值。
- 三个 Prompt 数据块会转义 XML 控制字符，降低 Prompt 结构注入风险。
- `duration_ms` 由 BaseAgent 覆盖完整调用、重试和 fallback 时长。

测试结果：

- 最终隔离测试：7/7 通过
  - 正常输入
  - 信息不完整
  - 非法 JSON 后修复成功
  - Schema 持续错误后 fallback
  - LLM 异常
  - 规则 fallback
  - fallback 失败
- 编译检查：通过
- 注入合法 LLM 响应后的现有回归：7/7 通过
- Prompt 边界注入测试：通过

由于允许修改范围仅包含 `profile_agent.py`，没有新增持久化测试文件。旧 Mock 回归若在没有 API Key、也不注入 Mock LLM 的情况下直接运行，会有 2 项失败：旧断言要求始终 `success/code=0`，而真实 Agent 按新契约正确返回 `fallback/partial/-4`。没有通过伪造成功状态规避这一语义差异。