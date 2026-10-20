export const DEMO_STUDENT_ID = 92028
export const DEMO_PRIMARY_JOB_ID = 149
export const DEMO_REPORT_ID = 6201

export const DEMO_PROFILE_FORM = Object.freeze({
  name: '林晓宁',
  skills:
    'Python、FastAPI、LLM应用开发、Prompt工程、RAG、Tool Calling、MCP基础、Vue3、TypeScript、PostgreSQL、Redis、Git、Docker基础',
  certificates: 'CET-6；腾讯青科训练营结营；阿里AI实训营结营；全国性创新创业竞赛三等奖；省级软件开发竞赛二等奖',
  internships:
    '某AI应用服务公司｜AI应用落地实习生：参与知识库语料治理、销售Agent流程设计、RAG测试、Prompt约束、问答日志与用户反馈功能设计。\n\n某智能平台科技公司｜前端开发实习生：参与AI助手、设备控制、语音交互、状态管理及多接口联调。\n\nCareerPulse项目｜项目负责人、Agent开发：完成多Agent任务拆解、Tool Calling、职业知识RAG、路径规划、执行日志与结果校验。',
  selfEvaluation:
    '能够从业务场景拆解AI功能并完成可运行原型，优势是Agent流程设计、业务理解和前后端联调；当前需要继续加强Python工程化、RAG评测、MCP完整实践和容器化部署。'
})

export const DEMO_PROFILE_RESPONSE = Object.freeze({
  student_id: DEMO_STUDENT_ID,
  student_name: '林晓宁',
  profile: {
    name: '林晓宁',
    education: '本科（2028届）',
    major: '计算机科学与技术',
    city: '广东',
    years_of_experience: 0.7,
    skills: DEMO_PROFILE_FORM.skills,
    certificates: DEMO_PROFILE_FORM.certificates,
    internships: [
      '某AI应用服务公司：知识库语料治理、销售Agent流程、RAG测试与效果调试',
      '某智能平台科技公司：AI助手、设备控制、语音交互与多接口联调'
    ],
    projects: [
      'CareerPulse：多Agent职业导航系统，覆盖画像、匹配、路径、训练和反馈闭环'
    ],
    work_experience: ['累计约8个月项目型实习，覆盖AI应用落地、前端交互开发与多接口联调'],
    target_job: 'AI Agent开发工程师',
    target_industry: '人工智能/互联网',
    self_evaluation: DEMO_PROFILE_FORM.selfEvaluation,
    profile_completeness: 0.96,
    missing_fields: []
  }
})

interface DemoJobRecord {
  job_id: number
  job_name: string
  graph_label: string
  company_name: string
  industry: string
  salary_range: string
  match_score: number
  required_skills: string[]
  required_certs: string[]
  soft_skills: string[]
  ability_dimensions: {
    innovation: number
    learning: number
    stress_tolerance: number
    communication: number
    internship: number
  }
  highlights: string[]
  job_description: string
}

const createDemoJob = (
  job: Omit<DemoJobRecord, 'required_certs' | 'ability_dimensions'> &
    Partial<Pick<DemoJobRecord, 'required_certs' | 'ability_dimensions'>>
): DemoJobRecord => ({
  ...job,
  required_certs: job.required_certs ?? ['项目作品与工程实践优先，证书不作硬性要求'],
  ability_dimensions: job.ability_dimensions ?? {
    innovation: 82,
    learning: 86,
    stress_tolerance: 78,
    communication: 80,
    internship: 84
  }
})

