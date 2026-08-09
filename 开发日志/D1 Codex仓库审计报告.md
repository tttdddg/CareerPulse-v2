已完成只读检查，未修改任何文件。仓库当前是 Vue 3 + Vite 前端、FastAPI + PostgreSQL 后端；数据库使用 `psycopg2` 和手写 SQL，没有 ORM 模型或迁移框架。

## 1. 前后端入口和路由结构

### 前端入口

- HTML 入口：[front/index.html](D:/vue/CareerPulse-Pro/front/index.html)
- Vue 启动入口：[front/src/main.ts (line 1)](D:/vue/CareerPulse-Pro/front/src/main.ts:1)
  - 注册 Pinia、Vue Router、Element Plus
  - 恢复用户和历史记录本地状态
  - 挂载到 `#app`
- 根组件：[front/src/App.vue](D:/vue/CareerPulse-Pro/front/src/App.vue)
- Vite 配置：[front/vite.config.ts (line 10)](D:/vue/CareerPulse-Pro/front/vite.config.ts:10)
  - `/api` 默认代理到 `http://127.0.0.1:8000`
- Axios 封装：[front/src/api/request.ts (line 110)](D:/vue/CareerPulse-Pro/front/src/api/request.ts:110)
- 默认布局：[front/src/layouts/DefaultLayout.vue](D:/vue/CareerPulse-Pro/front/src/layouts/DefaultLayout.vue)

### 前端路由

路由定义：[front/src/router/index.ts (line 33)](D:/vue/CareerPulse-Pro/front/src/router/index.ts:33)，使用 `createWebHashHistory()`。

| 路径             | 页面                                                         | 说明                |
| ---------------- | ------------------------------------------------------------ | ------------------- |
| `/`              | [HomeLanding.vue](D:/vue/CareerPulse-Pro/front/src/views/home/HomeLanding.vue) | 首页，公开          |
| `/login`         | [Login.vue](D:/vue/CareerPulse-Pro/front/src/views/login/Login.vue) | 登录，公开          |
| `/register`      | 同上                                                         | 注册，公开          |
| `/app`           | [DefaultLayout.vue](D:/vue/CareerPulse-Pro/front/src/layouts/DefaultLayout.vue) | 重定向 `/app/input` |
| `/app/input`     | [DataInput.vue](D:/vue/CareerPulse-Pro/front/src/views/input/DataInput.vue) | 简历/画像输入       |
| `/app/analysis`  | [AnalysisBoard.vue](D:/vue/CareerPulse-Pro/front/src/views/analysis/AnalysisBoard.vue) | 匹配分析            |
| `/app/recommend` | —                                                            | 重定向到分析页      |
| `/app/jobs`      | [JobLibraryPage.vue](D:/vue/CareerPulse-Pro/front/src/views/jobs/JobLibraryPage.vue) | 岗位库              |
| `/app/path`      | [PathGraphPage.vue](D:/vue/CareerPulse-Pro/front/src/views/path/PathGraphPage.vue) | 职业路径            |
| `/app/plan`      | [GrowthPlan.vue](D:/vue/CareerPulse-Pro/front/src/views/plan/GrowthPlan.vue) | 成长计划            |
| `/app/profile`   | [Profile.vue](D:/vue/CareerPulse-Pro/front/src/views/profile/Profile.vue) | 个人中心/历史       |
| 其他             | —                                                            | 重定向 `/`          |

路由守卫会检查本地 token；路径页还依赖 `analysisStore.canVisitPathGraph`。

另有几个疑似旧版/未接入路由的页面：

- [front/src/views/InputCenterView.vue](D:/vue/CareerPulse-Pro/front/src/views/InputCenterView.vue)
- [front/src/views/AnalyticsDashboardView.vue](D:/vue/CareerPulse-Pro/front/src/views/AnalyticsDashboardView.vue)
- [front/src/views/LoginView.vue](D:/vue/CareerPulse-Pro/front/src/views/LoginView.vue)
- [front/src/views/recommend/JobRecommendPage.vue](D:/vue/CareerPulse-Pro/front/src/views/recommend/JobRecommendPage.vue)

### 后端入口

