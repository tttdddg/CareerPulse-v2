# 04_API_CONTRACTS — 公共数据契约

## 阶段3统一领域 Schema（增量，不替换冻结字段）

阶段3新增请求、领域、响应三层 Pydantic Schema。现有 `CareerState.student_profile`、
`job_profile`、`trend_result` 字段及阶段2 Agent 输出保持兼容；后续 Service 负责从旧结构
映射到统一领域结构，Schema 层不执行评分、趋势推断或 LLM 调用。

- 固定能力维度仅由 `AbilityDimension` 定义：专业知识、技术与工具、项目实践、沟通协作、
  问题解决、学习成长、行业认知。
- `AbilityDimensionProfile` 同时供统一学生画像与岗位画像使用，包含 `dimension`、`tags`、
  `level`（1-5）、`confidence`（0-1）、`evidence[]`、`evidence_source`。
- `evidence_source` 可标记 `resume`、`form`、`project`、`assessment`、
  `job_description`、`knowledge_base`、`user_supplement`、`history` 或 `demo`；
  ProfileAgent 更新画像时用 `history` 保留已有画像中的可验证证据。
- 请求层：`StudentProfileRequest`、`JobProfileRequest`、`CareerTrendRequest`。
- 领域层：`StudentProfile`、`JobProfile`、`CareerTrend`。
- 响应层：泛型 `AgentResponse[T]`，统一承载状态、数据、摘要、fallback 与错误信息。
- `profile_completeness` 范围为 0-1；`career_competitiveness_score` 范围为 0-100，分数必须
  由确定性 Service 提供，不能由 Schema 或 LLM 自行计算。


> **锁定状态：FROZEN（D2 冻结）**
> 本文件定义的字段名、类型、枚举值不得随意修改。
> 修改本文件须同时更新：`05_AGENT_CONTRACTS.md`、`13_MCP_TOOL_CATALOG.md`、后端 Schema 和百宝箱工具配置。
> 修改前须在 `decisions/` 下创建 ADR 记录原因。

---

## 0. 约定

- 所有字段名使用 **snake_case**（后端 / 数据库）
- 前端 API 请求/响应同样使用 snake_case（后端返回即前端消费）
- 数值字段：分数统一 `0.0–100.0`，等级统一 `1–5`，百分比统一 `0.0–1.0`
- 时间字段：ISO-8601 字符串 `"2026-08-04T14:30:00+08:00"`
- JSON Schema 中 `"required"` 字段不得删减

---

## 1. CareerState

CareerState 是跨 Agent 共享的会话级状态对象，由 CareerOrchestrator 持有并逐 Agent 更新。

```json
{
  "session_id": "string, required — 后端会话ID, e.g. sess-20260804-001",
  "platform_session_id": "string | null — 百宝箱会话ID, 首次对话时填充",
  "user_id": "string | null — 登录用户ID",
  "student_input": "object | null — 用户原始输入 {resume_text, form_fields, target_job}",
  "target_job_input": "object | null — 目标岗位 {job_id, job_title, industry}",
  "student_profile": "object | null — ProfileAgent 输出, 见 §2.1",
  "job_profile": "object | null — JobAgent 输出, 见 §3.1",
  "trend_result": "object | null — 趋势分析结果, 见 §3.2",
  "match_result": "object | null — MatchAgent 输出, 见 §4.1",
  "path_plan": "object | null — PathAgent 输出, 见 §5.1",
  "learning_plan": "object | null — 学习计划, 见 §5.2",
  "training_plan": "object | null — TrainingAgent 输出, 见 §6.1",
  "resource_result": "object | null — 资源推荐结果, 见 §6.2",
  "feedback_result": "object | null — FeedbackAgent 输出, 见 §7.1",
  "final_report": "object | null — 完整报告聚合",
  "agent_logs": "array — AgentLog[], 见 §8"
}
```

### 1.1 状态流转规则

```
student_input + target_job_input
  → ProfileAgent → student_profile
  → JobAgent → job_profile + trend_result
  → MatchAgent → match_result
  → PathAgent → path_plan + learning_plan
  → TrainingAgent → training_plan
  → (用户完成训练) → resource_result
  → FeedbackAgent → feedback_result
  → CareerOrchestrator → final_report
```

每个 Agent 执行前检查前置字段是否为 null；为 null 时跳过并记录 fallback。

---

## 2. 学生画像（StudentProfile）

### 2.1 结构

