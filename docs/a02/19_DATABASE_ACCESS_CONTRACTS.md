# CareerPulse A02 数据库接入契约

> 契约版本：D7-01 v1.0  
> 冻结日期：2026-09-19  
> 状态：文档冻结；业务数据 Repository 尚未实现，不代表数据库已接入生产链路  
> 适用范围：PostgreSQL 业务四表、`StateRepository` 会话持久化、显式 Demo Mode JSON

## 1. 目的与强制边界

本契约冻结 PostgreSQL 业务数据、`CareerState` 快照和 Demo JSON 的所有权、调用方向、字段映射、故障行为与工具暴露边界。后续实现必须满足本文件，不能以 Agent 自由推理替代确定性数据访问或计算。

以下词语具有规范含义：

- **必须**：实现和调用方均不可省略。
- **禁止**：任何环境都不得执行。
- **当前未实现**：这里只冻结目标契约，不声称代码已经具备该能力。

强制原则：

1. PostgreSQL `careerpulse_micro` 的业务四表是业务事实真源。
2. `StateRepository` 只保存会话快照、Agent 日志和平台工具调用账本；其物理后端可以是 SQLite，也可以是迁移后的 PostgreSQL，但逻辑角色不变。
3. `students_demo.json`、`jobs_demo.json` 和 `career_graph.json` 只允许在显式 Demo Mode 使用，不得在生产模式静默兜底。
4. Agent 不得直连数据库。读写必须经过固定参数、固定返回 Schema 的内部 Repository/Tool，再由 Orchestrator 注入 `CareerState`。
5. LLM 不得生成或修改 `student_id`、`job_id`、匹配分、能力缺口、路径分、图边成本、成长价值、风险等级和幂等结果。
6. 数据库结果必须先经过 Pydantic/JSON Schema 校验，才可写入 `CareerState`。
7. 本任务不修改公共 Schema、业务代码、数据库字段或迁移。

## 2. 当前实现事实与目标契约的区分

| 能力 | 当前事实 | 本契约要求 |
|---|---|---|
| 业务四表 | 设计与增量迁移存在；当前 Agent/Tool 未建立专用业务 Repository | 实现专用只读/写入 Repository，Agent 不直接执行 SQL |
| 会话持久化 | `StateRepository` 已保存 `career_state`、`agent_logs`、`platform_tool_calls` | 继续仅作快照、日志、调用账本，不升级为业务真源 |
| 学生画像运行 Schema | `ProfileAgent/ProfileService` 实际输出 `schemas.career_profile_schema.StudentProfile` | 数据库适配器必须完成第 7 节的显式转换 |
| 学生数据库结构 | `student_profile` 与扁平 Demo JSON 结构一致 | 不得直接塞入当前 Unified `StudentProfile`；必须转换 |
| 岗位画像 | `JobAgent` 当前可从输入/规则/JSON fallback 生成 | PostgreSQL 成为生产读源；生产环境禁用 JSON fallback |
| 职业图谱 | `CareerGraphRepository` 当前默认读取 JSON | 生产环境改由数据库节点和边组装；JSON 仅限 Demo Mode |
| Feedback | `FeedbackService` 当前为进程内字典，不是持久化业务数据 | 不得宣称已持久化；未有正式业务表前只保留会话结果 |
| 来源标识 | 现有公共结果并未统一携带 `data_source` | 数据库接入不得上线，直到调用边界可返回第 5 节来源元数据 |

## 3. 数据所有权与优先级

### 3.1 所有权矩阵

