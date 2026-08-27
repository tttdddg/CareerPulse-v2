# ADR-003：阶段4三个工具注册到现有 MCP Server

- 状态：Accepted
- 日期：2026-08-27
- 范围：阶段4 Training / Resource / Feedback 的仓库侧 MCP 协议接入

## 背景

阶段3已经提供唯一的标准远程 MCP Server、Streamable HTTP 传输、Bearer 鉴权、
严格参数 Schema、session 状态、trace 幂等账本和四个已注册工具。阶段4已经在
`CareerMCPToolService` 中实现并测试三个真实 handler，但尚未进入 MCP `tools/list`。

D2 工具目录中的阶段4规划参数允许客户端传 `student_id/job_id/ability_gaps/target_job`，
与当前已验收的 session-state 内部契约不一致。继续使用这些旧参数会允许调用方重复或覆盖
后端业务上下文。

## 决策

1. 复用现有 `create_career_mcp_server()`，不创建第二套 Server；在同一工厂注册
   `generate_and_score_training`、`recommend_learning_and_job_resources`、
   `save_growth_feedback`，使工具总数为 7。
2. MCP 适配函数只把协议参数构造成现有严格 Request Schema，再调用同名
   `CareerMCPToolService` handler；Training/Resource/Feedback 业务逻辑保持在既有
   Agent/Service 中。
3. Training 保持一个合并工具。生成模式要求 `training_type`；评分模式要求
   `training_id + user_answer`。数值分数和 ability updates 只由 TrainingService 产生。
4. Resource 工具只接收 `session_id/user_id/trace_id`；ability gaps 和 target job 从
   CareerState 读取，调用方不能覆盖。
5. Feedback 工具只接收用户真实评分和 comments；match/training/growth 上下文由
   CareerState 投影，rating 严格为整数 1–5。
6. 三个工具复用现有统一结果 envelope、状态、identity、trace 幂等、日志隐私、超时和
   safe-failure 规则。Server 能力版本更新为 `stage4-mcp-v1`，HTTP `stage3-tool-v1`
   契约保持不变。

## 影响

- MCP `tools/list` 返回 7 个真实工具，阶段3四工具行为和现有鉴权不变。
- 阶段4公开输入与已验收的内部 Schema 一致，不再暴露可覆盖系统计算上下文的旧规划字段。
- 本 ADR 只确认代码仓库侧 MCP 能力；百宝箱配置、公网 HTTPS、Cloudflare、固定 Token
  和现场联调仍需后续人工完成，不能据此宣称平台已经接入或发布。