```json
{
  "student_id": "int | null",
  "name": "string — 匿名化姓名",
  "basic_info": {
    "education_level": "string — 专科/本科/硕士/博士",
    "major": "string",
    "graduation_year": "int | null",
    "target_job": "string",
    "target_industry": "string | null",
    "years_of_experience": "float | null"
  },
  "abilities": [
    {
      "tag": "string — 能力标签名, 必须来自能力标签体系 §11",
      "level": "int — 1-5, 见 §10",
      "confidence": "float — 0.0-1.0, 证据置信度",
      "evidence": "string — 证据文本摘要, 禁止包含手机号/邮箱/身份证"
    }
  ],
  "competitiveness_score": "float — 0.0-100.0, 综合竞争力评分",
  "completeness": "float — 0.0-1.0, 画像完整度",
  "missing_fields": ["string — 缺失信息字段名"]
}
```

### 2.2 约束

- `abilities` 至少包含 3 个标签，至多 30 个
- `level` 为 1-5 整数
- `confidence` < 0.3 的条目应在百宝箱对话中追问
- `completeness` < 0.5 时百宝箱应引导补充信息

---

## 3. 岗位画像（JobProfile / TrendResult）

### 3.1 JobProfile

```json
{
  "job_id": "int | null",
  "title": "string — 岗位名称",
  "normalized_title": "string — 归一化岗位名",
  "industry": "string",
  "required_abilities": [
    {
      "tag": "string — 能力标签名",
      "required_level": "int — 1-5",
      "weight": "float — 0.0-1.0, 该能力在岗位中的权重, 同一岗位所有权重之和为1.0",
      "importance": "string — critical / important / nice_to_have"
    }
  ],
  "soft_skills": ["string"],
  "salary_range": "string | null",
  "job_description": "string"
}
```

### 3.2 TrendResult（岗位趋势分析）

```json
{
  "job_title": "string",
  "industry": "string",
  "trend_summary": "string — 1-2句趋势总结",
  "hot_skills": ["string — 近期高频技能标签"],
  "rising_skills": ["string — 正在变重要的技能"],
  "declining_skills": ["string — 需求下降的技能"],
  "ai_risk_assessment": "string — low / medium / high",
  "ai_risk_detail": "string — AI替代风险说明",
  "development_opportunities": ["string"],
  "development_risks": ["string"],
  "data_source": "string — 知识库来源说明, 如 '基于2025Q4-2026Q1公开招聘数据' "
}
```

---

## 4. 匹配结果（MatchResult）

### 4.1 结构

```json
{
  "overall_score": "float — 0.0-100.0, 综合匹配度, 由 MatchService 代码计算",
  "match_level": "string — high / good / fair / weak / low / insufficient_data",
  "dimension_matches": [
    {
      "dimension": "string — 统一能力标签",
      "student_level": "int 1-5 | null — null 表示画像未提供，不等于0级",
      "required_level": "int — 1-5",
      "gap": "int >=0 | null — 仅学生等级已知时计算",
      "score": "float 0.0-100.0 | null",
      "weight": "float — 0.0-1.0",
      "student_evidence": "string | null",
      "job_evidence": "string | null",
      "confidence": "float 0.0-1.0 | null",
      "importance": "string — critical / important / nice_to_have",
      "status": "string — matched / gap / unknown / excluded"
    }
  ],
  "matched_skills": ["string — 达到要求的正权重能力"],
  "missing_skills": ["string — 岗位需要但学生画像未提供的正权重能力"],
  "skill_gaps": ["object — 有明确学生等级且低于岗位要求的能力差距、证据和优先级"],
  "hard_constraint_results": ["object — critical能力的passed/failed/unknown结论"],
  "confidence": "float — 0.0-1.0, 结果可靠度而非能力等级",
  "evidence": ["object — 按能力维度对齐的学生和岗位证据"],
  "calculation_version": "string — 固定为 deterministic-match-v2",
  "data_quality_flags": ["string — 画像缺失、低置信度等确定性标志"],
  "dimensions": [
    {
      "name": "string — 维度名称",
      "student_score": "float — 0.0-100.0",
      "job_required": "float — 0.0-100.0",
      "gap": "float — student_score - job_required, 负数表示不足",
      "weight": "float — 0.0-1.0"
    }
  ],
  "ability_gaps": [
    {
      "tag": "string — 能力标签",
      "current_level": "int — 0-5；0仅为旧兼容投影中的未知哨兵",
      "required_level": "int — 1-5",
      "gap": "int — required_level - current_level, ≥0",
      "priority": "int — 提升优先级, 1=最高, 正整数, 由 MatchService 计算"
    }
  ],
  "gap_analysis": [
    {
      "item": "string — 差距项描述",
      "status": "string — missing / insufficient / adequate",
      "suggestion": "string — 提升建议"
    }
  ],
  "strengths": ["string — 匹配优势项"],
  "matching_algorithm_version": "string — 固定为 'deterministic-v1' , 证明不是LLM计算"
}
```

