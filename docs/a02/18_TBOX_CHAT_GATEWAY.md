# 百宝箱正式智能体 Chat Gateway 联调说明

## 1. 已实现边界

`POST /api/tbox/chat` 已接入主 FastAPI 应用，负责：

- 接收 Vue 未来发送的 `session_id/user_id/message/stream`；
- 以服务端凭据调用百宝箱正式 `POST /api/chat`；
- 用 `CareerState.platform_session_id` 持久化 `conversationId`；
- 将同步 JSON 或上游 SSE 转成 CareerPulse 固定响应；
- 安全处理配置、超时、限流、上游错误、协议错误和 session 冲突；
- 在 `platform_tool_calls` 记录不含对话正文和 Token 的调用状态。

旧 `/api/tbox/mock-career-analysis` 仍只属于独立 Mock app，不会被新入口调用。没有正式配置
时，新入口返回 503，不会用 Mock 伪装成功。

## 2. 协议依据

- Ant Design X 官方 TBox 集成页确认 Node SDK 使用完整 `authorization` 值，并以
  `appId/query/userId` 发起 chat：<https://x.ant.design/docs/react/agent-use-tbox/>
- 百宝箱开放平台文档的阿里云开发者社区转载页给出正式地址、`conversationId`、同步响应和
  SSE 双层 JSON：<https://developer.aliyun.com/article/1685577>
- 官方公开 Node SDK README 同时提供 `chat` 和 `chatSync`：
  <https://www.npmjs.com/package/tbox-nodejs-sdk?activeTab=readme>

目标租户的实际 App ID、授权值、限流和可用能力仍以百宝箱企业版控制台为准。当前仓库没有
真实租户凭据，因此测试使用 `httpx.MockTransport`，不能据此声称已完成线上租户调用。

## 3. 服务端配置

在部署环境配置，不要把真实值写入仓库：

```dotenv
TBOX_CHAT_API_URL=https://api.tbox.cn/api/chat
TBOX_CHAT_AUTHORIZATION=<百宝箱签发的完整 Authorization 值>
TBOX_APP_ID=<正式智能体 App ID>
TBOX_USER_ID_SECRET=<独立的高强度 HMAC secret>
TBOX_CHAT_TIMEOUT_SECONDS=45
```

`TBOX_CHAT_AUTHORIZATION` 会原样进入上游 `Authorization` header；按官方 SDK 示例通常是
`Tbox-...`，适配器不会擅自添加 `Bearer`。它与供百宝箱调用 CareerPulse 工具的
`A02_TBOX_API_TOKEN` 完全不同。`TBOX_USER_ID_SECRET` 用于把 CareerPulse user_id 转成稳定
匿名的百宝箱 userId；不要与任何 API Token 复用，轮换它会改变百宝箱侧用户标识。

## 4. 普通响应联调

从 `backend/` 启动：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

请求示例（均为匿名占位值）：

```powershell
$body = @{
  session_id = "career-session-001"
  user_id = "anonymous-user-001"
  message = "请分析我的职业方向"
  stream = $false
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/tbox/chat" `
  -ContentType "application/json" `
  -Body $body
```

第二条消息复用相同 `session_id/user_id` 即可；浏览器不需要也不应提交 conversationId，后端
会从 CareerState 自动带回。

## 5. 流式联调

```powershell
curl.exe -N -X POST "http://127.0.0.1:8000/api/tbox/chat" `
  -H "Content-Type: application/json" `
  --data '{"session_id":"career-stream-001","user_id":"anonymous-user-001","message":"给我下一步建议","stream":true}'
```

前端只处理 `session/delta/done/error`。不要读取百宝箱原始 `thinking/meta`；适配层已经主动
丢弃。SSE 建立后发生错误时 HTTP 可能仍为 200，应以最后的 `done` 或 `error` 事件为准。

## 6. 安全与部署限制

- `/api/tbox/chat` 不接受任何 token/api_key 字段；额外字段返回 422。
- `user_id` 是会话归属字段，不是认证。当前项目尚无正式登录系统，公网部署前必须由可信
  认证层或 API Gateway 提供用户身份，不能直接信任浏览器任意填写的 user_id。
- 对话正文会发送给百宝箱智能体，但不会写入 CareerPulse 平台调用账本。不要在消息中主动
  提交不必要的身份证号、手机号等敏感信息。
- CareerPulse 明文 user_id 不发送给百宝箱；上游只收到以 `cp_` 开头的 HMAC 匿名标识。
- 同一进程内，同 session 的消息会串行。多 worker 部署在引入分布式 session 锁前应使用
  sticky routing，且前端不要并发发送同一 session 的首条消息。
- 适配器不会自动重试聊天，防止重复执行非幂等消息；只根据 `retryable` 由调用方决定是否
  提示用户重试。

## 7. 本地自动验证

```powershell
python -m unittest tests.test_tbox_chat -v
```

测试覆盖同步 envelope/直接响应、会话续接、流式事件、thinking 隔离、超时、5xx、损坏协议、
配置缺失、session 用户冲突、日志隐私和 OpenAPI。测试不会访问真实百宝箱 API。
