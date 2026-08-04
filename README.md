# CareerPulse-Pro开发规范

# 0\. 定位

## 0\.1 项目名称

**CareerPulse：面向未来工作的AI职业导航与终身学习伙伴系统**

## 0\.2 改造目标

在原CareerPulse已有的简历解析、学生画像、岗位画像、人岗匹配、职业路径图谱、职业报告和历史记录等功能基础上，升级为完整的AI职业成长Agent系统。

系统核心业务闭环为：

```Plain Text
用户信息和简历采集
→ 动态职业能力画像
→ 岗位能力与职业趋势分析
→ 人岗匹配与能力缺口诊断
→ 3—5年个性化职业路径
→ 学习任务和资源推荐
→ 职场模拟训练
→ 训练评分和用户反馈
→ 成长档案与路径动态更新
```

项目既要满足A02赛题要求，也要能够作为“大模型应用开发／AI Agent方向”的核心简历项目，真实体现：

```Plain Text
蚂蚁百宝箱企业版智能体开发
多智能体编排
大模型结构化输出
Tool Calling / MCP
确定性业务算法
职业知识库
状态管理
运行日志与可观测
Agent评测
异常降级
多端发布
完整产品落地
```

## 0\.3 最终系统形态

项目采用“指定平台智能体 \+ 自建业务能力 \+ Web可视化系统”的混合架构。

```Plain Text
用户
  ↓
蚂蚁百宝箱企业版
  ├─ 职业成长伙伴智能体
  ├─ 自然语言交互
  ├─ 用户信息追问
  ├─ 职业知识库检索
  ├─ MCP/API工具调用
  ├─ 对话流程与结果解释
  └─ Web及其他渠道发布
              ↓
CareerPulse业务能力层
  ├─ ProfileAgent / 学生画像服务
  ├─ JobAgent / 岗位与趋势分析服务
  ├─ MatchAgent / 人岗匹配服务
  ├─ PathAgent / 路径规划服务
  ├─ TrainingAgent / 职场训练服务
  ├─ FeedbackAgent / 成长反馈服务
  └─ ResourceService / 学习与岗位资源服务
              ↓
PostgreSQL / Redis / 职业知识库
              ↓
CareerPulse Vue可视化系统
  ├─ 能力雷达图
  ├─ 职场匹配度
  ├─ 能力缺口和提升优先级
  ├─ 3年/5年职业路径
  ├─ 学习进度和训练记录
  └─ 成长轨迹与Agent执行日志
```

## 0\.4 三部分职责

原则上：

```Plain Text
百宝箱负责“与用户交互和调用能力”
CareerPulse后端负责“真实计算和业务状态”
CareerPulse Web负责“完整产品展示”
```

---

# A02赛题要求与项目实现映射

## 1\.1 感知：用户状态采集

A02要求系统能够采集用户状态。

CareerPulse实现：

```Plain Text
简历上传
个人基础信息
学习经历
项目经历
技能证书
兴趣偏好
目标岗位
训练记录
用户反馈
```

百宝箱负责：

```Plain Text
通过对话补充追问缺失信息
判断画像完整度
引导用户完善目标岗位和成长目标
```

## 1\.2 认知：职业趋势分析

CareerPulse实现：

```Plain Text
岗位JD解析
岗位能力向量
行业趋势知识库
岗位技能变化分析
岗位需求趋势摘要
职业发展机会与风险
```

不能只分析“用户适合什么岗位”，还应回答：

```Plain Text
目标岗位未来是否具有发展空间
近期高频技能是什么
哪些能力正在变得重要
哪些能力可能被AI替代
```

## 1\.3 决策：路径规划

CareerPulse实现：

```Plain Text
人岗匹配度
能力缺口
能力提升优先级
3年职业路径
5年职业路径
纵向晋升路线
横向转岗路线
```

## 1\.4 生成：学习内容与建议

CareerPulse实现：

```Plain Text
阶段学习计划
实践任务
项目建议
证书建议
职场训练题
学习资源推荐
岗位准备建议
```

## 1\.5 执行：任务提醒与资源对接

CareerPulse实现：

```Plain Text
阶段任务清单
预计完成时间
学习进度状态
训练任务
学习资源入口
岗位资源入口
任务完成记录
```

平台不支持主动提醒时，可由CareerPulse Web中的任务中心实现，并在材料中如实说明。

## 1\.6 反馈：效果评估与动态调整

CareerPulse实现：

```Plain Text
训练得分
用户满意度
推荐岗位反馈
职业路径反馈
学习计划反馈
任务完成情况
能力等级变化
成长档案更新
路径重新排序
```

---

# 总体开发原则

## 2\.1 不推翻原项目

本次不是重新开发一个系统，而是在原CareerPulse基础上进行垂直升级。

优先保留：

```Plain Text
原有用户与登录体系
简历上传和文本提取
岗位库和岗位详情
学生画像页面
人岗匹配页面
岗位图谱页面
职业报告页面
个人中心和历史记录
Vue3 / FastAPI / PostgreSQL / Redis技术栈
```

重点改造：

```Plain Text
普通学生画像
→ 动态职业能力画像

普通岗位画像
→ 岗位能力向量和职业趋势画像

LLM直接给匹配分
→ 确定性匹配算法 + LLM解释

岗位图谱展示
→ 基于能力缺口的3年/5年路径搜索

一次性报告
→ 学习计划 + 任务执行 + 训练 + 反馈更新

普通API调用
→ 百宝箱智能体 + Tool Calling / MCP
```

重点新增：

```Plain Text
百宝箱主智能体
百宝箱知识库
平台工具配置
CareerOrchestrator
六个专业Agent节点
职业趋势分析
三类职场训练
资源推荐
成长反馈
Agent运行日志
Agent离线评测
Demo Mode
Web和其他渠道发布
```

## 2\.2 百宝箱是必做平台，不是最后补充

开发第一天即应完成：

```Plain Text
登录比赛报名平台
确认百宝箱权限
登录百宝箱企业版
查看平台操作指引
确认模型、知识库、工具和发布能力
```

相关地址：

```Plain Text
百宝箱企业版：
https://b.tbox.cn

官方操作文档：
https://alipaytbox.yuque.com/sxs0ba/huntb8/boxfq2nzvs3stt7a

报名与作品提交：
https://tournament.cloudlab.top/zhejiangpv
```

百宝箱具体菜单、MCP接入方法和发布流程，以报名后详情页及平台实际界面为准。

## 2\.3 不做六个机器人自由聊天

材料中可以称为“多智能体协同”，代码中采用更稳定的结构：

