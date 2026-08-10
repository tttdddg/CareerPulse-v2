# 任务计划（CareerPulse）

## 目标
开发「吾 AI 职导 / CareerPulse」AI 职业规划系统（Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router 4 + Axios + ECharts + AntV X6 + 富文本编辑器），完成模块化目录划分、自定义蓝紫主题、页面跳转逻辑与可视化功能。

## 范围与约束
- 技术栈固定：Vue 3、TypeScript、Vite、Element Plus、Pinia、Vue Router 4、Axios、ECharts、AntV X6、富文本编辑器
- 核心模块：
  - 首页
  - 登录注册
  - 数据输入中心
  - 人岗匹配分析看板
  - 职业路径图谱
  - 个性化成长计划
  - 个人中心/历史记录
- 交付物：模块化目录结构、Element Plus 蓝紫主题、页面路由与可视化

## 计划分解
| 阶段 | 任务 | 状态 | 产出 |
| --- | --- | --- | --- |
| 1 | 盘点当前项目结构与依赖（若已有代码） | pending | 现状说明、风险点 |
| 2 | 设计模块化目录结构与路由信息架构 | pending | 目录与路由草案 |
| 3 | 自定义 Element Plus 蓝紫主题 | pending | 主题变量与样式文件 |
| 4 | 搭建路由与页面跳转逻辑（含守卫） | pending | 路由配置 |
| 5 | 核心页面骨架与布局（首页/登录/输入中心等） | pending | 页面骨架 |
| 6 | 数据输入中心表单与数据流 | pending | 表单与状态管理 |
| 7 | 人岗匹配分析看板（ECharts） | pending | 图表与指标布局 |
| 8 | 职业路径图谱（AntV X6） | pending | 图谱画布与数据绑定 |
| 9 | 个性化成长计划与富文本编辑器 | pending | 编辑器接入 |
| 10 | 个人中心/历史记录与数据展示 | pending | 列表与详情 |
| 11 | 体验优化与验证（响应式/可用性） | pending | 调整记录 |

## 关键决策
- 主题实现方式：Element Plus 变量 + 自定义样式层
- 图表与图谱：ECharts + AntV X6 分离封装
- 目录划分：按模块与通用组件双维度

## 风险与依赖
- 富文本编辑器选型需确认（如无指定，默认准备多方案）
- 若项目已有代码，需要避免破坏现有结构

## 错误记录
| 错误 | 尝试 | 解决方案 |
| --- | --- | --- |
| session-catchup 脚本缺失 | 1 | 已记录；继续手动生成计划文件 |
| 当前技能目录缺少 session-catchup.py | 1 | 已读取现有规划文件与 git 状态，手动恢复上下文 |
| 预期的 backend/app/core 与 backend/requirements.txt 不存在 | 1 | 继续按实际目录结构盘点，从根目录依赖文件确认实现边界 |
| rg 查找依赖文件无匹配并返回 exit 1 | 1 | 改用文件枚举和定向检查，不重复同一失败命令 |
| 枚举 backend/app/schemas 时目录不存在导致命令 exit 1 | 1 | 已确认需要新建允许的 profile_schema.py，不再依赖该目录预存在 |
| PowerShell here-string 传给 Python 时中文测试字面量变为 `??` | 1 | 改用模块内 UTF-8 Mock 数据及 ASCII 测试变体，避免管道编码污染 |
| 枚举 prompts/profile_agent 时目录不存在导致命令 exit 1 | 1 | 已确认在允许范围内新建 Prompt 目录与文件 |
| PowerShell 管道再次破坏 Python 脚本中的中文断言文本 | 1 | 静态自动检查改用 ASCII 关键标记；中文语义由人工审阅记录，不重复传输中文字面量 |
| 现有 Mock 全链路测试 2/7 失败 | 1 | 测试假设 ProfileAgent 无外部配置也 success；新真实 Agent 正确 fallback。改用测试进程注入合法 LLM 响应验证兼容链路，并记录需后续获准更新旧测试 |
| 首次注入 LLM 的回归测试仍有 1/7 失败 | 2 | TBox adapter 在 patch 前已持有模块级 orchestrator；下一次同时注入该既有 ProfileAgent 实例，不重复原方案 |
| 审查报告称无 Key 时旧 Mock 测试仍通过，但实测 2/7 失败 | 1 | 已确认报告此结论不准确；专项测试应注入 fake LLM，旧集成测试需明确测试 success 还是 fallback 语义 |
| `unittest discover -s app` 将 namespace 子目录当顶级包，发生相对导入越界 | 1 | 改用完整模块名执行；记录 `app/__init__.py` 缺失的发现限制 |
| `unittest discover -s app -t .` 因 `app` 不是常规包而拒绝 start directory | 2 | 不再重复 discovery，使用完整测试模块名合跑 |
| 预期的 `backend/app/data/job_type_profiles.json` 不存在 | 1 | 使用实际存在的 `jobs_demo.json` 与数据字典岗位权重示例，不创建数据文件 |
| PowerShell 管道将 Job Schema 回归脚本中的中文标签变成 `????` | 1 | 改为从 UTF-8 `jobs_demo.json` 动态读取标签，测试脚本仅保留 ASCII 字面量 |
| Job Prompt 最终脚本中的中文权重断言被 PowerShell 管道破坏 | 1 | 最终检查改用 JSON 字段名与枚举值等 ASCII 标记，不重复中文管道断言 |
| grounding 后平台注入脚本的中文空趋势说明被管道转成问号 | 1 | 直接调用 `JobAgent._fallback_trend()` 构造中性趋势对象后重跑 |

