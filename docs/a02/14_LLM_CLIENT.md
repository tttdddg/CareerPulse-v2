# 14_UNIFIED_LLM_CLIENT — 统一模型调用约定

阶段3所有 Agent 和业务模块只能依赖 `app.core.llm_client.LLMClient`，禁止直接依赖具体
模型供应商 SDK。业务 Prompt 保留在 Agent 或业务模块中，不进入 Client。

## 配置

- `A02_LLM_API_KEY`：模型服务密钥。
- `A02_LLM_BASE_URL`：OpenAI-compatible API 根地址。
- `A02_LLM_MODEL`：模型名称。
- `A02_LLM_TIMEOUT_SECONDS`：请求超时秒数。
- `A02_LLM_TEMPERATURE`：默认温度，范围 0-2。
- `A02_LLM_MAX_RETRIES`：结构化解析/校验失败后的重试次数，范围 0-2。
- `A02_LLM_MOCK_MODE`：开启后不访问网络。
- `A02_LLM_MOCK_RESPONSE`：Mock 模式的默认文本响应。

`A02_DEMO_MODE=true` 在未显式配置 `A02_LLM_MOCK_MODE` 时也会启用 Mock 模式。

## 调用

```python
from app.core.llm_client import llm_client

text = await llm_client.generate(
    [{"role": "user", "content": "请简要总结输入"}]
)

profile = await llm_client.generate_structured(
    messages,
    StudentProfile,
    fallback=lambda error: deterministic_profile,
)
```

结构化调用会清理完整 JSON Markdown 代码块，使用 Pydantic 校验结果。失败后最多修复两次；
每次修复只向模型反馈不含原始输入的 JSON/Pydantic 错误摘要。网络、超时、限流、空响应
使用分类异常；调用方可以提供规则或默认结构作为 fallback，fallback 仍须通过相同 Schema。

日志只记录模型名、Mock 状态、消息数量、耗时、状态和错误类型，不记录 API Key、消息正文、
模型输出或完整简历。