| 数据 | 唯一权威来源 | 可缓存位置 | JSON 用途 | 禁止行为 |
|---|---|---|---|---|
| 学生画像业务记录 | PostgreSQL `student_profile` | `CareerState.student_profile` 会话快照 | 显式 Demo 学生 | 用旧快照或 Demo 记录反向覆盖 PostgreSQL |
| 具体岗位实例 | PostgreSQL `job_clean` | `target_job_input`/`job_profile` 会话投影 | 显式 Demo 岗位 | 用 LLM/JSON 更新岗位库 |
| 岗位类型画像 | PostgreSQL `job_type_profile` | `CareerState.job_profile` 会话投影 | 显式 Demo 岗位画像 | 用 Agent 输出回写聚合字段 |
| 职业图谱边 | PostgreSQL `job_type_graph_edge` | PathService 调用期内存、`career_roadmap` 结果快照 | 显式 Demo 图谱 | 从 JSON 同步、补边或覆盖数据库边 |
| 会话状态 | `StateRepository.career_state` | Orchestrator 进程内副本 | 不适用 | 把快照当作业务主表 |
| Agent 日志 | `StateRepository.agent_logs` | 无 | Demo 也必须记录 | 记录姓名、完整简历、邮箱、电话、证件号 |
| 工具幂等账本 | `StateRepository.platform_tool_calls` | 无 | Demo 也必须记录 | 复用同一键执行不同请求 |
| 能力标签词表、算法配置 | 版本化代码/配置 | 进程缓存 | Demo 与生产共用校验词表 | 把业务样例 JSON 当成生产事实 |

### 3.2 读取优先级

生产模式固定为：

```text
PostgreSQL 业务表 -> Pydantic 映射与语义校验 -> CareerState 快照 -> Agent/Service
```

显式 Demo Mode 固定为：

```text
Demo JSON -> Pydantic 校验 -> CareerState 快照 -> Agent/Service
```

禁止以下优先级：

- PostgreSQL 失败后在生产模式读取 JSON。
- `CareerState` 有旧值时跳过 PostgreSQL 的版本/更新时间检查，并把旧值当作最新业务数据。
- 在一个学生画像、一个岗位画像或一张职业图谱中混合 PostgreSQL 与 Demo JSON 字段。
- 将 Demo ID（当前为 `90001+`/`91001+`）写入生产业务表。

### 3.3 禁止双向覆盖规则

1. PostgreSQL 到 `CareerState` 是只读投影；刷新只替换本会话投影，不改变业务记录。
2. `CareerState` 到 PostgreSQL 只允许通过显式的学生画像创建/更新命令，禁止 Orchestrator 在 `persist()` 时顺带回写业务表。
3. JSON 到 PostgreSQL、PostgreSQL 到 JSON 均禁止自动同步。
4. StateRepository 恢复旧会话时，不得覆盖 `student_profile.updated_at` 更新后的业务记录。
5. `job_profile`、`match_result`、`career_roadmap` 和 `feedback_result` 的快照不得反向写入四张业务表。

## 4. 数据源、Demo 与故障行为

### 4.1 统一来源元数据

每次业务数据读取结果必须在 Tool/Repository 边界携带：

```json
{
  "data_source": "postgresql | demo_json",
  "fallback_used": false,
  "demo_mode": false
}
```

语义固定如下：

| 场景 | `data_source` | `fallback_used` | `demo_mode` |
|---|---|---:|---:|
| 生产正常读取 | `postgresql` | `false` | `false` |
| 显式 Demo，直接使用样例 | `demo_json` | `false` | `true` |
| 显式 Demo，先尝试数据库后因故障回退 | `demo_json` | `true` | `true` |

`fallback_used` 只表示本次调用是否发生来源降级，不表示 LLM 文案 fallback。Agent 日志中的同名字段仍按现有 Agent 执行语义记录；两者必须分别落在业务读取 ToolCall 和 AgentRunLog 中，不能相互覆盖。

### 4.2 Demo Mode 判定

只有服务端可信配置 `A02_DEMO_MODE=true` 可以授权读取 Demo JSON。请求头 `X-Demo-Mode: true` 只能在部署配置明确允许的非生产环境生效；客户端字段不能单独打开 Demo Mode。

**生产模式禁止静默回退 JSON。**

生产环境中 PostgreSQL 超时、断连、表不存在、Schema 校验失败或记录不存在时：

