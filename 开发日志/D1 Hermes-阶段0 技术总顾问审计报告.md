现在我已完整读取仓库代码（2535行README.md + 全部后端源码 + 全部前端源码），以下是我作为技术总顾问的完整审计输出。

---

# CareerPulse A02 升级 — 阶段0 技术总顾问审计报告

> **声明**：以下"来自代码"结论基于对 `backend/`、`front/`、`README.md` 的实际文件读取；"来自平台"结论来自 README.md 中对百宝箱企业版（https://b.tbox.cn）的详细文档描述。**用户未在本对话中上传百宝箱截图**——以下平台相关结论基于 README 记录，实际以平台界面为准，需验证后修正。

---

## 1. 当前前端、后端、数据库能力清单

### 1.1 前端（Vue 3 + TypeScript + Vite）

| 层级            | 已有能力                                                     | 证据来源                               |
| --------------- | ------------------------------------------------------------ | -------------------------------------- |
| **路由**        | Landing、Login/Register、DataInput、AnalysisBoard、JobLibrary、PathGraph、GrowthPlan、Profile 共 8 个页面 + 路由守卫 | `front/src/router/index.ts`            |
| **状态管理**    | Pinia: `analysis`（匹配分、雷达图、图谱权限）、`user`、`history` 三个 Store | `front/src/stores/analysis.ts`         |
| **可视化组件**  | RadarChart（ECharts 雷达图）、PathGraph（AntV X6 职业图谱）、GrowthChart（ECharts 成长曲线） | `front/src/components/business/`       |
| **业务组件**    | ResumeUpload（简历上传）、AiAssistantDrawer（AI 助手抽屉）、RichTextEditor（富文本编辑器）、ExportButton（导出按钮） | 同上目录                               |
| **Mock API 层** | 完整 Mock 层：登录、简历解析、匹配分析、岗位列表、路径图谱、成长计划、历史记录 | `front/src/services/mockApi.ts`        |
| **API 模块**    | user、analysis、career、history 四个 API 模块                | `front/src/api/modules/`               |
| **技术栈**      | Vue 3 + TS + Vite + Element Plus + Pinia + Vue Router 4 + Axios + ECharts + AntV X6 | `front/package.json`, `vite.config.ts` |
| **HTTP 客户端** | Axios 封装，JWT token 管理                                   | `front/src/api/request.ts`             |

### 1.2 后端（FastAPI + psycopg2 + PostgreSQL）

| 层级           | 已有能力                                                     | 证据来源                                              |
| -------------- | ------------------------------------------------------------ | ----------------------------------------------------- |
| **核心入口**   | FastAPI app + CORS + 路由聚合                                | `backend/app/main.py`, `routers.py`                   |
| **简历解析**   | PDF/DOCX/TXT/图片 多格式文本提取 + DeepSeek LLM 结构化解析   | `routes/students.py` + `services/resume_service.py`   |
| **学生画像**   | 画像保存/读取（PostgreSQL JSONB 存储）                       | `services/student_service.py`                         |
| **岗位服务**   | 岗位搜索（关键词+分页）、岗位画像（含 skill/soft_skill/ability_dimensions）、岗位关系图谱（晋升vertical/换岗lateral） | `services/job_service.py`                             |
| **人岗匹配**   | DeepSeek LLM 语义评分（overall_score + 4维度 gap）+ 规则兜底（基于技能字面匹配+证书映射+实践/学习/软技能加权） | `services/matching_service.py`                        |
| **职业报告**   | 报告生成（基于匹配结果拼接）、报告查询、段落润色、PDF/DOCX/TXT 导出 | `services/report_service.py`                          |
| **资源推荐**   | 简单关键词规则推荐（Spring/Python/SQL 映射到固定课程 URL）   | `services/recommendation_service.py`                  |
| **历史记录**   | 用户匹配历史列表 + 完整快照查询                              | `services/history_service.py`                         |
| **数据库**     | PostgreSQL: `student_profile`, `job_clean`, `job_type_profile`, `job_type_graph_edge`, `career_report`, `matching_history` | `services/db.py`                                      |
| **LLM 客户端** | 直接使用 openai SDK（DeepSeek），无统一封装、无重试、无 fallback 链 | `routes/students.py` + `services/matching_service.py` |