- FastAPI 入口：[backend/app/main.py (line 1)](D:/vue/CareerPulse-Pro/backend/app/main.py:1)
- 路由聚合：[backend/app/routers.py (line 18)](D:/vue/CareerPulse-Pro/backend/app/routers.py:18)
- 子路由导出：[backend/app/routes/__init__.py](D:/vue/CareerPulse-Pro/backend/app/routes/__init__.py)
- 配置：[backend/app/config.py](D:/vue/CareerPulse-Pro/backend/app/config.py)
- 依赖：[backend/requirements.txt](D:/vue/CareerPulse-Pro/backend/requirements.txt)

后端实际 API：

| 方法与路径                             | 路由文件                                                     |
| -------------------------------------- | ------------------------------------------------------------ |
| `GET /jobs`                            | [routes/jobs.py (line 11)](D:/vue/CareerPulse-Pro/backend/app/routes/jobs.py:11) |
| `GET /jobs/{job_id}/profile`           | [routes/jobs.py (line 16)](D:/vue/CareerPulse-Pro/backend/app/routes/jobs.py:16) |
| `GET /jobs/{job_id}/graph`             | [routes/jobs.py (line 25)](D:/vue/CareerPulse-Pro/backend/app/routes/jobs.py:25) |
| `GET /student/{student_id}/profile`    | [routes/students.py (line 59)](D:/vue/CareerPulse-Pro/backend/app/routes/students.py:59) |
| `POST /student/upload/resume`          | [routes/students.py (line 68)](D:/vue/CareerPulse-Pro/backend/app/routes/students.py:68) |
| `POST /student/upload/profile`         | [routes/students.py (line 111)](D:/vue/CareerPulse-Pro/backend/app/routes/students.py:111) |
| `POST /matching/analyze`               | [routes/matching.py (line 12)](D:/vue/CareerPulse-Pro/backend/app/routes/matching.py:12) |
| `POST /reports/generate`               | [routes/reports.py (line 12)](D:/vue/CareerPulse-Pro/backend/app/routes/reports.py:12) |
| `GET /reports/{report_id}`             | [routes/reports.py (line 26)](D:/vue/CareerPulse-Pro/backend/app/routes/reports.py:26) |
| `POST /reports/{report_id}/polish`     | [routes/reports.py (line 35)](D:/vue/CareerPulse-Pro/backend/app/routes/reports.py:35) |
| `GET /reports/{report_id}/export`      | [routes/reports.py (line 44)](D:/vue/CareerPulse-Pro/backend/app/routes/reports.py:44) |
| `GET /users/{user_id}/histories`       | [routes/history.py (line 11)](D:/vue/CareerPulse-Pro/backend/app/routes/history.py:11) |
| `GET /histories/{history_id}/snapshot` | [routes/history.py (line 17)](D:/vue/CareerPulse-Pro/backend/app/routes/history.py:17) |
| `GET /recommendations`                 | [routes/recommendations.py (line 11)](D:/vue/CareerPulse-Pro/backend/app/routes/recommendations.py:11) |

## 2. 现有数据库模型

没有 SQLAlchemy 模型。唯一明确建表代码在 [backend/app/db.py (line 46)](D:/vue/CareerPulse-Pro/backend/app/db.py:46)。

### 代码负责创建的表

`career_report`：

- `id BIGSERIAL PRIMARY KEY`
- `student_id BIGINT NOT NULL`
- `job_id INTEGER NOT NULL`
- `status VARCHAR(32) DEFAULT 'ready'`
- `content JSONB NOT NULL`
- `created_at TIMESTAMPTZ`
- `updated_at TIMESTAMPTZ`

`matching_history`：

- `id BIGSERIAL PRIMARY KEY`
- `user_id VARCHAR(64) DEFAULT 'default'`
- `student_id BIGINT NOT NULL`
- `job_id INTEGER NOT NULL`
- `overall_score NUMERIC(5,2)`
- `analysis JSONB NOT NULL`
- `report_id BIGINT`
- `created_at TIMESTAMPTZ`

目前没有显式外键和索引。

### 依赖但不负责创建的表

这些表只能从查询代码反推，仓库内没有完整 DDL：

- `student_profile`
  - 已使用字段：`id`、`student_name`、`parsed_data`、`created_at`
  - 使用位置：[student_service.py (line 11)](D:/vue/CareerPulse-Pro/backend/app/services/student_service.py:11)