- 返回明确错误，`fallback_used=false`；
- 不读取 JSON；
- 不复用其他用户或其他会话的快照；
- 保留安全的失败日志，禁止记录 SQL 参数中的私人文本。

### 4.3 错误分类

| 条件 | 行为 | 是否可重试 |
|---|---|---:|
| 数据库连接/超时 | 失败关闭；生产禁用 JSON | 是，复用原幂等键 |
| 表或迁移缺失 | `DATABASE_SCHEMA_NOT_READY` | 否，先部署迁移 |
| 记录不存在 | `BUSINESS_RECORD_NOT_FOUND` | 否，除非先创建记录 |
| 数据行未通过 Pydantic/语义校验 | `BUSINESS_RECORD_SCHEMA_INVALID` | 否，修复数据 |
| StateRepository 不可用 | 写操作必须在业务写入前失败关闭 | 是，复用原幂等键 |
| 显式 Demo 文件损坏 | `DEMO_DATA_INVALID`，不得伪造结果 | 否 |

## 5. 六个 Agent 的数据库调用矩阵

所有“读/写”均指通过内部 Tool/Repository 间接执行；六个 Agent 的直接 SQL 权限全部为零。

| Agent | 可读取的业务数据 | 可写入业务数据 | 可写入 StateRepository | 禁止操作 |
|---|---|---|---|---|
| `ProfileAgent` | 经授权的单个 `student_profile` 历史记录；首次创建时无记录 | 仅通过显式画像创建/更新内部命令；分数必须由 `ProfileService` 确定性计算 | `student_profile` 会话投影、Agent/Tool 日志 | 按姓名搜索；读取其他学生；让 LLM 指定 `student_id`/分数；自动覆盖较新数据库画像 |
| `JobAgent` | `job_clean` 单条实例和对应 `job_type_profile`；无趋势表时只返回保守趋势 | 无 | `target_job_input`、`job_profile`、`trend_result` 和日志 | 修改岗位/画像；读任意表；把公司名送入非必要日志；凭 LLM 补数据库不存在的数值事实 |
| `MatchAgent` | 正常只读 `CareerState.student_profile/job_profile`；必要时由前置内部 Tool 刷新对应记录 | 无 | `match_result` 和日志 | SQL 计算匹配；从 JSON 补字段；LLM 生成分数/缺口/权重 |
| `PathAgent` | 数据库组装的 `job_type_profile` 节点和 `job_type_graph_edge` 边，以及 State 中的确定性匹配结果 | 无 | `path_plan`、`learning_plan`、`career_roadmap` 和日志 | 修改节点/边；LLM 生成成本、成长值、风险或路径分；生产读取 JSON 图谱 |
| `TrainingAgent` | 只读 State 中的学生、岗位、缺口和训练上下文；当前四张业务表无训练记录 | 无 | `training_plan`、`resource_result` 和日志 | 更新 `student_profile.abilities`；把训练评分当作数据库画像等级；写四张业务表 |
| `FeedbackAgent` | 只读 State 中的缺口、能力、匹配分和训练结果 | 无（当前没有正式反馈/成长业务表） | `feedback_result` 和日志 | 宣称进程内字典已持久化；修改学生画像、岗位画像、图谱边；把评论写入日志 |

额外约束：

- `CareerOrchestrator` 控制调用顺序和持久化时点。
- Service 负责确定性转换、评分和语义校验。
- Tool 负责固定输入输出、授权、来源标识、超时、幂等和安全日志。
- Repository 只负责参数化 SQL、事务、行锁和数据库异常转换。

## 6. 学生画像字段映射

### 6.1 PostgreSQL 行到当前 Unified `StudentProfile`

当前运行链使用 `backend/app/schemas/career_profile_schema.py::StudentProfile`，不是 `schemas/profile_schema.py::StudentProfile`。适配器必须显式映射，禁止把数据库行原样传入。