### 1.3 数据库

| 表                    | 用途                    | 关键字段                                                     | 来源                            |
| --------------------- | ----------------------- | ------------------------------------------------------------ | ------------------------------- |
| `student_profile`     | 学生画像                | id, student_name, parsed_data(JSONB)                         | `db.py` / `student_service.py`  |
| `job_clean`           | 岗位实例                | job_id, job_title, normalized_job_title, industry, salary_desc, job_description_clean, title_level | `job_service.py`                |
| `job_type_profile`    | 岗位类型画像（聚合）    | type_key, core_skills, optional_skills, soft_skills, salary_desc_p50, profile_summary | `job_service.py`                |
| `job_type_graph_edge` | 岗位关系（晋升/换岗边） | source_type_key, target_type_key, relation_type, reason, score | `job_service.py`                |
| `career_report`       | 职业报告                | id, student_id, job_id, status, content(JSONB)               | `db.py` / `report_service.py`   |
| `matching_history`    | 匹配历史                | id, user_id, student_id, job_id, overall_score, analysis(JSONB), report_id | `db.py` / `matching_service.py` |

---

## 2. A02 要求与现有系统差距矩阵

| A02 六大环节                 | A02 具体要求                                                 | 现有系统状态                                                 | 差距评级 | 差距描述                                           |
| ---------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | -------- | -------------------------------------------------- |
| **感知：用户状态采集**       | 简历上传、表单信息、多轮追问、画像完整度判断                 | 🟢 简历上传+表单已实现；🔴 无多轮追问能力、无画像完整度计算    | **高**   | 缺少对话追问流程、画像完整度元数据、结构化能力标签 |
| **认知：职业趋势分析**       | 岗位JD解析、岗位能力向量、行业趋势、技能变化、AI替代风险     | 🟡 岗位画像有 basic skills 提取；🔴 无趋势分析、无技能变化检测、无 AI 替代评估 | **高**   | 完全缺少趋势分析模块、知识库                       |
| **决策：路径规划**           | 人岗匹配度、能力缺口、提升优先级、3年/5年路径、纵向晋升/横向转岗 | 🟡 匹配分由 LLM 产生（规范要求禁止）；🟢 有岗位图谱（晋升/换岗边）；🔴 无 gap/priority 公式计算、无 3年/5年路径规划 | **高**   | 匹配需改为确定性算法；需新增 PathService           |
| **生成：学习内容与建议**     | 阶段学习计划、实践任务、证书建议、职场训练题、资源推荐       | 🔴 仅简单关键词推荐（3个固定 URL）；🔴 无训练题、无学习计划    | **严重** | 几乎全部缺失                                       |
| **执行：任务提醒与资源对接** | 阶段任务清单、学习进度、训练任务、资源入口                   | 🔴 完全缺失                                                   | **严重** | 全部需新增                                         |
| **反馈：效果评估与动态调整** | 训练得分、用户满意度、成长档案更新、路径重排序               | 🔴 完全缺失                                                   | **严重** | 全部需新增                                         |
| **百宝箱平台集成**           | 智能体创建、模型配置、系统 Prompt、知识库、MCP/API 工具、Web 发布 | 🔴 未开始                                                     | **严重** | 零平台配置                                         |
| **Agent 工程化**             | CareerOrchestrator、6 Agent、Tool Calling、结构化输出、降级、日志、评测 | 🔴 完全缺失                                                   | **严重** | 零 Agent 代码                                      |

**结论**：现有系统是"传统 Web 应用 + LLM 辅助评分"，距离"平台智能体驱动的 Agent 系统"差距巨大。

---

## 3. 必须由百宝箱完成的内容

> 这些是 CareerPulse 后端**无法替代**的百宝箱原生能力。