### 4.2 匹配公式（确定性）

```
Score(u,i) = Σ wk × min(Suk / Jik, 1)
  其中:
    wk  = 岗位能力 k 的权重, Σwk = 1.0
    Suk = 学生能力 k 的等级 (1-5)
    Jik = 岗位要求能力 k 的等级 (1-5)

Gap_k    = max(Jik - Suk, 0)

Priority_k = Gap_k × wk × (1 / Difficulty_k)
  其中 Difficulty_k 为能力提升难度系数 (1.0-3.0)

已知维度集合 Kobs = 学生画像提供 level 且岗位 weight > 0 的能力维度
Score(u,i) = Σ(k∈Kobs) wk × min(Suk / Jik, 1) / Σ(k∈Kobs) wk

缺失能力: student_level / gap / score = null，不直接判定为0级；
可观测岗位权重 < 0.5 时 match_level = insufficient_data。
旧 ability_gaps.current_level=0 仅为 deterministic-v1 兼容投影。
```

> 匹配分 **严禁由 LLM 直接产出**。LLM 仅负责 `gap_analysis[].suggestion` 和 `strengths` 的自然语言生成。
> 阶段3加法扩展与缺失语义见 `decisions/ADR-001-stage3-match-result-extension.md`。

---

## 5. 路径规划（PathPlan / LearningPlan）

### 5.1 PathPlan

```json
{
  "target_job": "string",
  "plan_3year": {
    "phases": [
      {
        "phase": "int — 1-based",
        "duration_months": "int",
        "target_role": "string",
        "required_abilities": ["string"],
        "tasks": ["string"],
        "milestone": "string"
      }
    ],
    "total_score": "float — 路径评分, 由 PathService 计算"
  },
  "plan_5year": {
    "phases": [
      {
        "phase": "int",
        "duration_months": "int",
        "target_role": "string",
        "required_abilities": ["string"],
        "tasks": ["string"],
        "milestone": "string"
      }
    ],
    "total_score": "float"
  },
  "alternative_paths": [
    {
      "type": "string — vertical(纵向晋升) / lateral(横向转岗)",
      "target_role": "string",
      "score": "float",
      "reason": "string"
    }
  ],
  "path_algorithm_version": "string — 固定为 'graph-search-v1'"
}
```

### 5.2 LearningPlan

```json
{
  "phases": [
    {
      "phase": "int",
      "title": "string — 阶段标题 e.g. '第1阶段：基础能力补齐'",
      "tasks": [
        {
          "task_id": "string",
          "description": "string",
          "target_ability": "string — 关联能力标签",
          "estimated_hours": "int",
          "resources": ["string — 推荐资源URL或名称"]
        }
      ]
    }
  ],
  "certificate_suggestions": ["string"],
  "project_suggestions": ["string"]
}
```

### 5.3 路径评分公式

```
PathScore = GrowthValue - TransferCost - AbilityGapCost

GrowthValue       = Σ (目标岗位能力等级 × 该能力市场溢价系数)
TransferCost      = Σ (需要学习的新能力数 × 学习难度)
AbilityGapCost    = Σ (Gap_k × Difficulty_k)
```

### 5.4 阶段3确定性 PathResult（加法扩展）

PathService 独立返回以下结构；冻结 `path_plan` 仍保留，后续由 PathAgent 做兼容投影：

```json
{
  "status": "success / no_reachable_path / insufficient_data",
  "requested_horizon_years": "3 / 5",
  "candidate_paths": ["CandidatePath — 图谱节点序列、边、评分与数据标志"],
  "recommended_path": "CandidatePath | null",
  "alternative_paths": ["CandidatePath"],
  "path_scores": {"path_id": "PathScore"},
  "three_year_roadmap": "CareerRoadmap — 3个年度阶段",
  "five_year_roadmap": "CareerRoadmap — 5个年度阶段",
  "assumptions": ["string"],
  "risks": ["string"],
  "confidence": "float 0.0-1.0",
  "data_quality_flags": ["string"],
  "calculation_version": "deterministic-path-v1"
}
```