- `job_clean`
  - 已使用字段：`job_id`、`job_title`、`normalized_job_title`、`location_raw`、`city`、`salary_desc`、`company_name`、`industry`、`job_description_clean`、`title_level`、`updated_at`
  - 使用位置：[job_service.py (line 123)](D:/vue/CareerPulse-Pro/backend/app/services/job_service.py:123)
- `job_type_profile`
  - 已使用字段：`type_key`、`normalized_job_title`、`core_skills`、`optional_skills`、`soft_skills`、`salary_desc_p50`、`industry`、`profile_summary`、`exemplar_job_id`、`exemplar_job_title`
  - 使用位置：[job_service.py (line 261)](D:/vue/CareerPulse-Pro/backend/app/services/job_service.py:261)
- `job_type_graph_edge`
  - 已使用字段：`id`、`source_type_key`、`target_type_key`、`target_job_id`、`target_job_title`、`relation_type`、`reason`、`score`
  - 使用位置：[job_service.py (line 435)](D:/vue/CareerPulse-Pro/backend/app/services/job_service.py:435)

风险：`student_profile` 没有存在性检查；另外三张岗位表只做运行时存在性判断，没有迁移或初始化保障。

## 3. 简历、岗位、匹配、路径、报告代码位置

### 简历与学生画像

- 文件文本/OCR 提取：[resume_service.py (line 12)](D:/vue/CareerPulse-Pro/backend/app/services/resume_service.py:12)
  - `extract_image_text`
  - `extract_all_content`
  - `parse_llm_json`
- 上传与 LLM 调用：[routes/students.py (line 19)](D:/vue/CareerPulse-Pro/backend/app/routes/students.py:19)
- 画像持久化与读取：[student_service.py (line 11)](D:/vue/CareerPulse-Pro/backend/app/services/student_service.py:11)
- Pydantic 输入/上传响应：[schemas.py (line 6)](D:/vue/CareerPulse-Pro/backend/app/schemas.py:6)
- 前端上传接口：[career.ts (line 740)](D:/vue/CareerPulse-Pro/front/src/api/modules/career.ts:740)
- 前端输入页：[DataInput.vue](D:/vue/CareerPulse-Pro/front/src/views/input/DataInput.vue)
- 上传组件：[ResumeUpload.vue](D:/vue/CareerPulse-Pro/front/src/components/business/ResumeUpload.vue)

### 岗位

- 查询、画像、路径图：[job_service.py (line 123)](D:/vue/CareerPulse-Pro/backend/app/services/job_service.py:123)
- API：[routes/jobs.py](D:/vue/CareerPulse-Pro/backend/app/routes/jobs.py)
- 前端 API：[career.ts (line 670)](D:/vue/CareerPulse-Pro/front/src/api/modules/career.ts:670)
- 岗位库页面：[JobLibraryPage.vue](D:/vue/CareerPulse-Pro/front/src/views/jobs/JobLibraryPage.vue)
- 前端岗位多样性规则：[jobDiversity.ts](D:/vue/CareerPulse-Pro/front/src/utils/jobDiversity.ts)

### 匹配与差距分析

- 确定性回退评分、LLM 评分、历史写入：[matching_service.py (line 85)](D:/vue/CareerPulse-Pro/backend/app/services/matching_service.py:85)
- API：[routes/matching.py](D:/vue/CareerPulse-Pro/backend/app/routes/matching.py)
- 请求 schema：[schemas.py (line 14)](D:/vue/CareerPulse-Pro/backend/app/schemas.py:14)
- 前端主调用：[career.ts (line 790)](D:/vue/CareerPulse-Pro/front/src/api/modules/career.ts:790)
- 分析页面：[AnalysisBoard.vue](D:/vue/CareerPulse-Pro/front/src/views/analysis/AnalysisBoard.vue)
- 分析状态：[stores/analysis.ts](D:/vue/CareerPulse-Pro/front/src/stores/analysis.ts)
- 雷达图：[RadarChart.vue](D:/vue/CareerPulse-Pro/front/src/components/business/RadarChart.vue)

重要 A02 冲突：`build_matching_analysis()` 当前允许 LLM直接产生 `overall_score` 和维度分数，违反“匹配分数、差距分析和路径分数不得由 LLM 发明”的规则。

### 职业路径