| #    | 必须由百宝箱完成                        | 原因                                                         | 来源         |
| ---- | --------------------------------------- | ------------------------------------------------------------ | ------------ |
| 1    | **用户对话交互与多轮追问**              | 百宝箱智能体提供自然语言对话能力，后端做不了对话 UI          | README §0.4  |
| 2    | **模型选择与推理**                      | 百宝箱内置大模型（如千问等），CareerPulse 后端不承担主对话推理 | README §3.3  |
| 3    | **系统 Prompt 托管**                    | 对话角色、行为约束、工具调用规则由平台 Prompt 控制           | README §10.9 |
| 4    | **知识库（岗位趋势/行业报告）检索**     | 平台提供知识库上传、分块、语义检索，后端无此能力             | README §11.5 |
| 5    | **MCP/API 工具注册与调用编排**          | 平台负责工具的注册、参数传递、连续调用和结果回传             | README §14.5 |
| 6    | **Web 发布（独立访问入口）**            | 百宝箱一键生成 Web 聊天页面                                  | README §15.4 |
| 7    | **小程序/H5 多端发布**                  | 支付宝/微信小程序发布依赖平台能力                            | README §15.4 |
| 8    | **对话流程编排（追问→工具→解释→推荐）** | 平台智能体控制"先问什么、何时调工具、如何解释结果"           | README §12.1 |

**关键约束**：百宝箱只负责"与用户交互 + 知识检索 + 调用工具 + 解释结果 + 多端发布"。**不负责真正的业务计算。**

---

## 4. 应由 CareerPulse 后端完成的内容

| #    | 应由后端完成                      | 原因                                                         |
| ---- | --------------------------------- | ------------------------------------------------------------ |
| 1    | **简历解析与结构化（File→JSON）** | 涉及 PDF/DOCX/OCR 处理，百宝箱工具无法做文件解析             |
| 2    | **确定性匹配算法**                | `Score(u,i) = Σ wk × min(Suk/Jik, 1)`，代码计算，不是 LLM    |
| 3    | **能力缺口与优先级计算**          | `Gapk = max(Jik - Suk, 0)`, `Priorityk = Gapk × wk / Difficultyk` |
| 4    | **3年/5年职业路径搜索**           | `PathScore = GrowthValue - TransferCost - AbilityGapCost` 图搜索 |
| 5    | **训练评分规则引擎**              | 基于规则或代码打分的训练评估，不依赖 LLM                     |
| 6    | **成长档案状态管理**              | 用户的能力变化、进度、历史版本持久化                         |
| 7    | **学习与岗位资源数据管理**        | 资源库的 CRUD 和推荐逻辑                                     |
| 8    | **统一 LLM 客户端**               | Agent 调用的模型推理（结构化输出、重试、降级）               |
| 9    | **Agent 编排后台**                | CareerOrchestrator 流程控制、6 Agent 节点调度                |
| 10   | **工具实现与 MCP/API 适配**       | 将 Service 封装为平台可调用的工具接口                        |
| 11   | **Agent 日志与可观测**            | tool_calls、duration_ms、fallback 记录                       |
| 12   | **Demo Mode 降级**                | 无外部模型时的固定数据返回                                   |

---

## 5. 可直接保留的模块

| #    | 模块                                                         | 文件                                        | 保留方式                                    |
| ---- | ------------------------------------------------------------ | ------------------------------------------- | ------------------------------------------- |
| 1    | **简历文件解析**（PDF/DOCX/TXT/图片文本提取）                | `services/resume_service.py`                | **原样保留**——这是纯工具函数，不依赖 LLM    |
| 2    | **前端布局框架**（DefaultLayout、路由骨架、Element Plus 主题） | `layouts/`, `router/`, `App.vue`            | **保留结构**——新增页面在现有框架上扩展      |
| 3    | **RadarChart 组件**（ECharts 能力雷达图）                    | `components/business/RadarChart.vue`        | **保留**——需适配新的指标格式                |
| 4    | **PathGraph 组件**（AntV X6 图谱画布）                       | `components/business/PathGraph.vue`         | **保留**——需适配 3年/5年路径数据            |
| 5    | **GrowthChart 组件**（ECharts 成长曲线）                     | `components/business/GrowthChart.vue`       | **保留**——直接用于成长档案                  |
| 6    | **用户认证体系**（登录/注册/Token）                          | `views/login/`, `stores/user.ts`            | **保留**——不在此次改造范围                  |
| 7    | **岗位库查询**（搜索/详情/图谱）                             | `routes/jobs.py`, `services/job_service.py` | **保留作为数据层**——Agent 通过 Service 复用 |
| 8    | **数据库基础设施**（PostgreSQL 连接、表管理）                | `db.py`, `config.py`                        | **保留**——新增表通过 migration              |
| 9    | **Mock API 层**                                              | `services/mockApi.ts`                       | **改造**——作为 Demo Mode 的基础             |
| 10   | **报告导出功能**（PDF/DOCX/TXT）                             | `services/report_service.py` (export 部分)  | **保留**——作为最终报告输出                  |

