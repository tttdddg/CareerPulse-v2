import type {
  GenerateTrainingPayload,
  ScoreTrainingPayload,
  TrainingEvaluationCriterion,
  TrainingScore,
  TrainingTask,
  TrainingType
} from '../api/modules/training'
import { waitForDemoResponse } from './demoMode'

interface DemoCriterion extends TrainingEvaluationCriterion {
  keywords: string[]
}

interface DemoTrainingTask extends TrainingTask {
  evaluationCriteria: DemoCriterion[]
}

const tasks: Record<TrainingType, DemoTrainingTask> = {
  remote_collaboration: {
    trainingId: 'demo-remote-review',
    type: 'remote_collaboration',
    title: '远程需求评审与风险同步',
    scenario: 'Agent项目由产品、研发和运营远程协作，当前需求边界与验收口径尚未统一。',
    role: 'AI应用开发实习生',
    taskDescription: '设计一次异步优先的远程评审流程，说明会前准备、会议决策和会后跟进。',
    evaluationCriteria: [
      { dimension: '准备充分', maxScore: 100, weight: 0.3, description: '提前共享材料与问题清单。', keywords: ['材料', '问题清单', '预读'] },
      { dimension: '讨论聚焦', maxScore: 100, weight: 0.4, description: '围绕争议、风险和决策展开。', keywords: ['争议', '风险', '决策'] },
      { dimension: '闭环跟进', maxScore: 100, weight: 0.3, description: '明确负责人、期限与记录。', keywords: ['负责人', '期限', '记录'] }
    ],
    targetAbilities: ['远程协作', '需求分析'],
    referenceAnswer: '要点：会前预读、问题清单、决策记录、负责人和截止时间。'
  },
  ai_office_task: {
    trainingId: 'demo-agent-requirement',
    type: 'ai_office_task',
    title: '企业知识库Agent需求拆解',
    scenario: '业务团队希望把销售SOP接入AI助手，但目标用户、知识范围和风险边界尚未明确。',
    role: 'AI应用落地实习生（FDE方向）',
    taskDescription: '给出澄清问题、Agent处理流程、验收标准、风险控制与人工接管方案。',
    evaluationCriteria: [
      { dimension: '问题识别', maxScore: 100, weight: 0.3, description: '识别目标、资料、用户和边界。', keywords: ['澄清', '资料', '用户', '边界'] },
      { dimension: '任务拆解', maxScore: 100, weight: 0.35, description: '形成完整可执行的Agent流程。', keywords: ['意图', '画像', '检索', '生成', '合规', '人工'] },
      { dimension: '验收标准', maxScore: 100, weight: 0.2, description: '给出可验证的质量口径。', keywords: ['召回', '引用', '拒答', '准确', '测试集'] },
      { dimension: '风险与人工接管', maxScore: 100, weight: 0.15, description: '覆盖隐私、合规、停止回复和人工处理。', keywords: ['隐私', '合规', '停止回复', '人工'] }
    ],
    targetAbilities: ['需求分析', 'LLM应用开发', '风险意识'],
    referenceAnswer: '要点：先澄清业务范围，再拆解处理流程，以评测集验收，并设置合规检查与人工接管。'
  },
  cross_role_communication: {
    trainingId: 'demo-solution-briefing',
    type: 'cross_role_communication',
    title: '向业务团队说明Agent试点方案',
    scenario: '业务负责人关注上线时间和效果，但不了解RAG、召回和拒答等技术概念。',
    role: 'AI解决方案工程师（FDE）',
    taskDescription: '用非技术语言说明试点范围、预期收益、限制、风险和下一步安排。',
    evaluationCriteria: [
      { dimension: '受众适配', maxScore: 100, weight: 0.3, description: '使用业务语言，减少不必要术语。', keywords: ['业务', '通俗', '场景'] },
      { dimension: '影响清晰', maxScore: 100, weight: 0.4, description: '说明收益、限制和风险。', keywords: ['收益', '限制', '风险'] },
      { dimension: '行动明确', maxScore: 100, weight: 0.3, description: '给出试点、负责人和反馈安排。', keywords: ['试点', '负责人', '反馈'] }
    ],
    targetAbilities: ['沟通表达', '需求分析'],
    referenceAnswer: '要点：从业务影响出发，说明小范围试点、风险控制、责任人和反馈周期。'
  }
}