## 当前任务：逐页业务逻辑检查与补齐（2026-03-09）

| 阶段 | 任务 | 状态 | 产出 |
| --- | --- | --- | --- |
| A1 | 盘点路由与页面业务现状 | complete | 缺口清单（登录联动、前置校验、数据恢复） |
| A2 | 补齐关键缺失逻辑 | complete | 多页面逻辑修复 |
| A3 | 构建验证与回归检查 | complete | 构建通过，输出剩余风险 |

## 当前任务：阶段2统一 LLM Client（2026-08-09）

| 阶段 | 任务 | 状态 | 产出 |
| --- | --- | --- | --- |
| B1 | 阅读 A02 契约并盘点现有 LLM 配置、依赖与测试结构 | complete | 约束与复用点 |
| B2 | 设计并实现统一 LLM Client 与配置 | complete | 稳定接口、统一异常、超时及结构化输出 |
| B3 | 补充最小测试 | complete | 本地 Mock Transport 覆盖 6 条路径 |
| B4 | 运行相关测试并复核 diff | complete | 最小测试 6/6、阶段1回归 7/7 通过 |

## 当前任务：ProfileAgent 阶段2结构化输出 Schema（2026-08-09）

| 阶段 | 任务 | 状态 | 产出 |
| --- | --- | --- | --- |
| C1 | 核对公共契约、数据字典、ProfileAgent、CareerState 与能力标签 | complete | 字段、范围与兼容性结论 |
| C2 | 实现 ProfileAgent Pydantic Schema 与必要统一导出 | complete | 可直接写入 CareerState 的严格模型 |
| C3 | 验证合法及非法输入并运行回归测试 | complete | 合法 1 项、非法 8 项、现有回归 7 项通过 |
| C4 | 复核 diff、评分风险与修改边界 | complete | 仅新增允许的 profile_schema.py 业务文件 |

## 当前任务：CareerPulse ProfileAgent Prompt V1（2026-08-09）

| 阶段 | 任务 | 状态 | 产出 |
| --- | --- | --- | --- |
| D1 | 核对 Agent 契约、数据字典、ProfileSchema、能力标签与三份匿名样例 | complete | Prompt 输入输出边界 |
| D2 | 编写 system prompt 与 user template | complete | prompts/profile_agent 下 V1 文件 |
| D3 | 用三份匿名样例人工模拟检查 | complete | 输入覆盖、预期抽取及幻觉检查 |
| D4 | 复核文件、禁止项与风险 | complete | 3 个 Prompt 文件、UTF-8 与静态规则检查通过 |

## 当前任务：ProfileAgent 真实 LLM 升级（2026-08-10）

| 阶段 | 任务 | 状态 | 产出 |
| --- | --- | --- | --- |
| E1 | 复核冻结契约、Client、Schema、BaseAgent、State 与 Prompt | complete | 调用、重试、fallback 和日志边界 |
| E2 | 升级 profile_agent.py | complete | 真实 LLM 结构化画像与规则 fallback |
| E3 | 隔离测试六类场景并跑现有回归 | complete | 最终隔离 7/7、注入 LLM 回归 7/7 |
| E4 | 复核 diff、隐私与状态语义 | complete | fallback/status/error/duration/日志边界已验证 |

## 当前任务：阶段2 ProfileAgent 独立验证（2026-08-10）

