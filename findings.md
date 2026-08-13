# 阶段3第1步检查发现

- 仓库根目录包含 `backend/`、`front/`、`docs/`、`prompts/`、`开发日志/`。
- 根目录初始无本任务计划文件；`front/` 下的计划文件属于其他工作，保持不动。
- 初始 `git status --short` 无输出，工作树干净。
- FastAPI 主应用为 `backend/app/main.py`，传统 Vue 调用路由由 `routers.py` 聚合；另有 A02 Agent API 与 TBox adapter，但本任务不触碰后者。
- 当前使用 Pydantic v2 API（`ConfigDict`、`field_validator`、`model_validator`、`TypeAdapter`）。
- 已有严格的 `profile_schema.py` / `job_schema.py`，面向冻结的旧 Agent 输出；字段仍是 `student_id/abilities/completeness` 与 `title/required_abilities` 等，不能直接删除，应以兼容扩展或清晰分层方式演进。
- `a02_models.py` 是 Demo 种子数据校验模型，与运行期 Schema 部分重名；需避免再复制能力维度字符串。
- `CareerState` 当前以 `dict[str, Any]` 保存 Agent 各阶段结果，保持该公共字段形状可避免破坏调用链。
- 实际环境为 Pydantic 2.13.4、FastAPI 0.133.1，可使用现有 v2 校验 API。
- 仓库原有 `app/schemas.py` 和 `app/schemas/` 同名且目录缺少 `__init__.py`，使 Agent 对目录 Schema 的导入失败；包入口需保留传统路由导入的六个模型。

## 第2步检查发现

- `app/core/llm_client.py` 已使用 `httpx.AsyncClient` 调 OpenAI-compatible `/chat/completions`，定义配置/传输/响应/校验异常，并有 `generate`、`generate_json`。
- `ProfileAgent` 与 `JobAgent` 已支持构造函数注入 Client，但各自在 Agent 内实现最多两次结构修复重试。
- `app/core/config.py` 已从 `A02_LLM_*` 环境变量读取模型、地址、Key、超时和温度；`.env.example` 已列出这些配置及 `A02_DEMO_MODE`，但 Settings 尚未读取 Mock 开关或重试次数。
- 当前没有独立日志配置模块；Agent 执行日志写入 `CareerState.agent_logs`，LLM Client 自身尚无标准库安全日志。
- 仍有两处具体 SDK 直调：异步学生路由使用 `AsyncOpenAI`/`DEEPSEEK_*`，同步 `matching_service.py` 使用 `OpenAI`/`DEEPSEEK_*`；需要迁移才能真正只保留一套模型调用框架。
- 测试主要使用 `unittest.IsolatedAsyncioTestCase`、注入队列 Client/`AsyncMock`，适合为统一 Client 增加 `httpx.MockTransport` 测试且不会访问真实网络。
- 统一 Client 采用 `messages` 主接口，保留 `system_prompt/user_prompt` 与 `generate_json` 兼容入口；结构化重试仅针对 JSON/Pydantic 失败，网络/超时/限流直接抛出分类异常或进入调用方显式 fallback。
- 传统 `matching_service.py` 原先让 LLM 直接产出匹配分数，违反 A02 架构规则；已保留同形状接口并统一改用确定性规则计算，而不是把该逻辑迁入新 Client。

## 第3步检查发现

- 数据库 `student_profile.parsed_data` 保存已有解析结果，常见字段为 `skills`、`certificates`、`education`、`internships`、`projects`；本步骤直接消费这些字段，不重写文件解析/OCR/简历解析器。
- ProfileAgent 原实现及 Prompt 面向阶段2冻结结构，能力重试与fallback也依赖旧 `abilities`；需切换到统一 `StudentProfile`，并将LLM限制为候选证据抽取。
- CareerState 的 `student_profile` 可同时作为历史画像输入和本轮输出；当前明确资料覆盖基础字段，经历类字段去重合并，历史 `created_at` 和有证据能力需保留。
- 现有48个有效能力标签均已映射到七个统一能力维度，无未映射标签。
- 旧平台全链路7项仍有2项冻结断言失败；统一画像不再提供旧 `abilities` 后，下游旧Match链路进入fallback，属于后续兼容迁移范围，本步骤不修改TBox或匹配模块。