```Plain Text
一个CareerOrchestrator
+
六个职责明确的Agent节点
+
确定性Service和Tool
+
共享CareerState
```

流程：

```Plain Text
ProfileAgent
→ JobAgent
→ MatchAgent
→ PathAgent
→ TrainingAgent
→ FeedbackAgent
```

职责：

```Plain Text
ProfileAgent：
使用大模型解析简历、表单和经历，生成学生能力画像。

JobAgent：
使用大模型解析岗位JD和行业资料，生成岗位画像与趋势分析。

MatchAgent：
调用确定性MatchService，计算匹配分、能力缺口和提升优先级。

PathAgent：
调用PathService，根据职业图谱生成3年和5年路径。

TrainingAgent：
生成职场训练任务，调用TrainingService完成评分。

FeedbackAgent：
保存用户反馈，更新学习优先级和成长档案。
```

## 2\.4 大模型不负责凭空计算

以下结果必须由代码或规则计算：

```Plain Text
综合匹配度
各维度得分
能力缺口
提升优先级
路径评分
学习进度
训练基础评分
```

大模型主要负责：

```Plain Text
语义解析
信息归纳
结果解释
训练任务生成
改进建议生成
自然语言交互
```

---

# Hermes、Codex和百宝箱的角色

## 3\.1 Hermes：项目技术总控助手

Hermes主要负责：

```Plain Text
理解旧项目
分析A02差距
检查百宝箱适配遗漏
制定每日任务
评审系统架构
维护长期开发上下文
识别过度设计
检查材料和代码是否一致
进行阶段复盘
```

Hermes原则：

```Plain Text
先分析
先给方案
重要决策写入仓库文档
不直接大范围修改代码
不与Codex同时修改同一批文件
```

## 3\.2 Codex：代码执行与审查助手

Codex主要负责：

```Plain Text
读取仓库
修改指定文件
新增Agent和Service
实现MCP Server
生成数据库模型和迁移
写测试
修复Bug
运行命令
检查Git diff
进行代码审查
```

Codex使用原则：

```Plain Text
一次只交一个明确任务
规定允许修改的文件
规定禁止修改的文件
提供固定输入输出
明确验收标准
完成后运行测试
输出diff摘要
不要自动提交Git
```

## 3\.3 百宝箱：正式运行和发布平台

百宝箱负责：

```Plain Text
创建CareerPulse职业成长伙伴
配置模型
配置系统Prompt
配置对话流程
创建和使用知识库
配置MCP或API工具
运行完整对话
发布Web服务
验证其他可选渠道
```

百宝箱不是帮助写代码的工具，而是A02项目必须实际运行的平台。

## 3\.4 推荐组合流程

```Plain Text
Hermes分析赛题、平台和仓库
→ 你确认方案
→ 决策写入docs
→ Codex修改后端或前端代码
→ 人工检查diff
→ Codex运行测试
→ 部署业务工具
→ 百宝箱配置和调用工具
→ 保存平台截图和日志
→ Hermes进行阶段复盘
```

---

# 两名技术成员分工

## 4\.1 你的定位

**技术负责人／Agent架构与平台集成负责人**

你负责所有决定系统整体结构、智能体运行逻辑、平台配置和最终演示的工作。

### 你负责

```Plain Text
A02总体技术方案
百宝箱平台调研
百宝箱智能体创建
百宝箱系统Prompt
百宝箱工具与知识库配置
CareerState
公共Schema与接口契约
CareerOrchestrator
六个Agent的流程编排
ProfileAgent
JobAgent
统一LLM客户端
结构化输出校验
工具Schema与工具注册
MCP/API平台接入
Agent日志与可观测
Agent评测
前端页面改造
前后端联调
多端发布
最终演示
```

## 4\.2 成员2定位

**后端能力与工程质量负责人**

成员2不负责前端，也不决定整体Agent架构，主要负责可以独立开发、独立测试和被平台调用的底层能力。

### 成员2负责

```Plain Text
能力标签体系
岗位、学生和职业图谱样例
知识库数据整理
MatchService
PathService
TrainingService
FeedbackService
ResourceService
数据库模型和迁移
数据初始化
MCP Server底层实现
后端HTTPS部署
Service单元测试
知识库测试
接口测试
Docker和环境配置
Swagger / Postman样例
```

## 4\.3 分工边界

---

# 仓库准备

正式开发前建立以下目录。

```Plain Text
docs/
  a02/
    01_REQUIREMENTS.md
    02_GAP_ANALYSIS.md
    03_ARCHITECTURE.md
    04_API_CONTRACTS.md
    05_AGENT_CONTRACTS.md
    06_DATA_DICTIONARY.md
    07_EVAL_PLAN.md
    08_DEMO_SCENARIO.md
    09_TASKS.md

    10_TBOX_REQUIREMENTS.md
    11_TBOX_AGENT_CONFIG.md
    12_TBOX_SYSTEM_PROMPT.md
    13_MCP_TOOL_CATALOG.md
    14_KNOWLEDGE_BASE_PLAN.md
    15_PLATFORM_TEST_PLAN.md
    16_MULTI_END_RELEASE.md
    17_RESOURCE_CONNECTOR.md
    18_AI_ETHICS.md

    decisions/
      ADR-001-agent-architecture.md
      ADR-002-ability-vector.md
      ADR-003-tool-calling.md
      ADR-004-tbox-integration.md
      ADR-005-platform-backend-boundary.md

    daily/
      YYYY-MM-DD.md

evidence/
  architecture/
  api/
  algorithms/
  agent-logs/
  prompts/
  mcp/
  knowledge-base/
  tbox/
    project/
    agent-config/
    model-config/
    system-prompt/
    knowledge-base/
    tools/
    tool-calls/
    run-tests/
    web-release/
    mini-program/
    errors/
  tests/
  evaluations/
  screenshots/
  demo/
```

---

# AGENTS\.md开发规则