| 阶段 | 任务 | 状态 | 产出 |
| --- | --- | --- | --- |
| F1 | 读取 Agent/Schema/Prompt/三份样例并确认模型环境 | complete | 无 API Key，采用受控模拟 LLM |
| F2 | 运行正常样例 3 次与重复一致性检查 | complete | 结构、事实对应、受控一致性检查 |
| F3 | 运行不完整、模型异常、非法 JSON | complete | completeness/retry/fallback/日志检查 |
| F4 | 汇总独立测试报告与 Bug/限制 | complete | 6 个测试 ID + 2 个对抗探针 |

## 当前任务：ProfileAgent 审查反馈核验（2026-08-10）

| 阶段 | 任务 | 状态 | 产出 |
| --- | --- | --- | --- |
| G1 | 读取审查报告并逐项定位当前实现 | complete | 9 项问题映射 |
| G2 | 用代码探针确认争议问题 | complete | 可变性、namespace import、转义行为 |
| G3 | 设计专项测试落盘方案与样例 | complete | app/agents/tests + unittest 注入方案 |
| G4 | 输出问题真伪、优先级和建议 | complete | 核验报告 |

## 当前任务：ProfileAgent 阶段2封板（2026-08-10）

| 阶段 | 任务 | 状态 | 产出 |
| --- | --- | --- | --- |
| H1 | 将专项测试持久化到仓库 | complete | ProfileAgent 7 项可重复回归测试 |
| H2 | 修复 Prompt 输入中 `&` 语义失真并补回归 | complete | 保留 `&` 语义、中和尖括号的最小修复 |
| H3 | 运行专项测试与阶段1集成基线 | complete | 专项 7/7；合跑 12/14，2 项为已知旧断言冲突 |
| H4 | 固化语义 grounding 风险和 JobAgent 前置边界 | complete | Prompt 检查文档新增封板基线与风险边界 |

## 当前任务：JobAgent 阶段2结构化输出 Schema（2026-08-10）

| 阶段 | 任务 | 状态 | 产出 |
| --- | --- | --- | --- |
| I1 | 核对冻结契约、数据字典、JobAgent、CareerState 与岗位样例 | complete | 两个独立状态模型及契约差异结论 |
| I2 | 实现严格 Pydantic Schema | complete | JobProfile、TrendResult、JobAgentOutput |
| I3 | 验证合法示例和两类非法输入 | complete | 合法通过；等级越界/权重和错误被拒绝 |
| I4 | 运行回归、复核 diff 与修改边界 | complete | 三岗位+趋势校验通过，ProfileAgent 7/7，编译通过 |

## 当前任务：CareerPulse JobAgent Prompt V1（2026-08-10）

| 阶段 | 任务 | 状态 | 产出 |
| --- | --- | --- | --- |
| J1 | 核对 Agent 契约、数据字典、JobSchema、标签、岗位与趋势样例 | complete | 缺少真实趋势样例，采用保守空上下文策略 |
| J2 | 编写 system prompt 与 user template | complete | system.txt + user_template.txt |
| J3 | 用三个岗位样例检查输入结构和推断边界 | complete | PROMPT_V1_CHECK.md 三样例记录 |
| J4 | 静态验证 Prompt、Schema 对齐和禁止项 | complete | 三样例组装、UTF-8、字段与禁令检查通过 |

## 当前任务：JobAgent 真实 LLM 升级（2026-08-10）

| 阶段 | 任务 | 状态 | 产出 |
| --- | --- | --- | --- |
| K1 | 复核冻结契约、Client、Schema、BaseAgent、State、Prompt 与 Mock | complete | Client/Schema/状态/日志/fallback 边界确认 |
| K2 | 升级 `job_agent.py` | complete | 真实 LLM、身份回填、evidence、规则/Demo fallback |
| K3 | 隔离测试七类场景 | complete | 7/7 通过，含重试/异常/隐私/双状态写回 |
| K4 | 运行相关回归并复核 diff | complete | 隔离7/7、注入平台7/7、Profile7/7、编译通过 |

## 当前任务：阶段2 JobAgent 独立验证（2026-08-10）

| 阶段 | 任务 | 状态 | 产出 |
| --- | --- | --- | --- |
| L1 | 复核 Agent/Schema/Prompt/岗位及趋势样例和模型环境 | complete | 无 provider、无独立趋势文件，采用受控验证 |
| L2 | 执行三岗位语义与结构验证 | complete | AI产品/数据分析/后端三组通过 |
| L3 | 执行稀疏/空趋势/非法JSON/模型异常 | complete | 四组通过，retry/fallback 真实触发 |
| L4 | 对抗检查幻觉、禁止字段、State 与日志 | complete | grounding Bug 修复后四类造假被拦截 |
