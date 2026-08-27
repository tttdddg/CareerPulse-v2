# 阶段 5 百宝箱接入前接口清单

**适用阶段**: 阶段 5（百宝箱平台接入）  
**版本**: v1.0  
**日期**: 2026-08-24  
**状态**: 内部开发完成， awaiting 平台接入

---

## 接口总览

| 工具名称 | 用途 | 外部输入参数 | 返回结果 | 依赖当前 session | 对应内部 Agent / Service |
|----------|------|-------------|----------|-----------------|-------------------------|
| `generate_training` | 生成训练任务 | session_id, training_type | training_task | 是 - 从 session 读取 skill_gaps | TrainingAgent / TrainingService |
| `score_training` | 评分训练答案 | session_id, training_id, user_answer | training_score + feedback | 是 - 从 session 读取 task 和 context | TrainingAgent / TrainingService |
| `recommend_resources` | 推荐学习资源 | session_id | learning_resources[] | 是 - 从 session 读取 skill_gaps 和 job | TrainingAgent / ResourceService |
| `save_feedback` | 保存成长反馈 | session_id, satisfaction, ratings, comments | growth_snapshot + priority_updates | 是 - 从 session 读取 gaps/scores/targets | FeedbackAgent / FeedbackService |

---

## 详细接口定义

### 1. generate_training

**用途**: 为用户生成一个训练任务

**外部输入参数**:
```json
{
  "session_id": "string (required) - CareerPulse 会话 ID",
  "training_type": "string (required) - 训练类型",
  "training_type 可选项": [
    "remote_collaboration",
    "ai_office_task",
    "cross_role_communication"
  ]
}
```

**返回结果**:
```json
{
  "success": true,
  "data": {
    "mode": "generate",
    "training_task": {
      "training_id": "train-xxx",
      "type": "remote_collaboration",
      "title": "任务标题",
      "scenario": "场景描述",
      "task_description": "任务说明",
      "evaluation_criteria": [...],
      "target_abilities": ["能力 1", "能力 2"],
      "reference_answer": "参考答案"
    }
  },
  "message": "训练任务生成成功"
}
```

**依赖当前 session**:
- ✅ 是 - 从 CareerState.match_result.skill_gaps 读取能力缺口
- ✅ 是 - 从 CareerState.job_profile.title 读取目标岗位
- 内部逻辑：TrainingService 根据 gaps 选择最匹配的训练任务

**对应内部组件**:
- Agent: TrainingAgent
- Service: TrainingService
- 数据库操作：持久化 training_plan 到 CareerState

---

### 2. score_training

**用途**: 对用户训练答案进行评分

**外部输入参数**:
```json
{
  "session_id": "string (required) - CareerPulse 会话 ID",
  "training_id": "string (required) - 训练任务 ID（来自 generate_training 返回）",
  "user_answer": "string (required) - 用户训练答案"
}
```

**返回结果**:
```json
{
  "success": true,
  "data": {
    "mode": "score",
    "training_score": {
      "training_id": "train-xxx",
      "total_score": 85.5,
      "dimension_scores": [
        {"dimension": "信息完整", "score": 90.0, "comment": "..."},
        {"dimension": "异步友好", "score": 80.0, "comment": "..."},
        {"dimension": "责任清晰", "score": 85.0, "comment": "..."}
      ],
      "overall_comment": "整体表现优秀，训练目标达成度高。",
      "improvement_suggestions": ["建议补充..."],
      "ability_updates": [
        {"tag": "远程协作", "level_change": 1},
        {"tag": "时间管理", "level_change": 1}
      ]
    },
    "natural_language_feedback": {
      "commentary": "自然语言反馈...",
      "strengths": ["优势 1", "优势 2"],
      "next_steps": ["改进步骤 1", "改进步骤 2"]
    }
  },
  "message": "训练评分完成"
}
```

**依赖当前 session**:
- ✅ 是 - 从 CareerState.training_plan 读取 training_task
- ✅ 是 - 从 CareerState 读取当前训练上下文
- 内部逻辑：TrainingAgent 调用 LLM 分析覆盖度 → TrainingService 计算分数

**对应内部组件**:
- Agent: TrainingAgent
- Service: TrainingService
- 数据库操作：更新 CareerState.training_plan 中的 latest_score

---

### 3. recommend_resources

**用途**: 推荐学习资源

**外部输入参数**:
```json
{
  "session_id": "string (required) - CareerPulse 会话 ID"
}
```

**返回结果**:
```json
{
  "success": true,
  "data": {
    "resource_result": {
      "learning_resources": [
        {
          "title": "资源标题",
          "type": "course|certificate|project",
          "url": "https://...",
          "target_ability": "Python",
          "description": "资源描述"
        },
        // ... 最多 10 条
      ],
      "certificate_suggestions": ["证书 1", "证书 2"],
      "data_quality_flags": ["job_resources_unavailable"]
    }
  },
  "message": "资源推荐完成"
}
```