```Markdown
# CareerPulse A02 Development Rules

## Project goal

Upgrade CareerPulse into an AI career navigation and lifelong
learning companion based on Ant TBox Enterprise.

## Architecture

- Preserve stable existing CareerPulse functions.
- Ant TBox is a mandatory runtime and publishing platform.
- CareerOrchestrator controls the internal workflow.
- Agent handles reasoning and workflow decisions.
- Service handles deterministic calculations.
- Tool exposes reusable business capability.
- API/MCP exposes tools to Ant TBox and frontend.
- LLM output must be validated using Pydantic or JSON Schema.
- Match scores, gap analysis and path scores must not be invented by LLM.
- Every Agent and platform tool call must have a log.
- External model and tool failures require fallback.
- Demo Mode must work without external model APIs.
- Do not claim a platform capability unless it is actually configured and tested.

## Collaboration

- Public schemas are owned by the technical lead.
- Do not change public fields without updating API_CONTRACTS.md.
- Do not modify another member's files without approval.
- Do not rename database fields without migration.
- Platform tool schemas and backend schemas must remain consistent.

## Privacy

- Never commit real resume private information.
- Never log full resume text in platform or Agent logs.
- Mask phone numbers, emails, names and identity information.
- Never expose tokens or API keys in screenshots.

## Quality

- Every new Service requires tests.
- Every platform tool requires success and failure tests.
- Run tests after every task.
- Report modified files, tests and known risks.
- Do not automatically commit Git changes.
```

---

# Git与协作方式

## 7\.1 分支

```Plain Text
upgrade/a02
最终集成分支

feat/a02-agent-platform
你的开发分支

feat/a02-services
成员2开发分支
```

使用两个worktree：

```Bash
git worktree add ../careerpulse-agent-platform \
  -b feat/a02-agent-platform upgrade/a02

git worktree add ../careerpulse-services \
  -b feat/a02-services upgrade/a02
```

## 7\.2 目录所有权

### 你负责

```Plain Text
frontend/

backend/app/agents/
backend/app/orchestrator/
backend/app/api/career_agent_api.py
backend/app/schemas/
backend/app/core/llm_client.py
backend/app/core/config.py
backend/app/platform/

docs/a02/03_ARCHITECTURE.md
docs/a02/04_API_CONTRACTS.md
docs/a02/05_AGENT_CONTRACTS.md
docs/a02/07_EVAL_PLAN.md
docs/a02/10_TBOX_REQUIREMENTS.md
docs/a02/11_TBOX_AGENT_CONFIG.md
docs/a02/12_TBOX_SYSTEM_PROMPT.md
docs/a02/13_MCP_TOOL_CATALOG.md
```

### 成员2负责

```Plain Text
backend/app/services/
backend/app/models/
backend/app/data/
backend/app/tools/
backend/app/mcp/
backend/migrations/
backend/tests/
backend/scripts/

docs/a02/06_DATA_DICTIONARY.md
docs/a02/14_KNOWLEDGE_BASE_PLAN.md
docs/a02/17_RESOURCE_CONNECTOR.md
```

### 共同修改但由你审核

```Plain Text
backend/app/main.py
requirements.txt
docker-compose.yml
.env.example
README.md
```

## 7\.3 合并频率

```Plain Text
每天同步一次公共契约
每完成一个Service就合并一次
每完成一个Agent节点就联调一次
每完成一个平台工具就进行一次百宝箱测试
每天晚上跑一次当前完整链路
```

不能等到最后一天再统一合并。

---

# 总体开发阶段

推荐按照10个开发日推进。

```Plain Text
阶段0：原项目与百宝箱双审计
阶段1：公共契约、Mock链路与平台骨架
阶段2：学生画像、岗位分析和职业趋势
阶段3：人岗匹配、能力缺口和职业路径
阶段4：职场训练、任务执行、资源推荐和反馈
阶段5：MCP/API正式接入百宝箱
阶段6：Web系统与多端发布
阶段7：Agent、知识库、平台和算法评测
阶段8：演示冻结与证据整理
```

---

# 阶段0：原项目与百宝箱双审计

## 时间

```Plain Text
D1
共同完成
```

## 目标

确认原项目已有能力、百宝箱实际能力和两者的职责边界，避免代码开发完成后才发现平台不支持某种接入方式。

## 9\.1 共同完成

```Plain Text
启动现有前后端 √
跑一遍现有主流程
用hermes/codex：
列出现有页面
列出现有接口
列出现有数据库表
找到简历解析逻辑
找到岗位画像逻辑
找到匹配逻辑
找到路径图谱逻辑
找到报告生成逻辑

登录比赛报名平台 √
查看A02报名详情 √
获取百宝箱试用权限 √和Token说明
登录百宝箱企业版 √
查看可选模型
查看知识库入口
查看智能体或工作流配置
查看工具/MCP接入方式
查看Web发布方式
查看小程序权限
```

## 9\.2 你负责

```Plain Text
确定原系统可保留模块
确定百宝箱和CareerPulse职责边界
确定平台主智能体设计
确定首批工具清单
确定知识库清单
确定平台发布路线
```

## 9\.3 成员2负责

```Plain Text
整理数据库和数据现状
整理后端可复用Service
阅读百宝箱MCP和工具说明
确认公网HTTPS部署要求
确认知识库数据来源
```

## 9\.4 Hermes审计提示词

```Plain Text
请作为CareerPulse A02升级项目的技术总顾问。

请读取：
1. 当前CareerPulse仓库
2. A02赛题要求
3. 我提供的蚂蚁百宝箱平台截图和操作说明

暂时不要修改代码。

请输出：
1. 当前前端、后端、数据库能力清单
2. A02要求与现有系统差距矩阵
3. 必须由百宝箱完成的内容
4. 应由CareerPulse后端完成的内容
5. 可直接保留的模块
6. 必须改造和新增的模块
7. 平台智能体和自建Agent的职责边界
8. 建议的MCP/API工具清单
9. 建议的知识库清单
10. 两名技术成员的任务边界
11. 10天开发路线
12. 主要风险

约束：
- 百宝箱不能被写成可选项
- 不要为了多智能体过度设计
- 不要修改代码
- 明确哪些结论来自现有代码，哪些来自平台实际能力
```

## 9\.5 Codex仓库审计提示词

```Plain Text
读取AGENTS.md和当前仓库。

暂时不要修改任何文件。

请输出：
1. 前后端入口和路由结构
2. 现有数据库模型
3. 简历、岗位、匹配、路径、报告代码位置
4. 现有测试覆盖
5. 可以封装为平台工具的现有函数
6. 可能受A02改造影响的公共接口
7. 最小风险改造顺序
8. 需要增加的MCP/API适配层

请给出精确文件路径。
```

## 9\.6 保留的记录和证据

```Plain Text
原系统启动截图
旧系统完整流程录屏
原页面截图
原Swagger截图
原数据库表清单
Hermes审计输出
Codex审计输出
A02差距矩阵
百宝箱登录截图
平台项目页截图
可用模型截图
知识库入口截图
工具配置入口截图
发布入口截图
平台限制说明
```

## 9\.7 完成标准

```Plain Text
两人都能说明原系统主流程
已确认百宝箱账号和权限
已确认平台工具接入方式
已确定平台和后端边界
已确定首批工具和知识库
已确定10天分工
暂时没有大规模代码修改
```