| PostgreSQL `student_profile` | 当前 Pydantic/CareerState | 转换规则 |
|---|---|---|
| `student_id` | 不进入 `CareerState.student_profile` | 作为受保护的业务引用由 Tool 结果单独返回；不得塞入 `extra=forbid` 模型 |
| 调用方认证身份 | `user_id` | 从已认证请求取得；数据库当前无 `user_id`，禁止由 `student_id` 猜测 |
| `name` | `basic_info.name` | 默认投影为 `null`，避免身份信息进入 Agent 状态；只有明确展示场景可返回匿名展示名 |
| `basic_info.education_level` | `basic_info.education_level` | 原值；枚举校验 |
| `basic_info.major` | `basic_info.major` | 原值 |
| `basic_info.graduation_year` | `basic_info.graduation_year` | 原值或 `null` |
| 无对应列 | `basic_info.city` | `null`；不得从目标岗位城市推断 |
| `basic_info.target_job` | `basic_info.target_job` | 原值 |
| `basic_info.target_industry` | `basic_info.target_industry` | 原值或 `null` |
| `basic_info.years_of_experience` | `basic_info.years_of_experience` | 原值或 `null` |
| `abilities[]` | `ability_dimensions[]` | 按 6.2 确定性聚合 |
| `abilities[].tag` 集合 | `ability_tags` | 标准化、去重、按稳定顺序输出；未知/停用标签使整行校验失败 |
| `completeness` | `profile_completeness` | 数值原样转换为 `float`，不得重算后静默覆盖 |
| `competitiveness_score` | `career_competitiveness_score` | 数值原样转换为 `float`；它是确定性 Service 缓存 |
| `missing_fields` | `missing_fields` | 字符串数组原样复制并校验非空项 |
| `missing_fields` | `follow_up_questions` | 用版本化固定字典生成；无映射项不生成问题 |
| 固定确定性模板 | `summary` | 只总结维度数量、标签数量和缺失项数量，不包含姓名或完整证据 |
| `created_at` | `created_at` | ISO-8601/`datetime` 直接映射 |
| `updated_at` | `updated_at` | ISO-8601/`datetime` 直接映射，且不得早于 `created_at` |

### 6.2 `abilities[]` 到 `ability_dimensions[]`

1. 每个 `tag` 必须先通过 `ability_tags.json` 的有效标签校验和 `AbilityTagNormalizer` 归一化。
2. 使用与 `ProfileService` 相同的版本化 `tag -> AbilityDimension` 映射；无维度映射的标签不得丢弃，必须使接入校验失败并进入修复队列。
3. 同一维度内：
   - `tags` 为该维度的唯一标签稳定排序；
   - 以 `(level, confidence, tag)` 最大的同一条能力作为该维度的 `level` 和 `confidence`，禁止把不同能力的最大等级和最大置信度拼接；
   - `evidence` 为该维度能力证据去重后的列表，每项继续执行隐私检查；
   - `evidence_source="history"`。
4. 同一标签若因“项目实践”投影出现在多个维度，写回数据库时只保留版本化映射中的规范维度，避免 `abilities` 重复标签。
5. 适配器不得根据证据文本重新猜测已持久化的等级或置信度。

### 6.3 当前 Unified `StudentProfile` 写入 PostgreSQL

| Unified 字段 | PostgreSQL 列 | 写入规则 |
|---|---|---|
| 外部匿名展示名 | `name` | 当前 Unified 模型通常不保留姓名；创建命令必须单独提供合规匿名展示名，不能从简历解析 |
| `basic_info` | `basic_info` | 仅写数据库约定的 6 个键；丢弃 `name/city`，缺失必需键则拒绝写入 |
| `ability_dimensions` | `abilities` | 按规范维度扁平化为唯一 `tag/level/confidence/evidence`；同标签冲突则拒绝 |
| `career_competitiveness_score` | `competitiveness_score` | 仅接受 `ProfileService` 同版本计算结果 |
| `profile_completeness` | `completeness` | 仅接受 `ProfileService` 同版本计算结果 |
| `missing_fields` | `missing_fields` | 直接映射 |
| 数据库生成值 | `student_id` | `INSERT ... RETURNING student_id`，不得由 LLM/客户端指定 |
| 数据库时间 | `created_at/updated_at` | 由数据库生成/更新；客户端时间不覆盖 |