每个 `PathScore` 至少包含：`current_match_score/growth_value/transfer_cost/ability_gap_cost/`
`base_score/preference_adjustment/industry_continuity/region_fit/risk_penalty/`
`target_consistency/data_confidence/total_score`。

```text
base_score = growth_value - transfer_cost - ability_gap_cost
adjusted = base_score + preference + industry_continuity×5 + region_fit×5 - risk_penalty
total_score = adjusted × target_consistency
```

未知学生能力不按0级计 Gap；未知岗位不创建推断节点。具体决策见
`decisions/ADR-002-stage3-career-graph-and-roadmap.md`。

---

## 6. 训练（TrainingTask / TrainingScore）

### 6.1 TrainingTask

```json
{
  "training_id": "string",
  "type": "string — remote_collaboration / ai_office_task / cross_role_communication",
  "title": "string",
  "scenario": "string — 场景背景描述",
  "task_description": "string — 任务要求",
  "evaluation_criteria": [
    {
      "dimension": "string — 评分维度名",
      "max_score": "float",
      "weight": "float",
      "description": "string — 评分标准"
    }
  ],
  "reference_answer": "string | null — 参考答案要点"
}
```

### 6.2 TrainingScore（用户提交后返回）

```json
{
  "training_id": "string",
  "total_score": "float — 0.0-100.0",
  "dimension_scores": [
    {
      "dimension": "string",
      "score": "float",
      "comment": "string"
    }
  ],
  "overall_comment": "string — 综合评价",
  "improvement_suggestions": ["string"],
  "ability_updates": [
    {
      "tag": "string",
      "level_change": "int — -1 / 0 / +1"
    }
  ]
}
```

---

## 7. 反馈（FeedbackResult / GrowthArchive）

### 7.1 FeedbackResult

```json
{
  "session_id": "string",
  "satisfaction": "int — 1-5, 用户总体满意度",
  "path_rating": "int | null — 1-5",
  "training_rating": "int | null — 1-5",
  "resource_rating": "int | null — 1-5",
  "comments": "string | null",
  "updated_priorities": [
    {
      "tag": "string",
      "old_priority": "int",
      "new_priority": "int",
      "reason": "string"
    }
  ],
  "growth_archive_updated": "bool"
}
```

### 7.2 GrowthArchive（成长档案快照）

```json
{
  "user_id": "string",
  "snapshot_time": "string — ISO-8601",
  "abilities": [
    {
      "tag": "string",
      "level": "int — 1-5",
      "updated_at": "string — ISO-8601"
    }
  ],
  "competitiveness_score": "float",
  "completed_trainings": "int",
  "completed_phases": "int",
  "growth_trend": "string — improving / stable / declining"
}
```

---

## 8. AgentLog

```json
{
  "session_id": "string",
  "agent_name": "string — ProfileAgent / JobAgent / MatchAgent / PathAgent / TrainingAgent / FeedbackAgent",
  "status": "string — success / partial / failed",
  "summary": "string — 1句话摘要",
  "duration_ms": "int",
  "tool_calls": [
    {
      "tool_name": "string",
      "input_summary": "string — 禁止包含完整简历文本",
      "output_summary": "string",
      "duration_ms": "int",
      "status": "string — success / error"
    }
  ],
  "fallback_used": "bool",
  "error": "string | null",
  "timestamp": "string — ISO-8601"
}
```

> 隐私约束：`input_summary` 和 `output_summary` 中**不得出现**手机号、邮箱、身份证号、完整简历文本。

---

## 9. 统一错误格式

### 9.1 后端 API 响应

```json
{
  "code": "int — 0=成功, 非0=错误",
  "message": "string — 人类可读消息",
  "request_id": "string — 请求追踪ID",
  "data": "object | null — 成功时携带数据",
  "error": "object | null — 失败时携带详情"
}
```

### 9.2 Agent 统一返回格式

```json
{
  "agent_name": "string",
  "status": "string — success / partial / failed",
  "data": "object | null",
  "summary": "string",
  "duration_ms": "int",
  "tool_calls": "array",
  "fallback_used": "bool",
  "error": "string | null"
}
```

### 9.3 百宝箱 Tool 统一返回格式

```json
{
  "code": "int — 0=成功",
  "message": "string",
  "request_id": "string — UUID, 后端生成",
  "data": "object | null",
  "error": "object | null — {type: string, detail: string}"
}
```

### 9.4 错误码约定