---

# 阶段1：公共契约、Mock链路与平台骨架

## 时间

```Plain Text
D2
上午共同设计
下午并行开发
晚上第一次合并和平台测试
```

## 目标

固定数据契约，使Agent、Service、前端和百宝箱可以并行开发。

## 10\.1 上午共同完成

确定：

```Plain Text
CareerState
Agent输入输出
Service输入输出
后端API
平台工具Schema
统一错误结构
能力等级范围
能力标签分类
知识库元数据
Demo数据格式
百宝箱对话主流程
```

## 10\.2 CareerState

```JSON
{
  "session_id": "demo-001",
  "platform_session_id": null,
  "user_id": null,
  "student_input": {},
  "target_job_input": {},
  "student_profile": null,
  "job_profile": null,
  "trend_result": null,
  "match_result": null,
  "path_plan": null,
  "learning_plan": null,
  "training_plan": null,
  "resource_result": null,
  "feedback_result": null,
  "final_report": null,
  "agent_logs": []
}
```

## 10\.3 Agent统一返回格式

```JSON
{
  "agent_name": "ProfileAgent",
  "status": "success",
  "data": {},
  "summary": "学生职业能力画像生成完成",
  "duration_ms": 825,
  "tool_calls": [],
  "fallback_used": false,
  "error": null
}
```

## 10\.4 平台工具统一返回格式

```JSON
{
  "code": 0,
  "message": "success",
  "request_id": "req-001",
  "data": {},
  "error": null
}
```

## 10\.5 你负责

```Plain Text
建立CareerState
建立BaseAgent
建立CareerOrchestrator
建立Mock Agent链路
建立主接口
建立日志接口
在百宝箱创建CareerPulse主智能体
配置系统Prompt V1
配置一个Mock工具
```

主接口：

```Plain Text
POST /api/career-agent/run
GET  /api/career-agent/session/{session_id}
GET  /api/agent/logs/{session_id}
```

## 10\.6 成员2负责

```Plain Text
建立能力标签文件
准备3份学生样例
准备3个岗位样例
准备岗位权重
准备职业图谱Mock
准备训练样例
建立数据库模型
建立Mock工具API
准备第一版知识库文件
```

最低数据：

```Plain Text
30—50个能力标签
3份学生样例
3个岗位样例
10—20个职业节点
15—30条职业边
10道训练题
10条学习资源
```

## 10\.7 你给Codex的任务

```Plain Text
任务：建立A02多智能体Mock骨架及平台适配接口。

读取：
AGENTS.md
docs/a02/03_ARCHITECTURE.md
docs/a02/04_API_CONTRACTS.md
docs/a02/13_MCP_TOOL_CATALOG.md

允许修改：
backend/app/agents/**
backend/app/orchestrator/**
backend/app/schemas/**
backend/app/api/career_agent_api.py
backend/app/platform/**

禁止修改：
backend/app/services/**
数据库模型
原有公共接口

要求：
1. 实现CareerState
2. 实现BaseAgent
3. 实现CareerOrchestrator
4. 顺序执行Mock Agent
5. 生成final_report
6. 失败时fallback并继续
7. 保存Agent日志
8. 提供一个供百宝箱调用的Mock工具接口
9. 补充基本测试
10. 不自动提交Git

完成后运行测试并输出diff摘要。
```

## 10\.8 成员2给Codex的任务

```Plain Text
任务：建立A02基础数据、数据库和Mock工具。

读取：
AGENTS.md
docs/a02/04_API_CONTRACTS.md
docs/a02/06_DATA_DICTIONARY.md
docs/a02/13_MCP_TOOL_CATALOG.md

允许修改：
backend/app/data/**
backend/app/models/**
backend/migrations/**
backend/scripts/**
backend/app/tools/mock_tools.py

要求：
1. 建立30个以上能力标签
2. 建立3份匿名学生样例
3. 建立3个岗位样例
4. 建立岗位权重
5. 建立职业节点和边
6. 建立训练题和资源样例
7. 提供数据库初始化脚本
8. 提供Mock平台工具
9. 不使用真实个人隐私数据
10. 运行初始化检查
```

## 10\.9 百宝箱操作步骤

```Plain Text
1. 登录https://b.tbox.cn
2. 创建CareerPulse项目或应用
3. 创建“CareerPulse职业成长伙伴”智能体
4. 选择可用大模型
5. 填写角色说明和开场白
6. 配置系统Prompt V1
7. 根据平台实际方式配置Mock工具
8. 发起一次工具调用测试
9. 保存配置与调用截图
```

## 10\.10 保留的证据

```Plain Text
CareerState定义
API契约
工具Schema
Mock主接口JSON
Swagger截图
Mock Agent日志
数据库结构截图
初始化数据
百宝箱项目截图
智能体配置截图
系统Prompt V1
平台Mock工具配置
平台首次调用截图
```

## 10\.11 完成标准

```Plain Text
自建主接口能返回Mock报告
可以查询Agent状态
平台已创建主智能体
平台至少能调用一个Mock工具
工具字段已固定
数据可以初始化
```

---

# 阶段2：学生画像、岗位分析和职业趋势

## 时间

```Plain Text
D3—D4
主要并行
D4晚上完成平台联调
```

## 目标

将用户和岗位信息转成统一能力向量，并通过百宝箱完成用户追问、画像工具调用和趋势知识检索。

## 11\.1 你负责

```Plain Text
统一LLM客户端
ProfileAgent
JobAgent
职业趋势分析
Prompt模板
结构化输出Schema
JSON失败重试
规则和Mock兜底
能力证据提取
百宝箱信息追问流程
百宝箱画像工具配置
```

ProfileAgent输出：

```Plain Text
基本信息
能力标签
能力等级
置信度
证据文本
画像完整度
职业竞争力评分
```

JobAgent输出：

```Plain Text
岗位名称
岗位类型
岗位能力
所需等级
能力权重
岗位原文证据
技能趋势
岗位发展趋势
岗位摘要
```

## 11\.2 成员2负责

```Plain Text
MatchService
能力标签归一化
岗位趋势知识数据
岗位知识库清洗
岗位知识库导入文件
画像样例测试
匹配算法测试
```

匹配公式：

```Plain Text
Score(u,i) = Σ wk × min(Suk / Jik, 1)

Gapk = max(Jik - Suk, 0)

Priorityk = Gapk × wk / Difficultyk
```

## 11\.3 你给Codex的任务