## 7. 岗位画像字段映射

### 7.1 `job_clean` 到 `TargetJobInput`

| `job_clean` | `schemas.mcp_tool_schema.TargetJobInput` / `CareerState.target_job_input` | 规则 |
|---|---|---|
| `job_id` | `job_id` | 原值 |
| `job_title` | `job_title` | 原值 |
| `industry` | `industry` | 原值或 `null` |
| `city` | `city` | 原值或 `null` |
| `job_description` | `job_description` | 清洗后的 JD；不得写入日志 |
| `normalized_job_title` | Repository 查询键 | 用于连接 `job_type_profile.type_key`，不作为未声明字段注入请求 |
| `company_name` | 不进入 Agent 输入 | 只允许展示层按授权读取；日志和 Prompt 默认排除 |
| `salary_range` | 后续 `JobProfile.salary_range` | 具体岗位模式优先使用该值 |
| `updated_at` | 缓存新鲜度 | 不进入公共模型 |

### 7.2 `job_clean + job_type_profile` 到 `JobProfile`

| 目标 `schemas.job_schema.JobProfile` | 来源 | 规则 |
|---|---|---|
| `job_id` | `job_clean.job_id` 或 `job_type_profile.exemplar_job_id` | 查询具体岗位时用具体 ID；类型查询时可用代表岗位 ID |
| `title` | `job_clean.job_title` 或 `job_type_profile.type_key` | 具体实例保留原始标题；类型查询使用类型名 |
| `normalized_title` | `job_type_profile.type_key` | 必须等于标准化类型名 |
| `industry` | 类型画像 `industry`，否则具体岗位 `industry` | 两者都空则数据无效，禁止写“待确认”冒充数据库事实 |
| `required_abilities` | `job_type_profile.skill_requirements` | `tag/required_level/weight/importance` 直接映射并校验唯一、权重和为 1；`evidence` 仅可取 JD 中可定位原句，否则 `null` |
| `soft_skills` | `skill_requirements` + 版本化能力标签类别 | 只投影 `soft_skill` 类标签；不能把全部 `nice_to_have` 当软技能 |
| `salary_range` | 具体岗位 `salary_range`，否则类型 `salary_desc_p50` | 保持来源文本，不由 LLM换算 |
| `job_description` | 类型 `profile_summary`，否则具体岗位 `job_description` | 类型画像优先使用摘要；两者均空则校验失败 |

### 7.3 `TrendResult`

四张业务表没有岗位趋势时间序列表。因此数据库记录只能提供岗位画像，不足以证明趋势：

- `job_title/industry` 取已校验岗位画像；
- `hot_skills/rising_skills/declining_skills/development_opportunities/development_risks` 为空；
- `ai_risk_assessment="medium"` 仅作为“未知/待验证”的保守枚举兼容值，文案必须明确资料未提供；
- `data_source` 写明 `PostgreSQL job_clean + job_type_profile；未提供可验证趋势数据`；
- 禁止根据 `sample_size` 或当前 JD 自称市场趋势。

## 8. 职业图谱字段映射

### 8.1 `job_type_profile` 到 `CareerGraphNode`