export const DEMO_JOBS: readonly DemoJobRecord[] = Object.freeze([
  createDemoJob({
    job_id: DEMO_PRIMARY_JOB_ID,
    job_name: 'AI Agent开发工程师',
    graph_label: 'AI Agent开发',
    company_name: '星河智能科技',
    industry: '人工智能/互联网',
    salary_range: '实习4-7K / 校招12-20K',
    match_score: 81.67,
    required_skills: ['LLM应用开发', 'RAG', 'Python', '后端开发', 'API设计', 'Tool Calling', 'MCP', 'Docker/K8s'],
    soft_skills: ['需求分析', '沟通表达', '学习能力'],
    ability_dimensions: {
      innovation: 84,
      learning: 88,
      stress_tolerance: 76,
      communication: 82,
      internship: 86
    },
    highlights: ['Agent项目经历', '业务场景落地', '前后端联调'],
    job_description:
      '面向企业业务场景完成AI Agent需求拆解、工具编排、知识库构建、模型API集成、效果评测与上线复盘。'
  }),
  createDemoJob({
    job_id: 150,
    job_name: 'RAG应用开发工程师',
    graph_label: 'RAG应用开发',
    company_name: '云栈知识科技',
    industry: '人工智能/企业服务',
    salary_range: '实习5-8K / 校招13-22K',
    match_score: 78,
    required_skills: ['RAG', 'LLM应用开发', 'Python', '后端开发', 'API设计', '向量检索', '评测'],
    soft_skills: ['解决问题', '团队协作'],
    ability_dimensions: {
      innovation: 82,
      learning: 86,
      stress_tolerance: 74,
      communication: 76,
      internship: 82
    },
    highlights: ['知识库实践', '引用溯源', '失败案例分析'],
    job_description:
      '负责企业知识库的切分、召回、重排、引用与拒答策略，并通过质量评测集持续改进回答效果。'
  }),
  createDemoJob({
    job_id: 151,
    job_name: 'AI解决方案工程师（FDE）',
    graph_label: 'FDE解决方案',
    company_name: '智联方舟科技',
    industry: '人工智能/企业服务',
    salary_range: '实习5-8K / 校招14-24K',
    match_score: 85.83,
    required_skills: ['需求分析', '流程设计', 'LLM应用开发', 'RAG', 'Python', 'API设计', '沟通表达'],
    soft_skills: ['沟通表达', '项目管理', '业务理解'],
    ability_dimensions: {
      innovation: 80,
      learning: 85,
      stress_tolerance: 78,
      communication: 88,
      internship: 84
    },
    highlights: ['需求到交付', '跨角色沟通', '业务流程AI化'],
    job_description:
      '深入客户场景完成需求澄清、AI方案设计、快速原型、系统集成、试点验收和交付培训。'
  }),
  createDemoJob({
    job_id: 152,
    job_name: 'LLM应用开发工程师',
    graph_label: 'LLM应用开发',
    company_name: '启明模型应用中心',
    industry: '人工智能/软件服务',
    salary_range: '实习5-8K / 校招14-23K',
    match_score: 75,
    required_skills: ['LLM应用开发', 'Prompt工程', '结构化输出', 'Python', '评测', '模型API'],
    soft_skills: ['实验意识', '问题定位', '文档表达'],
    highlights: ['模型API接入', '结构化输出', 'Prompt评测'],
    job_description: '负责大模型应用流程、结构化输出、模型路由、质量评测和成本延迟优化。'
  }),
  createDemoJob({
    job_id: 153,
    job_name: 'Python后端开发工程师',
    graph_label: 'Python后端',
    company_name: '云帆软件',
    industry: '互联网/软件服务',
    salary_range: '实习4-7K / 校招11-19K',
    match_score: 79.25,
    required_skills: ['Python', 'FastAPI', 'PostgreSQL', 'Redis', '异步任务', '自动化测试'],
    soft_skills: ['工程规范', '故障定位', '协作交付'],
    highlights: ['API设计', '数据库实践', '多接口联调'],
    job_description: '负责Python服务接口、数据访问、异步任务、缓存、测试与运行监控建设。'
  }),
  createDemoJob({
    job_id: 154,
    job_name: 'AI全栈开发工程师',
    graph_label: 'AI全栈开发',
    company_name: '光年交互实验室',
    industry: '人工智能/互联网',
    salary_range: '实习4-7K / 校招12-21K',
    match_score: 82.25,
    required_skills: ['Vue3', 'TypeScript', 'Python', 'FastAPI', '模型API', '状态管理'],
    soft_skills: ['产品意识', '交互沟通', '快速迭代'],
    highlights: ['Vue3实践', 'AI助手交互', '端到端联调'],
    job_description: '负责AI应用从交互页面到后端服务的端到端开发、联调与体验优化。'
  }),
  createDemoJob({
    job_id: 155,
    job_name: 'Agent平台开发工程师',
    graph_label: 'Agent平台开发',
    company_name: '矩阵智能平台',
    industry: '人工智能/平台服务',
    salary_range: '校招15-25K',
    match_score: 78.75,
    required_skills: ['Agent编排', 'Tool Calling', 'MCP', '任务队列', '可观测性', '权限控制'],
    soft_skills: ['平台思维', '接口治理', '稳定性意识'],
    highlights: ['多Agent系统', '工具调用', '执行日志'],
    job_description: '建设Agent编排、工具注册、运行状态、权限、日志和评测等平台能力。'
  }),
  createDemoJob({
    job_id: 156,
    job_name: 'AI应用测试工程师',
    graph_label: 'AI应用测试',
    company_name: '青藤质量工程中心',
    industry: '人工智能/质量服务',
    salary_range: '实习4-6K / 校招10-18K',
    match_score: 76.5,
    required_skills: ['测试设计', '模型评测', 'RAG评测', '接口测试', 'Python', '质量分析'],
    soft_skills: ['质量意识', '细节判断', '风险沟通'],
    highlights: ['RAG测试', '失败案例分析', '结果校验'],
    job_description: '负责AI应用功能、接口、模型输出、RAG质量和安全边界的测试与质量分析。'
  }),
  createDemoJob({
    job_id: 157,
    job_name: 'MLOps工程师',
    graph_label: 'MLOps',
    company_name: '算舟基础设施',
    industry: '人工智能/云计算',
    salary_range: '校招14-24K',
    match_score: 72.75,
    required_skills: ['Docker', 'Kubernetes', 'CI/CD', '模型部署', '监控告警', 'Linux'],
    soft_skills: ['可靠性意识', '排障能力', '协作交付'],
    highlights: ['Docker基础', '工程交付意识', '服务化经验'],
    job_description: '负责模型与Agent服务的持续集成、部署、监控、容量和故障恢复体系。'
  }),
  createDemoJob({
    job_id: 158,
    job_name: 'AI数据工程师',
    graph_label: 'AI数据工程',
    company_name: '数澜数据科技',
    industry: '数据智能/人工智能',
    salary_range: '校招13-22K',
    match_score: 74.5,
    required_skills: ['Python', 'SQL', '数据治理', 'ETL', '知识库语料', '数据质量'],
    soft_skills: ['数据敏感度', '规范意识', '业务理解'],
    highlights: ['语料治理', 'PostgreSQL', '数据结构设计'],
    job_description: '负责AI应用所需数据与语料的采集、清洗、质量治理、任务调度和可追溯管理。'
  }),
  createDemoJob({
    job_id: 159,
    job_name: 'AI平台DevOps工程师',
    graph_label: 'AI DevOps',
    company_name: '瀚海云原生团队',
    industry: '云计算/人工智能',
    salary_range: '校招13-23K',
    match_score: 71.5,
    required_skills: ['DevOps', 'Docker', 'Kubernetes', 'GitHub Actions', '日志监控', '服务治理'],
    soft_skills: ['自动化意识', '可靠性意识', '应急沟通'],
    highlights: ['Git协作', '容器基础', '接口部署'],
    job_description: '负责AI平台的发布流水线、环境管理、容器编排、监控告警和稳定性改进。'
  }),
  createDemoJob({
    job_id: 160,
    job_name: 'AI产品工程师',
    graph_label: 'AI产品工程',
    company_name: '知行产品创新中心',
    industry: '人工智能/产品研发',
    salary_range: '校招12-20K',
    match_score: 80.25,
    required_skills: ['需求分析', 'AI产品设计', 'Prompt原型', '数据分析', '项目推进', '验收设计'],
    soft_skills: ['用户洞察', '跨团队沟通', '项目管理'],
    highlights: ['业务需求拆解', '原型验证', '跨角色协作'],
    job_description: '连接业务、设计与研发，完成AI功能定义、原型验证、指标设计和迭代推进。'
  }),
  createDemoJob({
    job_id: 161,
    job_name: '高级AI Agent开发工程师',
    graph_label: '高级Agent开发',
    company_name: '星河智能科技',
    industry: '人工智能/互联网',
    salary_range: '20-35K',
    match_score: 69.5,
    required_skills: ['Agent架构', '多Agent协作', '质量评测', '可观测性', '系统设计', '性能优化'],
    soft_skills: ['技术决策', '项目带领', '跨团队协作'],
    highlights: ['Agent项目基础', '业务理解', '快速学习'],
    job_description: '独立负责复杂Agent项目架构、质量评测、可观测性和交付标准建设。'
  }),
  createDemoJob({
    job_id: 162,
    job_name: 'AI应用架构师',
    graph_label: 'AI应用架构师',
    company_name: '星河智能科技',
    industry: '人工智能/企业服务',
    salary_range: '30-50K',
    match_score: 61.25,
    required_skills: ['架构设计', 'Agent平台', '数据治理', '安全合规', '成本治理', '复杂交付'],
    soft_skills: ['技术领导力', '业务咨询', '关键决策'],
    highlights: ['系统全局视角', 'Agent开发积累', '业务交付经验'],
    job_description: '负责跨业务AI应用架构、技术治理、交付方法论和关键项目技术决策。'
  }),
  createDemoJob({
    job_id: 163,
    job_name: 'Agent研发负责人',
    graph_label: 'Agent研发负责人',
    company_name: '星河智能科技',
    industry: '人工智能/平台服务',
    salary_range: '35-55K',
    match_score: 56.75,
    required_skills: ['技术战略', '团队管理', 'Agent平台', '架构治理', '质量体系', '业务规划'],
    soft_skills: ['团队领导', '资源协调', '战略沟通'],
    highlights: ['项目主导意识', '产品与技术协同', '成长潜力'],
    job_description: '负责Agent研发方向、团队建设、平台演进、质量体系与重点业务交付。'
  }),
  createDemoJob({
    job_id: 164,
    job_name: 'AI安全开发工程师',
    graph_label: 'AI安全开发',
    company_name: '砺盾智能安全',
    industry: '人工智能/网络安全',
    salary_range: '校招14-24K',
    match_score: 70.25,
    required_skills: ['内容安全', 'Prompt注入防护', '权限控制', '审计日志', 'Python', '安全测试'],
    soft_skills: ['风险意识', '规则思维', '严谨表达'],
    highlights: ['权限与日志意识', '结果校验', '异常处理'],
    job_description: '负责Agent输入输出安全、工具权限、Prompt注入防护、审计日志与安全测试。'
  })
])