```Plain Text
任务：实现ProfileAgent、JobAgent和职业趋势输出。

允许修改：
backend/app/agents/profile_agent.py
backend/app/agents/job_agent.py
backend/app/core/llm_client.py
backend/app/schemas/profile_schema.py
backend/app/schemas/job_schema.py
prompts/profile_agent/**
prompts/job_agent/**

要求：
1. ProfileAgent接收简历和表单
2. JobAgent接收岗位JD
3. 输出符合Pydantic Schema
4. JSON失败最多重试2次
5. 失败后使用规则或Demo fallback
6. 保留证据文本
7. 输出岗位趋势摘要
8. 不让LLM计算最终匹配分
9. 写运行日志
10. 补充测试
```

## 11\.4 成员2给Codex的任务

```Plain Text
任务：实现MatchService和岗位知识数据预处理。

允许修改：
backend/app/services/match_service.py
backend/app/data/job_trends/**
backend/scripts/build_job_knowledge.py
backend/tests/test_match_service.py

要求：
1. 对齐学生和岗位能力标签
2. 计算加权匹配分
3. 计算维度得分
4. 计算gap
5. 计算priority
6. 缺失能力按0处理
7. 防止除零
8. 输出固定Schema
9. 生成知识库导入文件
10. 编写正常、边界和异常测试
```

## 11\.5 百宝箱操作步骤

```Plain Text
1. 创建岗位与技能趋势知识库
2. 导入清洗后的岗位和行业资料
3. 配置分块和元数据
4. 使用10个问题测试检索效果
5. 配置analyze_student_profile工具
6. 配置analyze_job_and_trend工具
7. 更新系统Prompt，要求缺失信息先追问
8. 跑通“用户介绍自己—补充追问—生成画像—分析岗位趋势”
```

## 11\.6 保留的证据

```Plain Text
ProfileAgent Prompt版本
JobAgent Prompt版本
学生画像JSON
岗位画像JSON
趋势分析JSON
Schema成功日志
重试日志
fallback日志
知识库数据来源
数据清洗脚本
百宝箱知识库导入截图
知识库检索测试
平台画像工具调用日志
平台完整对话截图
```

## 11\.7 完成标准

```Plain Text
至少3份简历生成结构化画像
至少3个岗位生成岗位画像
能够返回岗位趋势分析
知识库完成导入和测试
百宝箱可以追问用户并调用画像工具
模型失败时仍能返回Demo结果
```

---

# 阶段3：人岗匹配、能力缺口和职业路径

## 时间

```Plain Text
D5
并行开发
晚上完成百宝箱三工具联调
```

## 目标

在百宝箱对话中完成学生画像、岗位分析、人岗匹配和3—5年职业路径生成。

## 12\.1 你负责

```Plain Text
MatchAgent
PathAgent
CareerState状态流转
平台工具注册
工具结果自然语言解释
百宝箱对话流程串联
AgentRunLog
```

## 12\.2 成员2负责

```Plain Text
MatchService完善
PathService
职业图谱
候选路径生成
路径评分
3年路径
5年路径
阶段任务
路径算法测试
```

路径公式：

```Plain Text
PathScore =
GrowthValue
- TransferCost
- AbilityGapCost
```

## 12\.3 成员2给Codex的任务

```Plain Text
任务：实现职业路径推荐Service。

允许修改：
backend/app/services/path_service.py
backend/app/data/career_graph.json
backend/tests/test_path_service.py

要求：
1. 读取职业节点和职业边
2. 根据用户当前能力和目标岗位生成候选路径
3. 使用GrowthValue、TransferCost、AbilityGapCost评分
4. 返回3年路径
5. 返回5年路径
6. 返回阶段任务和所需能力
7. 返回推荐理由和路径分数
8. 无路径时返回兜底建议
9. 编写正常、无路径和异常测试
```

## 12\.4 你给Codex的任务

```Plain Text
任务：接入MatchService和PathService，并提供平台工具。

允许修改：
backend/app/agents/match_agent.py
backend/app/agents/path_agent.py
backend/app/orchestrator/**
backend/app/platform/**
backend/app/services/log_service.py
backend/app/api/career_agent_api.py

要求：
1. MatchAgent调用真实MatchService
2. PathAgent调用真实PathService
3. 暴露calculate_job_match工具
4. 暴露recommend_career_path工具
5. 校验工具参数
6. 记录tool_calls、duration_ms和fallback_used
7. 更新CareerState
8. 失败时不终止完整链路
9. 补充集成测试
```

## 12\.5 百宝箱操作步骤

```Plain Text
1. 配置calculate_job_match工具
2. 配置recommend_career_path工具
3. 确认工具输入字段与后端Schema一致
4. 配置工具调用规则
5. 测试参数缺失情况
6. 测试正常调用
7. 测试后端异常情况
8. 跑通画像→岗位→匹配→路径完整对话
```

## 12\.6 保留的证据

```Plain Text
匹配算法代码
匹配测试报告
3组匹配案例
能力缺口结果
职业图谱JSON
职业节点和边说明
3年路径案例
5年路径案例
路径评分结果
无路径兜底测试
平台工具配置截图
平台正常调用日志
参数错误日志
平台完整对话截图
```

## 12\.7 完成标准

```Plain Text
匹配分由真实代码计算
至少3个案例输出能力缺口
至少3个案例输出3年和5年路径
每个阶段包含学习任务
百宝箱在一次对话中调用画像、匹配和路径工具
```

---

# 阶段4：职场训练、任务执行、资源推荐和反馈

## 时间

```Plain Text
D6
主要并行
晚上完成训练和反馈联调
```

## 目标

满足A02的生成、执行和反馈环节。

## 13\.1 你负责

```Plain Text
TrainingAgent
FeedbackAgent
训练Prompt
训练交互流程
任务计划生成
资源推荐接入
平台工具Schema
反馈引导
成长档案状态流转
```

## 13\.2 成员2负责

```Plain Text
TrainingService
FeedbackService
ResourceService
三类训练评分规则
成长记录保存
反馈基础调权
学习和岗位资源数据
单元测试
```

训练类型至少包括：

```Plain Text
远程协作
AI辅助办公
跨岗位沟通
```

可以增加：

```Plain Text
模拟面试
```

至少一类训练完成完整交互和评分。

## 13\.3 成员2给Codex的任务

```Plain Text
任务：实现训练、资源推荐和反馈Service。

允许修改：
backend/app/services/training_service.py
backend/app/services/resource_service.py
backend/app/services/feedback_service.py
backend/tests/test_training_service.py
backend/tests/test_resource_service.py
backend/tests/test_feedback_service.py

要求：
1. 支持remote_collaboration
2. 支持ai_office_task
3. 支持cross_role_communication
4. 可选支持mock_interview
5. 输出任务背景、题目、评分维度和评分规则
6. 输入回答后返回总分、维度分和建议
7. 返回能力更新项
8. 推荐学习或岗位资源
9. 保存用户反馈
10. 更新学习优先级和成长记录
11. 编写空回答、无资源和异常测试
```

