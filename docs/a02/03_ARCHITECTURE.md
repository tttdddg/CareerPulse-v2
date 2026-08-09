# 03_ARCHITECTURE — 系统架构

> **锁定状态：FROZEN（D2 冻结）**
> 架构层级划分、模块职责边界、数据流向不得随意变更。
> 修改须在 `decisions/` 创建 ADR。

---

## 1. 系统分层

```
┌───────────────────────────────────────────────────────┐
│                   百宝箱平台层                          │
│  • 智能体对话 UI                                       │
│  • 系统 Prompt                                        │
│  • 知识库检索                                         │
│  • 工具调用编排（MCP/HTTP API）                        │
│  • Web / 小程序发布                                    │
└────────────┬──────────────────────────────────────────┘
             │ MCP / HTTP API
             ▼
┌───────────────────────────────────────────────────────┐
│              CareerPulse Agent 编排层                   │
│  POST /api/career-agent/run                           │
│  GET  /api/career-agent/session/{session_id}          │
│  GET  /api/agent/logs/{session_id}                    │
│                                                       │
│  CareerOrchestrator                                    │
│    ├─ ProfileAgent → student_profile                  │
│    ├─ JobAgent → job_profile + trend_result           │
│    ├─ MatchAgent → match_result                       │
│    ├─ PathAgent → path_plan + learning_plan           │
│    ├─ TrainingAgent → training_plan                   │
│    └─ FeedbackAgent → feedback_result                 │
│                                                       │
│  CareerState (会话级共享状态)                           │
│  BaseAgent (统一基类)                                  │
│  LLMClient (统一 LLM 客户端)                            │
└────────────┬──────────────────────────────────────────┘
             │ 内部调用
             ▼
┌───────────────────────────────────────────────────────┐
│              CareerPulse Service 层                     │
│  MatchService      — 确定性匹配算法                     │
│  PathService       — 职业路径图搜索                     │
│  TrainingService   — 训练评分规则引擎                   │
│  ResourceService   — 资源推荐                           │
│  FeedbackService   — 反馈与成长档案                     │
│  StudentService    — 学生画像 CRUD                      │
│  JobService        — 岗位画像与图谱 CRUD                 │
│  ReportService     — 报告生成与导出                      │
│  LogService        — Agent 日志持久化                    │
└────────────┬──────────────────────────────────────────┘
             │ psycopg2
             ▼
┌───────────────────────────────────────────────────────┐
│              PostgreSQL + Redis                        │
│  student_profile, job_clean, job_type_profile,         │
│  job_type_graph_edge, career_report,                   │
│  matching_history, ability_tags, training_records,     │
│  learning_plans, growth_archives, agent_logs           │
└───────────────────────────────────────────────────────┘
```

---

## 2. 目录结构（改造后）