- 后端图谱读取：[job_service.py (line 379)](D:/vue/CareerPulse-Pro/backend/app/services/job_service.py:379)
- API：[routes/jobs.py (line 25)](D:/vue/CareerPulse-Pro/backend/app/routes/jobs.py:25)
- 前端 API：[career.ts (line 732)](D:/vue/CareerPulse-Pro/front/src/api/modules/career.ts:732)
- 页面：[PathGraphPage.vue](D:/vue/CareerPulse-Pro/front/src/views/path/PathGraphPage.vue)
- 图组件：[PathGraph.vue](D:/vue/CareerPulse-Pro/front/src/components/business/PathGraph.vue)

当前路径来自 `job_type_graph_edge`，但边上的 `score` 来源及计算过程不在仓库中，尚不能证明满足 A02 确定性要求。

### 报告

- 生成、查询、润色、PDF/DOCX 导出：[report_service.py (line 16)](D:/vue/CareerPulse-Pro/backend/app/services/report_service.py:16)
- API：[routes/reports.py](D:/vue/CareerPulse-Pro/backend/app/routes/reports.py)
- Pydantic 输入：[schemas.py (line 20)](D:/vue/CareerPulse-Pro/backend/app/schemas.py:20)
- 前端 API：[career.ts (line 806)](D:/vue/CareerPulse-Pro/front/src/api/modules/career.ts:806)
- 富文本编辑：[RichTextEditor.vue](D:/vue/CareerPulse-Pro/front/src/components/business/RichTextEditor.vue)
- 导出组件：[ExportButton.vue](D:/vue/CareerPulse-Pro/front/src/components/business/ExportButton.vue)
- 历史服务：[history_service.py](D:/vue/CareerPulse-Pro/backend/app/services/history_service.py)
- 历史前端状态：[stores/history.ts](D:/vue/CareerPulse-Pro/front/src/stores/history.ts)

### 推荐与成长计划

- 推荐后端：[recommendation_service.py](D:/vue/CareerPulse-Pro/backend/app/services/recommendation_service.py)
- 推荐 API：[routes/recommendations.py](D:/vue/CareerPulse-Pro/backend/app/routes/recommendations.py)
- 成长计划页面：[GrowthPlan.vue](D:/vue/CareerPulse-Pro/front/src/views/plan/GrowthPlan.vue)
- AI 助手：[AiAssistantDrawer.vue](D:/vue/CareerPulse-Pro/front/src/components/business/AiAssistantDrawer.vue)

当前没有独立的后端 path service、growth-plan service 或 CareerOrchestrator。

## 4. 现有测试覆盖

实际仓库中没有找到：

- `backend/tests/`
- 前端 `*.test.*`、`*.spec.*`
- pytest、Vitest、Jest、Playwright、Cypress 配置
- 测试命令

[front/package.json](D:/vue/CareerPulse-Pro/front/package.json) 只有：

- `dev`
- `build`
- `preview`
- `typecheck`

[backend/requirements.txt](D:/vue/CareerPulse-Pro/backend/requirements.txt) 也未声明 `pytest`。

README 中出现的 `backend/tests/test_match_service.py`、`test_path_service.py`、`test_platform_tools.py` 等是 A02 规划文本，不是仓库现有文件。因此当前实际自动化测试覆盖可视为 **0**；API 成功/失败路径、数据库服务、LLM 回退、文件解析、导出和前端契约都未被测试保护。

## 5. 可以封装为平台工具的现有函数

优先封装公开业务函数，不直接暴露以下划线开头的内部函数。