| 数据库字段 | `models.CareerGraphNode` | 规则 |
|---|---|---|
| `type_key` | `node_key`、`job_title` | 两者都使用中文类型 key |
| `industry` | `industry` | 原值或 `null` |
| `profile_summary` | `description` | 非空；缺失则整节点校验失败 |
| `level_range` | `level_range` | `entry/junior/mid/senior/lead` |
| `skill_requirements` | `required_skills` | 四字段直接映射，标签唯一且权重和为 1 |
| 无列 | `typical_duration` | 使用 `path_config.DEFAULT_DURATION_MONTHS`：12/18/24/30/36，并记录 `node_duration_default:*` |
| 无列 | `risk_level` | 设为 `null`，由 Repository 确定性落到 `medium` 并记录 `node_risk_default:*` |
| 无列 | `cities` | `null`，禁止从岗位实例城市集合推断为限制条件 |
| `sample_size` | 数据置信度输入 | 不进入节点公共字段；可生成质量标记，不能直接变成路径分 |

### 8.2 `job_type_graph_edge` 到 `CareerGraphEdge`

| 数据库字段 | `models.CareerGraphEdge` | 规则 |
|---|---|---|
| `source_type_key` | `source_key` | 必须能连接已加载节点 |
| `target_type_key` | `target_key` | 必须能连接已加载节点 |
| `relation_type` | `relation_type` | 只接受 `vertical/lateral` |
| `reason` | `reason` | 原值；空值视为数据无效 |
| `transfer_cost` | `transfer_cost` | 原值，不允许 LLM 修改 |
| `growth_value` | `growth_value` | 原值，不允许 LLM 修改 |
| 源节点联接 | `source_industry` | 从源 `job_type_profile.industry` 投影 |
| 目标节点联接 | `target_industry` | 从目标 `job_type_profile.industry` 投影 |
| `transition_requirements` | `transition_requirements` | 原数组，标签必须有效且唯一 |
| `risk_level` | `risk_level` | 原枚举 |
| `id/updated_at` | 不进入图模型 | 仅作审计和缓存新鲜度 |

整图组装后必须执行 `CareerGraph`/`CareerGraphRepository` 的节点唯一、边唯一、无自环、无未知节点、无孤立节点、纵向严格升层级和标签校验。任何一项失败时，生产模式整图读取失败，不得仅删除坏边继续计算。

## 9. 首次写入、重复请求与跨库恢复

### 9.1 首次学生画像写入协议

1. 接收固定请求：`session_id`、认证后的 `user_id`、`idempotency_key`、画像证据和合规匿名展示名。
2. 在 StateRepository 创建调用账本，唯一键为 `tool_name + idempotency_key`，保存规范化请求指纹；不得保存完整简历或明文 `user_id`。
3. 调用 `ProfileService` 生成 Unified 画像并完成确定性评分。
4. 按第 6.3 节转换和校验数据库写入 DTO。
5. 在 PostgreSQL 单事务内持久化“业务幂等回执”和 `student_profile`，执行 `INSERT ... RETURNING student_id`。
6. 提交成功后，将返回的 `student_id` 与数据库 `updated_at` 写入调用结果元数据，再保存 `CareerState` 投影。
7. 返回同一个 `student_id`、`data_source="postgresql"`、`fallback_used=false`。

`student_id` 必须由数据库回传。不得使用会话 ID 哈希、数组下标、Demo ID 或 LLM 结果作为生产 `student_id`。

### 9.2 幂等语义

| 请求情况 | 固定行为 |
|---|---|
| 相同工具 + 相同幂等键 + 相同指纹 | 不再插入；返回第一次成功的同一 `student_id` 和结果 |
| 相同工具 + 相同幂等键 + 不同指纹 | `IDEMPOTENCY_KEY_CONFLICT`，不执行写入 |
| 前次状态为运行中且租约有效 | 返回处理中，不并发创建第二行 |
| 前次状态不确定/超时 | 查询 PostgreSQL 业务幂等回执；命中则完成重放，未命中才安全重试 |
| 调用方换新幂等键重发相同内容 | 视为新命令；上层必须明确是创建还是更新，禁止自动内容去重猜测身份 |