interface DemoDimension {
  name: string
  student_score: number
  job_required: number
  gap: number
  weight: number
}

interface DemoGap {
  item: string
  status: 'insufficient'
  priority: string
  suggestion: string
}

interface DemoMatchAnalysis {
  overall_score: number
  confidence: number
  match_level: 'high'
  strengths: string[]
  gaps: string[]
  dimensions: DemoDimension[]
  gap_analysis: DemoGap[]
  history_id: number
  report_id: number
  calculation_version: 'deterministic-match-v2'
}

const mainDimensions: DemoDimension[] = [
  { name: 'LLM应用开发', student_score: 75, job_required: 100, gap: -25, weight: 0.2 },
  { name: 'RAG', student_score: 75, job_required: 100, gap: -25, weight: 0.15 },
  { name: 'Python', student_score: 75, job_required: 100, gap: -25, weight: 0.15 },
  { name: '后端开发', student_score: 75, job_required: 100, gap: -25, weight: 0.1 },
  { name: 'API设计', student_score: 100, job_required: 100, gap: 0, weight: 0.1 },
  { name: 'Tool Calling', student_score: 100, job_required: 100, gap: 0, weight: 0.1 },
  { name: 'MCP', student_score: 66.67, job_required: 100, gap: -33.33, weight: 0.05 },
  { name: 'SQL/数据库', student_score: 100, job_required: 100, gap: 0, weight: 0.05 },
  { name: 'Git/版本控制', student_score: 100, job_required: 100, gap: 0, weight: 0.05 },
  { name: 'Docker/K8s', student_score: 66.67, job_required: 100, gap: -33.33, weight: 0.05 }
]

