import { request } from '../request'

export interface MatchAnalysisPayload {
  role: string
  skills: string
  industry?: string
  targetRole: string
}

export interface RadarIndicator {
  name: string
  max: number
}

export interface RadarSeries {
  name: string
  values: number[]
}

export interface AnalysisResult {
  matchScore: number
  radarIndicators: RadarIndicator[]
  radarSeries: RadarSeries[]
  strengths: string[]
  gaps: string[]
}

export interface PathNode {
  id: string
  label: string
  x?: number
  y?: number
  type?: 'vertical' | 'horizontal' | 'target'
}

export interface PathEdge {
  source: string
  target: string
  label?: string
  type?: 'vertical' | 'horizontal' | 'target'
}

export interface PathGraph {
  nodes: PathNode[]
  edges: PathEdge[]
}

export interface GrowthPlanResult {
  content: string
  updatedAt: string
}

export const fetchMatchAnalysis = (payload: MatchAnalysisPayload): Promise<AnalysisResult> =>
  request<AnalysisResult>({
    url: '/analysis/match',
    method: 'POST',
    data: payload
  })

export const fetchPathGraph = (targetRole?: string): Promise<PathGraph> =>
  request<PathGraph>({
    url: '/analysis/path',
    method: 'GET',
    params: targetRole ? { targetRole } : undefined
  })

export const fetchGrowthPlan = (reportId?: string): Promise<GrowthPlanResult> =>
  request<GrowthPlanResult>({
    url: '/analysis/growth-plan',
    method: 'GET',
    params: reportId ? { reportId } : undefined
  })