**依赖当前 session**:
- ✅ 是 - 从 CareerState.match_result.skill_gaps 读取能力缺口（按优先级排序）
- ✅ 是 - 从 CareerState.job_profile.title 读取目标岗位
- 内部逻辑：ResourceService 根据 gaps 顺序匹配资源

**对应内部组件**:
- Agent: TrainingAgent（调用 ResourceService）
- Service: ResourceService
- 数据库操作：持久化 resource_result 到 CareerState

---

### 4. save_feedback

**用途**: 保存用户对训练的成长反馈

**外部输入参数**:
```json
{
  "session_id": "string (required) - CareerPulse 会话 ID",
  "satisfaction": "integer (required) - 总体满意度 1-5",
  "path_rating": "integer (optional) - 职业路径评分 1-5",
  "training_rating": "integer (optional) - 训练任务评分 1-5",
  "resource_rating": "integer (optional) - 资源推荐评分 1-5",
  "comments": "string (optional) - 反馈意见（不允许包含隐私信息）"
}
```

**返回结果**:
```json
{
  "success": true,
  "data": {
    "feedback_result": {
      "feedback_saved": true,
      "growth_archive_updated": true,
      "updated_priorities": [
        {
          "tag": "数据分析",
          "old_priority": 2,
          "new_priority": 1,
          "reason": "训练反馈低，需优先补齐"
        }
      ],
      "growth_snapshot": {
        "competitiveness_score": 66.5,
        "completed_trainings": 0,
        "completed_phases": 0,
        "growth_trend": "improving|stable|declining"
      },
      "data_quality_flags": ["low_satisfaction_recorded"]
    },
    "natural_language_summary": "反馈已保存，成长档案已更新。"
  },
  "message": "成长反馈保存成功"
}
```

**依赖当前 session**:
- ✅ 是 - 从 CareerState.match_result.skill_gaps 读取能力缺口
- ✅ 是 - 从 CareerState.match_result.overall_score 读取竞争力分数
- ✅ 是 - 从 CareerState 读取 latest_training_target_abilities
- ✅ 是 - 从 CareerState.student_profile 读取 abilities
- 内部逻辑：FeedbackService 计算 priority 调整和 growth trend

**对应内部组件**:
- Agent: FeedbackAgent
- Service: FeedbackService
- 数据库操作：持久化 feedback_result 到 CareerState

---

## 调用示例（百宝箱配置）

### 示例 1: 生成训练任务

```yaml
tool:
  name: generate_training
  description: 为用户生成职场模拟训练任务
  endpoints:
    http: POST https://career-pulse.example.com/api/bbx/v1/tools/generate_training
    mcp: career_pulse.generate_training
  
  request_schema:
    type: object
    required:
      - session_id
      - training_type
    properties:
      session_id:
        type: string
        description: CareerPulse 会话 ID（来自用户首次对话）
      training_type:
        type: string
        enum: [remote_collaboration, ai_office_task, cross_role_communication]
        description: 训练类型
  
  response_schema:
    type: object
    properties:
      success:
        type: boolean
      data:
        type: object
        properties:
          mode:
            type: string
          training_task:
            type: object
```

### 示例 2: 评分训练答案

```yaml
tool:
  name: score_training
  description: 对用户的训练答案进行评分
  endpoints:
    http: POST https://career-pulse.example.com/api/bbx/v1/tools/score_training
    mcp: career_pulse.score_training
  
  request_schema:
    type: object
    required:
      - session_id
      - training_id
      - user_answer
    properties:
      session_id:
        type: string
      training_id:
        type: string
      user_answer:
        type: string
        description: 用户的训练回答
```

### 示例 3: 推荐学习资源

```yaml
tool:
  name: recommend_resources
  description: 推荐个性化学习资源
  endpoints:
    http: POST https://career-pulse.example.com/api/bbx/v1/tools/recommend_resources
    mcp: career_pulse.recommend_resources
  
  request_schema:
    type: object
    required:
      - session_id
    properties:
      session_id:
        type: string
```

### 示例 4: 保存成长反馈

```yaml
tool:
  name: save_feedback
  description: 保存用户对训练流程的反馈
  endpoints:
    http: POST https://career-pulse.example.com/api/bbx/v1/tools/save_feedback
    mcp: career_pulse.save_feedback
  
  request_schema:
    type: object
    required:
      - session_id
      - satisfaction
    properties:
      session_id:
        type: string
      satisfaction:
        type: integer
        minimum: 1
        maximum: 5
      path_rating:
        type: integer
        minimum: 1
        maximum: 5
      training_rating:
        type: integer
        minimum: 1
        maximum: 5
      resource_rating:
        type: integer
        minimum: 1
        maximum: 5
      comments:
        type: string
```

---

## 会话依赖关系图