const mainGaps: DemoGap[] = [
  {
    item: 'Python',
    status: 'insufficient',
    priority: 'P1',
    suggestion: '补充异步处理、自动化测试、依赖管理和异常分层，形成可复用的FastAPI工程模板。'
  },
  {
    item: 'LLM应用开发',
    status: 'insufficient',
    priority: 'P2',
    suggestion: '从可运行原型提升到可观测、可评测、可回滚的业务服务，并保留完整执行日志。'
  },
  {
    item: 'RAG',
    status: 'insufficient',
    priority: 'P3',
    suggestion: '建立不少于30条质量评测样例，跟踪召回、引用准确性、拒答和失败类型。'
  },
  {
    item: '后端开发',
    status: 'insufficient',
    priority: 'P4',
    suggestion: '补齐鉴权、缓存、任务状态、接口测试和故障降级，强化服务化交付证据。'
  },
  {
    item: 'Docker/K8s',
    status: 'insufficient',
    priority: 'P5',
    suggestion: '完成容器化、健康检查和基础监控；K8s暂以理解部署对象和排障流程为目标。'
  },
  {
    item: 'MCP',
    status: 'insufficient',
    priority: 'P6',
    suggestion: '独立实现一个带参数校验、调用日志、失败测试和降级返回的MCP工具。'
  }
]