当前 `student_profile` 没有 `user_id` 或幂等键列，`platform_tool_calls` 又可能位于 SQLite，因此**仅靠现有表无法保证崩溃后的 exactly-once 创建**。正式开放首次写入前，必须由技术负责人批准并通过迁移提供与业务插入同事务的耐久幂等回执/身份绑定。未完成前，生产写入口必须保持关闭。

比赛环境例外（2026-09-21）：经项目负责人明确接受受控演示风险后，MCP 组合根启用画像写入，
并把调用方 `user_id` 当作可信逻辑身份。读取只允许当前 CareerState 中完全一致的
`session_id + user_id + student_profile_id`。现有 trace 账本继续处理普通重试，但该例外不宣称
跨 PostgreSQL/StateRepository 崩溃窗口的严格 exactly-once，也不等同于生产级身份认证。

### 9.3 跨 SQLite/PostgreSQL 失败恢复

| 故障时点 | 可观察状态 | 恢复策略 |
|---|---|---|
| StateRepository 记账前失败 | PostgreSQL 未写 | 直接失败；复用原键重试 |
| 画像计算/校验失败 | PostgreSQL 未写；账本失败 | 修正输入后使用新键；相同键重放同一失败 |
| PostgreSQL 事务回滚 | 无学生行/无业务回执 | 将账本标记失败；复用原键可按错误可重试性处理 |
| PostgreSQL 已提交，State 快照失败 | 学生行和业务回执已存在，账本可能运行中 | 返回“不确定/503”；复用原键时由业务回执恢复同一 `student_id`，禁止再次插入 |
| State 快照成功，调用终态写失败 | 业务行与快照存在 | 通过业务回执和请求指纹修复账本终态，返回同一结果 |
| 进程在任意阶段崩溃 | 状态未知 | 恢复任务只根据幂等回执和账本判定；不得按姓名/画像内容模糊匹配 |

不能对 SQLite 与 PostgreSQL 做分布式事务假设；采用“先记账、业务库同事务回执、可重放协调”的 Saga。补偿只修复账本/快照，不删除已经成功创建的学生画像。

## 10. Internal Tool 与 MCP 暴露边界

### 10.1 内部数据库能力（逻辑契约，当前未注册）

| 能力 | 类型 | 允许调用方 | 关键限制 |
|---|---|---|---|
| 按授权引用读取学生画像 | 只读 | Orchestrator/Profile 入口 | 必须校验 `user_id -> student_id` 绑定；禁止姓名搜索 |
| 创建学生画像并返回 ID | 写 | 受信任的应用服务 | 必须执行第 9 节幂等协议 |
| 按 ID/版本更新学生画像 | 写 | 受信任的应用服务 | 使用 `student_id + expected_updated_at` 乐观并发；冲突不覆盖 |
| 按固定条件读取具体岗位 | 只读 | Job 入口 | 参数化过滤；固定字段投影 |
| 按 `type_key` 读取岗位类型画像 | 只读 | Job/Path 入口 | 不接受表名、列名或表达式 |
| 加载完整职业图谱 | 只读 | Path 入口 | 单一一致性快照中读取节点和边，再做整图校验 |
| 数据库健康/迁移检查 | 只读 | 启动检查、运维 | 只返回状态和版本，不返回连接串或数据行 |

### 10.2 允许通过现有 MCP 间接使用的只读业务能力

| 现有 MCP Tool | 可间接读取 | 是否暴露数据库原语 | 当前状态 |
|---|---|---:|---|
| `build_student_profile` | 经授权的历史学生画像可作为合并输入 | 否 | 完整画像在比赛模式写 PostgreSQL；部分画像保持 session 快照 |
| `analyze_target_job` | 固定岗位实例/类型画像 | 否 | `job_id/type_key` 进入确定性 PostgreSQL 读取分支 |
| `analyze_job_match` | 已进入 State 的学生与岗位投影 | 否 | 可按业务引用水合后调用确定性 MatchService |
| `generate_career_path` | 已校验的数据库职业图谱 | 否 | 生产 Provider 读取 PostgreSQL 后调用确定性 PathService |
| `generate_and_score_training` | State 上下文 | 否 | 四张业务表无训练数据 |
| `recommend_learning_and_job_resources` | State 上下文 | 否 | 无数据库原语 |
| `save_growth_feedback` | State 上下文 | 否 | 当前无正式反馈业务表，不得宣称数据库写入 |

