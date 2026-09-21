# 06_DATA_DICTIONARY — 数据字典

> **锁定状态：FROZEN（D2 冻结）**
> 本文件定义所有新增/改造的数据库表、字段和初始化数据规范。
> 表名、字段名、类型不得随意修改。修改须带 migration。

---

## 1. 保留表（不修改字段）

| 表名 | 说明 | 管理 |
|------|------|------|
| `student_profile` | 学生画像 | 保留，原样使用 |
| `job_clean` | 岗位实例 | 保留，原样使用 |
| `job_type_profile` | 岗位类型画像 | 保留，原样使用 |
| `job_type_graph_edge` | 岗位关系边 | 保留，原样使用 |
| `career_report` | 职业报告 | 保留，原样使用 |
| `matching_history` | 匹配历史 | 保留，原样使用 |

---

## 2. 新增表

### 2.1 ability_tags — 能力标签字典

```sql
CREATE TABLE ability_tags (
    id          SERIAL PRIMARY KEY,
    tag         VARCHAR(64)  NOT NULL UNIQUE,  -- 标签名（唯一标识）
    category    VARCHAR(32)  NOT NULL,          -- 一级分类: hard_skill / product_business / soft_skill / domain_knowledge / certification
    difficulty  REAL         NOT NULL DEFAULT 1.0,  -- 提升难度系数 1.0-3.0
    description TEXT,                            -- 标签说明
    deprecated  BOOLEAN      NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);
```

### 2.2 student_ability_records — 学生能力记录

```sql
CREATE TABLE student_ability_records (
    id          BIGSERIAL PRIMARY KEY,
    student_id  BIGINT       NOT NULL REFERENCES student_profile(id),
    tag         VARCHAR(64)  NOT NULL,
    level       SMALLINT     NOT NULL CHECK (level BETWEEN 1 AND 5),
    confidence  REAL         NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    evidence    TEXT,
    recorded_at TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_student_ability_student ON student_ability_records(student_id);
```

### 2.3 career_graph_nodes — 职业图谱节点

```sql
CREATE TABLE career_graph_nodes (
    id           SERIAL PRIMARY KEY,
    node_key     VARCHAR(128) NOT NULL UNIQUE,  -- 节点唯一key
    job_title    VARCHAR(128) NOT NULL,          -- 岗位名称
    level_range  VARCHAR(16),                   -- 级别范围: entry / junior / mid / senior / lead
    industry     VARCHAR(64),
    description  TEXT,
    required_skills JSONB,                      -- 统一能力标签向量
    typical_duration INTEGER,                   -- 典型停留月数 1-120
    risk_level VARCHAR(16),                     -- low / medium / high
    cities JSONB                                -- 城市数据缺失时为 null，不推断
);
```

### 2.4 career_graph_edges — 职业图谱边

```sql
CREATE TABLE career_graph_edges (
    id              SERIAL PRIMARY KEY,
    source_key      VARCHAR(128) NOT NULL REFERENCES career_graph_nodes(node_key),
    target_key      VARCHAR(128) NOT NULL REFERENCES career_graph_nodes(node_key),
    relation_type   VARCHAR(16)  NOT NULL CHECK (relation_type IN ('vertical', 'lateral')),
    reason          TEXT,
    transfer_cost   REAL         NOT NULL DEFAULT 1.0,  -- 转移成本
    growth_value    REAL         NOT NULL DEFAULT 1.0,  -- 成长价值
    source_industry VARCHAR(64),
    target_industry VARCHAR(64),
    transition_requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_level VARCHAR(16) NOT NULL DEFAULT 'medium'
);
CREATE UNIQUE INDEX uq_graph_edge_identity
ON career_graph_edges(source_key, target_key, relation_type);
CREATE INDEX idx_graph_source ON career_graph_edges(source_key);
CREATE INDEX idx_graph_target ON career_graph_edges(target_key);
```

> 图谱扩展由 `V002__extend_career_graph_for_path_planning.sql` 加法迁移提供；V001不改。

### 2.5 training_records — 训练记录

```sql
CREATE TABLE training_records (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(64)  NOT NULL,
    user_id         VARCHAR(64),
    student_id      BIGINT,
    job_id          INTEGER,
    training_type   VARCHAR(32)  NOT NULL CHECK (training_type IN ('remote_collaboration', 'ai_office_task', 'cross_role_communication')),
    training_data   JSONB        NOT NULL,  -- 训练题完整数据
    user_answer     TEXT,                    -- 用户回答
    score_data      JSONB,                   -- 评分结果
    created_at      TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
    scored_at       TIMESTAMPTZ
);
CREATE INDEX idx_training_session ON training_records(session_id);
```

### 2.6 learning_plans — 学习计划

```sql
CREATE TABLE learning_plans (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(64),
    session_id      VARCHAR(64)  NOT NULL,
    plan_data       JSONB        NOT NULL,  -- 完整学习计划
    status          VARCHAR(16)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    created_at      TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);
```

### 2.7 growth_archives — 成长档案