```
backend/
├── app/
│   ├── main.py                    # FastAPI 入口
│   ├── routers.py                 # 路由聚合
│   ├── config.py                  # 数据库配置
│   ├── db.py                      # 数据库连接与工具
│   ├── schemas.py                 # [保留] 原有 Pydantic 模型
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # [新] 统一配置（模型/平台/降级）
│   │   ├── llm_client.py          # [新] 统一 LLM 客户端
│   │   └── career_state.py        # [新] CareerState 定义
│   │
│   ├── schemas/                   # [新] 公共 Schema
│   │   ├── __init__.py
│   │   ├── profile_schema.py      # 学生画像 Schema
│   │   ├── job_schema.py          # 岗位画像 Schema
│   │   ├── match_schema.py        # 匹配结果 Schema
│   │   ├── path_schema.py         # 路径 Schema
│   │   ├── training_schema.py     # 训练 Schema
│   │   ├── feedback_schema.py     # 反馈 Schema
│   │   └── common.py              # 统一错误/工具响应 Schema
│   │
│   ├── agents/                    # [新] Agent 实现
│   │   ├── __init__.py
│   │   ├── base_agent.py          # BaseAgent 基类
│   │   ├── profile_agent.py       # ProfileAgent
│   │   ├── job_agent.py           # JobAgent
│   │   ├── match_agent.py         # MatchAgent
│   │   ├── path_agent.py          # PathAgent
│   │   ├── training_agent.py      # TrainingAgent
│   │   └── feedback_agent.py      # FeedbackAgent
│   │
│   ├── orchestrator/              # [新] 编排器
│   │   ├── __init__.py
│   │   └── career_orchestrator.py # CareerOrchestrator
│   │
│   ├── services/                  # [保留+扩展] 业务 Service
│   │   ├── __init__.py
│   │   ├── student_service.py     # [保留]
│   │   ├── job_service.py         # [保留]
│   │   ├── resume_service.py      # [保留]
│   │   ├── matching_service.py    # [重写] 确定性匹配算法
│   │   ├── path_service.py        # [新]
│   │   ├── training_service.py    # [新]
│   │   ├── resource_service.py    # [新]
│   │   ├── feedback_service.py    # [新]
│   │   ├── report_service.py      # [保留] 报告+导出
│   │   ├── recommendation_service.py  # [保留,可能合并到resource]
│   │   ├── history_service.py     # [保留]
│   │   └── log_service.py         # [新]
│   │
│   ├── tools/                     # [新] 百宝箱工具封装
│   │   ├── __init__.py
│   │   ├── tool_registry.py       # 工具注册
│   │   ├── profile_tool.py
│   │   ├── job_trend_tool.py
│   │   ├── match_tool.py
│   │   ├── path_tool.py
│   │   ├── training_tool.py
│   │   ├── resource_tool.py
│   │   ├── feedback_tool.py
│   │   └── mock_tools.py          # Mock 工具（阶段1-4使用）
│   │
│   ├── mcp/                       # [新] MCP 适配（如平台支持）
│   │   ├── __init__.py
│   │   └── mcp_server.py          # MCP Server 实现
│   │
│   ├── platform/                  # [新] 平台适配层
│   │   ├── __init__.py
│   │   └── tbox_adapter.py        # 百宝箱工具适配
│   │
│   ├── api/                       # [新+保留] API 路由
│   │   ├── career_agent_api.py    # [新] Agent 主接口
│   │   └── (原有 routes 目录保留)
│   │
│   ├── routes/                    # [保留]
│   │   ├── __init__.py
│   │   ├── students.py
│   │   ├── jobs.py
│   │   ├── matching.py
│   │   ├── reports.py
│   │   ├── recommendations.py
│   │   └── history.py
│   │
│   ├── models/                    # [新] 数据库模型
│   │   ├── __init__.py
│   │   └── a02_models.py
│   │
│   ├── data/                      # [新] 初始化数据
│   │   ├── ability_tags.json      # 能力标签
│   │   ├── students_demo.json     # Demo 学生
│   │   ├── jobs_demo.json         # Demo 岗位
│   │   ├── career_graph.json      # 职业图谱
│   │   ├── training_tasks.json    # 训练题
│   │   ├── resources.json         # 学习资源
│   │   └── job_trends/            # 趋势数据
│   │
│   └── scripts/                   # [新+保留]
│       ├── build_job_knowledge.py # [新] 知识库构建
│       └── init_db.py             # [新] 数据库初始化
│
├── migrations/                    # [新]
├── tests/                         # [保留+扩展]
├── prompts/                       # [新] Prompt 模板
├── requirements.txt
└── docker-compose.yml

front/
├── src/
│   ├── api/modules/               # [保留+扩展]
│   │   ├── career_agent.ts        # [新] Agent API
│   │   └── (原有模块保留)
│   ├── views/                     # [保留+新增]
│   │   ├── training/              # [新] 职场训练页
│   │   ├── agent-log/             # [新] Agent 执行链路页
│   │   ├── progress/              # [新] 学习进度页
│   │   └── (原有页面保留)
│   └── (其余原有结构保留)
```

---

## 3. 核心模块职责

### 3.1 CareerOrchestrator

```
职责：
- 接收 session_id 和输入数据
- 初始化 CareerState
- 顺序执行 6 个 Agent
- 每个 Agent 执行前检查前置依赖
- 失败时记录 log + fallback，继续执行
- 全部完成后生成 final_report
- 返回最终 CareerState
```

### 3.2 BaseAgent

```
职责：
- 统一入口：async def run(state: CareerState) -> AgentResult
- 统一日志：开始/结束时间、tool_calls、fallback
- 统一降级：LLM 失败 → 规则/Demo 数据
- 子类实现：async def _execute(state) -> dict
```

### 3.3 LLMClient

```
职责：
- 封装 openai SDK（统一 provider 切换）
- 结构化输出：Pydantic Schema → JSON → 校验
- JSON 失败重试：max 2 次
- 超时控制：默认 30s
- Demo Mode：直接返回固定数据
- 日志：不记录完整 resume 文本
```