新的“查学生表”“执行查询”“列出表”等 MCP Tool 全部禁止。若未来增加岗位搜索，只能由技术负责人冻结独立公共 Schema，并满足：

- 过滤字段白名单；
- 排序使用枚举映射到服务端固定 SQL，不接受原始排序表达式；
- 分页上限固定；
- 返回固定 DTO，不返回整行或内部列；
- 成功、无结果、越权、超时和数据库失败测试齐全。

### 10.3 永久禁止的输入

**禁止暴露任意 SQL、表名和排序表达式。**

任何外部 API/MCP/Agent Tool 都不得接受：

- SQL 字符串、SQL 片段或数据库函数；
- 表名、Schema 名、列名；
- `ORDER BY`、排序表达式、任意过滤表达式；
- 连接串、数据库用户名、口令；
- 任意批量更新/删除条件。

## 11. 日志、隐私与审计

每次业务 Repository 调用必须产生一条 ToolCallLog 摘要，至少记录：固定工具名、服务名、来源、结果状态、时长、返回记录数或业务引用哈希、`fallback_used` 和安全错误类型。

禁止记录：

- 完整简历、完整 JD、完整画像 JSON；
- 姓名、邮箱、电话、证件号；
- 明文 `user_id`、数据库口令、连接串；
- SQL 参数中的原始证据或反馈评论。

允许记录示例：`student_ref_hash=...; source=postgresql; fields=7; status=success`。

## 12. 上线门禁

数据库接入进入生产前必须同时满足：

1. 专用业务 Repository 和映射器已实现并有成功/失败测试。
2. 完整四表建库 DDL 可从空库复现，而不只依赖增量迁移。
3. 学生身份绑定与 PostgreSQL 同事务幂等回执已经迁移、测试并经技术负责人批准。
4. 公共响应可在不破坏既有契约的前提下返回 `data_source/fallback_used`；涉及公共字段时先更新 `API_CONTRACTS.md` 并由 Schema 所有者批准。
5. 生产模式的数据库失败测试证明不会读取 JSON。
6. Demo Mode 响应明确显示 `demo_mode=true`、`data_source=demo_json` 和固定 Demo 提示。
7. 全部 Agent/Tool 调用有隐私安全日志。
8. PostgreSQL 行、Pydantic 模型、CareerState 和 MCP 结果的契约测试通过。

## 13. 已知未解决问题

1. 画像扁平 abilities 与 Unified ability dimensions 的双向映射已实现；但数据库仍没有
   `user_id`/外部主体列。比赛模式只能依赖调用方 `user_id` 与 CareerState 三元引用绑定，
   不能等同于生产级身份认证。
2. 数据库没有与画像插入同事务的幂等回执。现有 trace 账本能覆盖普通重试与“检查点已写入、
   State 快照失败”的恢复，但不能保证 PostgreSQL 提交与检查点之间崩溃时的 exactly-once。
3. 从空库创建四张业务表的完整基线 DDL 仍缺失；V005～V007 是依赖既有基表的增量迁移。
4. 职业图谱节点与边尚未固定在同一只读事务快照；并发更新期间可能读取到不同版本。
5. `FeedbackService` 仍使用进程内字典，重启后数据丢失；没有正式反馈/成长业务表。
6. 数据库 `job_type_profile` 没有节点时长、节点风险和城市字段；当前使用有版本的确定性默认值
   并记录质量标记，不允许 LLM 补值。
7. 本地 PostgreSQL 16 与 MCP 2.0 已验证，但远程 HTTPS/Ant TBox 现场发布仍需独立验收。