---

## 6. 必须改造和新增的模块

### 6.1 必须改造

| #    | 模块                  | 当前问题                             | 改造方向                                                     | 优先级 |
| ---- | --------------------- | ------------------------------------ | ------------------------------------------------------------ | ------ |
| 1    | **人岗匹配算法**      | LLM 直接计算匹配分，违反 A02 规范    | 改为确定性向量匹配：`Score = Σ wk × min(Suk/Jik, 1)`；LLM 仅做语义解释 | P0     |
| 2    | **学生画像**          | JSONB 存储，无结构化能力标签等级     | 增加能力标签体系（30-50个标签 + 5级评分）、证据提取、完整度计算 | P0     |
| 3    | **岗位画像**          | 有 skills 列表但无能力向量、无趋势   | 增加岗位能力向量、趋势数据关联                               | P0     |
| 4    | **ProfileAgent 逻辑** | 简历解析散落在 routes/students.py    | 抽取为 Agent，增加信息追问、完整度判断                       | P0     |
| 5    | **前端分析看板**      | 匹配分来自 LLM 一次性调用            | 改为调用 Agent 链路，展示维度分/gap/priority                 | P1     |
| 6    | **前端路径图谱**      | 展示所有关联岗位，非个人路径         | 改为展示 3年/5年个人路径，含阶段任务                         | P1     |
| 7    | **配置管理**          | API Key 硬编码在环境变量，无统一配置 | 增加 `core/config.py` 统一管理模型/平台/降级配置             | P1     |

### 6.2 必须新增

| #    | 模块                     | 说明                                                         | 优先级 |
| ---- | ------------------------ | ------------------------------------------------------------ | ------ |
| 1    | **CareerState**          | 跨 Agent 共享状态对象（session_id → 画像 → 匹配 → 路径 → 训练 → 反馈） | P0     |
| 2    | **BaseAgent**            | Agent 基类：统一输入/输出、日志、fallback                    | P0     |
| 3    | **CareerOrchestrator**   | 编排 6 Agent 顺序执行、状态流转、失败继续                    | P0     |
| 4    | **ProfileAgent**         | 画像生成 Agent：简历解析 + 能力标签 + 等级评估 + 证据提取    | P0     |
| 5    | **JobAgent**             | 岗位分析 Agent：JD 解析 + 能力向量 + 趋势分析                | P0     |
| 6    | **MatchAgent**           | 匹配 Agent：调用 MatchService 计算 gap/priority，解释结果    | P0     |
| 7    | **PathAgent**            | 路径 Agent：调用 PathService 搜索 3年/5年路径                | P1     |
| 8    | **TrainingAgent**        | 训练 Agent：生成训练题、调用评分、推荐资源                   | P1     |
| 9    | **FeedbackAgent**        | 反馈 Agent：保存反馈、更新成长档案、调整优先级               | P1     |
| 10   | **MatchService**（重写） | 确定性匹配算法：能力向量对齐 → 加权匹配分 → gap → priority   | P0     |
| 11   | **PathService**          | 图搜索路径：GrowthValue - TransferCost - AbilityGapCost      | P1     |
| 12   | **TrainingService**      | 三类训练生成 + 评分规则引擎（至少含 remote_collaboration/ai_office_task/cross_role_communication） | P1     |
| 13   | **FeedbackService**      | 反馈保存 + 成长档案更新 + 学习优先级调权                     | P1     |
| 14   | **ResourceService**      | 学习资源 + 岗位资源推荐                                      | P1     |
| 15   | **统一 LLM 客户端**      | OpenAI SDK 封装：结构化输出、JSON 校验、最大 2 次重试、Demo 兜底 | P0     |
| 16   | **MCP/API 工具适配层**   | 将 Service 封装为百宝箱可调用的 7 个工具接口                 | P0     |
| 17   | **Agent 日志服务**       | tool_calls、duration_ms、fallback_used、error 结构化日志     | P1     |
| 18   | **能力标签系统**         | 30-50 个标准化能力标签 + 5 级评分 + 权重体系                 | P0     |
| 19   | **数据库新表**           | ability_tags, career_graph（节点+边+权重）, training_records, learning_plans, growth_archives, agent_logs | P0     |
| 20   | **前端新页面**           | 职场训练页、Agent 执行链路页、学习进度页                     | P2     |
| 21   | **Demo Mode 开关**       | `A02_DEMO_MODE=true` → 全部 Agent 返回固定数据               | P2     |
| 22   | **评测脚本**             | 20-30 组评测集 + 结构化输出合法率 / 工具调用成功率等指标     | P2     |