```sql
CREATE TABLE growth_archives (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             VARCHAR(64)  NOT NULL,
    abilities           JSONB        NOT NULL,  -- [{tag, level, updated_at}]
    competitiveness_score REAL       NOT NULL,
    completed_trainings INTEGER      NOT NULL DEFAULT 0,
    completed_phases    INTEGER      NOT NULL DEFAULT 0,
    growth_trend        VARCHAR(16)  NOT NULL DEFAULT 'stable' CHECK (growth_trend IN ('improving', 'stable', 'declining')),
    snapshot_time       TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_growth_user ON growth_archives(user_id);
```

### 2.8 agent_logs — Agent 执行日志

```sql
CREATE TABLE agent_logs (
    id            BIGSERIAL PRIMARY KEY,
    session_id    VARCHAR(128) NOT NULL,
    agent_name    VARCHAR(64)  NOT NULL,
    service_name  VARCHAR(64),             -- MatchService / PathService 等
    run_key       VARCHAR(256),            -- 新写入幂等键，旧记录允许 null
    status        VARCHAR(16)  NOT NULL CHECK (status IN ('success', 'partial', 'failed')),
    summary       TEXT,
    duration_ms   INTEGER,
    tool_calls    JSONB,                   -- [{tool_name, input_summary, output_summary, duration_ms, status}]
    fallback_used BOOLEAN      NOT NULL DEFAULT false,
    error         TEXT,
    demo          BOOLEAN      NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_agent_logs_session ON agent_logs(session_id);
CREATE INDEX idx_agent_logs_agent ON agent_logs(agent_name);
CREATE UNIQUE INDEX uq_agent_logs_run_key ON agent_logs(run_key) WHERE run_key IS NOT NULL;
```

上述阶段3字段由 `V003__persist_stage3_career_state.sql` 加法迁移提供。

### 2.9 user_feedback — 用户反馈

```sql
CREATE TABLE user_feedback (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(64)  NOT NULL,
    user_id         VARCHAR(64)  NOT NULL,
    satisfaction    SMALLINT     NOT NULL CHECK (satisfaction BETWEEN 1 AND 5),
    path_rating     SMALLINT     CHECK (path_rating BETWEEN 1 AND 5),
    training_rating SMALLINT     CHECK (training_rating BETWEEN 1 AND 5),
    resource_rating SMALLINT     CHECK (resource_rating BETWEEN 1 AND 5),
    comments        TEXT,
    created_at      TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);
```

### 2.10 career_state — 阶段3会话状态快照

```sql
CREATE TABLE career_state (
    session_id          VARCHAR(128) PRIMARY KEY,
    platform_session_id VARCHAR(128),
    user_id             VARCHAR(128),
    status              VARCHAR(32) NOT NULL DEFAULT 'INITIALIZED',
    error_type          VARCHAR(128),
    state_data          JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_career_state_user ON career_state(user_id);
```

`state_data` 保存完整 Pydantic `CareerState` 快照；`agent_logs` 仍独立保存可查询的
AgentRunLog。两者在同一事务写入。生产 PostgreSQL 使用 V003；本地 Demo/测试使用等价
SQLite 表结构和真实文件数据库，不使用内存成功兜底。

### 2.11 platform_tool_calls — 百宝箱阶段3工具调用记录

```sql
CREATE TABLE platform_tool_calls (
    tool_call_id        VARCHAR(64) PRIMARY KEY,
    tool_name           VARCHAR(64) NOT NULL,
    idempotency_key     VARCHAR(128) NOT NULL,
    request_fingerprint CHAR(64) NOT NULL,
    session_id          VARCHAR(128) NOT NULL,
    platform_session_id VARCHAR(128),
    user_id_hash        CHAR(64),
    status              VARCHAR(16) NOT NULL,
    result_data         JSONB,
    error_code          INTEGER,
    error_type          VARCHAR(128),
    agent_run_key       VARCHAR(256),
    duration_ms         INTEGER,
    created_at          TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL,
    UNIQUE (tool_name, idempotency_key)
);
```

V004 只保存请求 SHA-256 指纹、`user_id` 哈希、CareerState 结果字段指针和安全错误类型；
不保存原始 StudentProfile/JobProfile 请求副本、证据文本、完整结果、明文 user_id、
完整简历或鉴权 token。完整结果仍由 `career_state` 保存，并仅通过鉴权结果接口读取。
`agent_run_key` 关联 V003 `agent_logs.run_key`（`session_id:AgentName`）。状态只允许
`running/succeeded/failed/timed_out`。

---

## 3. 初始化数据规范

### 3.1 ability_tags.json（≥40 条）

当前文件包含 81 个有效标签。该文件是合法标签全集的唯一来源；画像维度映射必须与有效标签
做集合相等校验（不缺失、不多出），岗位软技能分类按 `category` 动态派生。标签别名只维护在
`ability_tag_aliases.json`，使用侧不得复制不完整的硬编码别名表。

见 `04_API_CONTRACTS.md §11`，字段格式：

