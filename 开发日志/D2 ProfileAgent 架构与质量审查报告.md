# 阶段2 ProfileAgent 架构与质量审查报告

## 审查范围

| 文件                                       | 行数 | 审查结论                   |
| ------------------------------------------ | ---- | -------------------------- |
| `backend/app/agents/profile_agent.py`      | 397  | 通过，3 个 P1 / 5 个 P2    |
| `backend/app/agents/base_agent.py`         | 140  | 通过                       |
| `backend/app/core/llm_client.py`           | 209  | 通过，1 个 P2              |
| `backend/app/core/config.py`               | 39   | 通过                       |
| `backend/app/schemas/profile_schema.py`    | 114  | 通过，1 个 P2              |
| `prompts/profile_agent/system.txt`         | 138  | 通过，1 个 P1              |
| `prompts/profile_agent/user_template.txt`  | 17   | 通过                       |
| `prompts/profile_agent/PROMPT_V1_CHECK.md` | 37   | 通过（人工模拟检查文档）   |
| **测试**                                   | —    | 🔴 无 ProfileAgent 专项测试 |
| `backend/app/core/__init__.py`             | —    | 🔴 缺失                     |
| `backend/app/schemas/__init__.py`          | —    | 🔴 缺失                     |
| `backend/app/schemas/common.py`            | —    | 🔴 缺失（约定但未实现）     |

---

### 【问题 1】
【严重程度：P1】
【文件】`backend/app/agents/profile_agent.py:45-58`
【原因】`ProfileAgent.run()` 覆写了 `BaseAgent.run()`，调用 `super().run(state)` 后直接对已返回的 `AgentResult` 实例和 `state.agent_logs[-1]` 进行事后修补。两个问题：(a) `AgentResult` 作为 Pydantic 模型，创建后再通过属性赋值修改其字段违反了 Pydantic 的不可变语义——虽未设 `frozen=True`，但后续如果有人给 `AgentResult` 加 `frozen=True`，这行就会在运行时破裂；(b) `state.agent_logs[-1]` 依赖数组末尾恰好是当前 Agent 的日志这个隐式假设，如果将来 BaseAgent 改变日志写入顺序（例如先写日志再调用 _fallback）或引入异步并发，索引 `[-1]` 会指错对象。

**建议**：不在 `run()` 中覆写。改为在 BaseAgent 中增加一个可覆写的 `def _summary(status: str, fallback_used: bool) -> str` 模板方法，让子类只覆写 summary 文本，不碰 AgentResult 和 agent_logs。在 BaseAgent 不改之前，当前实现可以工作但要标记为技术债——**JobAgent 不要再复制这种覆盖模式**。
```python
# 期望的 BaseAgent 改动（本次不改，作为后续建议）：
# 在 BaseAgent.run() 中把 summary = f"{self.name} Mock 执行完成"
# 改为 summary = self._summary_for_status(status, fallback_used)
```

---

### 【问题 2】
【严重程度：P1】
【文件】`prompts/profile_agent/system.txt:177-178`（对应 `profile_agent.py:174-180` 中的 `_repair_prompt`）
【原因】repair prompt 写 "仅修复...敏感 evidence 问题" 但没有给 LLM 具体指令说明什么是敏感内容。该 repair prompt 被注入到 user prompt 然后重新发给 LLM，模型不知道"敏感 evidence"的具体规则（Prompt 主体中明确禁止的是姓名/手机号/邮箱/身份证号）。对于 `_repair_prompt`，模型不知道什么叫"修复敏感 evidence"，可能随意删除内容或做错误修改。更严重的是——如果初试输出的 `abilities` 数量不足（少于 3 个），repair prompt 说"仅修复 JSON 语法、必填字段..."，模型可能为了满足 `abilities` 最小值而**编造能力标签**，这与 system prompt 中"不得为了满足能力数量而编造标签"直接冲突。

**建议**：修改 repair prompt，明确指示：
```text
仅修复以下结构问题：JSON 语法错误、缺失必填字段但可从已有文字提取（不得新增事实）、
字段类型错误、数值超范围、非标准标签名、重复标签、evidence 含手机号/邮箱/身份证号。
若 abilities 数量不足因输入事实不足，保持当前数量不变；不得为满足最小数量而编造标签。
若无法修复则照原样输出，由校验层拒绝后进入 fallback。
```