---

## 7. 平台智能体和自建 Agent 的职责边界

```
┌─────────────────────────────────────────────────────────────┐
│                    百宝箱平台智能体                            │
│  • 与用户自然语言对话                                         │
│  • 系统 Prompt 控制对话风格和行为                              │
│  • 多轮追问、信息补全、画像完整度判断                           │
│  • 调用知识库检索（岗位趋势、行业报告）                          │
│  • 调用 MCP/API 工具（7个业务工具）                            │
│  • 工具调用编排：决定何时调、调哪个、连续调                     │
│  • 将工具返回的 JSON 结果翻译成用户可理解的自然语言              │
│  • Web/小程序多渠道发布                                       │
│  ─────────────────────────────────────────────────────────  │
│  ⚠ 不做：能力等级打分、匹配分计算、路径规划、训练评分            │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ MCP / HTTP API
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  CareerPulse 自建 Agent 层                    │
│  CareerOrchestrator → ProfileAgent → JobAgent →              │
│  MatchAgent → PathAgent → TrainingAgent → FeedbackAgent      │
│                                                              │
│  职责：                                                       │
│  • 接收平台工具调用 → 内部编排 → 返回结构化结果                 │
│  • CareerState 跨 Agent 状态管理                              │
│  • 统一 LLM 客户端（结构化输出、JSON 校验、重试、降级）          │
│  • Agent 日志记录（tool_calls / duration / fallback）         │
│  • Demo Mode 降级（无外部模型时返回固定数据）                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 内部调用
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  CareerPulse Service 层                       │
│  MatchService | PathService | TrainingService                 │
│  FeedbackService | ResourceService                            │
│                                                              │
│  职责：                                                       │
│  • 纯代码/规则计算（无 LLM）                                   │
│  • 匹配分 = Σ wk × min(Suk/Jik, 1)                           │
│  • PathScore = GrowthValue - TransferCost - AbilityGapCost   │
│  • 训练基础评分规则                                           │
│  • 反馈权重调整                                               │
└─────────────────────────────────────────────────────────────┘
```

**边界原则**：
- 百宝箱：管对话、管知识、管工具调度、管发布
- Agent 层：管编排、管状态、管 LLM 调用（限语义理解/解释/生成）
- Service 层：管计算（所有数字结果由代码产生）

---

## 8. 建议的 MCP/API 工具清单