```json
[
  {
    "tag": "Python",
    "category": "hard_skill",
    "difficulty": 1.5,
    "description": "Python编程语言"
  },
  ...
]
```

### 3.2 students_demo.json（≥3 份）

```json
[
  {
    "_comment": "匿名演示学生 - 禁止使用真实个人信息",
    "name": "演示学生A",
    "basic_info": {
      "education_level": "本科",
      "major": "...",
      "graduation_year": 2025,
      "target_job": "...",
      "target_industry": "..."
    },
    "abilities": [
      {"tag": "...", "level": 3, "confidence": 0.8, "evidence": "..."}
    ]
  }
]
```

### 3.3 jobs_demo.json（≥3 份）

```json
[
  {
    "title": "AI产品经理",
    "normalized_title": "AI产品经理",
    "industry": "人工智能",
    "required_abilities": [
      {"tag": "...", "required_level": 4, "weight": 0.25, "importance": "critical"}
    ],
    "soft_skills": ["沟通表达", "团队协作"],
    "salary_range": "15K-30K",
    "job_description": "..."
  }
]
```

### 3.4 career_graph.json（≥10 节点, ≥15 边）

```json
{
  "nodes": [
    {
      "node_key": "ai-assistant-pm",
      "job_title": "AI产品助理",
      "level_range": "entry",
      "industry": "人工智能",
      "description": "..."
    }
  ],
  "edges": [
    {
      "source_key": "ai-assistant-pm",
      "target_key": "ai-pm",
      "relation_type": "vertical",
      "reason": "纵向晋升：助理→独立负责",
      "transfer_cost": 0.5,
      "growth_value": 2.0
    }
  ]
}
```

### 3.5 training_tasks.json（≥10 题, 覆盖 3 类）

```json
[
  {
    "type": "remote_collaboration",
    "title": "跨时区项目同步",
    "scenario": "你是一个跨国团队的成员...",
    "task_description": "请描述你会如何组织一次跨时区的项目同步会议...",
    "evaluation_criteria": [
      {"dimension": "沟通清晰度", "max_score": 30, "weight": 0.3, "description": "..."},
      {"dimension": "时间管理", "max_score": 25, "weight": 0.25, "description": "..."},
      {"dimension": "工具运用", "max_score": 25, "weight": 0.25, "description": "..."},
      {"dimension": "团队协调", "max_score": 20, "weight": 0.2, "description": "..."}
    ],
    "reference_answer": "要点：1.确定共同时段 2.准备异步议程 3.记录决策 4.明确下一步...",
    "target_abilities": ["沟通表达", "团队协作"]
  }
]
```

### 3.6 resources.json（≥10 条）

```json
[
  {
    "title": "Spring Boot实战",
    "type": "course",
    "url": "https://spring.io/guides",
    "target_ability": "后端开发",
    "description": "Spring Boot入门到实践"
  }
]
```

### 3.7 最终真源与存储边界（D7-11）

| 数据 | 生产真源 | Demo/测试来源 | 是否进入 StateRepository |
|---|---|---|---|
| 学生画像 | `careerpulse_micro.student_profile` | `students_demo.json` | 只保存当前会话投影/引用，不是业务主表 |
| 岗位实例/类型 | `job_clean` + `job_type_profile` | `jobs_demo.json` | 只保存会话岗位投影/引用 |
| 职业图谱 | `job_type_profile` + `job_type_graph_edge` | `career_graph.json` | 只保存计算后的路径快照 |
| 训练题 | `training_tasks.json` | 同一文件 | 可保存本次任务/评分快照，文件仍是真源 |
| 学习资源 | `resources.json` | 同一文件 | 可保存本次推荐快照，文件仍是真源 |
| 会话/日志/幂等 | `career_state`、`agent_logs`、`platform_tool_calls` | SQLite 等价三表 | 本身即 StateRepository 范围 |

生产业务数据库固定为 PostgreSQL 16，默认端点 `localhost:5433`、库名
`careerpulse_micro`，配置键为 `POSTGRES_DATABASE`；`POSTGRES_DB` 不作为别名接受。
早期章节中的规划表不代表当前已建业务表，四张业务表的最终列定义以
`数据库改进设计.md` 与 `19_DATABASE_ACCESS_CONTRACTS.md` 为准。

---

## 4. 数据库迁移规则

1. 所有 DDL 变更写入 `migrations/` 目录，命名 `V{序号}__{描述}.sql`
2. 不删除已有字段，用 `ALTER TABLE ... ADD COLUMN` 新增
3. 废弃字段用注释标记 `-- deprecated: reason`
4. 每次迁移需在测试环境先跑
5. 迁移脚本需包含 `ROLLBACK` 注释

---

## 5. 版本记录

| 日期 | 版本 | 变更 | 作者 |
|------|------|------|------|
| 2026-09-20 | v1.1 | 收口 PostgreSQL、Demo JSON、训练资源和 StateRepository 的数据所有权 | Codex |
| 2026-08-04 | v1.0 | 初始冻结：9张新表+6类初始化数据规范 | 技术负责人 |