| 候选平台工具                   | 可复用函数                             | 位置                                                         |
| ------------------------------ | -------------------------------------- | ------------------------------------------------------------ |
| `extract_resume_content`       | `extract_all_content`                  | [resume_service.py (line 27)](D:/vue/CareerPulse-Pro/backend/app/services/resume_service.py:27) |
| `save_student_profile`         | `save_resume_profile`                  | [student_service.py (line 11)](D:/vue/CareerPulse-Pro/backend/app/services/student_service.py:11) |
| `get_student_profile`          | 同名函数                               | [student_service.py (line 34)](D:/vue/CareerPulse-Pro/backend/app/services/student_service.py:34) |
| `search_jobs`                  | 同名函数                               | [job_service.py (line 123)](D:/vue/CareerPulse-Pro/backend/app/services/job_service.py:123) |
| `get_job_profile`              | 同名函数                               | [job_service.py (line 219)](D:/vue/CareerPulse-Pro/backend/app/services/job_service.py:219) |
| `get_career_path_graph`        | `get_job_graph`                        | [job_service.py (line 379)](D:/vue/CareerPulse-Pro/backend/app/services/job_service.py:379) |
| `calculate_job_match`          | `_rule_fallback_analysis` 经公开化重构 | [matching_service.py (line 85)](D:/vue/CareerPulse-Pro/backend/app/services/matching_service.py:85) |
| `analyze_matching`             | 同名函数，但需先移除 LLM 定分职责      | [matching_service.py (line 230)](D:/vue/CareerPulse-Pro/backend/app/services/matching_service.py:230) |
| `generate_career_report`       | `generate_report`                      | [report_service.py (line 37)](D:/vue/CareerPulse-Pro/backend/app/services/report_service.py:37) |
| `get_career_report`            | `get_report`                           | [report_service.py (line 103)](D:/vue/CareerPulse-Pro/backend/app/services/report_service.py:103) |
| `polish_report_section`        | `polish_report`                        | [report_service.py (line 126)](D:/vue/CareerPulse-Pro/backend/app/services/report_service.py:126) |
| `export_career_report`         | `export_report`                        | [report_service.py (line 157)](D:/vue/CareerPulse-Pro/backend/app/services/report_service.py:157) |
| `list_matching_histories`      | `get_user_histories`                   | [history_service.py (line 12)](D:/vue/CareerPulse-Pro/backend/app/services/history_service.py:12) |
| `get_history_snapshot`         | 同名函数                               | [history_service.py (line 43)](D:/vue/CareerPulse-Pro/backend/app/services/history_service.py:43) |
| `get_learning_recommendations` | `get_recommendations`                  | [recommendation_service.py (line 4)](D:/vue/CareerPulse-Pro/backend/app/services/recommendation_service.py:4) |

兼容性导出集中在 [backend/app/services.py](D:/vue/CareerPulse-Pro/backend/app/services.py) 和 [backend/app/services/__init__.py](D:/vue/CareerPulse-Pro/backend/app/services/__init__.py)。

## 6. 可能受 A02 改造影响的公共接口

### 已存在且需要保持兼容

- 全部 FastAPI 路由及 `{code,msg,data}` 响应包络
- [backend/app/schemas.py](D:/vue/CareerPulse-Pro/backend/app/schemas.py) 中：
  - `ProfileUploadRequest`
  - `MatchingAnalyzeRequest`
  - `ReportGenerateRequest`
  - `ReportPolishRequest`
  - `StudentUploadResponse`
- 前端公开 TypeScript 类型和归一化逻辑：
  - [career.ts](D:/vue/CareerPulse-Pro/front/src/api/modules/career.ts)
  - [analysis.ts](D:/vue/CareerPulse-Pro/front/src/api/modules/analysis.ts)
  - [history.ts](D:/vue/CareerPulse-Pro/front/src/api/modules/history.ts)
  - [user.ts](D:/vue/CareerPulse-Pro/front/src/api/modules/user.ts)
- 数据库 JSON 字段：
  - `student_profile.parsed_data`
  - `matching_history.analysis`
  - `career_report.content`
- 路径图返回结构：
  - `center`
  - `vertical`
  - `lateral`
  - `relations`
- 匹配返回结构：
  - `overall_score`
  - `dimensions`
  - `gap_analysis`

仓库没有实际的 `API_CONTRACTS.md`；只有 [README.md](D:/vue/CareerPulse-Pro/README.md) 提及未来路径 `docs/a02/04_API_CONTRACTS.md`。在变更任何公共字段前，应先补齐这份契约文档。

### 前端已调用但后端不存在的接口

- `/analysis/match`
- `/analysis/path`
- `/analysis/growth-plan`
- `/history/summary`
- `/history/growth`
- `/history/reports/*`
- `/reports` 的列表、创建、删除变体
- `/user/login`
- `/user/register`
- `/user/profile`

位置分别是：

- [analysis.ts (line 53)](D:/vue/CareerPulse-Pro/front/src/api/modules/analysis.ts:53)
- [history.ts (line 162)](D:/vue/CareerPulse-Pro/front/src/api/modules/history.ts:162)
- [user.ts (line 34)](D:/vue/CareerPulse-Pro/front/src/api/modules/user.ts:34)

