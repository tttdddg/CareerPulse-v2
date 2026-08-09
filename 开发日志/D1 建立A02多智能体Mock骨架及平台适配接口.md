已完成 A02 多智能体 Mock 骨架与平台适配接口。所有改动均在允许目录内，未修改 Service、数据库模型、原路由或原公共 Schema，也未提交 Git。

### 实现内容

- `CareerState` 与冻结契约中的全部共享字段

- `BaseAgent`、统一 `AgentResult`、`AgentLog`、`ToolCallLog`

- 六个顺序执行的 Mock Agent：

  - ProfileAgent
  - JobAgent
  - MatchAgent
  - PathAgent
  - TrainingAgent
  - FeedbackAgent

- ```
  CareerOrchestrator
  ```

  - 顺序执行
  - 前置依赖检查
  - Agent 异常 fallback
  - fallback 自身失败也会记录并继续
  - 内存保存会话和 Agent 日志
  - 聚合生成 `final_report`

- 确定性 Mock 匹配和路径分数，不由 LLM 生成

- 日志仅记录字段摘要，不记录简历正文

- 独立 Agent HTTP API

- 百宝箱 Mock 工具统一响应包络

- 成功、失败、缺失输入、日志脱敏和路由测试

### 新增文件

编排与状态：

- [career_state.py](D:/vue/CareerPulse-Pro/backend/app/orchestrator/career_state.py)
- [career_orchestrator.py](D:/vue/CareerPulse-Pro/backend/app/orchestrator/career_orchestrator.py)
- [orchestrator/__init__.py](D:/vue/CareerPulse-Pro/backend/app/orchestrator/__init__.py)

Agent：

- [base_agent.py](D:/vue/CareerPulse-Pro/backend/app/agents/base_agent.py)
- [profile_agent.py](D:/vue/CareerPulse-Pro/backend/app/agents/profile_agent.py)
- [job_agent.py](D:/vue/CareerPulse-Pro/backend/app/agents/job_agent.py)
- [match_agent.py](D:/vue/CareerPulse-Pro/backend/app/agents/match_agent.py)
- [path_agent.py](D:/vue/CareerPulse-Pro/backend/app/agents/path_agent.py)
- [training_agent.py](D:/vue/CareerPulse-Pro/backend/app/agents/training_agent.py)
- [feedback_agent.py](D:/vue/CareerPulse-Pro/backend/app/agents/feedback_agent.py)
- [agents/__init__.py](D:/vue/CareerPulse-Pro/backend/app/agents/__init__.py)

API 与平台适配：

- [career_agent_api.py](D:/vue/CareerPulse-Pro/backend/app/api/career_agent_api.py)
- [api/__init__.py](D:/vue/CareerPulse-Pro/backend/app/api/__init__.py)
- [tbox_adapter.py](D:/vue/CareerPulse-Pro/backend/app/platform/tbox_adapter.py)
- [platform/__init__.py](D:/vue/CareerPulse-Pro/backend/app/platform/__init__.py)

测试：

- [test_mock_career_flow.py](D:/vue/CareerPulse-Pro/backend/app/platform/tests/test_mock_career_flow.py)
- [tests/__init__.py](D:/vue/CareerPulse-Pro/backend/app/platform/tests/__init__.py)

没有创建 `backend/app/schemas/` 包，避免遮蔽现有 [schemas.py](D:/vue/CareerPulse-Pro/backend/app/schemas.py)，从而影响原公共接口。

### 新接口

Agent API：

- `POST /api/career-agent/run`
- `GET /api/career-agent/session/{session_id}`
- `GET /api/agent/logs/{session_id}`

独立启动入口：

```
cd backend
uvicorn app.api.career_agent_api:app
```

百宝箱 Mock 工具：

- `POST /api/tbox/mock-career-analysis`
- 返回 `{code, message, request_id, data, error}`
- 发生 fallback 时返回 `code=-4`
- 无法执行时返回脱敏的 `code=-1` 错误包络

独立启动入口：

```
cd backend
uvicorn app.platform.tbox_adapter:app
```

### 测试结果

执行：

```
$env:PYTHONPATH='backend'
python -B -m unittest discover -s backend\app\platform\tests -p 'test_*.py' -v
```

结果：`7 tests, OK`

覆盖：

- 六 Agent 完整顺序执行
- `final_report` 生成
- Agent 执行失败后的 fallback
- fallback 自身失败后仍继续生成报告
- 完全缺少输入时全链路继续
- 日志不包含简历正文
- 百宝箱工具成功响应
- 百宝箱工具失败响应
- 独立 FastAPI 路由存在

### Diff 摘要

- 新增文件：17
- 新增代码：约 827 行
- 禁止目录变更：无
- `__pycache__`：已清理
- Git 提交：未执行

已知限制：新接口以独立 FastAPI `app` 暴露，没有挂载进原 [main.py](D:/vue/CareerPulse-Pro/backend/app/main.py)，因为原路由属于本任务禁止修改范围。另外，验证旧 `app.main` 导入时发现当前 Python 环境缺少既有依赖 `psycopg2`；本次未安装依赖，也未修改 `requirements.txt`。