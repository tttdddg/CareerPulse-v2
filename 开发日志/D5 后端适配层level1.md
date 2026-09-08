已完成 CareerPulse 后端百宝箱适配层，Vue、MCP、Agent、Service 和评分算法均未修改。

## 实现内容

新增正式适配层：

- [client.py (line 50)](D:/vue/CareerPulse-Pro/backend/app/platform/tbox/client.py:50)：百宝箱异步 HTTP、普通响应与 SSE 解析、超时和安全错误。
- [chat_service.py (line 67)](D:/vue/CareerPulse-Pro/backend/app/platform/tbox/chat_service.py:67)：统一响应、调用日志、HMAC 用户匿名化。
- [session_mapper.py (line 35)](D:/vue/CareerPulse-Pro/backend/app/platform/tbox/session_mapper.py:35)：CareerPulse session 与 `conversationId` 持久化映射。
- [schemas.py (line 17)](D:/vue/CareerPulse-Pro/backend/app/platform/tbox/schemas.py:17)：严格请求、响应和流事件 Schema。
- [router.py (line 107)](D:/vue/CareerPulse-Pro/backend/app/platform/tbox/router.py:107)：正式入口 `POST /api/tbox/chat`。

入口已挂载到主 FastAPI：

```
{
  "session_id": "career-session-001",
  "user_id": "anonymous-user-001",
  "message": "请分析我的职业方向",
  "stream": false
}
```

支持：

- 普通 JSON envelope。
- `session / delta / done / error` 四类 SSE 事件。
- 自动保存并续传百宝箱 `conversationId`。
- 丢弃上游 `thinking/meta`。
- 超时、限流、5xx、协议错误和会话冲突的安全响应。
- 无配置时返回 503，不回退到旧 Mock。
- 不自动重试非幂等聊天消息。

## 安全与配置

新增服务端配置：

```
TBOX_CHAT_API_URL=https://api.tbox.cn/api/chat
TBOX_CHAT_AUTHORIZATION=
TBOX_APP_ID=
TBOX_USER_ID_SECRET=
TBOX_CHAT_TIMEOUT_SECONDS=45
```

`TBOX_CHAT_AUTHORIZATION` 与现有入站工具密钥 `A02_TBOX_API_TOKEN` 完全分离。CareerPulse 的明文 `user_id` 会经 HMAC 转换为稳定的 `cp_<digest>` 后再发送给百宝箱。

调用账本只记录哈希、状态、耗时和响应模式，不保存用户消息、智能体回复、Token 或上游错误正文。

协议依据包括官方 Ant Design X 的 TBox SDK 示例、公开 SDK 的 `chat/chatSync` 能力，以及百宝箱开放平台文档转载中的 `/api/chat`、`conversationId` 和 SSE 格式：[Ant Design X](https://x.ant.design/docs/react/agent-use-tbox/)、[TBox Node SDK](https://www.npmjs.com/package/tbox-nodejs-sdk?activeTab=readme)、[API 协议资料](https://developer.aliyun.com/article/1685577)。

## 文档与契约

- [API_CONTRACTS.md (line 232)](D:/vue/CareerPulse-Pro/docs/a02/04_API_CONTRACTS.md:232)
- [ADR-004](D:/vue/CareerPulse-Pro/decisions/ADR-004-tbox-chat-gateway.md)
- [后端联调说明](D:/vue/CareerPulse-Pro/docs/a02/18_TBOX_CHAT_GATEWAY.md)
- [.env.example (line 29)](D:/vue/CareerPulse-Pro/.env.example:29)
- [联调测试](D:/vue/CareerPulse-Pro/backend/tests/test_tbox_chat.py)

## 验证结果

- `python -m unittest discover -s tests -t .`：194/194 通过。
- Chat + 原阶段3平台工具：11/11 通过。
- Chat 专项：6/6 通过。
- `python -m compileall -q app tests`：通过。
- `python scripts/init_a02_data.py --check`：通过。
- OpenAPI：同时声明 `application/json` 与 `text/event-stream`，无凭据泄露。
- `git diff --check`：通过，仅有 Windows 行尾提示。

旧独立 Mock app 测试仍为 5/7；两项既有失败来自旧断言要求 `success/0`，而 Agent fallback 实际返回 `partial/-4`。正式 `/api/tbox/chat` 不使用该 Mock，因此未伪造成功或扩大修改。

当前尚未配置真实企业租户凭据，所以完成的是后端协议与传输联调。下一步是在部署环境填入正式 App ID/Authorization 后进行真实智能体 smoke test。公网开放前还需接入可信用户认证；多 worker 部署目前应对同一 session 使用 sticky routing。