这些接口可能是旧契约、Mock 遗留或待实现能力。A02 适配时不能默认视为已经可用。

## 7. 最小风险改造顺序

1. **冻结并记录现有契约**
   - 建立 `docs/a02/04_API_CONTRACTS.md`
   - 记录现有 REST 路由、Pydantic schema、JSONB 结构和前端类型。
   - 不改字段名和数据库字段。
2. **先补基线测试**
   - 为现有 Service 和 API 建成功/失败测试。
   - 覆盖无模型密钥、数据库缺表、无效简历、岗位不存在、报告导出。
   - 固化前端实际依赖的返回结构。
3. **把确定性计算与 LLM 推理拆开**
   - 将规则匹配正式提升为 Match Service。
   - LLM 只解释已计算的结果，不产生或覆盖分数。
   - 路径边评分也需要明确确定性来源。
4. **补结构化输出 schema**
   - 为学生画像、匹配结果、差距、路径、报告分别建立 Pydantic 模型。
   - 替换当前仅 `json.loads`/字典检查的弱校验。
5. **建立 Tool 层**
   - Tool 只调用 Service。
   - 每个 Tool 定义稳定 JSON Schema，并有成功与失败测试。
   - 加入脱敏日志，禁止记录完整简历正文。
6. **建立 CareerOrchestrator**
   - 编排“解析画像 → 查询岗位 → 计算匹配 → 生成路径 → 生成报告”。
   - Agent 只做决策与解释。
   - 每个外部模型/工具调用都有日志、超时和 fallback。
7. **增加 Demo Mode**
   - 简历解析、匹配解释、报告生成在无外部 API 时仍可运行。
   - 当前匹配已有部分规则回退，但简历上传没有模型密钥时会直接失败，应优先补齐。
8. **最后接入 Ant TBox 与前端**
   - 先通过适配层复用现有 REST 契约。
   - 验证平台配置和发布后，再声明平台能力。
   - 最后清理或兼容前端幽灵接口，避免一次性大改页面。

## 8. 需要增加的 MCP/API 适配层

建议新增独立层级，避免 MCP、Ant TBox 和 FastAPI 直接调用数据库或彼此复制业务逻辑：

```
backend/app/
  orchestrators/
    career_orchestrator.py
  agents/
    career_agent.py
  tools/
    resume_tools.py
    student_tools.py
    job_tools.py
    matching_tools.py
    path_tools.py
    report_tools.py
    history_tools.py
  mcp/
    server.py
    schemas.py
    adapters.py
  api/
    adapters.py
  observability/
    tool_logger.py
    masking.py
  fallback/
    demo_provider.py
```

需要的适配职责：

- **API adapter**
  - 在现有 REST 请求/响应与统一 Tool schema 之间转换。
  - 保留当前 `{code,msg,data}` 和下载响应。
  - 不让前端直接感知 Ant TBox 内部 schema。
- **MCP server/adapter**
  - 将平台工具注册为 MCP tools。
  - 输入输出复用 Pydantic/JSON Schema。
  - 统一处理业务异常、超时、模型失败和数据库失败。
- **Ant TBox adapter**
  - 把 MCP/Tool 描述转换成平台需要的注册格式。
  - 传入调用上下文、用户标识、追踪 ID 和 Demo Mode 标志。
  - 只注册实际配置且经过测试的工具。
- **CareerOrchestrator**
  - 控制调用顺序及状态，不承担具体计算。
  - 对部分失败进行降级，保留可继续执行的结果。
- **Tool logging adapter**
  - 记录工具名、调用 ID、耗时、状态、错误类型和脱敏参数摘要。
  - 不记录简历原文、姓名、邮箱、电话或身份信息。
- **Provider/fallback adapter**
  - 封装 DeepSeek/OpenAI 等模型调用。
  - 简历解析、解释、报告生成分别提供确定性或模板化 Demo fallback。

最适合首批暴露的 MCP 工具是：`get_student_profile`、`search_jobs`、`get_job_profile`、`calculate_job_match`、`get_career_path_graph`、`generate_career_report`、`get_history_snapshot`。简历文件上传和报告二进制导出可继续由 REST 处理，MCP 侧先暴露文本/资源引用形式，风险更低。