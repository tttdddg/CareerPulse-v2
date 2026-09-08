# ADR-004：CareerPulse 到百宝箱正式智能体的服务端对话网关

- 状态：Accepted
- 日期：2026-09-03
- 范围：阶段5后半段 / 阶段6前置的后端对话适配

## 背景

项目已经具备“百宝箱调用 CareerPulse”的 MCP/HTTP 工具入口，但 Vue 用户消息进入
百宝箱正式智能体是相反方向，不能复用工具侧 Bearer token 或旧
`/api/tbox/mock-career-analysis`。百宝箱公开资料确认正式 Chat API 使用
`appId/query/userId`，以 `conversationId` 延续会话，并提供同步 JSON 与 SSE 两种响应。

## 决策

1. 新增 `POST /api/tbox/chat` 作为唯一浏览器对话入口，后端持有
   `TBOX_CHAT_AUTHORIZATION`、`TBOX_APP_ID` 和独立 `TBOX_USER_ID_SECRET`；响应、OpenAPI
   和日志均不得出现凭据，本地 user_id 经 HMAC 匿名化后才作为上游 userId。
2. 出站智能体凭据与入站工具凭据 `A02_TBOX_API_TOKEN` 分离，两种方向不共享鉴权语义。
3. 使用 `CareerState.platform_session_id` 持久化百宝箱 `conversationId`，无需新增数据库字段；
   同一进程内对同一 CareerPulse session 串行调用，避免首轮并发创建多条会话。
4. 普通响应转换为 CareerPulse 固定 envelope；流式响应只输出
   `session/delta/done/error` SSE，不透传百宝箱 `thinking/meta` 或原始错误体。
5. 复用 `platform_tool_calls` 记录每次出站调用。账本只保存请求指纹、哈希 user_id、状态、
   耗时和响应模式，不保存用户消息、智能体回复或 Token。
6. 聊天调用不自动重试。超时、限流和 5xx 返回安全且可判断的 retryable 错误，避免非幂等
   消息被重复执行。
7. 本轮不接 Vue、不增加认证系统、不传文件、不启用搜索开关，也不修改 MCP、Agent、
   Service 或确定性评分算法。

## 影响

- 主 FastAPI 应用可以在服务端配置后代理百宝箱正式智能体的普通和流式对话。
- 没有配置正式凭据时 fail closed 为 503，不回退到旧 Mock 或伪造回复。
- `user_id` 是会话归属标识，不等同于登录鉴权；在正式公网开放此入口前，仍需由现有/后续
  用户认证层或可信网关校验登录身份。
- 当前同 session 串行锁是进程内锁；多 worker 部署应使用 sticky routing，或后续增加
  分布式 session 锁后再允许同一 session 并发首轮消息。