const buildAlternativeAnalysis = (jobId: number): DemoMatchAnalysis => {
  if (jobId === 150) {
    return {
      overall_score: 85,
      confidence: 0.8812,
      match_level: 'high',
      strengths: ['后端开发', 'API设计', 'Tool Calling', 'MCP', 'SQL/数据库', 'Docker/K8s'],
      gaps: ['RAG', 'Python', 'LLM应用开发'],
      dimensions: [
        { name: 'RAG', student_score: 75, job_required: 100, gap: -25, weight: 0.25 },
        { name: 'LLM应用开发', student_score: 75, job_required: 100, gap: -25, weight: 0.2 },
        { name: 'Python', student_score: 75, job_required: 100, gap: -25, weight: 0.15 },
        { name: '后端开发', student_score: 100, job_required: 100, gap: 0, weight: 0.1 },
        { name: 'API设计', student_score: 100, job_required: 100, gap: 0, weight: 0.1 },
        { name: 'Tool Calling', student_score: 100, job_required: 100, gap: 0, weight: 0.05 },
        { name: 'MCP', student_score: 100, job_required: 100, gap: 0, weight: 0.05 },
        { name: 'SQL/数据库', student_score: 100, job_required: 100, gap: 0, weight: 0.05 },
        { name: 'Docker/K8s', student_score: 100, job_required: 100, gap: 0, weight: 0.05 }
      ],
      gap_analysis: mainGaps.filter((item) => ['RAG', 'Python', 'LLM应用开发'].includes(item.item)),
      history_id: 6304,
      report_id: 6202,
      calculation_version: 'deterministic-match-v2'
    }
  }

  if (jobId === 151) {
    const gaps = ['需求分析', '流程设计', '沟通表达', 'LLM应用开发', 'MCP']
    return {
      overall_score: 85.83,
      confidence: 0.8812,
      match_level: 'high',
      strengths: ['RAG', 'Python', 'API设计', 'Tool Calling', '项目管理'],
      gaps,
      dimensions: [
        { name: 'LLM应用开发', student_score: 75, job_required: 100, gap: -25, weight: 0.15 },
        { name: 'RAG', student_score: 100, job_required: 100, gap: 0, weight: 0.1 },
        { name: 'Python', student_score: 100, job_required: 100, gap: 0, weight: 0.1 },
        { name: 'API设计', student_score: 100, job_required: 100, gap: 0, weight: 0.1 },
        { name: 'Tool Calling', student_score: 100, job_required: 100, gap: 0, weight: 0.1 },
        { name: '需求分析', student_score: 75, job_required: 100, gap: -25, weight: 0.15 },
        { name: '流程设计', student_score: 75, job_required: 100, gap: -25, weight: 0.1 },
        { name: '沟通表达', student_score: 75, job_required: 100, gap: -25, weight: 0.1 },
        { name: '项目管理', student_score: 100, job_required: 100, gap: 0, weight: 0.05 },
        { name: 'MCP', student_score: 66.67, job_required: 100, gap: -33.33, weight: 0.05 }
      ],
      gap_analysis: gaps.map((item, index) => ({
        item,
        status: 'insufficient',
        priority: `P${index + 1}`,
        suggestion: `通过一次完整交付补充「${item}」的可验证证据。`
      })),
      history_id: 6305,
      report_id: 6203,
      calculation_version: 'deterministic-match-v2'
    }
  }

  return DEMO_MATCH_ANALYSIS
}

