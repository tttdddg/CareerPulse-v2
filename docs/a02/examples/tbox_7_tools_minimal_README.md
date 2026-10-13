# 百宝箱 7 工具最小验收数据

数据文件：`tbox_7_tools_minimal.json`。依据当前 `backend/app/mcp/server.py` 的公开扁平入口生成，不适用于 `/api/platform/v1/tools` 的 stage3 HTTP 请求。全部学生证据均为虚构，无姓名、联系方式或凭据。

## 执行前提

1. 在百宝箱确认注册的工具名称与 JSON 中一致。每次仅粘贴该条 `arguments`，不要粘贴 `id/tool/expect` 等测试包字段。
2. S02 的 `job_id` 必须替换为部署库里真实存在且具有有效类型画像的正整数；`job_title` 和 S01 的 `target_job` 应对应这个岗位。示例岗位名不是对部署库数据的保证。不要使用 Demo ID 冒充实际数据库 ID。
3. S01 的三个能力标签和一条项目证据是为了满足画像落库最低条件（至少三个能力标签，且学历、专业、目标岗位齐全）。若实际返回仍为 session 来源，画像构建成功不能计为 PostgreSQL 写入验收通过。
4. 使用独立测试会话。重复整轮测试时统一更换所有成功用例的 `session_id`，以及所有 `trace_id`；同一轮 `user_id` 保持一致。认证密钥仅在平台密钥配置中填写。

## 最小成功链：7 个工具，8 次调用

依次执行 S01～S08；前一步失败时先排查，不能将后续级联失败记为独立工具故障。S05 后把返回的 `data.training_task.training_id` 原样写入 S06。S06 是同一个训练工具的评分分支，不能省略，否则只测试了题目生成。

| 用例 | 通过标准 |
|---|---|
| S01 画像 | `success=true`；有 `data.student_profile` 和 Agent 运行标识。数据库验收另外要求 `data.student_id` 为正整数、`data.data_source=postgresql`、`data.demo_mode=false`，由授权查询核实对应学生行。 |
| S02 岗位 | `success=true`；有 `data.job_profile`、`data.trend_result`；`data.job_id` 等于实际输入；数据库验收要求 `data.data_source=postgresql`、`data.demo_mode=false`。当前库缺少趋势时间序列，不能把空趋势结果判为失败或要求模型补趋势。 |
| S03 匹配 | `success=true`；有 `data.match_result`；分数、缺口由后端确定性服务返回，不在测试输入中预设或覆盖。 |
| S04 路径 | `success=true`；有 `data.career_roadmap`；核实运行日志的图谱来源为 PostgreSQL。无有效图谱时如实判数据库前置条件未满足；不能切换 Demo 后宣称生产链通过。 |
| S05 训练生成 | `success=true`；`data.mode=generate`；题目及非空 `training_id` 返回。 |
| S06 训练评分 | `success=true`；`data.mode=score`；有 `data.training_score`；ID 对应 S05，同一会话内完成。答案只是测试输入，不保证固定分数。 |
| S07 资源 | `success=true`；有 `data.resource_result` 的学习资源、岗位资源、证书建议、质量标记字段；允许如实返回空集合，不能将静态资源视为数据库或实时招聘验证。 |
| S08 反馈 | `success=true`；`data.feedback_result.feedback_saved=true`；有成长快照。当前 FeedbackService 使用进程内字典，这不证明反馈已持久化到业务数据库或重启后可恢复。 |

所有业务成功结果同时检查：`error_code=null`、`missing_fields=[]`、`retryable=false`，返回的会话和 trace 与请求一致。正常进入 Agent 的工具应能关联 Agent/Tool 日志；资源是 Service 调用，应有 Tool 日志。日志不能包含完整简历、证据、反馈正文或密钥。

## 最小失败链：每个工具 1 次

执行 F01～F07。F03/F04/F06 的会话必须从未创建；若已有同名会话，更换新名称。验证错误可能由 MCP `isError=true` 和内容文本呈现，不一定具有业务层 `success/error_code`，也不能套用 stage3 HTTP 的 `code=-2`。

F01/F02/F05/F07 是输入校验失败；应无相应业务写入、计算或状态推进。F03/F04/F06 是业务失败，应返回 `success=false`、`error_code=SESSION_NOT_FOUND`、`data=null`，并核对安全的失败日志。入口校验发生在业务服务之前，不能强求每个 Schema 拒绝都产生 AgentRunLog。

这 15 次调用是最小冒烟集，不能替代完整验收。建议额外检查：S01 完全相同参数及 trace 重放不增加学生行；同 trace 改证据应拒绝；换 user_id 访问成功会话应拒绝；错误 Bearer 应拒绝；实际中断模型/数据库测试 fallback、超时和生产来源策略。故障注入只在独立测试环境执行。

## 记录与限制

逐条记录用例 ID、时间、trace、成功/错误类型、来源、fallback、耗时和脱敏日志关联标识。不把 HTTP 200 单独当作业务成功，不预填“已通过”。本数据包仅依据本地仓库契约，未连接用户的远程 HTTPS、百宝箱或部署数据库；线上版本不同需以实际 `tools/list` schema 为准。