```
用户首次对话
    │
    ▼
CareerPulse 初始化 CareerState
    │
    ├── session_id (自动生成)
    ├── platform_session_id (来自百宝箱)
    ├── user_id (来自百宝箱登录态)
    │
    └── 阶段 1-3 链路 (Profile→Job→Match→Path)
            │
            ▼
        match_result.skill_gaps
        job_profile.title
        student_profile.abilities
            │
            ▼
    阶段 4 工具就绪
            │
            ├── generate_training → training_plan
            ├── score_training → training_plan.latest_score
            ├── recommend_resources → resource_result
            └── save_feedback → feedback_result
```

---

## 错误处理

### 通用错误 envelope

```json
{
  "success": false,
  "error_code": "TRAINING_NOT_FOUND",
  "message": "训练任务不存在",
  "details": {
    "training_id": "train-unknown"
  }
}
```

### 已知错误码

| 错误码 | HTTP 状态 | 含义 | 是否可重试 |
|--------|----------|------|-----------|
| SESSION_NOT_FOUND | 404 | 会话不存在 | 否 - 需重新初始化 |
| TRAINING_NOT_FOUND | 404 | 训练任务不存在 | 否 - 需重新生成 |
| MATCH_RESULT_NOT_FOUND | 409 | 前置匹配未完成 | 否 - 需先执行阶段 3 |
| PRIVACY_VIOLATION | 422 | 输入包含隐私信息 | 否 - 需修改输入 |
| VALIDATION_FAILED | 422 | 请求参数验证失败 | 否 - 需修正参数 |
| SERVICE_ERROR | 500 | Service 层内部错误 | 是 - 可重试 |
| DATABASE_ERROR | 503 | 数据库写入失败 | 是 - 可重试 |
| TIMEOUT | 504 | 处理超时 | 是 - 可重试 |

---

## 幂等性保证

所有工具均支持幂等性：

- `generate_training`: 相同 session_id + training_type 返回相同任务
- `score_training`: 相同 session_id + training_id + user_answer 返回相同分数
- `recommend_resources`: 相同 session_id 返回相同资源列表
- `save_feedback`: 相同 session_id + 满意度 可多次调用（更新而非追加）

---

## 调用顺序约束

```
正确顺序:
  1. generate_training (生成任务)
  2. 用户完成训练
  3. score_training (评分)
  4. recommend_resources (推荐资源 - 可选)
  5. 用户学习资源
  6. save_feedback (反馈)

错误顺序:
  - score_training 在 generate_training 之前 → TRAINING_NOT_FOUND
  - recommend_resources 在 Match 完成之前 → MATCH_RESULT_NOT_FOUND
  - save_feedback 在 training 完成之前 → 可能缺失 training_target_abilities
```

---

## 平台接入注意事项

### 百宝箱配置项

1. **工具注册**:
   - 工具名称：固定为四个名称
   - operationId: 与 FastAPI router 的 operationId 对应
   - 请求/响应 Schema: 使用 Pydantic 模型 JSON Schema

2. **认证配置**:
   - Bearer Token: `A02_TBOX_API_TOKEN` 环境变量
   - Session 绑定：session_id 与 platform_session_id 映射

3. **超时设置**:
   - 推荐超时：25 秒（与现有 platform_tool_timeout_seconds 一致）
   - 重试策略：503/504 错误可重试，其他错误直接返回

4. **日志与监控**:
   - 工具调用日志：记录到 CareerPulse 本地数据库
   - Agent 执行日志：记录到 AgentLog 表
   - 错误追踪：通过 tool_call_id 关联

### 不需要百宝箱配置的内容

- ❌ 不需要理解 skill_gaps 计算逻辑
- ❌ 不需要理解 training_task 选择算法
- ❌ 不需要理解 ResourceService 匹配逻辑
- ❌ 不需要理解 FeedbackService priority 调整
- ❌ 不需要访问 CareerState 内部结构
- ❌ 不需要直接调用 MatchService/PathService

---

## 开发与测试环境

### 本地开发

```bash
# 启动 FastAPI 后端
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 运行测试
python -m pytest tests/test_stage4_internal_tools.py -v
```

### 环境要求

- Python 3.11+
- FastAPI 0.100+
- Pydantic 2.0+
- SQLite (开发) / PostgreSQL (生产)

---

## 下一步行动

1. **阶段 5 任务 1**: 配置百宝箱工具注册
2. **阶段 5 任务 2**: 设置 Bearer Token 认证
3. **阶段 5 任务 3**: 配置生产环境数据库
4. **阶段 5 任务 4**: 端到端测试（百宝箱 → CareerPulse）
5. **阶段 5 任务 5**: 性能测试和负载测试

---

**文档维护**: 修改本文件需同步更新 `04_API_CONTRACTS.md` 和 `13_MCP_TOOL_CATALOG.md`  
**最后更新**: 2026-08-24 (D4 验收通过)