export const DEMO_MATCH_ANALYSIS: DemoMatchAnalysis = Object.freeze({
  overall_score: 81.67,
  confidence: 0.8812,
  match_level: 'high',
  strengths: ['API设计', 'Tool Calling', 'SQL/数据库', 'Git/版本控制'],
  gaps: mainGaps.map((item) => item.item),
  dimensions: mainDimensions,
  gap_analysis: mainGaps,
  history_id: 6303,
  report_id: DEMO_REPORT_ID,
  calculation_version: 'deterministic-match-v2'
})

export const getDemoMatchAnalysis = (jobId: number): DemoMatchAnalysis =>
  buildAlternativeAnalysis(jobId)

export const getDemoJob = (jobId: number): DemoJobRecord =>
  DEMO_JOBS.find((job) => job.job_id === jobId) ?? DEMO_JOBS[0]

export const getDemoGraph = (jobId: number): Record<string, unknown> => {
  const current = getDemoJob(jobId)
  const centerId = String(current.job_id)
  const verticalIds = [161, 162, 163].filter((id) => id !== current.job_id)
  const lateralIds = [150, 151, 152, 153, 154, 155, 156, 157, 158, 159].filter((id) => id !== current.job_id)
  const verticalJobs = verticalIds.map(getDemoJob)
  const lateralJobs = lateralIds.map(getDemoJob)

  const toGraphNode = (job: DemoJobRecord, relation: '晋升' | '换岗', strength: number) => ({
    id: String(job.job_id),
    name: job.graph_label,
    relation,
    relation_strength: strength,
    job_description: job.job_description,
    core_skills: job.required_skills,
    salary_range: job.salary_range
  })

  return {
    center: {
      id: centerId,
      name: current.graph_label,
      relation: '目标岗位',
      job_description: current.job_description,
      core_skills: current.required_skills,
      salary_range: current.salary_range
    },
    vertical: verticalJobs.map((job, index) => toGraphNode(job, '晋升', 0.86 - index * 0.08)),
    lateral: lateralJobs.map((job, index) => toGraphNode(job, '换岗', 0.83 - index * 0.025)),
    relations: [
      { source: centerId, target: '161', label: '1-3年', type: 'vertical', weight: 1.35 },
      { source: '161', target: '162', label: '3-5年', type: 'vertical', weight: 1.2 },
      { source: '162', target: '163', label: '5年以上', type: 'vertical', weight: 1.05 },
      ...lateralJobs.map((job) => ({
        source: centerId,
        target: String(job.job_id),
        label: '换岗',
        type: 'horizontal',
        weight: 1
      })),
      { source: '150', target: '158', label: '数据能力', type: 'horizontal', weight: 0.82 },
      { source: '152', target: '150', label: '检索增强', type: 'horizontal', weight: 0.9 },
      { source: '153', target: '155', label: '平台工程', type: 'horizontal', weight: 0.85 },
      { source: '154', target: '151', label: '交付能力', type: 'horizontal', weight: 0.78 },
      { source: '156', target: '157', label: '质量运维', type: 'horizontal', weight: 0.75 }
    ]
  }
}

