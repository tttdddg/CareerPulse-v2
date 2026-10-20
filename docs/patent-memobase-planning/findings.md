# 第二件专利调研发现

## 初始判断

- 当前题目应避免直接使用开源项目名 Memobase，拟采用“职业时序证据记忆管理与上下文装配”作为技术主题。
- 正式权利要求只采用项目代码、亮点材料可明确支持或可由其固有实现推出的技术特征。
- 通用的用户画像、事件时间线、向量检索和缓存批处理属于高风险现有技术区域，需要通过职业阶段、证据来源、确定性结果隔离、角色权限和隐私预算等组合限定形成差异。

## 项目代码证据

- `backend/app/services/profile_service.py` 已实现多源画像合并：解析简历、表单、项目、实习、竞赛、证书及历史画像，采集证据、标准化能力标签、去重、计算能力维度、完整度和竞争力分数；历史证据以 `EvidenceSource.HISTORY` 参与合并。
- `backend/app/services/history_service.py` 已提供按用户查询历史匹配摘要及按历史编号获取完整快照的能力，快照包含学生画像、岗位画像、分析、报告和时间。
- `backend/app/orchestrator/career_state.py` 已定义会话级 `CareerState`，承载画像、岗位、匹配、路径、训练、资源、反馈和 Agent 日志；`apply_agent_data` 只允许声明字段更新，并对阶段结果做深拷贝隔离。
- `backend/app/orchestrator/career_orchestrator.py` 已实现按 Agent 顺序运行、阶段性执行、状态持久化和失败/降级状态汇总；阶段输入在调用前临时注入，调用结束后恢复。
- `backend/app/services/feedback_service.py` 已实现反馈保存、优先级调整、成长快照和趋势判断；但反馈与成长数据仍由服务实例内存字典保存，不能证明统一长期记忆已经完成。
- `backend/app/db_state.py`、V001/V003/V004 迁移已提供 `career_state`、`agent_logs`、`platform_tool_calls`、`growth_archives`、`user_feedback` 等持久化结构；平台调用账本只保存请求指纹、结果字段指针和安全错误类型，不保存原始画像、证据文本或令牌。
- Profile 与 Feedback Schema 对额外字段、能力标签、证据隐私、评分范围和身份字段有严格校验；这些机制可作为记忆写入前的事实/隐私门禁证据。

## 亮点文件的方案证据

- 亮点文件明确提出 EG-Memobase，在 Profile Memory 和 Event Memory 之外增加 Emotion State 与 Goal State，并采用 Agent Status Bar / Working Memory 按任务融合当前对话、相关历史、情感状态、目标状态和任务上下文。
- 亮点文件明确提出选择性写入、更新、合并与摘要沉淀，按需召回而非把全部历史对话塞入上下文；并提出“长期记忆—状态融合—事件触发—共情/监督/激励/调整—反馈更新记忆”闭环。
- 亮点文件还明确提出焦虑/挫败触发共情与任务降阶、目标过大触发阶段拆解、临近或停滞触发提醒、关键节点触发激励以及能力/兴趣/岗位环境变化触发成长计划调整。

## 现有技术与检索边界

- Memobase 官方公开资料已明确 Profile Memory、Event Memory、按需 Context API、批量处理和 token 预算等通用能力，不能作为本案独立创新本身。来源：[GitHub](https://github.com/memodb-io/memobase)。
- CN120766888A《面向心理咨询场景的ai长时记忆系统及方法》公开了会话总结、用户画像、事件向量检索和滑动窗口上下文；来源：[Google Patents](https://patents.google.com/patent/CN120766888A/zh)。
- CN121031669A《一种多层次模块化个人记忆大模型及其构建方法》公开了时序记忆数据库、时间范围查询、情绪标签和多模态记忆组织；来源：[Google Patents](https://patents.google.com/patent/CN121031669A/zh)。
- CN119990277A《用户记忆数据生成的方法、系统、计算机以及存储介质》公开了基于对话建立用户记忆知识图谱；来源：[Google Patents](https://patents.google.com/patent/CN119990277A/zh)。
- CN121303359A《一种对话交互方法、装置、设备及存储介质》公开了事件记忆召回、情感强度/交互频率/事件重要性评分和记忆衰减强化；来源：[Google Patents](https://patents.google.com/patent/CN121303359A/zh)。
- 本轮国知局公布公告浏览器探测因 Windows 子进程权限失败，未把失败误写成“无相关专利”；因此查新采用可访问的官方项目仓库和 Google Patents 公开页面作补充，证据级别标为“摘要/公开页面级，未通读全部法律文本”。

## 暂定发明构思

- 技术问题：职业导航多 Agent 在跨会话、跨职业阶段运行时，如何避免事实、确定性结果和模型推断相互覆盖，同时只向当前任务提供必要的历史上下文，并让情感与目标变化能够触发可审计的陪伴策略。
- 技术手段：对职业证据记忆对象按来源/时间/职业阶段/隐私级别/可见 Agent 范围分层；保留原始证据、确定性服务结果、模型推断及版本关系；以情感状态和目标状态形成状态投影；按 Agent 任务、有效期、相关性和上下文预算装配最小上下文；将事件触发动作及反馈回写为新版本记忆。
- 技术输出：供指定 CareerPulse Agent 使用的角色化最小上下文包、当前情感状态、目标进度状态及可追溯的陪伴动作指令。

## 初步区别特征

- F1：面向职业阶段的证据记忆对象，将来源、发生时间、有效期、职业阶段、隐私级别和可见 Agent 范围与记忆内容绑定。
- F2：将原始职业证据、确定性 Service 结果、用户确认事实和模型推断分层保存，并禁止低可信层覆盖高可信层。
- F3：在 Profile Memory、Event Memory 之外维护 Emotion State 与 Goal State，并由当前事件联合驱动策略选择。
- F4：依据当前 Agent 任务、记忆有效期、相关性、令牌预算和隐私约束装配最小上下文包，而非返回全部历史。
- F5：将冲突处理、状态变化、陪伴动作和反馈更新写成带版本的可审计记忆变更，形成跨会话闭环。
