# CareerPulse改造开发指南

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
CareerPulse
                         │
         ┌───────────────┴────────────────┐
         │                                │
         ▼                                ▼
CareerPulse Vue Web               蚂蚁百宝箱原生发布渠道
【主要Web产品端】                  【平台验证/支付宝等渠道】
         │                                │
         │                                │
         ▼                                ▼
CareerPulse FastAPI  ←────── MCP ─── 百宝箱Agent
         │                         ↑
         │                         │
         └──── TBox Agent API ─────┘
                  ↑
                  │
              Vue AI对话

FastAPI内部：
CareerOrchestrator
→ Agent
→ Service
→ PostgreSQL / Redis
```

## 0\.4 参考资料（可预览/下载）

国服2026原A13赛题：

\[T2600073\-第五象限队\-【A13】\-项目概要介绍\.pdf\]

\[T2600073\-第五象限队\-【A13】\-项目简介PPT\.pdf\]

\[T2600073\-第五象限队\-【A13】\-项目详细方案\.pdf\]

\[T2600073\-第五象限队\-【A13】\-项目演示视频\.mp4\]

\[区域二等证书\.pdf\]（打码放进文档里\-\-\>仿国创的成果图重做一个）

国创2026立项：

\[丽水学院 基于智能算法优化的大学生职业规划辅助系统研究与实现\.pdf\]

计设2026软开web赛道：

\[答辩演示文档\.pdf\]

\[AI工具使用说明\.pdf\]

\[设计和开发文档\.pdf\]

\[浙江省省二证书\.png\]（打码放进文档里\-\-\>仿国创的成果图重做一个）

软件杯2026原A3赛题：

\[介绍PPT\.pdf\]

\[开发说明书文档\.pdf\]

\[演示视频\.mp4\]

已有软著证书：（打码放进文档里）

\[软著26\.6\.11\.pdf\]

## 0\.5 三部分职责

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

## 时间  8\.8\-17:10over

```Plain Text
D1
共同完成
```

## 目标

确认原项目已有能力、百宝箱实际能力和两者的职责边界，避免代码开发完成后才发现平台不支持某种接入方式。

## 9\.1 共同完成

```Plain Text
启动现有前后端 √
跑一遍现有主流程 √

用hermes/codex： √
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
获取百宝箱试用权限 √和Token说明 √（报名提交的apikey：inc-akbe2e38a0249e1d0a851f150f714d1a6471a36e7086974655b1f7b43f6e35f497）
登录百宝箱企业版 √
以下和coze差不多（用的时候再慢慢琢磨）：√
查看可选模型
查看知识库入口
查看智能体或工作流配置
查看工具/MCP接入方式
查看Web发布方式
查看小程序权限
```

## 9\.2 你负责  x

```Plain Text
确定原系统可保留模块
确定百宝箱和CareerPulse职责边界
确定平台主智能体设计
确定首批工具清单
确定知识库清单
确定平台发布路线
```

## 9\.3 成员2负责   x

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

hermes回应： √ dyy\-8\.4 22:01

\[D1 Hermes\-阶段0 技术总顾问审计报告\.md\]



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

codex回应： √ dyy\-8\.8 17:00

\[D1 Codex仓库审计报告\.md\]

## 9\.6 保留的记录和证据（只需要有颜色标注的）

```Plain Text
原系统启动截图 √
旧系统完整流程录屏 √
原页面截图 √
原Swagger截图 √
原数据库表清单 √
Hermes审计输出  √ dyy-8.4 22:01
Codex审计输出  √ dyy-8.8 17:00
A02差距矩阵 √
百宝箱登录截图 √
平台项目页截图 x
可用模型截图 x
知识库入口截图 x
工具配置入口截图 x
发布入口截图 x
平台限制说明 √
```

## 9\.7 完成标准

```Plain Text
两人都能说明原系统主流程 √
已确认百宝箱账号和权限 √
已确认平台工具接入方式 √
已确定平台和后端边界 √
已确定首批工具和知识库 √
已确定10天分工 √
暂时没有大规模代码修改 √
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

这部分公共契约对应仓库里的几个文档是：（主要确认字段以后不要随便变） √ dyy\-8\.8 18:48\(未git commit\)

> docs/a02/
>
> ├── 03\_ARCHITECTURE\.md
>
> ├── 04\_API\_CONTRACTS\.md
>
> ├── 05\_AGENT\_CONTRACTS\.md
>
> ├── 06\_DATA\_DICTIONARY\.md
>
> ├── 10\_TBOX\_REQUIREMENTS\.md
>
> ├── 11\_TBOX\_AGENT\_CONFIG\.md
>
> ├── 12\_TBOX\_SYSTEM\_PROMPT\.md
>
> └── 13\_MCP\_TOOL\_CATALOG\.md
>
> 

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

**Diff 摘要：**  √ dyy\-8\.8 19:19