## 13\.4 你给Codex的任务

```Plain Text
任务：实现TrainingAgent、FeedbackAgent和平台工具。

允许修改：
backend/app/agents/training_agent.py
backend/app/agents/feedback_agent.py
backend/app/platform/**
backend/app/schemas/training_schema.py
backend/app/schemas/feedback_schema.py
backend/app/orchestrator/**

要求：
1. TrainingAgent根据目标岗位和短板生成训练
2. 调用TrainingService评分
3. 调用ResourceService推荐资源
4. FeedbackAgent保存用户反馈
5. 暴露generate_and_score_training工具
6. 暴露recommend_learning_and_job_resources工具
7. 暴露save_growth_feedback工具
8. 校验工具参数
9. 记录正常和异常调用
10. 更新CareerState
11. 增加集成测试
```

## 13\.5 百宝箱操作步骤

```Plain Text
1. 配置训练工具
2. 配置资源推荐工具
3. 配置成长反馈工具
4. 更新系统Prompt，要求训练完成后询问用户反馈
5. 测试三类训练
6. 测试至少一类完整“题目—回答—评分”
7. 测试资源推荐
8. 测试成长记录保存
9. 测试反馈后学习优先级变化
```

## 13\.6 保留的证据

```Plain Text
三类训练案例
训练题目
不同回答对比分数
训练评分维度
训练改进建议
资源推荐结果
资源数据来源
用户反馈记录
反馈前后优先级变化
成长记录更新
平台训练对话截图
工具调用日志
训练异常fallback日志
```

## 13\.7 完成标准

```Plain Text
三类训练都能生成
至少一类支持完整交互和评分
能够推荐学习或岗位资源
反馈能够保存
反馈能够影响成长记录或学习优先级
百宝箱能够完成训练和反馈对话
```

---

# 阶段5：MCP/API正式接入百宝箱

## 时间

```Plain Text
D7
两人共同完成
你主导平台配置
成员2主导后端部署
```

## 目标

完成真实的百宝箱工具调用，不再依赖Mock工具。

## 14\.1 必须接入的工具

至少完成：

```Plain Text
analyze_student_profile
calculate_job_match
recommend_career_path
generate_and_score_training
save_growth_feedback
```

推荐增加：

```Plain Text
analyze_job_and_trend
recommend_learning_and_job_resources
```

## 14\.2 你负责

```Plain Text
百宝箱正式工具配置
工具字段映射
系统Prompt V2
工具选择规则
工具结果解释规则
平台异常提示
完整对话测试
```

## 14\.3 成员2负责

```Plain Text
MCP Server或平台支持的API适配层
公网HTTPS部署
鉴权
参数校验
超时控制
工具日志
Service异常处理
后端工具测试
```

平台实际不支持直接MCP时，按照平台提供的HTTP、插件或其他接入方式完成，并在MCP说明文档中如实记录。

## 14\.4 成员2给Codex的任务

```Plain Text
任务：将CareerPulse核心Service封装为百宝箱可调用工具。

读取：
AGENTS.md
docs/a02/04_API_CONTRACTS.md
docs/a02/13_MCP_TOOL_CATALOG.md

允许修改：
backend/app/mcp/**
backend/app/tools/**
backend/app/platform/**
backend/tests/test_platform_tools.py

要求：
1. 暴露analyze_student_profile
2. 暴露calculate_job_match
3. 暴露recommend_career_path
4. 暴露generate_and_score_training
5. 暴露save_growth_feedback
6. 每个工具具有输入输出Schema
7. 增加参数校验
8. 增加超时和错误结构
9. 日志不得记录完整简历
10. 编写成功、参数错误、超时和Service异常测试
11. 输出供百宝箱配置使用的工具说明
```

## 14\.5 百宝箱操作步骤

```Plain Text
1. 在平台中删除或停用Mock工具
2. 根据实际支持方式添加正式MCP/API工具
3. 填写工具名称和功能说明
4. 填写输入字段
5. 填写返回字段
6. 配置鉴权信息
7. 测试单个工具
8. 测试多个工具连续调用
9. 测试参数缺失
10. 测试工具超时
11. 测试工具失败后的对话反馈
12. 保存配置、调用日志和失败截图
```

## 14\.6 保留的证据

```Plain Text
MCP Server代码
平台工具目录
工具Schema
平台配置截图
正常调用日志
参数错误日志
超时日志
后端异常日志
fallback日志
平台工具连续调用录像
鉴权和隐私设计说明
```

## 14\.7 完成标准

```Plain Text
至少5个核心工具真实可调用
平台调用的是正式后端
所有工具具有固定Schema
调用具有日志和异常处理
百宝箱完整职业成长对话可以运行
```

---

# 阶段6：Web系统与多端发布

## 时间

```Plain Text
D8
你负责前端和发布
成员2负责后端稳定
```

## 目标

完成CareerPulse Web展示和百宝箱Web发布验证。

## 15\.1 你负责

```Plain Text
修改原有Vue页面
接入真实后端
Agent执行链路页
职场训练页
学习进度和成长档案
百宝箱Web发布
移动端适配
根据权限进行小程序预览或发布
```

优先改造：

新增：

```Plain Text
职场训练页
Agent执行链路页
学习进度页
```

## 15\.2 成员2负责

```Plain Text
部署正式后端
配置HTTPS
配置跨域
数据库初始化
Docker启动
接口回归测试
百宝箱调用稳定性
```

## 15\.3 Demo Mode

前端：

```Plain Text
VITE_DEMO_MODE=true
```

后端：

```Plain Text
A02_DEMO_MODE=true
```

演示模式要求：

```Plain Text
不依赖外部大模型
固定返回可重复数据
Agent日志仍然生成
页面明确显示演示数据
不能冒充真实平台测试
```

## 15\.4 百宝箱发布步骤

```Plain Text
1. 检查正式智能体配置
2. 检查正式工具状态
3. 检查知识库状态
4. 配置Web发布
5. 生成访问地址
6. 使用未登录或普通用户环境测试
7. 使用移动端浏览器测试
8. 根据权限测试支付宝或微信小程序
9. 保存发布设置和访问截图
```

Web服务必须完成；支付宝和微信小程序根据平台权限完成发布或预览验证。

