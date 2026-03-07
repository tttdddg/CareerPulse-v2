export interface MockLoginParams {
  account: string
  password: string
}

export interface MockLoginResult {
  token: string
  profile: {
    id: string
    name: string
    role: string
    avatarUrl?: string
    title?: string
  }
}

export interface MockResumeParseResult {
  name: string
  role: string
  skills: string
  industry: string
  targetRole: string
}

export interface MockAnalysisResult {
  matchScore: number
  radarIndicators: { name: string; max: number }[]
  radarSeries: { name: string; values: number[] }[]
  strengths: string[]
  gaps: string[]
}

export interface MockJobProfile {
  id: string
  name: string
  match: number
  highlights: string[]
  description: string
}

export interface MockPathGraph {
  nodes: {
    id: string
    label: string
    x?: number
    y?: number
    type?: 'vertical' | 'horizontal' | 'target'
  }[]
  edges: {
    source: string
    target: string
    label?: string
    type?: 'vertical' | 'horizontal' | 'target'
  }[]
}

export interface MockGrowthPlan {
  content: string
}

export interface MockReportSummary {
  id: string
  title: string
  createdAt: string
  score: number
  tags: string[]
}

export interface MockGrowthPoint {
  date: string
  value: number
  label?: string
}

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms))

export const mockLogin = async (params: MockLoginParams): Promise<MockLoginResult> => {
  await sleep(800)

  if (!params.account || !params.password) {
    throw new Error('请输入账号与密码')
  }

  return {
    token: `mock-${Date.now()}`,
    profile: {
      id: 'u-1024',
      name: params.account.includes('@') ? params.account.split('@')[0] : '访客用户',
      role: 'career_user',
      title: '职业探索中'
    }
  }
}

export const mockParseResume = async (fileName: string): Promise<MockResumeParseResult> => {
  await sleep(600)

  if (!fileName) {
    throw new Error('未检测到简历文件')
  }

  return {
    name: '林思然',
    role: 'professional',
    skills: '数据分析 / 用户研究 / AI 产品规划',
    industry: 'internet',
    targetRole: 'AI 产品经理'
  }
}

export const mockStartAnalysis = async (): Promise<MockAnalysisResult> => {
  await sleep(900)

  return {
    matchScore: 82,
    radarIndicators: [
      { name: '业务理解', max: 100 },
      { name: '数据能力', max: 100 },
      { name: '产品规划', max: 100 },
      { name: '沟通协作', max: 100 },
      { name: '执行落地', max: 100 }
    ],
    radarSeries: [
      { name: '个人能力', values: [72, 78, 80, 74, 70] },
      { name: '目标岗位', values: [85, 82, 88, 80, 84] }
    ],
    strengths: ['数据洞察', '用户研究', '产品规划'],
    gaps: ['跨团队资源协调', '商业化策略', '项目复盘机制']
  }
}

export const mockFetchJobProfiles = async (): Promise<MockJobProfile[]> => {
  await sleep(700)

  return [
    {
      id: 'job-01',
      name: 'AI 产品经理',
      match: 86,
      highlights: ['AI 需求洞察', '跨团队协同', '数据驱动'],
      description: '负责 AI 产品规划与落地，建立智能化业务增长闭环。'
    },
    {
      id: 'job-02',
      name: '增长策略分析',
      match: 81,
      highlights: ['实验设计', '增长模型', '用户留存'],
      description: '围绕核心指标制定增长策略，推动业务增长。'
    },
    {
      id: 'job-03',
      name: '用户研究顾问',
      match: 78,
      highlights: ['用户访谈', '洞察整理', '体验设计'],
      description: '输出高质量用户洞察，支撑产品策略。'
    }
  ]
}

export const mockFetchPathGraph = async (): Promise<MockPathGraph> => {
  await sleep(500)

  return {
    nodes: [
      { id: 'n1', label: '助理岗位', x: 60, y: 40, type: 'vertical' },
      { id: 'n2', label: '初级岗位', x: 60, y: 140, type: 'vertical' },
      { id: 'n3', label: '资深岗位', x: 60, y: 240, type: 'vertical' },
      { id: 'n4', label: '目标岗位', x: 60, y: 340, type: 'target' },
      { id: 'n5', label: '横向岗位 A', x: 260, y: 140, type: 'horizontal' },
      { id: 'n6', label: '横向岗位 B', x: 260, y: 240, type: 'horizontal' }
    ],
    edges: [
      { source: 'n1', target: 'n2', type: 'vertical' },
      { source: 'n2', target: 'n3', type: 'vertical' },
      { source: 'n3', target: 'n4', type: 'vertical' },
      { source: 'n2', target: 'n5', type: 'horizontal', label: '跨岗探索' },
      { source: 'n3', target: 'n6', type: 'horizontal', label: '复合能力' }
    ]
  }
}

export const mockFetchGrowthPlan = async (): Promise<MockGrowthPlan> => {
  await sleep(650)

  return {
    content: '<h3>阶段目标</h3><p>聚焦 AI 产品能力建设，建立业务洞察 + 数据驱动模型。</p><h3>行动计划</h3><ul><li>3 周内完成业务拆解</li><li>6 周内完成核心指标体系</li><li>10 周内完成策略复盘</li></ul>'
  }
}

export const mockPolishContent = async (content: string): Promise<string> => {
  await sleep(500)
  return content.replace('完成', '系统完成').replace('计划', '成长计划')
}

export const mockCheckContent = async (): Promise<string[]> => {
  await sleep(450)
  return ['补充具体时间节点', '增加可量化指标']
}

export const mockFetchHistory = async (): Promise<{ reports: MockReportSummary[]; growth: MockGrowthPoint[] }> => {
  await sleep(600)

  return {
    reports: [
      {
        id: 'r-1',
        title: 'AI 产品经理匹配报告',
        createdAt: '2026-03-01',
        score: 82,
        tags: ['AI 产品', '数据分析']
      },
      {
        id: 'r-2',
        title: '增长策略岗位匹配报告',
        createdAt: '2026-02-20',
        score: 78,
        tags: ['增长', '策略']
      }
    ],
    growth: [
      { date: '01-10', value: 60 },
      { date: '02-10', value: 66 },
      { date: '03-10', value: 72 },
      { date: '04-10', value: 79 }
    ]
  }
}
