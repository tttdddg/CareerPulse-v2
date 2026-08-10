阶段2真实 JobAgent 已完成，业务修改仅涉及：

- [job_agent.py (line 1)](D:/vue/CareerPulse-Pro/backend/app/agents/job_agent.py:1)

另更新了过程记录 `task_plan.md`、`findings.md`、`progress.md`。未修改 ProfileAgent、Service、Orchestrator、MatchAgent、PathAgent、数据库或前端。

### 核心实现

- 使用统一 `llm_client.generate_json()`
- 加载 Job Prompt V1
- 使用 `JobAgentOutput` 校验完整响应
- 支持输入别名：
  - 岗位：`job_title / job_name / title`
  - JD：`job_description / jd_text / jd / description`
  - 趋势：`trend_context / trend_data / trend_material / knowledge_context`
- 正常 JD 下要求每项能力提供 evidence
- 输入中的 `job_id/title/industry` 会确定性回填，防止 LLM 改写目标岗位
- 不调用 MatchService，不生成匹配分、Gap 或路径

### CareerState 更新

成功或 fallback 通过 BaseAgent 分别写入：

```
state.job_profile = result["job_profile"]
state.trend_result = result["trend_result"]
```

写入前两个对象都会通过 Pydantic 校验，并保证：

```
job_profile.title == trend_result.job_title
job_profile.industry == trend_result.industry
```

BaseAgent 继续统一负责：

- `status`
- `duration_ms`
- `fallback_used`
- `error`
- `tool_calls`
- `agent_logs`
- CareerState 写回

### Retry 逻辑

仅 `LLMValidationError` 触发结构修复：

```
首次调用
  → JSON/Schema 失败
  → repair 1
  → 仍失败
  → repair 2
  → 仍失败
  → fallback
```

Repair Prompt 只允许修复：

- JSON 语法
- 必填字段和类型
- 标准标签和枚举
- `required_level`
- 权重范围及总和
- 重复标签
- 两个结果的岗位名称、行业一致性
- evidence 结构

Provider、配置和超时异常不会进行结构重试，直接 fallback。

### Fallback 逻辑

优先使用规则：

- 只从 JD 明确出现的标准能力标签中提取
- 不读取趋势资料作为当前 JD 硬性能力
- 等权归一化，权重和为 `1.0`
- evidence 使用包含标签的 JD 句子
- 邮箱、手机号自动脱敏

JD 无法提取能力时：

- 使用最接近岗位名称的 `jobs_demo.json`
- 明确标记为 Demo fallback
- `fallback_used=true`

趋势 fallback：

- 不根据行业常识填充 hot/rising/declining
- 趋势资料不足时明确说明无法形成可靠结论
- 不编造招聘数量、增长率或确定未来

### 测试结果

隔离测试：**7/7 通过**

- 正常 JD
- JD 信息较少
- 空趋势资料
- 非法 JSON，修复后成功
- Schema 错误，修复后成功
- LLM/provider 异常，规则 fallback
- 修复耗尽，Demo fallback

其他验证：

- ProfileAgent 专项：7/7 通过
- 受控 ProfileAgent + JobAgent LLM 平台链路：7/7 通过
- `compileall`：通过
- 最终 fallback smoke：通过
- 无 API Key 的旧平台 Mock 套件：5/7，仍是已知的两个旧 `success/code=0` 断言冲突

由于本任务白名单只允许修改 `job_agent.py`，七类 JobAgent 测试通过隔离脚本执行，没有将测试文件写入仓库。

### 已知风险

- Schema 只能保证 evidence 非空，不能确定性证明 LLM 摘要完全忠实于 JD；规则 fallback 的 evidence 才有句子级原文支撑。
- 无 JD 时 Demo 能力不代表当前岗位真实要求，调用方必须识别 `fallback_used=true`。
- AI 风险 Schema 没有 `unknown`，趋势不足时仍只能使用 `medium` 中性占位并在说明中标记资料缺失。
- 尚未使用真实 provider 验证趋势准确率、幻觉率和重复运行稳定性。
- JobAgent 专项测试尚未持久化，后续获得测试目录修改权限后应落盘。

没有新增依赖，没有自动提交 Git。