阶段2统一 LLM Client 已完成，未修改任何禁止目录，也未提交 Git。

修改文件：

- [llm_client.py](D:/vue/CareerPulse-Pro/backend/app/core/llm_client.py)：统一异步 LLM Client
- [config.py](D:/vue/CareerPulse-Pro/backend/app/core/config.py)：环境变量配置
- [.env.example](D:/vue/CareerPulse-Pro/.env.example)：配置示例
- `task_plan.md`、`findings.md`、`progress.md`：planning-with-files 任务记录

公开接口：

```
from app.core.llm_client import llm_client

text = await llm_client.generate(
    system_prompt="...",
    user_prompt="...",
    temperature=0.2,
    max_tokens=1000,
    timeout=30,
)

result = await llm_client.generate_json(
    system_prompt="...",
    user_prompt="...",
    response_model=YourPydanticModel,
)
```

也可通过 `LLMClient(settings=...)` 创建独立实例，便于测试或接入其他 OpenAI 兼容提供方。

统一异常：

- `LLMError`
- `LLMConfigurationError`
- `LLMTransportError`
- `LLMResponseError`
- `LLMValidationError`

Client 不负责业务重试或 fallback，由上层 Agent 捕获 `LLMError` 后决定。

环境变量：

```
A02_LLM_API_KEY=
A02_LLM_BASE_URL=https://api.openai.com/v1
A02_LLM_MODEL=gpt-4o-mini
A02_LLM_TIMEOUT_SECONDS=30
A02_LLM_TEMPERATURE=0.2
```

关键实现：

- 支持 system/user prompt、temperature、max_tokens、timeout。
- 使用 `/chat/completions` OpenAI 兼容协议。
- `generate_json()` 请求 JSON 输出，并通过 Pydantic `TypeAdapter` 本地校验。
- HTTP 状态、超时、响应格式及 Schema 错误统一转换为可识别异常。
- API Key 只进入 Authorization Header。
- 异常信息不包含 API Key、Prompt、响应正文或简历内容。
- `extra_parameters` 支持后续扩展 provider 参数，但禁止覆盖 `model` 和 `messages`。

验证结果：

- LLM Client Mock 最小调用测试：6/6 通过
  - 文本生成
  - Pydantic 结构化输出
  - 缺少 API Key
  - HTTP 503
  - 超时
  - 非法 JSON
- 阶段1回归测试：7/7 通过
- Python 编译检查通过

未新增依赖。复用了当前环境已有的 `httpx` 和 Pydantic，没有新增 OpenAI SDK。已知风险是仓库目前没有 Python 依赖清单；部署环境需要确保包含 `httpx`。此外，极少数 OpenAI 兼容提供方不支持 `response_format=json_object`，届时需通过 `extra_parameters` 调整或增加 provider 适配。

工作树原有的 `README.md` 修改和未跟踪开发日志均未触碰。`git diff --check` 仅报告了原有 `README.md` 尾随空格，与本任务无关。