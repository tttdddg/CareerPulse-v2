已完成标准远程 MCP 适配层；没有修改匹配/路径算法、没有执行 Git commit，也没有进入百宝箱配置。

## 1. MCP SDK

采用官方 Model Context Protocol Python SDK：

- 版本：`mcp==2.0.0`
- Python 要求：`>=3.10`
- 当前项目 Python：`3.11.15`
- 已锁定于 [backend/requirements.txt (line 12)](D:/vue/CareerPulse-Pro/backend/requirements.txt:12)

SDK 版本信息见 [PyPI](https://pypi.org/project/mcp/)，Streamable HTTP 挂载方式遵循[官方 ASGI 文档](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/asgi.md)。

## 2. 运行方式和端点

MCP Server 已挂载到现有 FastAPI 应用：

```
$env:MCP_ENABLED = "true"
$env:MCP_AUTH_ENABLED = "true"
$env:MCP_API_TOKEN = "example-local-token"

cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

端点：

```
http://127.0.0.1:8000/mcp
```

传输方式为 Streamable HTTP，没有无依据增加 `/sse`。鉴权格式：

```
Authorization: Bearer example-local-token
```

应用入口见 [main.py (line 45)](D:/vue/CareerPulse-Pro/backend/app/main.py:45)，MCP 创建及挂载见 [server.py (line 71)](D:/vue/CareerPulse-Pro/backend/app/mcp/server.py:71)。

## 3. 工具映射

| MCP 工具                | 复用的现有能力                           | HTTP Tool API              |
| ----------------------- | ---------------------------------------- | -------------------------- |
| `build_student_profile` | ProfileAgent / `analyze_student_profile` | 当前没有独立正式 HTTP 操作 |
| `analyze_target_job`    | JobAgent / `analyze_job_and_trend`       | 当前没有独立正式 HTTP 操作 |
| `analyze_job_match`     | MatchAgent + MatchService                | `analyze_job_match`        |
| `generate_career_path`  | PathAgent + PathService                  | `generate_career_path`     |

匹配和路径工具只读取相同 `session_id` 下的 CareerState，没有让调用方转传完整画像，也没有在 MCP 层重新计算分数。

## 4. tools/list 实际结果

```
[
  {
    "name": "build_student_profile",
    "required": ["session_id", "user_id", "student_input"]
  },
  {
    "name": "analyze_target_job",
    "required": ["session_id", "user_id", "target_job_input"]
  },
  {
    "name": "analyze_job_match",
    "required": ["session_id", "user_id"]
  },
  {
    "name": "generate_career_path",
    "required": ["session_id", "user_id"]
  }
]
```

所有输入 Schema 均禁止未知字段，输出统一包含：

```
success
error_code
message
missing_fields
retryable
trace_id
session_id
status
data
```

Schema 实现在 [mcp_tool_schema.py (line 23)](D:/vue/CareerPulse-Pro/backend/app/schemas/mcp_tool_schema.py:23)。

## 5. 四个主工具测试结果

| 调用                    | 结果                                                         | 最终状态            |
| ----------------------- | ------------------------------------------------------------ | ------------------- |
| `build_student_profile` | 成功，真实 ProfileAgent；离线 LLM 失败时使用既有结构化 fallback | `PROFILE_COMPLETED` |
| `analyze_target_job`    | 成功，真实 JobAgent；离线 LLM 失败时使用既有结构化 fallback  | `JOB_COMPLETED`     |
| `analyze_job_match`     | 成功，真实 MatchAgent/MatchService                           | `MATCH_COMPLETED`   |
| `generate_career_path`  | 成功，真实 PathAgent/PathService                             | `PATH_COMPLETED`    |

Profile/Job 的 `*_COMPLETED` 对应需求中的 `PROFILE_READY`、`JOB_READY` 语义，保持了仓库原有状态名称，没有新增第二套状态枚举。

## 6. 状态串联和一致性

同一个 `session_id` 已验证完整顺序：

```
画像 → 岗位 → 匹配 → 路径
```

验证结果：

- 缺少画像时匹配返回明确的前置条件错误。
- 匹配未完成时生成路径返回 `MATCH_NOT_COMPLETED`。
- MCP MatchResult 与 HTTP Tool API 完全一致。
- MCP PathResult 与 HTTP Tool API 完全一致。
- LLM 失败不会覆盖 Service 计算结果。
- 平台调用日志包含 `session_id`、`trace_id` 和 Agent 运行关联。
- 日志不包含完整简历、Token 或原始敏感输入。

核心复用层见 [tool_service.py (line 63)](D:/vue/CareerPulse-Pro/backend/app/mcp/tool_service.py:63)。

## 7. 测试结果

- MCP 新增测试：`6/6` 通过
- MCP + 正式 HTTP Tool API 定向测试：`11/11` 通过
- `backend/tests` 完整测试：`86/86` 通过
- `compileall`：通过
- A02 数据与契约检查：通过
- `git diff --check`：通过
- MatchService、PathService：无修改

测试覆盖官方客户端的 `initialize`、`tools/list`、`tools/call`、无效 Token、非法参数、状态串联、HTTP/MCP 结果一致性和隐私日志。测试文件见 [test_mcp_server.py (line 97)](D:/vue/CareerPulse-Pro/backend/tests/test_mcp_server.py:97)。

另有两个历史 `backend/app` 旧 Mock 测试仍保持任务开始前的失败状态，原因是旧 Mock 全链路默认离线 LLM 行为；本次未修改 `tbox_adapter.py` 或相关旧测试。正式 HTTP Tool API 测试全部通过。

## 8. 新增和修改文件

主要新增：

- [backend/app/mcp/server.py (line 71)](D:/vue/CareerPulse-Pro/backend/app/mcp/server.py:71)
- [backend/app/mcp/tool_service.py (line 63)](D:/vue/CareerPulse-Pro/backend/app/mcp/tool_service.py:63)
- [backend/app/schemas/mcp_tool_schema.py (line 23)](D:/vue/CareerPulse-Pro/backend/app/schemas/mcp_tool_schema.py:23)
- [backend/tests/test_mcp_server.py (line 97)](D:/vue/CareerPulse-Pro/backend/tests/test_mcp_server.py:97)
- [MCP 接入说明 (line 1)](D:/vue/CareerPulse-Pro/docs/a02/16_MCP_SERVER_INTEGRATION.md:1)

主要修改：

- `backend/app/main.py`
- `backend/requirements.txt`
- `.env.example`
- [04_API_CONTRACTS.md (line 159)](D:/vue/CareerPulse-Pro/docs/a02/04_API_CONTRACTS.md:159)
- [13_MCP_TOOL_CATALOG.md (line 54)](D:/vue/CareerPulse-Pro/docs/a02/13_MCP_TOOL_CATALOG.md:54)
- `03_ARCHITECTURE.md`
- `10_TBOX_REQUIREMENTS.md`

## 9. 配置项

新增配置：

```
MCP_ENABLED
MCP_AUTH_ENABLED
MCP_API_TOKEN
MCP_HOST
MCP_PORT
MCP_PATH
MCP_TOOL_TIMEOUT_SECONDS
MCP_ALLOWED_HOSTS
MCP_ALLOWED_ORIGINS
```

MCP Bearer Token 与现有 FastAPI/HTTP Tool API 鉴权相互独立，不会改变原接口行为。

## 10. 尚未完成事项

尚未执行：

- 公网 HTTPS 部署
- 域名和反向代理配置
- 公网 `/mcp` 连通性验证
- 百宝箱租户是否支持 Streamable HTTP 的实际确认
- 在百宝箱创建 MCP 服务并填写地址
- 生产 Token 配置

## 11. 是否可直接在百宝箱填写地址

代码和本地协议层已经达到“部署后可填写”的条件。

但目前还没有一个真实公网 HTTPS 地址，因此现在还不能填写一个可供百宝箱访问的最终地址。完成公网部署后，应填写类似：

```
https://career.example.com/mcp
```

并配置对应的 `Authorization: Bearer <production-token>`。