| #    | 工具名称                               | 输入                                | 输出                                                         | 调用方 | 优先级 |
| ---- | -------------------------------------- | ----------------------------------- | ------------------------------------------------------------ | ------ | ------ |
| 1    | `analyze_student_profile`              | 简历文本/表单字段                   | 学生画像（能力标签+等级+证据+完整度+竞争力评分）             | 百宝箱 | P0     |
| 2    | `analyze_job_and_trend`                | 岗位名称/岗位ID                     | 岗位画像（能力向量+权重+技能趋势+发展空间评估）              | 百宝箱 | P0     |
| 3    | `calculate_job_match`                  | student_id + job_id                 | 匹配分+4维度得分+能力缺口+提升优先级+自然语言解释            | 百宝箱 | P0     |
| 4    | `recommend_career_path`                | student_id + job_id                 | 3年路径+5年路径（节点+阶段任务+所需能力+推荐理由）           | 百宝箱 | P1     |
| 5    | `generate_and_score_training`          | student_id + job_id + training_type | 训练题+评分维度+参考答案+评分规则；提交回答后返回分数+维度分+改进建议 | 百宝箱 | P1     |
| 6    | `recommend_learning_and_job_resources` | gap_list + target_job               | 学习资源+岗位资源+证书建议                                   | 百宝箱 | P1     |
| 7    | `save_growth_feedback`                 | session_id + ratings                | 反馈保存+成长档案更新+学习优先级调整                         | 百宝箱 | P1     |

**每个工具的通用要求**：
- 固定 JSON Schema 输入输出（与百宝箱配置一致）
- 参数校验 + 错误码（`code: 0/-1`, `message`, `request_id`, `data`, `error`）
- 超时控制（建议 30s）
- 日志不记录完整简历文本（隐私）

---

## 9. 建议的知识库清单

| #    | 知识库名称             | 内容                                                         | 用途                                               | 来源                                   |
| ---- | ---------------------- | ------------------------------------------------------------ | -------------------------------------------------- | -------------------------------------- |
| 1    | **岗位技能趋势库**     | 目标行业（如互联网/AI/金融）的高频技能变化、技能要求演变；近12个月招聘数据摘要 | 百宝箱回答"这个岗位未来怎么样"、"什么技能在变重要" | 公开招聘报告 + 行业白皮书 + 清洗后导入 |
| 2    | **行业与职业发展资料** | 目标行业的发展报告、岗位晋升路径、薪资趋势                   | 百宝箱检索后解释职业发展趋势和AI替代风险           | 行业研究报告                           |
| 3    | **学习资源索引**       | 课程平台、证书体系、实践项目推荐                             | 百宝箱回答"学什么"、"考什么证"                     | 整理后导入                             |
| 4    | **岗位能力要求标准**   | 常见岗位的能力标签、等级要求、权重分布                       | 百宝箱解释岗位要求和能力缺口原因                   | 基于 job_type_profile 清洗             |
| 5    | **AI 职业伦理规范**    | 职业建议免责声明、AI结果仅供参考提示、隐私保护要求           | 百宝箱对话中的伦理合规引导                         | 自编                                   |

**知识库元数据要求**：每份文档注明来源、时间、行业标签。

---

## 10. 两名技术成员的任务边界

### 成员 1（技术负责人/Agent架构与平台集成）

| 职责域         | 具体任务                                                     |
| -------------- | ------------------------------------------------------------ |
| **架构决策**   | 总体技术方案、CareerState 协议、接口契约、能力标签体系       |
| **Agent 层**   | CareerOrchestrator、BaseAgent、ProfileAgent、JobAgent、MatchAgent、PathAgent、TrainingAgent、FeedbackAgent |
| **LLM 工程**   | 统一 LLM 客户端、结构化输出 Schema、JSON 校验+重试、Prompt 模板 |
| **平台集成**   | 百宝箱智能体创建、系统 Prompt、工具注册/字段映射、知识库配置、Web 发布 |
| **工具层**     | 工具 Schema 定义、工具注册、平台字段映射                     |
| **前端改造**   | 原有页面适配 + 新增训练页/Agent链路页/学习进度页             |
| **Demo/评测**  | Demo Mode、Agent 评测设计、百宝箱平台评测                    |
| **演示**       | 最终演示流程设计、录像、材料核对                             |
| **文件所有权** | `backend/app/agents/`, `orchestrator/`, `schemas/`, `core/`, `platform/`, `api/career_agent_api.py`；`front/`；`docs/a02/03-05,07,10-13` |

### 成员 2（后端能力与工程质量负责人）