## 15\.5 保留的证据

```Plain Text
改造前后页面对比
真实接口截图
Agent执行链路页
训练页
学习进度页
成长档案页
百宝箱Web发布配置
Web访问截图
移动端截图
支付宝或微信小程序预览截图
兼容性测试
Demo Mode截图
```

## 15\.6 完成标准

```Plain Text
Web完整流程可操作
百宝箱Web发布正常
CareerPulse Web能够展示复杂结果
移动端可访问
平台和Web数据一致
正式模式和Demo Mode都可用
```

---

# 阶段7：Agent、知识库、平台和算法评测

## 时间

```Plain Text
D9
共同完成
你负责评测设计
成员2负责执行测试
```

## 16\.1 Agent评测集

建议准备20—30组：

```Plain Text
5组学生画像
5组岗位和趋势分析
5组匹配与能力缺口
3组职业路径
3组职场训练
3组异常和fallback
```

## 16\.2 评测指标

```Plain Text
结构化输出合法率
关键字段完整率
能力证据覆盖率
匹配人工一致性
路径推荐合理性
工具调用成功率
工具参数合法率
主链路完成率
fallback触发率
平均执行耗时
```

## 16\.3 知识库评测

至少准备：

```Plain Text
20个正常检索问题
5个无答案问题
5个容易混淆的问题
```

指标：

```Plain Text
Top-K相关性
检索命中率
回答引用准确率
无答案拒答率
知识覆盖率
平均响应时间
```

## 16\.4 百宝箱平台评测

指标：

```Plain Text
完整对话完成率
正确工具选择率
工具连续调用成功率
平台工具调用耗时
异常恢复率
知识库调用成功率
Web发布可用率
移动端可用率
```

## 16\.5 AI伦理与隐私测试

检查：

```Plain Text
简历上传是否获得授权
是否支持删除数据
日志是否保存完整简历
手机号和邮箱是否脱敏
推荐是否带解释
是否存在性别、年龄或院校偏见
是否有职业建议免责声明
是否提示AI结果仅供参考
是否防止用户过度依赖
```

## 16\.6 Codex审查提示词

```Plain Text
请对当前A02改造分支进行代码审查。

重点检查：
1. Agent与Service职责是否混乱
2. 是否由LLM凭空生成匹配分
3. Schema是否完整
4. 工具是否有参数校验
5. 是否有未处理异常
6. 日志是否泄露简历隐私
7. MCP/API是否有鉴权
8. Demo Mode是否影响正式模式
9. 测试是否覆盖核心链路
10. 是否硬编码API Key
11. 是否与百宝箱工具Schema不一致
12. 是否存在材料中写了但代码未实现的能力

只输出问题、严重程度、文件位置和修改建议。
暂时不要修改代码。
```

## 16\.7 Hermes最终评审提示词

```Plain Text
请对照A02赛题要求评审当前CareerPulse实现。

检查：
1. 感知：用户信息和状态采集
2. 认知：岗位与职业趋势分析
3. 决策：匹配和路径规划
4. 生成：学习内容和训练
5. 执行：任务和资源对接
6. 反馈：训练评估和动态更新
7. 百宝箱智能体配置
8. 百宝箱知识库
9. MCP/API工具调用
10. Web和多端发布
11. AI伦理和隐私
12. Agent日志和评测

我会提供：
- 架构文档
- API契约
- 百宝箱截图
- 测试报告
- Git提交摘要
- 演示视频

请输出：
1. 已真实实现
2. 部分实现
3. 材料中需要限定表述的内容
4. 不能写进材料的内容
5. 提交前必须修复的问题
```

## 16\.8 保留的证据

```Plain Text
pytest报告
接口测试报告
Agent评测集
评测结果
知识库测试集
知识库评测结果
平台测试记录
人工评价表
Codex review结果
Hermes最终审计
隐私检查表
偏见检查表
完整session日志
```

## 16\.9 完成标准

```Plain Text
核心Service测试通过
至少一条端到端测试通过
Agent具有离线评测结果
知识库具有评测结果
平台工具具有测试结果
伦理和隐私检查完成
```

---

# 阶段8：演示冻结与证据整理

## 时间

```Plain Text
D10
共同完成
你主导演示
成员2保证后端稳定
```

## 17\.1 固定主案例

```Plain Text
1个演示账号
1份匿名学生简历
1个目标岗位
1套学生画像
1套岗位和趋势分析
1套匹配结果
1套3年/5年路径
1套训练任务
1套资源推荐
1次用户反馈
1条完整Agent日志
```

## 17\.2 固定演示流程

```Plain Text
1. 进入百宝箱CareerPulse智能体
2. 用户输入个人情况和职业目标
3. 智能体补充追问
4. 调用学生画像工具
5. 检索岗位趋势知识库
6. 调用匹配工具
7. 展示能力缺口和优先级
8. 调用路径规划工具
9. 展示3年和5年路径
10. 生成一项职场训练
11. 用户提交回答
12. 返回评分和改进建议
13. 推荐学习或岗位资源
14. 保存用户反馈
15. 打开CareerPulse Web
16. 展示雷达图、路径、学习进度和成长变化
```

## 17\.3 同时准备

```Plain Text
百宝箱正式版本
CareerPulse Web正式版本
后端正式服务
Demo Mode
备用录屏
备用截图
前端启动脚本
后端启动脚本
数据库初始化脚本
平台配置说明
```

## 17\.4 保留的证据

```Plain Text
百宝箱完整运行视频
CareerPulse Web完整运行视频
平台工具日志
Agent日志
正式模式截图
Demo Mode截图
发布链接测试
Git提交历史
版本标签
最终测试报告
材料功能核对表
```

## 17\.5 完成标准

```Plain Text
完整主链路稳定运行
平台和Web均可访问
所有提交材料中的功能真实存在
视频流程固定
正式模式和Demo Mode均可用
平台配置和发布证据齐全
```

---

# 两人的10天时间表

---

# 每天的Hermes、Codex和百宝箱工作流

## 19\.1 早上：Hermes拆任务

每天向Hermes提供：

```Plain Text
当前TASKS.md
昨日Git提交
昨日百宝箱配置变化
测试结果
当前阻塞问题
当天可投入时间
```

提示词：

```Plain Text
请根据当前任务、代码提交、平台配置和测试结果，
为今天拆分任务。

要求：
1. 给我最多3个任务
2. 给成员2最多2个任务
3. 每个任务控制在2—4小时
4. 明确允许修改的文件
5. 明确禁止修改的文件
6. 明确输入和输出
7. 明确验收标准
8. 标注两人依赖关系
9. 标注今天必须完成的平台操作
10. 标注今天必须保留的证据
```