---

### 【问题 3】
【严重程度：P1】
【文件】无——缺失文件
【原因】阶段2 没有为 ProfileAgent 编写任何专项测试。当前测试仍是阶段1的 `test_mock_career_flow.py`（7 个集成测试用例）。这 7 个用例调用了旧的 Mock ProfileAgent 链路——当前 ProfileAgent 因为 `_execute()` 改为调用 LLM（需要 API Key），原有测试在无 API Key 环境下会触发 fallback，测试仍能通过，但**无法验证 LLM 调用路径、结构化输出校验、repair prompt 效果、confidence 范围正确性、evidence 隐私脱敏等阶段2新写的核心逻辑**。

**建议**：必须在 JobAgent 开始前补写至少以下 ProfileAgent 专项测试：
1. `test_fallback_profile_rule_tags`：验证 `_rule_tags()` 从文本中正确匹配能力标签
2. `test_fallback_profile_output_schema`：验证 `_fallback_profile()` 返回的 `StudentProfile` 通过 Pydantic 校验
3. `test_fallback_profile_privacy`：验证 evidence 不含手机号/邮箱/身份证
4. `test_fallback_profile_competitiveness_zero`：验证 `competitiveness_score` 恒为 0.0
5. `test_fallback_profile_abilities_min_3`：验证规则匹配不足时降到 Demo 3 个标签
6. `test_escape_prompt_block_no_xml_injection`：验证 `<resume_text>` 中的 `</resume_text>` 被转义

---

### 【问题 4】
【严重程度：P2】
【文件】`backend/app/agents/profile_agent.py:287-308`
【原因】`_demo_abilities()` 返回的证据文本为 "阶段1 Demo fallback 标签"。既然这是阶段2代码，这个 label 具有误导性——它暗示这是阶段1遗留而非阶段2的规则降级输出。而且在 fallback 路径中，`_fallback_profile()` 会在第 210 行判断 `used_demo_abilities = len(abilities) < 3` 并走 `_demo_abilities()`——实际上 fallback 流程图是：正则提取能力标签 → 如果匹配到 ≥3 个则用规则结果 → 如果 <3 则用 Demo 硬编码数据。Demo 数据的 evidence 应准确反映其来源。

**建议**：将 evidence 改为 `"规则提取能力标签不足3项，使用Demo兜底数据"`。

---

### 【问题 5】
【严重程度：P2】
【文件】`backend/app/agents/profile_agent.py:149-150`
【原因】`_escape_prompt_block()` 将 `&` 转义为 `&amp;`。当 `form_data` 被 `json.dumps()` 序列化后再经 `_escape_prompt_block()` 处理，JSON 字符串中如果包含 `&`（例如 `"target_industry": "E-commerce & Retail"`），它会在 XML 标签 `<form_data>` 内变成 `"E-commerce &amp; Retail"`。LLM 读取时可能将 `&amp;` 当做原文字面量并写入输出 JSON——因为 LLM 不知道 `&amp;` 是转义后的 `&`。好在实际场景中 industry 字段很少含 `&`，risk 低但存在。

**建议**：仅对 `<` 和 `>` 做转义（防止 XML 标签注入），不转义 `&`。或者将 `form_data` 用 base64 编码后再放入 XML 块。

---

### 【问题 6】
【严重程度：P2】
【文件】`backend/app/core/llm_client.py:99-100`
【原因】`generate_json()` 使用 `TypeAdapter(response_model).validate_python(raw_data)` 做 Pydantic 校验。每次调用都创建新的 `TypeAdapter` 实例。`TypeAdapter` 内部会做 schema 构建缓存，但创建开销不是零。在 retry 循环中（最多 3 次调用），每次都新建 `TypeAdapter`。开销极低（微秒级），但属于不必要的重复对象创建。

**建议**：将 `TypeAdapter(response_model)` 提升到 `LLMClient.__init__()` 中缓存，或使用 `functools.lru_cache` 包装。低优先级，不改不阻塞。

---