| 职责域           | 具体任务                                                     |
| ---------------- | ------------------------------------------------------------ |
| **数据层**       | 能力标签体系数据（30-50个）、学生样例（3份）、岗位样例（3个）、职业图谱（10-20节点+边）、训练题（10道）、资源（10条） |
| **Service 层**   | MatchService（确定算法重写）、PathService（图搜索）、TrainingService（评分规则）、FeedbackService（权重调整）、ResourceService |
| **数据库**       | 新表模型+迁移、数据初始化脚本                                |
| **MCP/API 适配** | 将 Service 封装为平台工具接口、参数校验、超时控制            |
| **部署**         | 公网 HTTPS 部署、Docker、跨域配置                            |
| **测试**         | Service 单元测试、接口测试、知识库导入测试                   |
| **文件所有权**   | `backend/app/services/`, `models/`, `data/`, `tools/`, `mcp/`, `migrations/`, `tests/`, `scripts/`；`docs/a02/06,14,17` |

### 协作边界
- **公共契约**：由成员1定义，成员2实现，共同联调
- **每日同步**：拉取→测试→主链路→检查工具字段→合并小模块
- **不可越界**：成员2不碰前端和 Agent 编排；成员1不写 Service 内部算法

---

## 11. 10 天开发路线

| 日期     | 阶段              | 成员1（Agent/平台）                                          | 成员2（Service/数据）                                        | 联调                             | 产出物                                        |
| -------- | ----------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | -------------------------------- | --------------------------------------------- |
| **D1**   | 双审计            | 阅读仓库+A02+平台；输出差距矩阵和边界                        | 整理数据库+后端现状；确认平台MCP方式                         | 共同确认职责边界和10天分工       | Hermes审计报告、Codex审计报告、差距矩阵       |
| **D2**   | 公共契约+Mock骨架 | CareerState + BaseAgent + CareerOrchestrator + Mock 6 Agent链路 + 百宝箱创建智能体 + 系统Prompt V1 + 1个Mock工具 | 能力标签数据 + 3学生/3岗位样例 + 职业图谱Mock + DB新表 + Mock工具API | 夜间合并，百宝箱首次工具调用测试 | API契约、工具Schema、DB结构、平台项目截图     |
| **D3-4** | 画像+岗位+趋势    | 统一LLM客户端 + ProfileAgent + JobAgent + 趋势Prompt + JSON校验+重试 + 百宝箱追问流程配置 + 知识库创建+导入 | MatchService重写（确定性算法） + 标签归一化 + 趋势知识数据清洗 + 知识库导入文件 | D4晚百宝箱追问→画像→趋势工具联调 | 3份画像JSON、3份岗位画像JSON、知识库检索测试  |
| **D5**   | 匹配+路径         | MatchAgent + PathAgent + CareerState流转 + 百宝箱三工具注册（match/path/profile） | PathService（图搜索+评分） + 职业图谱数据完善                | D5晚画像→匹配→路径完整对话       | 3组匹配案例、3组3年/5年路径、平台工具连续调用 |
| **D6**   | 训练+反馈+资源    | TrainingAgent + FeedbackAgent + 训练Prompt + 资源推荐接入 + 百宝箱训练/反馈/资源工具配置 | TrainingService（3类训练+评分规则） + FeedbackService + ResourceService | D6晚训练→评分→反馈完整对话       | 3类训练题、完整交互+评分、反馈→优先级变化     |
| **D7**   | MCP/API正式接入   | 百宝箱正式工具配置（删除Mock） + 字段映射 + 系统Prompt V2 + 工具选择规则 + 完整对话测试 | MCP/API适配层 + 公网HTTPS部署 + 鉴权 + 参数校验 + 超时控制   | D7全部7工具真实调用              | 至少5工具正式可调用、完整对话录像             |
| **D8**   | Web+多端发布      | 前端改造（训练页+Agent链路页+学习进度页） + 百宝箱Web发布 + 移动端适配 + 小程序预览 | 后端稳定性 + Docker + 接口回归 + 跨域                        | D8 Web + 百宝箱双端可用          | 改造前后对比、Web发布链接、移动端截图         |
| **D9**   | 评测              | Agent评测设计 + 知识库评测 + 百宝箱平台评测 + AI伦理检查     | pytest/接口测试 + 评测集执行 + bug修复                       | 评级报告和材料核对               | 评测报告、测试报告、伦理检查表                |
| **D10**  | 演示冻结          | 固定主案例 + 固定演示流程 + 备用录屏 + 材料核对 + 不修新功能 | 后端稳定保证 + 数据冻结 + 备用应急脚本                       | 最终跑一遍完整链路               | 完整运行视频、Git版本标签、提交材料           |