export const DEMO_REPORT_HTML = `
  <h2>AI Agent开发方向成长报告</h2>
  <p><strong>当前结论：</strong>候选人具备Agent原型、RAG知识库和前后端联调经验，适合继续申请AI Agent开发实习及校招岗位。当前技术匹配分为81.67，优势集中在API设计、Tool Calling、数据库和版本协作。</p>
  <h3>关键提升方向</h3>
  <ul>
    <li>把Python与FastAPI项目补充为带测试、日志、异常分层和任务状态的工程化服务。</li>
    <li>为RAG建立质量评测集，记录召回、引用、拒答和失败类型，不只展示问答效果。</li>
    <li>独立完成一个带参数校验、调用日志、失败测试和降级返回的MCP工具。</li>
    <li>使用Docker完成本地部署、健康检查和基础运行监控。</li>
  </ul>
  <h3>90天行动计划</h3>
  <p><strong>第1-30天：</strong>完成Python/FastAPI工程模板和核心接口测试。</p>
  <p><strong>第31-60天：</strong>完成RAG评测集、指标看板和失败案例复盘。</p>
  <p><strong>第61-90天：</strong>完成MCP工具、Docker部署及一份可公开展示的技术说明。</p>
  <p><strong>阶段成果：</strong>形成一个可运行、可评测、可部署的AI Agent项目，并沉淀架构图、接口文档、评测记录和复盘报告。</p>
`

export const DEMO_HISTORY_REPORTS = Object.freeze([
  {
    history_id: 6303,
    job_title: 'AI Agent开发工程师',
    created_at: '2026-09-20T10:00:00+08:00',
    overall_score: 81.67,
    tags: ['AI实习后', '简历证据回放']
  },
  {
    history_id: 6302,
    job_title: 'AI Agent开发工程师',
    created_at: '2026-06-20T10:00:00+08:00',
    overall_score: 75.42,
    tags: ['项目完成期', '简历证据回放']
  },
  {
    history_id: 6301,
    job_title: 'AI Agent开发工程师',
    created_at: '2026-02-12T10:00:00+08:00',
    overall_score: 50,
    tags: ['项目启动期', '简历证据回放']
  }
])

export const getDemoHistorySnapshot = (historyId: number): Record<string, unknown> => {
  const report = DEMO_HISTORY_REPORTS.find((item) => item.history_id === historyId) ?? DEMO_HISTORY_REPORTS[0]
  return {
    history_id: report.history_id,
    created_at: report.created_at,
    overall_score: report.overall_score,
    job_profile: { title: report.job_title },
    report: {
      content:
        historyId === 6303
          ? DEMO_REPORT_HTML
          : `<h2>${report.tags[0]}</h2><p>该阶段已完成对应项目里程碑，能力变化依据项目成果、实习任务和技术复盘记录整理。</p><p>核心积累包括Agent流程设计、RAG质量测试、前后端联调与结构化交付。</p>`
    }
  }
}

export const DEMO_RESOURCES = Object.freeze([
  {
    title: 'Python / FastAPI工程化冲刺',
    type: 'practice',
    target_ability: 'Python',
    recommendation_reason: '围绕最高优先级Gap，补齐异步处理、测试、日志和异常分层。',
    source: 'FastAPI官方教程',
    url: 'https://fastapi.tiangolo.com/tutorial/'
  },
  {
    title: 'RAG质量评测集建设',
    type: 'practice',
    target_ability: 'RAG',
    recommendation_reason: '用不少于30条样例验证召回、引用、拒答和失败类型。',
    source: 'Ragas文档',
    url: 'https://docs.ragas.io/en/stable/'
  },
  {
    title: 'MCP工具完整实践',
    type: 'practice',
    target_ability: 'MCP',
    recommendation_reason: '实现参数校验、调用日志、成功/失败测试和降级返回。',
    source: 'Model Context Protocol文档',
    url: 'https://modelcontextprotocol.io/docs/getting-started/intro'
  },
  {
    title: 'Agent服务Docker化交付',
    type: 'practice',
    target_ability: 'Docker/K8s',
    recommendation_reason: '形成可重复启动、带健康检查和基础监控的工程交付物。',
    source: 'Docker官方文档',
    url: 'https://docs.docker.com/get-started/'
  }
])