\[D1 建立A02多智能体Mock骨架及平台适配接口\.md\]

- 新增文件：17

- 新增代码：约 827 行

- 禁止目录变更：无

- `pycache`：已清理

- Git 提交：未执行

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

**Diff 摘要： **√ dyy\-8\.9 0:59

\[D1 数据库迁移、初始化脚本和 Mock 平台工具\.md\]

- 新增 11 个文件，约 919 行

- 白名单外变更为 0，无缓存文件

- 实际 PostgreSQL `--apply` 未执行，因为没有提供 `A02_DATABASE_URL`

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

百宝箱自动生成的应用页面仅作为平台原生运行、
工具调试和多端发布验证入口。

CareerPulse正式Web产品继续使用原Vue3前端，
后续通过服务端接入百宝箱智能体能力。
不在阶段1重写或迁移原Vue前端。
```

## ！！！路线修正：

dyy\-8\.9 16:40

\[D1 本地 Vue 具体怎么接百宝箱\.md\]

对外话术：

> CareerPulse 采用前后端解耦与 Agent 平台解耦设计。Web 端采用自研 Vue3 可视化界面，通过服务端接入蚂蚁百宝箱智能体服务；百宝箱负责大模型交互、智能体编排和 MCP 工具调用，CareerPulse 自研后端负责职业画像、匹配、路径规划和训练等确定性业务能力。
>
> 

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NTVjYjM2Y2ZiZTMzMWU1MTRlNDlkN2VhMzVlZTdkNGZfOWI4YmRmOWI2ZDAxZDRhMjljODZlYzYwMDM0MjkwY2ZfSUQ6NzY3MTk1Mjk5MTIyNTkwODQ3MV8xNzg2MjY3OTk2OjE3ODYzNTQzOTZfVjM)

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZjM4NGE5NDliMWI1YzRkZjZhNDYzNWFlMTkyZTk5N2VfMTBkNjA1MTJmMjU2YTU4ODY1NWMxNTNjNGQ2YTY3ZWVfSUQ6NzY3MTk1Mjk4OTk1NTA1MDcyNl8xNzg2MjY3OTk2OjE3ODYzNTQzOTZfVjM)

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

# 阶段5：百宝箱Agent与CareerPulse双向正式集成

## 时间

```Plain Text
D7
主要并行
晚上完成第一次正式双向链路联调
```



## 目标

完成百宝箱与 CareerPulse 的正式集成，不再依赖阶段1 Mock工具。

```Plain Text
本阶段必须同时跑通两条链路：
链路A：百宝箱 → CareerPulse
百宝箱职业成长伙伴
→ Tool Calling / MCP
→ CareerPulse FastAPI
→ Agent / Service
→ 返回结构化业务结果
→ 百宝箱解释结果

链路B：CareerPulse Vue → 百宝箱
CareerPulse Vue
→ CareerPulse FastAPI
→ 百宝箱智能体服务
→ 百宝箱根据用户问题进行对话、知识库检索和工具选择
→ 必要时通过 MCP 调用 CareerPulse FastAPI
→ 返回智能体回答
→ CareerPulse Vue 展示

注意：
百宝箱负责自然语言交互、知识库、工具选择和结果解释；
CareerPulse 后端负责画像、匹配、路径、训练、反馈等真实业务能力；
CareerPulse Vue 不直接保存百宝箱 Token，也不直接调用需要服务端密钥的接口。
```

## 14\.1 正式工具清单

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



所有正式工具统一要求：

```Plain Text
固定输入输出 Schema
参数校验
统一错误结构
request_id
session_id
工具调用日志
超时控制
fallback
不得由大模型伪造确定性业务结果
```

## 14\.2 百宝箱 → CareerPulse接入

百宝箱正式工具通过MCP或平台实际支持的API方式调用CareerPulse。

核心链路：

```Plain Text
百宝箱
↓
MCP / Tool Calling
↓
CareerPulse MCP/API Adapter
↓
CareerOrchestrator / Agent / Service
↓
CareerState
↓
结构化结果
↓
百宝箱自然语言解释
```

正式接入后，不再使用阶段1的 Mock Tool 作为主要能力来源。

## 14\.3 CareerPulse → 百宝箱接入

在CareerPulse后端增加百宝箱适配层。

建议结构：

```Plain Text
backend/app/platform/tbox/
├── client.py
├── chat_service.py
├── schemas.py
└── session_mapper.py
```

新增统一入口：

```Plain Text
POST /api/tbox/chat
```

职责：

```Plain Text
接收 Vue 的用户消息
维护 CareerPulse session 与百宝箱会话映射
调用百宝箱正式智能体
接收普通或流式回复
统一转换为 CareerPulse 前端可用格式
处理平台超时和异常
不得向浏览器暴露 API Key / Token
```

百宝箱具体 API、SDK、鉴权和流式协议，以当前企业版实际文档和比赛平台说明为准

## 14\.4 你负责

```Plain Text
百宝箱正式智能体配置
正式工具配置
MCP Tool Schema 对齐
CareerPulse 与百宝箱字段映射
System Prompt V2
工具选择规则
工具结果解释规则
知识库调用规则
平台异常提示
TBox Client / Gateway 设计
POST /api/tbox/chat 接口设计
CareerPulse session 与百宝箱会话映射
Vue端聊天协议定义
完整对话测试
Agent调用日志和平台调用链检查
```

## 14\.5 成员2负责

```Plain Text
MCP Server 或平台支持的 API 适配层
正式 CareerPulse 后端部署
公网 HTTPS
鉴权
参数校验
超时控制
重试与 fallback
工具日志
数据库连接
Service接口稳定性
MCP接口测试
Swagger / Postman 调用样例
Docker与环境配置
```

## 14\.6 双向接口必须分开

禁止把两个方向混成一个接口。

建议：

```Plain Text
CareerPulse → 百宝箱：POST /api/tbox/chat
用于：Vue用户向 CareerPulse AI职业伙伴发送消息。