## 19\.2 开发阶段：分别使用Codex

固定模板：

```Plain Text
任务：
[只写一个明确任务]

背景：
CareerPulse正在升级为基于蚂蚁百宝箱企业版的
A02职业导航与终身学习伙伴。

读取：
AGENTS.md
docs/a02/03_ARCHITECTURE.md
docs/a02/04_API_CONTRACTS.md
docs/a02/13_MCP_TOOL_CATALOG.md

允许修改：
[精确文件]

禁止修改：
[精确文件]

输入：
[输入数据或接口]

输出：
[输出Schema]

验收标准：
1. ...
2. ...
3. ...

完成后：
1. 运行相关测试
2. 输出修改文件
3. 输出关键diff摘要
4. 说明API或平台兼容性影响
5. 说明未解决问题
6. 不要自动提交Git
```

## 19\.3 Codex修改后人工检查

```Plain Text
是否修改禁止文件
是否改变公共字段
是否与平台工具Schema一致
是否加入重复依赖
是否用假数据冒充真实结果
是否让LLM计算匹配分
是否暴露密钥
是否记录完整简历
是否真的运行测试
```

## 19\.4 每完成一个工具后：百宝箱联调

```Plain Text
部署或启动后端工具
在百宝箱中更新工具配置
测试正常输入
测试缺少参数
测试异常输入
测试超时或后端失败
保存配置截图
保存调用日志
记录问题和修复
```

## 19\.5 晚上：合并与Hermes复盘

共同完成：

```Plain Text
拉取两边最新代码
运行测试
跑一次阶段主链路
检查平台工具字段
合并小模块
更新TASKS.md
记录每日开发日志
整理当天证据
```

Hermes复盘提示词：

```Plain Text
这是今天两名成员的：

1. Git提交摘要
2. 修改文件
3. 测试结果
4. 接口变更
5. 百宝箱配置变更
6. 平台工具调用结果
7. 当前主链路状态
8. 未解决问题

请检查：
1. 是否存在数据契约冲突
2. 是否存在平台和后端字段冲突
3. 是否有职责重叠
4. 是否有材料写了但代码或平台未实现的功能
5. 哪些问题会阻塞下一阶段
6. 明天最高优先级
7. 哪些任务适合交给Codex
8. 哪些平台操作必须人工完成
9. 哪些证据还没有保存
```

---

# 每日开发记录模板

保存到：

```Plain Text
docs/a02/daily/YYYY-MM-DD.md
```

模板：

```Markdown
# 日期

## 今日目标

- 
- 

## 我完成的代码工作

- 修改文件：
- Git commit：
- 测试结果：
- 截图和证据：

## 我完成的百宝箱工作

- 智能体配置：
- Prompt版本：
- 知识库配置：
- 工具配置：
- 发布配置：
- 平台测试结果：
- 截图路径：

## 成员2完成的工作

- 修改文件：
- Git commit：
- 测试结果：
- 部署状态：
- 截图和证据：

## 今日联调结果

- 已跑通：
- 未跑通：
- 字段冲突：
- 平台问题：
- Bug：

## 关键决策

- 决策：
- 原因：
- 影响模块：
- 是否记录ADR：

## 已知问题

- 
- 

## 明日任务

- 我：
- 成员2：
- 百宝箱操作：

## Hermes复盘摘要

- 

## Codex审查摘要

- 
```

---

# 必须保留的开发记录与证据

## 21\.1 架构证据

```Plain Text
改造前后架构图
百宝箱与后端职责边界
CareerState
CareerOrchestrator流程
六个Agent职责
Agent—Service—Tool—平台关系
```

## 21\.2 大模型工程证据

```Plain Text
ProfileAgent Prompt
JobAgent Prompt
TrainingAgent Prompt
百宝箱系统Prompt
结构化输出Schema
JSON失败日志
重试日志
fallback日志
```

## 21\.3 百宝箱配置证据

```Plain Text
项目创建
模型配置
智能体配置
系统Prompt
开场白
知识库
工具配置
工具调用
异常测试
Web发布
小程序预览或发布
```

## 21\.4 知识库证据

```Plain Text
数据来源
清洗规则
切分规则
元数据
导入文件
导入截图
正常检索问题
无答案问题
评测结果
优化记录
```

## 21\.5 Tool Calling和MCP证据

```Plain Text
工具定义
输入输出Schema
MCP Server代码
平台工具配置
Agent工具调用日志
正常调用截图
参数错误截图
超时截图
fallback截图
```

## 21\.6 算法证据

```Plain Text
学生能力向量
岗位能力向量
匹配公式
缺口公式
优先级公式
路径评分公式
算法代码
测试案例
人工合理性评价
```

## 21\.7 Agent工程化证据

```Plain Text
Agent执行时间线
各Agent输入输出摘要
tool_calls
运行耗时
fallback_used
错误原因
完整session日志
离线评测集
评测结果
```

## 21\.8 产品和发布证据

```Plain Text
改造前后页面
画像页面
匹配页面
路径页面
训练页面
学习进度页面
成长档案页面
Agent执行链路页面
百宝箱Web页面
移动端页面
正式模式
Demo Mode
系统演示视频
```

## 21\.9 协作证据

```Plain Text
人员分工
Git分支
提交记录
PR和合并记录
每日开发日志
ADR决策
Bug修复记录
测试报告
Hermes任务拆解
Codex review结果
```

---

# 最小可交付标准

```Plain Text
1. 百宝箱中真实创建CareerPulse智能体
2. 完成模型和系统Prompt配置
3. 完成至少一个知识库的导入和测试
4. 至少5个业务工具可被百宝箱真实调用
5. MCP/API工具具有固定输入输出Schema
6. 工具具有参数校验和异常处理
7. 用户能够生成动态职业画像
8. 能够完成岗位与职业趋势分析
9. 匹配分、gap和priority由代码计算
10. 能够输出3年和5年职业路径
11. 提供至少3类职场训练
12. 至少1类训练支持完整交互和评分
13. 能够生成学习任务和资源建议
14. 反馈能够更新成长记录或学习优先级
15. 每个Agent和工具调用具有日志
16. CareerPulse Web展示能力雷达图、匹配度、路径和进度
17. 完成百宝箱Web发布验证
18. 根据权限完成小程序发布或预览
19. 知识库具有评测结果
20. 核心Service具有单元测试
21. 至少1条端到端测试
22. 模型失败时Demo Mode仍可演示
23. 隐私和AI伦理检查完成
24. 材料中出现的功能全部真实存在
```

