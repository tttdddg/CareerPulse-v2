export type TrainingType =
  | 'remote_collaboration'
  | 'ai_office_task'
  | 'cross_role_communication'

export type TrainingLifecycleState =
  | 'idle'
  | 'generating'
  | 'ready'
  | 'scoring'
  | 'completed'
  | 'unavailable'
  | 'error'

export interface TrainingEvaluationCriterion {
  dimension: string
  maxScore: number
  weight: number
  description: string
}

export interface TrainingTask {
  trainingId: string
  type: TrainingType
  title: string
  scenario: string
  role?: string
  taskDescription: string
  evaluationCriteria: TrainingEvaluationCriterion[]
  targetAbilities: string[]
  referenceAnswer?: string
}

export interface TrainingDimensionScore {
  dimension: string
  score: number
  comment: string
}

export interface TrainingScore {
  trainingId: string
  totalScore: number
  dimensionScores: TrainingDimensionScore[]
  overallComment: string
  strengths?: string[]
  improvementSuggestions: string[]
  nextSteps?: string[]
}

export interface GenerateTrainingPayload {
  userId: string
  trainingType: TrainingType
}

export interface ScoreTrainingPayload {
  userId: string
  trainingId: string
  answer: string
}

export interface TrainingApiCapability {
  available: boolean
  reason: string
}

export interface TrainingApiAdapter {
  readonly capability: TrainingApiCapability
  generateTask(payload: GenerateTrainingPayload): Promise<TrainingTask>
  scoreTask(payload: ScoreTrainingPayload): Promise<TrainingScore>
}

export class TrainingApiUnavailableError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'TrainingApiUnavailableError'
  }
}

const capability: TrainingApiCapability = Object.freeze({
  available: false,
  reason: '当前 Vue 尚无可调用的职场训练 HTTP API，训练服务接入中。'
})

const unavailable = async <T>(): Promise<T> => {
  throw new TrainingApiUnavailableError(capability.reason)
}

export const trainingApiAdapter: TrainingApiAdapter = {
  capability,
  generateTask: unavailable,
  scoreTask: unavailable
}