| code | 含义 |
|------|------|
| 0 | 成功 |
| -1 | 通用错误 |
| -2 | 参数校验失败 |
| -3 | 资源不存在（学生/岗位/报告） |
| -4 | LLM 调用失败（返回 fallback） |
| -5 | 数据库错误 |
| -6 | 超时 |

---

## 10. 能力等级范围

**统一 5 级评分**，适用范围：学生画像、岗位要求、能力缺口。

| Level | 含义 | 描述 |
|-------|------|------|
| 1 | 入门 | 了解基本概念，无实践经验 |
| 2 | 初级 | 能在指导下完成任务 |
| 3 | 中级 | 能独立完成任务，有一定深度 |
| 4 | 高级 | 能带领小团队完成任务，有深入理解 |
| 5 | 专家 | 行业领先水平，能指导和创新 |

**映射**：
- `current_level` / `required_level` 均为 1-5 整数
- 缺失能力时 `current_level = 0`（仅 Gap 计算中使用，画像中不存在 level=0 标签）
- `competitiveness_score` 是 0.0–100.0 的浮点数，由能力等级加权计算得出

---

## 11. 能力标签体系

### 11.1 分类

能力标签按 5 个一级类别组织。标签名使用中文，**标签名是全局唯一标识**，新增不删旧。

#### A. 技术硬技能（Hard Skills）

| 标签 | 难度系数 | 说明 |
|------|---------|------|
| Python | 1.5 | Python 编程 |
| Java | 1.5 | Java 编程 |
| JavaScript/TypeScript | 1.3 | 前端语言 |
| SQL/数据库 | 1.2 | 数据库查询与设计 |
| Linux/运维 | 1.8 | 系统运维 |
| Docker/K8s | 2.0 | 容器与编排 |
| 云计算 | 2.0 | AWS/Azure/阿里云 |
| 数据分析 | 1.5 | pandas/Excel/BI |
| 机器学习 | 2.5 | ML算法与框架 |
| 深度学习 | 3.0 | DL/NLP/CV |
| 大模型应用 | 2.5 | LLM应用开发/RAG/Agent |
| 前端开发 | 1.5 | Vue/React |
| 后端开发 | 2.0 | Spring/FastAPI/Django |
| 移动端开发 | 2.0 | iOS/Android/Flutter |
| 测试/QA | 1.3 | 自动化测试 |

#### B. 产品与业务能力（Product & Business）

| 标签 | 难度系数 | 说明 |
|------|---------|------|
| 需求分析 | 1.5 | 需求调研与文档 |
| 产品规划 | 2.0 | 产品路线图与策略 |
| 用户研究 | 1.8 | 用户访谈与洞察 |
| 数据驱动决策 | 1.8 | 用数据支持业务判断 |
| 商业分析 | 2.0 | 商业模式与市场分析 |
| 项目管理 | 1.5 | 敏捷/Scrum/进度管理 |

#### C. 通用素养（Soft Skills）

| 标签 | 难度系数 | 说明 |
|------|---------|------|
| 沟通表达 | 1.5 | 口头与书面表达 |
| 团队协作 | 1.2 | 跨团队合作 |
| 领导力 | 2.5 | 团队管理与激励 |
| 解决问题 | 1.5 | 分析与解决问题能力 |
| 学习能力 | 1.0 | 快速掌握新知识 |
| 时间管理 | 1.0 | 优先级与效率 |
| 抗压能力 | 1.5 | 高压环境适应 |

#### D. 行业知识（Domain Knowledge）

| 标签 | 难度系数 | 说明 |
|------|---------|------|
| 互联网金融 | 2.0 | 金融科技领域 |
| 电子商务 | 1.5 | 电商行业 |
| 企业服务/SaaS | 1.5 | B2B软件 |
| 游戏行业 | 1.8 | 游戏开发与运营 |
| 人工智能 | 2.5 | AI行业知识 |
| 教育培训 | 1.2 | 在线教育 |

#### E. 职业资质（Certifications）

| 标签 | 难度系数 | 说明 |
|------|---------|------|
| 软考认证 | 1.5 | 计算机技术与软件专业技术资格 |
| PMP | 2.0 | 项目管理专业认证 |
| 计算机等级考试 | 1.0 | 全国计算机等级考试 |
| 行业认证 | 1.5 | AWS/华为/思科等 |

### 11.2 管理规则