### 【问题 7】
【严重程度：P2】
【文件】`backend/app/core/__init__.py`、`backend/app/schemas/__init__.py`（均不存在）
【原因】尽管 Python 3.3+ 的隐式命名空间包使得 `from ..core.llm_client import ...` 在无 `__init__.py` 时也能工作，但 (a) 这违反 Python 社区约定，(b) 可能导致某些 IDE 和 linter 报错，(c) 如果将来有代码使用 `import app.core` 而非 `from app.core import ...`，会导入失败。

**建议**：创建空的 `__init__.py` 文件：`backend/app/core/__init__.py` 和 `backend/app/schemas/__init__.py`。

---

### 【问题 8】
【严重程度：P2】
【文件】`backend/app/schemas/profile_schema.py:84-98`
【原因】`StudentProfile.competitiveness_score` 字段的 `description` 为 `"综合竞争力评分；必须由确定性能力等级加权计算提供"`，但 Schema 本身不强制 `competitiveness_score == 0.0`——它只做了 `Field(ge=0.0, le=100.0)` 的范围约束。强制设置为 `0.0` 的责任在 `ProfileAgent._ensure_profile()` 第 194 行的 `model_copy(update={"competitiveness_score": 0.0})` 和 system prompt 的约束。这意味着如果将来有代码直接使用 `StudentProfile.model_validate()` 而不经过 `_ensure_profile()`，`competitiveness_score` 可以是任意值。**这是正确的设计**（Schema 不承担业务逻辑），但应在 `StudentProfile` 的 docstring 或注释中明确说明"该字段的 LLM 生成值不可信任，调用方必须用确定性计算覆盖"。

**建议**：在 `StudentProfile` 类的 docstring 中增加警告注释，避免后续开发者误解。

---

### 【问题 9】
【严重程度：信息——非错误】
【文件】`backend/app/agents/profile_agent.py:35-40` + `base_agent.py:20-24`
【原因】对于 `AgentResult.status`，BaseAgent 使用 `Field(pattern="^(success|partial|failed)$")`（base_agent.py:20），ProfileAgent 覆写 `run()` 后设置的 `summary` 基于 `result.status` 的值。两者没有不一致，但验证逻辑分散在两处：BaseAgent 的 Pydantic pattern 约束和 ProfileAgent 的 if/elif/else。如果将来新增第 4 种 status（如 `"skipped"`），ProfileAgent 的 else 分支会错误覆盖 summary。

**建议**：非阻塞——当前 3 种 status 覆盖正确。标记为警惕点，不需要现在修改。

---

## 逐项回答 15 个检查点