百宝箱 → CareerPulse：/mcp/*  或平台要求的正式 Tool API
用于：百宝箱调用画像、匹配、路径、训练、反馈等业务能力。

两类接口共享 CareerState 和 session_id，
但职责、鉴权方式和日志必须分开。
```

## 14\.7 安全要求

百宝箱 Token / API Key 只放服务端环境变量。

例如：

```Plain Text
TBOX_API_KEY=
TBOX_APP_ID=
```

不得：

```Plain Text
写入 Vue
提交 Git
写进开发文档
出现在 Swagger 示例
打印在普通日志
进入截图或演示视频

简历、手机号、邮箱等敏感信息进入日志前必须脱敏。
```

## 14\.8 正式联调场景

至少测试：

```Plain Text
场景1：
用户在百宝箱直接要求分析职业画像
→ 调用 analyze_student_profile
→ 返回真实结果

场景2：
用户在百宝箱询问与目标岗位的匹配情况
→ 调用 calculate_job_match
→ 返回真实 MatchService 结果

场景3：
用户要求生成未来职业路径
→ 调用 recommend_career_path
→ 返回真实3年/5年路径

场景4：
用户在 CareerPulse Vue 的 AI职业伙伴页面发送消息
→ FastAPI
→ 百宝箱
→ 百宝箱调用 CareerPulse MCP Tool
→ 返回最终回答到 Vue

场景5：
工具超时、参数错误或服务失败
→ 百宝箱不能编造业务结果
→ 返回明确异常提示
→ fallback生效
```

## 14\.9 完成标准

```Plain Text
百宝箱至少5个正式工具可正常调用
所有正式工具已脱离Mock主链路
百宝箱调用 CareerPulse MCP/API 成功
CareerPulse 后端可以正式调用百宝箱智能体
Vue → FastAPI → 百宝箱链路跑通
百宝箱 → MCP → CareerPulse链路跑通
同一用户session能够正确关联
确定性结果来自Service而不是LLM编造
公网HTTPS正常
API Key未暴露
参数错误、超时、fallback均已测试
Agent日志和tool_calls可以查询
```

## 14\.10 本阶段保留证据

```Plain Text
百宝箱正式智能体配置截图
System Prompt V2
正式工具列表
工具 Schema
MCP配置截图
百宝箱调用 CareerPulse 成功截图
CareerPulse调用百宝箱成功截图
Tool Calling日志
request_id / session_id链路日志
参数错误截图
超时截图
fallback截图
HTTPS接口截图
MCP Server核心代码
```

---

# 15\. 阶段6：CareerPulse主Web产品与百宝箱多端发布

## **时间**

```Plain Text
D8
你：CareerPulse Vue 前端、AI 交互、百宝箱接入与平台发布
成员2：正式后端部署与稳定性
```

## 目标

完成 CareerPulse 自研 Vue Web 的最终产品体验，将百宝箱职业成长伙伴正式接入 CareerPulse，并完成百宝箱平台原生运行和多端发布验证。

本阶段统一三部分定位：

```Plain Text
CareerPulse Vue
= 主要 Web 产品端 + 完整可视化交互界面

蚂蚁百宝箱
= AI Agent 中枢 + 模型 + Prompt + 知识库 + Tool Calling + 多端发布

CareerPulse FastAPI
= 共享业务能力层 + Agent + Service + 数据库
```

最终对外展示的是一个 CareerPulse 系统，不做成两个彼此独立的产品。

## 15\.1 最终系统链路

**普通业务功能：**

```Plain Text
用户
↓
CareerPulse Vue
↓
CareerPulse FastAPI
↓
Service / Database
↓
Vue 可视化展示
```

适用于：

- 用户信息

- 简历上传

- 历史记录

- 职业画像结果

- 匹配结果

- 职业路径

- 学习进度

- 成长档案等结构化功能

**AI 职业伙伴：**

```Plain Text
用户
↓
CareerPulse Vue
↓
POST /api/tbox/chat
↓
CareerPulse FastAPI
↓
百宝箱 CareerPulse职业成长伙伴
↓
Prompt / 知识库 / Tool Calling
↓
MCP
↓
CareerPulse FastAPI
↓
Agent / Service
↓
结构化业务结果
↓
百宝箱组织自然语言回复
↓
CareerPulse Vue
```

**百宝箱原生渠道：**

```Plain Text
用户
↓
百宝箱 Web / 支付宝等发布渠道
↓
CareerPulse职业成长伙伴
↓
MCP
↓
CareerPulse FastAPI
↓
同一套 Agent / Service / Database
```

CareerPulse Vue 和百宝箱原生端共享同一套核心业务能力。

## 15\.2 你负责

```Plain Text
重点完成：
保留并升级原 CareerPulse Vue
接入正式 FastAPI 后端
新增或改造 AI 职业伙伴页面
接入百宝箱智能体对话
支持流式回复
CareerState 页面同步
能力雷达图
职场匹配度
能力缺口
能力提升优先级
3 年 / 5 年职业路径
学习计划
学习进度
职场模拟训练
训练评分与建议
成长档案
Agent 执行链路
历史记录
加载状态
空状态
错误状态
桌面端适配
移动端基础适配
百宝箱 Web 发布
根据实际权限完成支付宝 / 小程序发布或预览验证
```

原则：不重新制作一套普通模板式 Web，而是在原 CareerPulse 产品基础上完成 A02 智能体升级。

**页面优先级：**

```Plain Text
第一优先级
AI 职业伙伴
职业画像
人岗匹配
职业路径

这四个页面直接构成 CareerPulse 最核心的职业导航链路。

第二优先级

学习计划
职场训练
成长档案

用于形成 A02 要求的“生成—执行—反馈”闭环。

第三优先级

Agent 执行链路
历史记录
系统说明

主要用于工程展示、可解释性和比赛材料。
```

**AI职业伙伴页面：**

AI 职业伙伴不能只做普通聊天框。

推荐采用“AI 对话 \+ 职业状态可视化”的组合设计。

例如：

```Plain Text
┌──────────────────────────────────────────────┐
│ CareerPulse AI职业伙伴                       │
├──────────────────┬───────────────────────────┤
│                  │                           │
│ AI 对话区域       │ 当前职业状态              │
│                  │                           │
│ 用户消息          │ 能力雷达图                │
│ AI回复            │ 当前匹配度                │
│ 信息追问          │ Top能力缺口               │
│ 训练互动          │ 提升优先级                │
│                  │ 当前职业阶段              │
│                  │ 下一阶段目标              │
│                  │ 当前学习任务              │
│                  │ 最近训练结果              │
└──────────────────┴───────────────────────────┘
```

职责分离：

```Plain Text
百宝箱
→ 自然语言理解
→ 多轮对话
→ 用户追问
→ 知识库
→ Tool Calling
→ 结果解释

CareerPulse Vue
→ 雷达图
→ 匹配度
→ Gap
→ 路径
→ 学习进度
→ 训练结果
→ 成长轨迹
```

这样既体现百宝箱能力，也保留 CareerPulse 自研前端的差异化。

**CareerState 页面同步：**

百宝箱对话或工具执行后可能更新：

```Plain Text
student_profile
job_profile
trend_result
match_result
path_plan
learning_plan
training_plan
resource_result
feedback_result
final_report
```

Vue 应根据当前 `session_id` 获取最新 CareerState，并同步页面。

例如：

```Plain Text
用户在 AI职业伙伴中完成个人画像
↓
student_profile 更新
↓
职业画像页面刷新
↓
能力雷达图更新
```

```Plain Text
用户更换目标岗位
↓
job_profile 更新
↓
重新调用 MatchService / PathService
↓
match_result、path_plan 更新
↓
匹配页和职业路径页同步刷新
```

```Plain Text
用户完成模拟训练
↓
training_plan / feedback_result 更新
↓
学习优先级或能力记录调整
↓
成长档案更新
```

## 15\.3 成员2负责

```Plain Text
重点完成：
CareerPulse FastAPI 正式部署
公网 HTTPS
PostgreSQL 初始化
Redis 配置
Docker 启动
MCP Server 稳定运行
CORS 配置
API 鉴权
数据初始化
后端接口回归测试
Vue 接口稳定性测试
百宝箱 MCP 调用稳定性
流式接口稳定性
服务异常恢复
部署配置文档

要求：
Vue 和百宝箱必须调用同一套正式后端
不维护两套独立业务数据
不允许演示环境和正式环境业务逻辑完全不同
```

## 15\.4 Demo Mode

保留 Demo Mode 作为比赛现场兜底能力。

前端：

```Plain Text
VITE_DEMO_MODE=true
```

后端：

```Plain Text
A02_DEMO_MODE=true
```

Demo Mode 要求：

- 使用固定、可重复的匿名模拟数据

- 不依赖不稳定的第三方岗位数据

- 外部模型短暂不可用时核心页面仍能展示

- Agent 执行日志仍然生成

- 页面明确说明当前为 Demo 数据

- 不伪造百宝箱真实调用记录

正式比赛材料中仍必须保留真实：

- 百宝箱运行记录

- Tool Calling 日志

- MCP 调用日志

- 正式接口截图

- 平台发布截图

Demo Mode 只是异常兜底，不代替正式系统。

## 15\.5 百宝箱原生页面定位

百宝箱自动生成的前端页面不作为 CareerPulse 的主要视觉开发对象。

主要作用：

1. 验证 CareerPulse职业成长伙伴在百宝箱中可以独立运行

2. 验证模型配置

3. 验证 System Prompt

4. 验证知识库

5. 验证 Tool Calling / MCP

6. 验证百宝箱 Web 发布

7. 验证支付宝 / 小程序等多渠道能力

不要投入大量开发时间重新制作一套与 CareerPulse Vue 重复的完整产品。

## 15\.6 百宝箱发布步骤

```Plain Text
检查 CareerPulse职业成长伙伴配置
检查模型
检查 System Prompt V2
检查知识库
检查 MCP / Tool
测试用户信息追问
测试职业画像
测试岗位分析
测试匹配和能力缺口
测试职业路径
测试职场训练
测试成长反馈
完整运行一次 Agent 主链路
发布百宝箱 Web
根据权限完成支付宝 / 小程序发布或预览
保存发布页面、二维码和平台截图
```

## 15\.7 A02 功能检查

```Plain Text
CareerPulse 主 Web 至少应清晰展示：

动态职业画像
能力雷达图
岗位画像
职业趋势
职场匹配度
能力缺口
能力提升优先级
3 年职业路径
5 年职业路径
学习计划
学习进度
学习资源
至少 3 类典型职场训练
训练评分
成长记录
用户反馈后的动态调整


同时确认：

百宝箱智能体正常运行
百宝箱真实调用 CareerPulse MCP
CareerPulse Vue 的 AI 对话真实经过百宝箱
Web 发布完成
多端发布能力有实际验证证据
```

## 15\.12 完成标准

```Plain Text
满足以下条件即可进入阶段7：

CareerPulse Vue 完整运行
Vue 使用正式 CareerPulse FastAPI
AI职业伙伴真实接入百宝箱
Vue 不绕过百宝箱直接调用第三方 LLM 完成主 Agent 功能
百宝箱能够真实调用 CareerPulse MCP
职业画像接入真实数据
匹配接入真实 MatchService
路径接入真实 PathService
训练接入真实 TrainingService
成长反馈能够更新用户状态
CareerState 能同步到 Vue
桌面端主要页面显示正常
关键页面具备移动端基本适配
百宝箱 Web 发布成功
根据实际权限完成额外渠道发布或预览验证
Demo Mode 和正式模式可以清晰区分
```

## 15\.13 本阶段保留证据

```Plain Text
CareerPulse 原页面截图
CareerPulse 改造后页面
AI职业伙伴页面
能力雷达图
人岗匹配页面
能力缺口页面
3 年 / 5 年职业路径
学习计划页面
职场训练页面
成长档案页面
Agent执行链路页面
Vue 调用百宝箱日志
百宝箱 Tool Calling 日志
MCP 调用日志
Vue → 百宝箱 → MCP → CareerPulse 完整链路截图
百宝箱原生运行页面
百宝箱 Web 发布截图
支付宝 / 小程序发布或预览截图
移动端页面截图
```

---

# 16\. 阶段7：Agent、知识库、算法、平台与端到端评测

## **时间**

```Plain Text
D9
共同完成
```

## 目标

```Plain Text
在最终演示冻结前，对CareerPulse的：
    Agent
    CareerOrchestrator
    知识库
    确定性算法
    MCP / Tool Calling
    百宝箱平台
    CareerPulse Vue
    FastAPI
    完整端到端链路
    AI伦理与隐私
进行系统评测。

本阶段原则：不再以增加功能为主，而是发现问题、修复问题、形成测试证据

重点检查：
Agent 回答错误
Agent 职责混乱
Tool 调用错误
Schema 不一致
LLM 编造确定性结果
知识库无依据回答
Match / Path 算法异常
百宝箱调用失败
Vue 与 CareerState 不同步
session 丢失
MCP 超时
fallback 失效
隐私泄露
API Key 泄露
```

## 16\.1 Agent 评测

重点评测：

```Plain Text
ProfileAgent
JobAgent
MatchAgent
PathAgent
TrainingAgent
FeedbackAgent
CareerOrchestrator
```

```Plain Text
测试输入至少覆盖：
正常输入
信息完整输入
信息不完整输入
模糊输入
错误输入
极短输入
超长输入
多轮补充信息
Tool 调用成功
Tool 调用失败
Service 异常
LLM 异常
单 Agent 失败
fallback
CareerState 连续更新

重点检查：
Agent 是否越权承担 Service 的确定性计算
LLM 是否自行编造匹配分
是否调用正确 Tool
是否读取正确 CareerState
是否正确更新 CareerState
某个 Agent 失败后是否导致全链路崩溃
summary 是否与 data 一致
tool_calls 是否是真实调用
duration_ms 是否正确记录
fallback_used 是否真实
```

## 16\.2 百宝箱对话与 Tool 选择评测

准备真实用户问题，例如：

```Plain Text
我适合做AI应用开发吗？

我是计算机专业学生，但不知道以后做什么。

我的Python能力够找后端岗位吗？

AI应用开发这个岗位未来还有发展吗？

我和这个岗位匹配度多少？

我最大的能力短板是什么？

未来3年应该怎么走？

给我安排一个职场训练。

刚才训练完了，我哪里需要改进？

我不想做这个岗位了，可以换一个方向吗？
```

检查百宝箱是否：

```Plain Text
正确理解用户意图
信息不足时主动追问
不重复询问已经知道的信息
正确选择 Tool
不需要 Tool 时不乱调用
正确选择知识库
不自行编造匹配分
不编造用户经历
不自行改变 Service 返回的确定性结果
Tool 失败时明确说明
Tool 返回后能够正确解释
多轮对话能够保持上下文
```

## 16\.3 知识库评测

```Plain Text
测试问题覆盖：
职业趋势
岗位技能
行业变化
学习资源
职场训练
职业发展
无答案问题
模糊问题
跨文档问题
错误诱导问题

检查：
检索结果是否相关
是否命中正确资料
是否出现无关文档
回答是否有资料依据
无资料时是否拒绝编造
知识库是否承担了本应由Service完成的计算
知识库旧资料是否与新资料冲突
元数据是否能够辅助筛选
```

记录：

```Plain Text
测试ID
用户问题
预期知识来源
实际检索结果
是否命中
最终回答
是否正确
问题原因
优化方式
优化后结果
```

形成：

- 测试集

- 首轮结果

- 问题分析

- 优化记录

- 最终效果

## 16\.4 MatchService 算法评测

```Plain Text
重点检查：
学生能力向量
岗位能力向量
岗位权重
MatchScore
Gap
Priority
```

```Plain Text
至少准备：
高匹配用户
中匹配用户
低匹配用户
缺失关键技能用户
多能力相同用户
岗位能力为空
用户能力为空
非法能力等级
权重异常

检查：

相同输入结果是否完全一致
匹配分是否由代码计算
能力 Gap 方向是否正确
缺失能力是否按规则处理
Priority 是否符合公式
是否存在除零问题
分数范围是否正常
LLM 是否只解释结果而没有修改分数
```

算法结果必须可重复。

## 16\.5 PathService 算法评测

```Plain Text
准备至少：
已接近目标岗位的用户
能力缺口较大的用户
需要横向转岗的用户
需要长期成长的用户
存在多条候选路径的用户
无可用路径用户

检查：
3 年路径是否合理
5 年路径是否合理
职业节点顺序是否合理
是否考虑当前能力
是否考虑目标岗位
是否考虑能力 Gap
GrowthValue 是否进入评分
TransferCost 是否进入评分
AbilityGapCost 是否进入评分
候选路径是否按分数排序
无路径时是否正常 fallback
相同输入是否产生稳定结果
```

## 16\.6 Training 与 Feedback 评测

至少覆盖 3 类典型职场训练：

```Plain Text
remote_collaboration
AI辅助办公
cross_role_communication
```

项目实际命名可以不同，但必须至少覆盖 3 类典型职场场景。

至少一类训练完成：

```Plain Text
生成任务
↓
用户回答
↓
系统评分
↓
维度得分
↓
问题分析
↓
改进建议
↓
能力更新
↓
成长档案更新
```

检查：

- 训练内容是否与目标岗位相关

- 是否优先针对用户能力缺口

- 评分维度是否固定

- 评分规则是否明确

- 极差回答是否能拉开分数

- 优秀回答是否得到合理分数

- 空回答是否正常处理

- 相同回答评分是否基本稳定

- 建议是否具体可执行

- 训练结果是否保存

- Feedback 是否真正影响成长记录

- 能力等级变化是否有依据

- 学习优先级变化是否可解释

## 16\.7 MCP / Tool Calling评测

逐个测试正式工具：

```Plain Text
analyze_student_profile
analyze_job_and_trend
calculate_job_match
recommend_career_path
generate_and_score_training
recommend_learning_and_job_resources
save_growth_feedback
```

每个 Tool 至少测试：

```Plain Text
正常情况：
参数完整
参数合法
Service 正常
返回正确 Schema

参数异常：
缺少必填参数
参数类型错误
参数值非法
session 不存在

服务异常：
Service 报错
数据库异常
LLM 超时
工具超时
网络异常

检查：
输入Schema
输出Schema
鉴权
参数校验
错误结构
超时
重试
fallback
request_id
session_id
Tool日志
隐私脱敏
```

## 16\.8 双向端到端评测

必须测试两条完整链路。

**链路 A：百宝箱原生端**

```Plain Text
百宝箱用户
↓
CareerPulse职业成长伙伴
↓
Tool Calling
↓
MCP
↓
CareerPulse FastAPI
↓
Agent / Service
↓
结构化结果
↓
百宝箱
↓
自然语言回答
```

必须真实跑通。

**链路 B：CareerPulse 主 Web**

```Plain Text
CareerPulse Vue
↓
POST /api/tbox/chat
↓
CareerPulse FastAPI
↓
百宝箱 CareerPulse职业成长伙伴
↓
Tool Calling
↓
MCP
↓
CareerPulse FastAPI
↓
Agent / Service
↓
CareerState
↓
百宝箱生成最终回复
↓
CareerPulse FastAPI
↓
CareerPulse Vue
```

必须真实跑通。

重点检查：

- `user_id` 是否一致

- `session_id` 是否一致

- `request_id` 是否能够追踪

- 百宝箱是否真实参与

- MCP 是否真实调用

- Tool 是否调用正确

- CareerState 是否被正确更新

- Vue 页面是否展示最新结果

- 多轮对话上下文是否连续

- 用户刷新页面后状态是否可以恢复

- Tool 异常后是否有合理提示

- 是否发生循环 Tool Calling

- 是否出现重复调用同一 Tool

## 16\.9 Web 产品评测

```Plain Text
检查主要页面：
首页
AI职业伙伴
职业画像
人岗匹配
职业路径
学习计划
职场训练
成长档案
Agent执行链路
历史记录

每个核心页面至少测试：
正常数据
空数据
数据加载
接口失败
接口超时
长文本
页面刷新
重复点击
历史记录恢复
移动端显示

不得出现：
页面白屏
原始 JSON 直接展示给普通用户
Python / JavaScript 错误堆栈暴露
Token 暴露
页面数据与 CareerState 不一致
图表数据与后端结果不一致
加载状态永久卡死
```

## 16\.10 AI 伦理与隐私检查

检查：



```Plain Text
用户信息：
简历是否按必要范围使用
手机号是否脱敏
邮箱是否脱敏
姓名是否尽量避免写入普通日志
完整简历是否避免进入 Agent 普通日志

模型输出：
不无依据评价用户能力
不把职业推荐说成唯一正确选择
不把匹配度包装成录用概率
不把职业路径说成确定未来
用户始终保留最终决策权
模型失败时不伪造结果

密钥：
百宝箱 Token、API Key、第三方模型 Key 必须：只存在服务端
↓
通过环境变量读取
↓
不进入 Git
↓
不进入前端
↓
不进入截图
↓
不进入演示视频

AI伦理材料至少说明：
数据最小化使用
用户隐私保护
算法偏见风险
推荐结果可解释
人保持最终决策权
AI 不替代用户本人进行职业选择
```

## 16\.11 内部验收建议

以下属于项目内部质量指标，不是 A02 官方强制指标。

建议达到：

```Plain Text
核心 Service 单元测试：全部通过

核心 Tool 正常调用通过率：≥95%

固定输入算法结果：
100% 可重复

正式 Demo 主链路：
连续运行至少5次无阻断错误

API Key 明文泄露：
0

高风险隐私泄露：
0

P0级问题：
0
```

如果核心链路仍然存在明显问题，本阶段不要继续增加新功能，应优先修复。

## 16\.12 问题分级

```Plain Text
P0：必须立即修复
包括：
系统无法启动
核心 Agent 链路断裂
百宝箱无法运行
MCP 无法调用
CareerPulse Vue 无法完成 AI 对话
核心 Service 不可用
API Key 泄露
主要页面白屏

P1：演示冻结前必须修复
包括：
Tool 选择错误
Schema 不一致
匹配算法明显异常
职业路径明显异常
CareerState 不同步
知识库严重误答
训练结果无法保存
用户反馈无法更新状态
主要页面功能异常

P2：可延后
包括：
非核心样式问题
非核心页面体验问题
次要文案问题
轻微响应式布局问题
```

## 16\.13 Codex 代码审查

给 Codex：

```Plain Text
任务：对当前 CareerPulse A02 改造分支进行最终代码审查。

暂时不要修改代码。

重点检查：

1. Agent 与 Service 职责是否混乱
2. 是否由 LLM 凭空生成匹配分
3. 是否由 LLM 凭空生成能力 Gap
4. Schema 是否统一
5. Tool 是否具有参数校验
6. 是否存在未处理异常
7. Agent 日志是否泄露简历隐私
8. MCP/API 是否有鉴权
9. Demo Mode 是否污染正式模式
10. 测试是否覆盖核心业务
11. 是否存在硬编码 API Key / Token
12. 百宝箱 Tool Schema 与后端 Schema 是否一致
13. 百宝箱 Token 是否暴露给 Vue
14. Vue 与 CareerState 是否存在状态不同步
15. 是否存在循环 Tool Calling
16. 是否存在重复 Tool Calling
17. 是否存在材料中声明实现但代码实际没有实现的能力
18. 是否存在已经废弃但仍在主链路中的旧 CareerPulse 逻辑
19. 是否存在两个不同版本的匹配或路径计算逻辑
20. 公共接口修改是否同步更新契约文档

输出：

【问题】
【严重程度：P0 / P1 / P2】
【文件位置】
【问题原因】
【修改建议】

不要自动修改代码。
不要自动提交 Git。
```

## 16\.14 Hermes 最终赛题评审

给 Hermes：

```Plain Text
请作为 CareerPulse A02 项目的最终技术评审顾问。

请严格对照 A02 赛题要求检查当前系统。

重点检查：

1. 感知：用户状态和信息采集
2. 认知：岗位与职业趋势分析
3. 决策：人岗匹配和职业路径
4. 生成：学习内容和训练任务
5. 执行：阶段任务和资源对接
6. 反馈：训练评估与动态更新

同时检查：

7. 百宝箱企业版是否真实使用
8. 百宝箱智能体是否真实配置
9. 百宝箱知识库是否真实使用
10. MCP / Tool Calling 是否真实调用
11. CareerPulse Vue 是否真实接入百宝箱 Agent
12. 自研 FastAPI 是否承担真实业务计算
13. Web发布是否完成
14. 多端发布是否有验证
15. AI伦理与隐私是否落实
16. Agent日志是否完整
17. Agent评测是否完成
18. 算法评测是否完成
19. 双向端到端链路是否跑通
20. 项目材料描述是否与实际代码一致

我会提供：

- 当前代码
- 架构文档
- API契约
- Agent契约
- MCP工具目录
- 百宝箱配置截图
- CareerPulse Web截图
- 测试报告
- Git提交摘要
- 演示视频

请输出：

1. 已满足项
2. 部分满足项
3. 未满足项
4. 高风险问题
5. 演示前必须修改项
6. 可以放进材料的亮点
7. 材料中必须补充的证据
8. 可能被评委质疑的架构点
9. A02平台适配度评价
10. 当前是否具备演示冻结条件

不要修改代码。
```

## 16\.15 完成标准

必须做到：

```Plain Text
六个 Agent 核心测试通过
CareerOrchestrator 测试通过
MatchService 算法测试通过
PathService 算法测试通过
至少 3 类职场训练完成测试
Feedback 动态更新测试通过
知识库测试完成
正式 MCP Tool 测试完成
百宝箱原生端完整链路通过
CareerPulse Vue 完整 AI 链路通过
Vue 与 CareerState 状态同步正常
Web 主要页面回归测试完成
移动端关键页面可正常使用
AI伦理和隐私检查完成
API Key / Token 明文泄露问题为 0
P0 问题全部清零
P1 问题基本清零
形成完整测试报告
形成迭代记录
具备进入阶段8演示冻结的条件
```

## 16\.16 本阶段保留证据

保留：

```Plain Text
Agent 离线评测集
Agent 测试结果
CareerOrchestrator 测试
知识库测试集
知识库优化前后对比
MatchService 测试案例
PathService 测试案例
3 类职场训练案例
不同回答评分对比
Feedback 更新前后结果
MCP Tool 测试记录
Tool Calling 日志
百宝箱原生端完整链路
CareerPulse Vue 完整链路
request_id 追踪记录
session_id 追踪记录
正常调用截图
参数异常截图
Tool 超时截图
fallback 截图
Web 回归测试
移动端测试
隐私与安全检查记录
用户测试反馈
Bug 修复记录
Codex 最终审查报告
Hermes 最终赛题评审报告
最终测试报告
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

比赛提交前技术侧至少满足：

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

---

# 与提交材料的对应关系xxxxxxxxxx src/  api/          # 接口封装与业务 API 模块  components/   # 业务组件（图表、图谱、上传、富文本等）  layouts/      # 页面布局  router/       # 路由与鉴权守卫  services/     # Mock 服务  stores/       # Pinia 状态管理  styles/       # 全局样式与主题  views/        # 页面视图（输入、分析、路径、计划、个人中心）text