- **新增**：可以新增标签，不可删除已有标签（数据中有引用）
- **废弃**：标记 `deprecated: true` 但保留标签名
- **标签名唯一**：不区分中英文括号和空格，统一为中文括号
- **最低数据**：初始至少包含上述 40 个标签

---

## 12. Demo 数据格式

### 12.1 触发方式

- 环境变量 `A02_DEMO_MODE=true`（后端）
- 环境变量 `VITE_DEMO_MODE=true`（前端）
- 请求头 `X-Demo-Mode: true`

### 12.2 Demo 数据要求

```json
{
  "demo_mode": "bool — true, 必须在响应中显式标示",
  "demo_notice": "string — 固定为 '当前为演示模式，数据为示例数据，不代表真实评估结果'"
}
```

Demo Mode 下：
- Agent 返回固定数据，不调用外部 LLM
- Agent 日志正常生成（标记 `demo: true`）
- 前端页面明确显示"演示数据"水印或标签
- **禁止**将 Demo 数据冒充为真实平台测试结果

### 12.3 Demo 固定数据

```json
{
  "student_profile_demo": {
    "name": "林思然（演示）",
    "basic_info": {
      "education_level": "本科",
      "major": "信息管理与信息系统",
      "graduation_year": 2025,
      "target_job": "AI产品经理",
      "target_industry": "人工智能"
    },
    "abilities": [
      {"tag": "Python", "level": 3, "confidence": 0.85, "evidence": "完成数据挖掘课程项目"},
      {"tag": "数据分析", "level": 3, "confidence": 0.80, "evidence": "用户行为分析实习"},
      {"tag": "产品规划", "level": 2, "confidence": 0.70, "evidence": "参与校园产品设计竞赛"},
      {"tag": "用户研究", "level": 3, "confidence": 0.75, "evidence": "用户调研课程项目"},
      {"tag": "沟通表达", "level": 3, "confidence": 0.80, "evidence": "课程汇报与团队项目"}
    ],
    "competitiveness_score": 42.0,
    "completeness": 0.60,
    "missing_fields": ["实习经历详情", "项目经历详情"]
  },
  "job_profile_demo": {
    "title": "AI产品经理",
    "industry": "人工智能",
    "required_abilities": [
      {"tag": "产品规划", "required_level": 4, "weight": 0.25, "importance": "critical"},
      {"tag": "需求分析", "required_level": 4, "weight": 0.20, "importance": "critical"},
      {"tag": "数据驱动决策", "required_level": 3, "weight": 0.15, "importance": "important"},
      {"tag": "大模型应用", "required_level": 3, "weight": 0.15, "importance": "important"},
      {"tag": "用户研究", "required_level": 3, "weight": 0.10, "importance": "important"},
      {"tag": "沟通表达", "required_level": 4, "weight": 0.10, "importance": "nice_to_have"},
      {"tag": "项目管理", "required_level": 2, "weight": 0.05, "importance": "nice_to_have"}
    ]
  },
  "match_result_demo": {
    "overall_score": 48.5,
    "dimensions": [
      {"name": "专业技能", "student_score": 55.0, "job_required": 75.0, "gap": -20.0, "weight": 0.60},
      {"name": "学习能力", "student_score": 70.0, "job_required": 65.0, "gap": 5.0, "weight": 0.15},
      {"name": "实践能力", "student_score": 45.0, "job_required": 75.0, "gap": -30.0, "weight": 0.15},
      {"name": "通用素养", "student_score": 68.0, "job_required": 70.0, "gap": -2.0, "weight": 0.10}
    ],
    "ability_gaps": [
      {"tag": "产品规划", "current_level": 2, "required_level": 4, "gap": 2, "priority": 1},
      {"tag": "大模型应用", "current_level": 0, "required_level": 3, "gap": 3, "priority": 1},
      {"tag": "需求分析", "current_level": 0, "required_level": 4, "gap": 4, "priority": 2},
      {"tag": "数据驱动决策", "current_level": 0, "required_level": 3, "gap": 3, "priority": 2}
    ]
  }
}
```

---

## 13. 版本记录

| 日期 | 版本 | 变更 | 作者 |
|------|------|------|------|
| 2026-08-04 | v1.0 | 初始冻结：CareerState、统一错误格式、能力等级、能力标签体系、Demo格式 | 技术负责人 |

> **后续修改本文件的流程**：
> 1. 在 `decisions/` 创建 ADR 记录变更原因
> 2. 更新本文件和关联文档
> 3. 通知成员2更新 Service 和工具
> 4. 通知百宝箱更新工具 Schema