---

## 12. 主要风险

| #    | 风险                                                         | 严重度 | 缓解措施                                                     | 来源                        |
| ---- | ------------------------------------------------------------ | ------ | ------------------------------------------------------------ | --------------------------- |
| 1    | **百宝箱 MCP 接入方式不确定**——平台可能不支持标准 MCP，只支持 HTTP/插件等方式 | 🔴 高   | D1 立即登录平台确认；若不支持 MCP 则用 HTTP API 适配；如实记录在材料中 | README §14.3 已提及此风险   |
| 2    | **对外服务的公网 HTTPS 部署延迟**——百宝箱调用工具需要公网可达、HTTPS | 🔴 高   | 成员2 D2 即开始评估部署方案（ngrok/云服务器/内网穿透）；D7 前完成 | 来自平台调用后端的基本要求  |
| 3    | **LLM 结构化输出不稳定**——JSON 格式错误、字段缺失、幻觉      | 🟡 中   | Pydantic 校验 + max 2 次重试 + 规则/Demo 兜底；不低于 D3 实现 | README §2.4 明确要求        |
| 4    | **百宝箱模型/知识库/工具数量限制**——平台可能有 Quota 限制    | 🟡 中   | D1 确认平台限制；根据实际限制调整知识库和工具数量            | 来自平台实际能力            |
| 5    | **匹配算法从 LLM 迁移到确定性算法，结果不一致**——新旧结果差异可能引起前端展示问题 | 🟡 中   | D2 设计公式时与旧结果校验；Demo Mode 保证可重复              | 来自现有代码依赖 LLM 匹配分 |
| 6    | **现有代码字段与新增 Schema 冲突**——改造时破坏原有接口       | 🟡 中   | 公共契约（API_CONTRACTS.md）先行；每次合并前运行回归；禁止修改原有公共字段 | README §AGENTS.md 规则      |
| 7    | **职业图谱/训练数据不足**——数据量小导致路径/训练质量差       | 🟡 中   | D2 成员2准备最低数据量（10-20节点、10题）；标注"样例数据"    | README §10.6 最低数据要求   |
| 8    | **前端改造量大导致 D8 延期**——新增 3 页面 + 改造 5 页面      | 🟡 中   | D5 开始并行做前端改造；优先改造而非新建                      | 来自前端现有 8 页面的改造量 |
| 9    | **小程序发布权限未开通**——支付宝/微信小程序可能需要审核      | 🔵 低   | D1 确认权限；若无法发布则截图"预览模式"，材料如实说明        | README §15.4                |
| 10   | **隐私泄露**——日志/截图/代码中包含真实简历信息               | 🔴 高   | D1 起使用匿名样例数据；日志脱敏；截图前检查；不 commit 任何真实简历 | README §AGENTS.md 隐私规则  |
| 11   | **Demo Mode 与正式模式混淆**——材料声称的功能实际由 Demo 数据冒充 | 🔴 高   | Demo 页面明确标记"演示数据"；材料不把 Demo 结果写成"真实运行" | README §15.3                |

---

## 下一步建议

1. **立即**：登录 `https://b.tbox.cn` 确认百宝箱权限和工具接入方式（**当前最大不确定性**）
2. **立即**：启动系统 `cd D:\vue\CareerPulse-Pro && 启动前后端`，跑通现有主流程并截图
3. **今日内**：将本审计报告保存为 `docs/a02/02_GAP_ANALYSIS.md`
4. **今日内**：确认公网 HTTPS 部署方案（云服务器/ngrok/其他）
