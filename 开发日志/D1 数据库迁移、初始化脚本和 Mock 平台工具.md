已完成 A02 基础数据、数据库迁移、初始化脚本和 Mock 平台工具。未使用真实个人隐私数据，未修改白名单外文件，未提交 Git。

### 数据成果

- 能力标签：43 个，覆盖冻结的 5 类标签
- 匿名学生：3 份，名称仅为“演示学生 A/B/C”
- 岗位样例：3 个
  - AI产品经理
  - 数据分析师
  - 后端开发工程师
- 每个岗位能力权重之和严格为 `1.0`
- 职业图谱：10 个节点、16 条边
- 训练题：10 道，覆盖全部 3 种训练类型
- 演示资源：12 条，使用 `example.com` 占位地址并标记 `demo_only`

### 新增文件

基础数据：

- [ability_tags.json](D:/vue/CareerPulse-Pro/backend/app/data/ability_tags.json)
- [students_demo.json](D:/vue/CareerPulse-Pro/backend/app/data/students_demo.json)
- [jobs_demo.json](D:/vue/CareerPulse-Pro/backend/app/data/jobs_demo.json)
- [career_graph.json](D:/vue/CareerPulse-Pro/backend/app/data/career_graph.json)
- [training_tasks.json](D:/vue/CareerPulse-Pro/backend/app/data/training_tasks.json)
- [resources.json](D:/vue/CareerPulse-Pro/backend/app/data/resources.json)

验证模型：

- [a02_models.py](D:/vue/CareerPulse-Pro/backend/app/models/a02_models.py)
- [models/__init__.py](D:/vue/CareerPulse-Pro/backend/app/models/__init__.py)

数据库：

- [V001__create_a02_tables.sql](D:/vue/CareerPulse-Pro/backend/migrations/V001__create_a02_tables.sql)
- [init_a02_data.py](D:/vue/CareerPulse-Pro/backend/scripts/init_a02_data.py)

Mock 工具：

- [mock_tools.py](D:/vue/CareerPulse-Pro/backend/app/tools/mock_tools.py)

### 数据库迁移

迁移包含 9 张冻结数据字典中的新增表：

- `ability_tags`
- `student_ability_records`
- `career_graph_nodes`
- `career_graph_edges`
- `training_records`
- `learning_plans`
- `growth_archives`
- `agent_logs`
- `user_feedback`

迁移使用增量 `CREATE TABLE IF NOT EXISTS`，没有修改既有表字段，并包含显式 ROLLBACK 注释。

初始化脚本的数据库写入是幂等的：

- 能力标签按 `tag` upsert
- 职业节点按 `node_key` upsert
- 职业边通过存在性检查防止重复

实际写库需要显式提供数据库连接：

```
$env:A02_DATABASE_URL = "postgresql://..."
python backend\scripts\init_a02_data.py --apply
```

匿名学生和岗位样例只保存在 JSON 中，没有强行写入结构未知且要求保留的旧表。

### Mock 平台工具

提供统一入口：

```
from app.tools.mock_tools import call_mock_tool

response = call_mock_tool(
    "calculate_job_match",
    {
        "session_id": "demo-session",
        "student_id": 90003,
        "job_id": 91002,
    },
)
```

实现冻结目录中的 7 个工具：

- `analyze_student_profile`
- `analyze_job_and_trend`
- `calculate_job_match`
- `recommend_career_path`
- `generate_and_score_training`
- `recommend_learning_and_job_resources`
- `save_growth_feedback`

所有工具：

- 返回 `{code, message, request_id, data, error}`
- 明确返回 `demo_mode` 和演示声明
- 匹配分和路径分使用确定性规则
- 不调用外部 LLM
- 保存内存调用日志
- 日志只记录字段名，不记录简历或用户回答正文

### 初始化检查

执行：

```
python -B backend\scripts\init_a02_data.py --check
```

结果：

```
ability_tags: 43
students: 3
jobs: 3
career_nodes: 10
career_edges: 16
training_tasks: 10
resources: 12
migration_tables: 9
privacy_check: passed
mock_tool_success_failure_check: passed (7 tools)
```

检查覆盖：

- JSON 和 Pydantic Schema
- 岗位权重总和
- 标签唯一性和交叉引用
- 图谱节点/边引用
- 三种训练类型覆盖
- 邮箱、手机号和身份证号扫描
- 7 个平台工具各自的成功与失败路径
- 迁移表完整性和 ROLLBACK 注释

Diff 摘要：新增 11 个文件，约 919 行；白名单外变更为 0，无缓存文件。实际 PostgreSQL `--apply` 未执行，因为没有提供 `A02_DATABASE_URL`。