| #    | 检查项                                           | 结果         | 详情                                                         |
| ---- | ------------------------------------------------ | ------------ | ------------------------------------------------------------ |
| 1    | ProfileAgent 与 BaseAgent 是否一致               | ⚠️ 存在不一致 | `run()` 覆写导致 summary 设置方式与 BaseAgent 不同（问题1）  |
| 2    | 是否正确使用统一 LLM Client                      | ✅ 正确       | 通过 `self._llm_client.generate_json()` 单一入口，temperature=0.1 传给 LLMClient |
| 3    | 是否存在重复模型调用封装                         | ✅ 不存在     | 只有一个 `llm_client` 单例；旧代码中的直接 `OpenAI()` 调用在 routes/students.py 中但未被 Agent 使用 |
| 4    | LLM 是否承担了确定性计算                         | ✅ 没有       | `_ensure_profile()` 强制 `competitiveness_score=0.0`；System prompt 写死 0.0；两条防线 |
| 5    | evidence 是否真正来源于输入                      | ✅ 是         | System prompt 强制"只依据输入中真实、明确出现的信息"+"evidence 应是输入事实的简洁摘要" |
| 6    | confidence 设计是否合理                          | ✅ 合理       | 5 级分层（0.90-1.00 / 0.75-0.89 / 0.55-0.74 / 0.30-0.54 / 0.00-0.29），对应证据充分度而非能力强弱 |
| 7    | JSON retry 是否真实有效                          | ✅ 有效       | `_execute()` 循环 3 次（初始 + 2 次 repair），每次 repair 有递增的 prompt 注入 |
| 8    | retry 次数是否最多 2 次                          | ✅ 是         | `_MAX_SCHEMA_RETRIES=2`，循环 `range(3)` = 初始 + 2 次 retry = 最多 3 次 LLM 调用 |
| 9    | fallback 是否真实可用                            | ✅ 可用       | 规则提取路径：`_rule_tags()` 正则匹配 + `_FALLBACK_ALIASES` 别名映射 → `_rule_abilities()` → `_fallback_completeness()`；不足 3 个时降级到 `_demo_abilities()` |
| 10   | fallback_used 是否正确                           | ✅ 正确       | `BaseAgent.run()` 第 55 行统一设置，_execute 抛任何异常都会 `fallback_used = True` |
| 11   | CareerState 更新是否正确                         | ✅ 正确       | `output_fields = ("student_profile",)` → 通过 `state.apply_agent_data()` 写入 |
| 12   | Schema 是否过度设计                              | ✅ 没有       | `StudentProfile` 53 行、`StudentAbility` 19 行、`StudentBasicInfo` 9 行——紧凑且精确 |
| 13   | 是否记录了敏感简历原文                           | ✅ 没有       | `_input_summary()` 只返回 "简历=已提供/未提供"；`evidence` 有 regex 校验阻断 PII；`_safe_error()` 截断到 200 字符 |
| 14   | 是否存在 JobAgent 可复用的工程模式               | ✅ 存在       | 以下模式可直接复制：<br>• `_execute()` 中 `for attempt in range(_MAX_SCHEMA_RETRIES+1)` 的 retry 循环<br>• `_repair_prompt()` 的模式（修改文本内容）<br>• `_ensure_profile()` → `_ensure_job()` 的模式（stamp 0.0 占位）<br>• `_fallback_profile()` 中 `self._rule_tags()` + `self._rule_abilities()` 的规则降级模式<br>• `_input_summary()` 覆写 BaseAgent 的模式 |
| 15   | 是否有必须现在修复、否则会复制到 JobAgent 的问题 | ⚠️ 有         | **问题1（run()覆写）** 和 **问题2（repair prompt 漏洞）** 必须在写 JobAgent 前修复 |

---

## 最终裁定

### 是否可以直接开始 JobAgent：**否**

### 必须先修复的问题（阻塞 JobAgent）：

| #    | 问题                                                         | 修复时间估计 |
| ---- | ------------------------------------------------------------ | ------------ |
| 🔴    | **问题1** — `run()` 覆写模式会在 JobAgent 中重复复制，导致 6 个 Agent 各有不同的 summary 设置逻辑 | 30 分钟      |
| 🔴    | **问题2** — repair prompt 中"敏感 evidence 问题"模糊 + "必填字段"修复可能诱导 LLM 编造能力标签 | 15 分钟      |

### JobAgent 开始时建议同时修复（不阻塞但强烈建议）：

| #    | 问题                                                         | 修复时间估计 |
| ---- | ------------------------------------------------------------ | ------------ |
| 🟡    | **问题3** — ProfileAgent 无专项测试，JobAgent 不应再跳过测试 | 45 分钟      |
| 🟡    | **问题7** — `core/__init__.py` 和 `schemas/__init__.py` 缺失 | 1 分钟       |

### 可延后到阶段3修复：

| #     | 问题                                      |
| ----- | ----------------------------------------- |
| 问题4 | `_demo_abilities()` evidence 文案         |
| 问题5 | `_escape_prompt_block()` 的 `&` → `&amp;` |
| 问题6 | `TypeAdapter` 重复创建                    |
| 问题8 | `StudentProfile` docstring 补充           |

---

## JobAgent 应复制的 ProfileAgent 模式清单

```
✅ 可复制的模式：
1. LLMClient 注入：__init__(self, client=None) → self._llm_client
2. Retry 循环：_MAX_SCHEMA_RETRIES = 2 + repair prompt 逐个增强
3. _ensure_*() 模式：_ensure_profile → _ensure_job_profile，stamp 占位值
4. 规则 fallback：_rule_tags() 正则 + 别名表 → _rule_abilities()
5. _input_summary() 覆写（但不覆写 run()）
6. _safe_text / _optional_text / _bounded_* 辅助方法
7. _build_prompts() 的三段式模板替换

❌ 不应复制的模式：
1. 覆写 run() 来改 summary → 等待 BaseAgent 增加 _summary() 模板方法后统一解决
2. repair prompt 的模糊表述 → 按问题2修复后的版本复制
```