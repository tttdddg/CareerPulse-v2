export interface AssistantPresetMessage {
  role: 'assistant' | 'user'
  content: string
}

export const ASSISTANT_QUICK_QUESTIONS = [
  '我最适合哪个岗位？',
  '未来30天怎么准备？',
  '如何优化Agent项目？',
  '帮我准备面试自我介绍'
] as const

export const ASSISTANT_WELCOME_MESSAGE =
  '你好，林晓宁。我已经结合你的 AI Agent 开发方向、82% 岗位匹配度和当前能力差距整理好建议。你可以问我岗位选择、项目补强或面试准备。'

const POSITION_RESPONSE =
  '优先推荐 AI Agent开发工程师，当前匹配度 82%。你的 Agent流程设计、RAG实践和前后端联调经历与岗位要求最接近。\n\n备选方向：\n1. RAG应用开发工程师｜78%：知识库与评测经历可直接迁移。\n2. LLM应用开发工程师｜75%：适合继续强化结构化输出、模型路由与效果评测。\n\n投递时建议把 CareerPulse 放在项目首位，并突出 Tool Calling、执行日志和结果校验。'

const PLAN_RESPONSE =
  '建议按四周完成一轮可展示的工程化补强：\n\n第1周｜用 FastAPI 重构 Agent 服务，补齐参数校验、异常分层和自动化测试。\n第2周｜建立不少于30条 RAG 评测集，记录召回、引用、拒答与失败类型。\n第3周｜完成一个 MCP 工具接入，展示调用日志、超时和降级处理。\n第4周｜使用 Docker 打包并整理 README、架构图、指标结果和两分钟演示视频。'

const PROJECT_RESPONSE =
  '把 CareerPulse 从“功能可用”升级成“证据可验证”，重点补四类内容：\n\n1. 流程证据：展示 Agent 如何拆解任务、选择工具并回收结果。\n2. 质量证据：给出 RAG 召回率、引用准确性、拒答率和失败案例。\n3. 工程证据：补充测试、日志、任务状态、异常降级与 Docker 启动方式。\n4. 业务证据：说明目标用户、使用场景、前后效果和下一步迭代。\n\n这样能同时支撑 AI Agent、RAG 和 LLM 应用开发三个岗位方向。'

const INTERVIEW_RESPONSE =
  '可以这样介绍：\n\n“我是一名计算机专业学生，目标方向是 AI Agent 应用开发。过去的项目和实习主要围绕企业知识库、RAG 测试、Agent 流程设计以及前后端联调展开。我主导完成了 CareerPulse 多 Agent 职业导航项目，负责需求拆解、Tool Calling、知识检索、执行日志和结果校验。目前我正在进一步补强 Python 工程化、RAG 评测和容器化交付，希望在真实业务场景中把 AI 能力做成稳定、可验证的产品。”\n\n控制在45秒左右，讲完后可接 CareerPulse 的一个具体技术难点。'

const DEFAULT_RESPONSE =
  '结合你当前的 AI Agent 开发目标，最值得优先补强的是“可验证的工程证据”。建议把问题落到 CareerPulse 项目中：明确业务目标，补齐 Agent 执行链路、RAG 评测、异常降级、测试日志和容器化交付，再把结果整理成可复现的项目说明。这样既能提升岗位匹配度，也更方便在面试中讲清楚你的实际贡献。'

export const getAssistantPresetResponse = (question: string): string => {
  const normalized = question.trim().toLowerCase()

  if (/岗位|适合|选择|推荐|方向/.test(normalized)) {
    return POSITION_RESPONSE
  }
  if (/30天|计划|学习|准备|提升|补强/.test(normalized)) {
    return PLAN_RESPONSE
  }
  if (/项目|作品|优化|careerpulse|agent/.test(normalized)) {
    return PROJECT_RESPONSE
  }
  if (/面试|介绍|自我|表达/.test(normalized)) {
    return INTERVIEW_RESPONSE
  }
  return DEFAULT_RESPONSE
}