### 3.4 6 个 Agent 职责（详见 05_AGENT_CONTRACTS.md）

| Agent | 调用 LLM | 调用 Service | 产出 |
|-------|---------|-------------|------|
| ProfileAgent | ✅ 简历/表单→结构化画像 | StudentService | student_profile |
| JobAgent | ✅ JD→岗位能力向量 | JobService | job_profile + trend_result |
| MatchAgent | ✅ 自然语言解释 | MatchService（计算分数） | match_result |
| PathAgent | ✅ 路径文字描述 | PathService（图搜索） | path_plan + learning_plan |
| TrainingAgent | ✅ 训练题+评价生成 | TrainingService（评分规则） | training_plan |
| FeedbackAgent | ❌ | FeedbackService | feedback_result |

---

## 4. 数据流

### 4.1 主链路

```
百宝箱用户对话
  → 百宝箱调用工具（如 analyze_student_profile）
  → POST /api/career-agent/run
  → CareerOrchestrator.run()
    → ProfileAgent.run(state) → state.student_profile = {...}
    → JobAgent.run(state) → state.job_profile = {...}
    → MatchAgent.run(state) → state.match_result = {...}
    → PathAgent.run(state) → state.path_plan = {...}
    → TrainingAgent.run(state) → state.training_plan = {...}
    → FeedbackAgent.run(state) → state.feedback_result = {...}
    → 生成 state.final_report
  → 返回最终 CareerState
  → 百宝箱展示结果
```

### 4.2 分步调用（推荐百宝箱对话流程）

```
用户: "我是数据分析专业，想做AI产品经理"
  → 百宝箱: 追问缺失信息（实习、项目经历等）
  → 百宝箱调用 analyze_student_profile
  → 返回 student_profile
  → 百宝箱: "这是你的能力画像，接下来我为你分析AI产品经理岗位"

用户: "好的"
  → 百宝箱调用 analyze_job_and_trend
  → 百宝箱检索知识库（岗位趋势）
  → 返回 job_profile + trend_result
  → 百宝箱: "AI产品经理需要…，趋势分析显示…"

  → 百宝箱调用 calculate_job_match
  → 返回 match_result
  → 百宝箱: "你的匹配度是XX分，能力缺口是…"

  → 百宝箱调用 recommend_career_path
  → 返回 path_plan + learning_plan
  → 百宝箱: "建议你3年内…"

  → 百宝箱调用 generate_and_score_training
  → 返回 training_plan
  → 用户完成训练
  → 百宝箱调用 generate_and_score_training（评分模式）
  → 返回 TrainingScore

  → 百宝箱调用 recommend_learning_and_job_resources
  → 返回 resource_result

  → 百宝箱调用 save_growth_feedback
  → 返回 feedback_result
```

---

## 5. 平台交互协议

### 5.1 百宝箱 → CareerPulse 后端

```
方式A: MCP (Model Context Protocol)
  百宝箱 MCP Client → CareerPulse MCP Server → tools → services

方式B: HTTP API (MCP 不支持时的备选)
  百宝箱 HTTP 工具 → POST https://<host>/api/tbox/<tool_name>
  鉴权: Bearer Token (X-API-Key)
```

> 以平台实际支持的方式为准。D1 确认后写入 `decisions/ADR-004-tbox-integration.md`。

### 5.2 CareerPulse 后端 → 百宝箱

```
单向：后端不主动调用百宝箱
后端仅作为工具提供方，响应平台的工具调用请求
```

---

## 6. 降级策略

| 层级 | 降级方式 | 触发条件 |
|------|---------|---------|
| LLM 调用 | 规则引擎 + Demo 数据 | API Key 缺失 / 超时 / 连续重试失败 |
| Agent 执行 | 跳过该 Agent，标记 fallback_used | 前置依赖缺失 / Agent 内部异常 |
| 外部模型 API | Demo Mode 固定数据 | A02_DEMO_MODE=true |
| 数据库 | 内存 Mock | 数据库连接失败 |
| 百宝箱工具 | 返回错误 JSON (code=-1) | 后端服务不可用 |

---

## 7. 版本记录

| 日期 | 版本 | 变更 | 作者 |
|------|------|------|------|
| 2026-08-04 | v1.0 | 初始冻结：分层架构、目录结构、模块职责、数据流 | 技术负责人 |