interface PresetTrainingResult {
  totalScore: number
  dimensionScores: TrainingScore['dimensionScores']
  overallComment: string
  strengths: string[]
  improvementSuggestions: string[]
  nextSteps: string[]
}

const presetResults: Record<TrainingType, PresetTrainingResult> = {
  remote_collaboration: {
    totalScore: 89.6,
    dimensionScores: [
      { dimension: '准备充分', score: 88, comment: '会前材料、问题清单和参与人准备较完整。' },
      { dimension: '讨论聚焦', score: 92, comment: '能够围绕争议、风险与决策形成清晰议程。' },
      { dimension: '闭环跟进', score: 86, comment: '已覆盖负责人、期限和决策记录，可继续补充升级机制。' }
    ],
    overallComment: '协作方案结构完整，能够把远程沟通转化为可追踪的决策与行动闭环。',
    strengths: ['讨论目标与决策边界清晰。', '会后责任人与跟进节奏明确。'],
    improvementSuggestions: ['补充阻塞事项的升级时限与替代负责人。'],
    nextSteps: ['整理一份30分钟远程评审议程。', '使用决策日志模板完成一次复盘。']
  },
  ai_office_task: {
    totalScore: 88.8,
    dimensionScores: [
      { dimension: '问题识别', score: 85, comment: '目标用户、资料范围与业务边界识别较完整。' },
      { dimension: '任务拆解', score: 92, comment: 'Agent处理流程清晰，关键步骤具备执行顺序。' },
      { dimension: '验收标准', score: 88, comment: '已覆盖引用、拒答和质量测试，可继续量化阈值。' },
      { dimension: '风险与人工接管', score: 90, comment: '隐私、合规与人工接管边界明确。' }
    ],
    overallComment: '整体表现良好，已形成从需求澄清、Agent流程到验收与人工接管的完整闭环。',
    strengths: ['任务拆解有明确顺序，可直接转化为流程图。', '风险控制与人工接管设计完整。'],
    improvementSuggestions: ['为引用准确率、拒答率和人工转接率补充量化阈值。'],
    nextSteps: ['把方案整理成一页Agent流程图。', '使用30条质量样例完成一次验收演练。']
  },
  cross_role_communication: {
    totalScore: 87.8,
    dimensionScores: [
      { dimension: '受众适配', score: 90, comment: '表达以业务目标为中心，技术术语控制得当。' },
      { dimension: '影响清晰', score: 86, comment: '收益、限制和风险均有说明，可补充效果口径。' },
      { dimension: '行动明确', score: 88, comment: '试点范围、责任人与反馈周期清晰。' }
    ],
    overallComment: '方案说明兼顾业务收益与实施边界，具备推动小范围试点的沟通基础。',
    strengths: ['能够用业务语言解释技术方案。', '试点与反馈安排具有可执行性。'],
    improvementSuggestions: ['补充试点成功与停止扩大的量化判断条件。'],
    nextSteps: ['整理一份三分钟业务汇报提纲。', '准备收益、限制与风险三栏说明。']
  }
}

export const generateDemoTrainingTask = async (
  payload: GenerateTrainingPayload
): Promise<TrainingTask> => {
  await waitForDemoResponse(520)
  return tasks[payload.trainingType]
}

export const scoreDemoTrainingTask = async (
  payload: ScoreTrainingPayload
): Promise<TrainingScore> => {
  await waitForDemoResponse(580)
  const task = Object.values(tasks).find((item) => item.trainingId === payload.trainingId)
  if (!task) {
    throw new Error('未找到对应的训练任务')
  }

  const result = presetResults[task.type]

  return {
    trainingId: task.trainingId,
    ...result
  }
}

