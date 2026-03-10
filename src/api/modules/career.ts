import { request } from '../request'

type UnknownRecord = Record<string, unknown>

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === 'object' && value !== null

const asArray = (value: unknown): unknown[] => (Array.isArray(value) ? value : [])

const toNumber = (value: unknown, fallback = 0): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return fallback
}

const toOptionalNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return undefined
}

const toStringSafe = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback

const pickRecordList = (source: unknown, keys: string[]): UnknownRecord[] => {
  if (Array.isArray(source)) {
    return source.filter(isRecord)
  }
  if (!isRecord(source)) {
    return []
  }
  for (const key of keys) {
    const value = source[key]
    if (Array.isArray(value)) {
      return value.filter(isRecord)
    }
  }
  return []
}

const getByKeys = (source: UnknownRecord, keys: string[]): unknown => {
  for (const key of keys) {
    if (key in source) {
      return source[key]
    }
  }
  return undefined
}

const pickPayloadRecord = (source: unknown): UnknownRecord => {
  if (!isRecord(source)) {
    return {}
  }
  const inner = source.data
  if (isRecord(inner)) {
    return inner
  }
  return source
}

export interface JobItem {
  id: number
  name: string
  match: number
  highlights: string[]
  description: string
}

export interface FetchJobsParams {
  keyword: string
  page?: number
  size?: number
}

export interface StudentUploadProfilePayload {
  name?: string
  skills: string
  certificates: string
  internships: string
  selfEvaluation: string
}

export interface StudentUploadProfileResult {
  studentId: number | null
  name: string
  skills: string
  certificates: string
  internships: string
  selfEvaluation: string
}

export interface MatchingAnalyzePayload {
  studentId: number
  jobId: number
  userId?: string
}

export interface RadarIndicator {
  name: string
  max: number
}

export interface RadarSeries {
  name: string
  values: number[]
}

export interface MatchingAnalyzeResult {
  matchScore: number
  radarIndicators: RadarIndicator[]
  radarSeries: RadarSeries[]
  strengths: string[]
  gaps: string[]
  reportId: number | null
}

export interface PathGraphNode {
  id: string
  label: string
  x?: number
  y?: number
  type?: 'vertical' | 'horizontal' | 'target'
}

export interface PathGraphEdge {
  source: string
  target: string
  label?: string
  type?: 'vertical' | 'horizontal' | 'target'
}

export interface PathGraphResult {
  nodes: PathGraphNode[]
  edges: PathGraphEdge[]
}

export interface ReportItem {
  id: string
  title: string
  createdAt: string
  score: number
  tags: string[]
}

export interface GrowthPoint {
  date: string
  value: number
  label?: string
}

export interface UserHistoriesResult {
  reports: ReportItem[]
  growth: GrowthPoint[]
}

export interface ReportGeneratePayload {
  studentId: number
  jobId: number
  customInstructions?: string
  userId?: string
}

export interface ReportDocument {
  reportId: number | null
  content: string
}

const normalizeJob = (input: UnknownRecord): JobItem => {
  const id = toNumber(getByKeys(input, ['job_id', 'id']), 0)
  const name = toStringSafe(getByKeys(input, ['job_name', 'name', 'title', 'position']), `Job ${id || ''}`)
  const highlightsSource = getByKeys(input, ['highlights', 'advantages', 'strengths'])
  const highlights = asArray(highlightsSource).map((item) => toStringSafe(item)).filter(Boolean)
  const description = toStringSafe(getByKeys(input, ['description', 'desc', 'summary']), '')
  const match = toNumber(getByKeys(input, ['match_score', 'match', 'score']), 0)

  return { id, name, match, highlights, description }
}

const normalizeAnalysis = (source: unknown): MatchingAnalyzeResult => {
  const record = isRecord(source) ? source : {}
  const strengths = asArray(getByKeys(record, ['strengths', 'advantages']))
    .map((item) => toStringSafe(item))
    .filter(Boolean)
  const gaps = asArray(getByKeys(record, ['gaps', 'weaknesses']))
    .map((item) => toStringSafe(item))
    .filter(Boolean)

  const radarIndicatorsSource = asArray(getByKeys(record, ['radar_indicators', 'radarIndicators']))
  const radarIndicators = radarIndicatorsSource
    .map((item) => {
      if (!isRecord(item)) {
        return null
      }
      const name = toStringSafe(getByKeys(item, ['name', 'label']), '')
      if (!name) {
        return null
      }
      return {
        name,
        max: toNumber(getByKeys(item, ['max', 'maxValue']), 100)
      }
    })
    .filter((item): item is RadarIndicator => item !== null)

  const radarSeriesSource = asArray(getByKeys(record, ['radar_series', 'radarSeries']))
  const radarSeries = radarSeriesSource
    .map((item) => {
      if (!isRecord(item)) {
        return null
      }
      const valuesSource = asArray(getByKeys(item, ['values', 'data']))
      const values = valuesSource.map((value) => toNumber(value, 0))
      if (!values.length) {
        return null
      }
      return {
        name: toStringSafe(getByKeys(item, ['name', 'label']), 'Capability'),
        values
      }
    })
    .filter((item): item is RadarSeries => item !== null)

  const fallbackNames = gaps.length
    ? gaps
    : ['Business Understanding', 'Data Skill', 'Role Competency', 'Communication', 'Execution']
  const fallbackIndicators =
    radarIndicators.length > 0
      ? radarIndicators
      : fallbackNames.map((name) => ({
          name,
          max: 100
        }))
  const fallbackSeries =
    radarSeries.length > 0
      ? radarSeries
      : [
          {
            name: 'Candidate',
            values: fallbackIndicators.map(() => 65)
          },
          {
            name: 'Target Role',
            values: fallbackIndicators.map(() => 80)
          }
        ]

  return {
    matchScore: toNumber(getByKeys(record, ['match_score', 'matchScore', 'score']), 0),
    radarIndicators: fallbackIndicators,
    radarSeries: fallbackSeries,
    strengths,
    gaps,
    reportId: toOptionalNumber(getByKeys(record, ['report_id', 'reportId'])) ?? null
  }
}

const normalizeGraph = (source: unknown): PathGraphResult => {
  const record = isRecord(source) ? source : {}
  const nodes = pickRecordList(record, ['nodes', 'vertexes', 'data']).map((node, index) => ({
    id: toStringSafe(getByKeys(node, ['id', 'node_id']), `node-${index}`),
    label: toStringSafe(getByKeys(node, ['label', 'name', 'title']), `Node ${index + 1}`),
    x: toOptionalNumber(getByKeys(node, ['x', 'posX'])),
    y: toOptionalNumber(getByKeys(node, ['y', 'posY'])),
    type: toStringSafe(getByKeys(node, ['type']), '') as PathGraphNode['type']
  }))
  const edges = pickRecordList(record, ['edges', 'links']).map((edge) => ({
    source: toStringSafe(getByKeys(edge, ['source', 'from']), ''),
    target: toStringSafe(getByKeys(edge, ['target', 'to']), ''),
    label: toStringSafe(getByKeys(edge, ['label', 'name']), '') || undefined,
    type: toStringSafe(getByKeys(edge, ['type']), '') as PathGraphEdge['type']
  }))

  return {
    nodes: nodes.filter((item) => item.id && item.label),
    edges: edges.filter((item) => item.source && item.target)
  }
}

const normalizeReport = (source: unknown): ReportItem => {
  const record = isRecord(source) ? source : {}
  const reportId = toStringSafe(getByKeys(record, ['report_id', 'id']), '')
  const title = toStringSafe(getByKeys(record, ['title', 'report_title', 'job_name']), 'Career Report')
  const createdAt = toStringSafe(
    getByKeys(record, ['created_at', 'createdAt', 'date']),
    new Date().toISOString().slice(0, 10)
  )
  const score = toNumber(getByKeys(record, ['score', 'match_score', 'matchScore']), 0)
  const tags = asArray(getByKeys(record, ['tags', 'labels'])).map((item) => toStringSafe(item)).filter(Boolean)

  return {
    id: reportId || `report-${Date.now()}`,
    title,
    createdAt: createdAt.slice(0, 10),
    score,
    tags
  }
}

const normalizeGrowth = (source: unknown): GrowthPoint[] => {
  const list = pickRecordList(source, ['growth', 'growth_series', 'series', 'points'])
  return list.map((item) => ({
    date: toStringSafe(getByKeys(item, ['date', 'x', 'month']), ''),
    value: toNumber(getByKeys(item, ['value', 'score', 'y']), 0),
    label: toStringSafe(getByKeys(item, ['label']), '') || undefined
  }))
}

export const fetchJobs = async (params: FetchJobsParams): Promise<JobItem[]> => {
  const response = await request<unknown>({
    url: '/jobs',
    method: 'GET',
    params: {
      keyword: params.keyword,
      page: params.page ?? 1,
      size: params.size ?? 20
    }
  })

  const items = pickRecordList(response, ['jobs', 'items', 'list', 'data'])
  if (items.length > 0) {
    return items.map(normalizeJob).filter((job) => job.id > 0)
  }

  if (Array.isArray(response)) {
    return response.filter(isRecord).map(normalizeJob).filter((job) => job.id > 0)
  }

  return []
}

export const fetchJobProfile = async (jobId: number): Promise<JobItem> => {
  const response = await request<unknown>({
    url: `/jobs/${jobId}/profile`,
    method: 'GET'
  })
  return normalizeJob(isRecord(response) ? response : {})
}

export const fetchJobGraph = async (jobId: number): Promise<PathGraphResult> => {
  const response = await request<unknown>({
    url: `/jobs/${jobId}/graph`,
    method: 'GET'
  })
  return normalizeGraph(response)
}

export const uploadStudentResume = async (formData: FormData): Promise<StudentUploadProfileResult> => {
  const response = await request<unknown>({
    url: '/student/upload/resume',
    method: 'POST',
    data: formData,
    skipAuth: true
  })

  const record = pickPayloadRecord(response)
  return {
    studentId: toOptionalNumber(getByKeys(record, ['student_id', 'studentId'])) ?? null,
    name: toStringSafe(getByKeys(record, ['name']), ''),
    skills: toStringSafe(getByKeys(record, ['skills']), ''),
    certificates: toStringSafe(getByKeys(record, ['certificates']), ''),
    internships: toStringSafe(getByKeys(record, ['internships', 'experience']), ''),
    selfEvaluation: toStringSafe(getByKeys(record, ['self_evaluation', 'selfEvaluation']), '')
  }
}

export const uploadStudentProfile = async (
  payload: StudentUploadProfilePayload
): Promise<StudentUploadProfileResult> => {
  const response = await request<unknown>({
    url: '/student/upload/profile',
    method: 'POST',
    data: {
      name: payload.name,
      skills: payload.skills,
      certificates: payload.certificates,
      internships: payload.internships,
      self_evaluation: payload.selfEvaluation
    }
  })

  const record = pickPayloadRecord(response)
  return {
    studentId: toOptionalNumber(getByKeys(record, ['student_id', 'studentId'])) ?? null,
    name: toStringSafe(getByKeys(record, ['name']), payload.name ?? ''),
    skills: toStringSafe(getByKeys(record, ['skills']), payload.skills),
    certificates: toStringSafe(getByKeys(record, ['certificates']), payload.certificates),
    internships: toStringSafe(getByKeys(record, ['internships']), payload.internships),
    selfEvaluation: toStringSafe(
      getByKeys(record, ['self_evaluation', 'selfEvaluation']),
      payload.selfEvaluation
    )
  }
}

export const matchingAnalyze = async (payload: MatchingAnalyzePayload): Promise<MatchingAnalyzeResult> => {
  const response = await request<unknown>({
    url: '/matching/analyze',
    method: 'POST',
    data: {
      student_id: payload.studentId,
      job_id: payload.jobId,
      user_id: payload.userId ?? 'default'
    }
  })

  return normalizeAnalysis(response)
}

export const generateReport = async (payload: ReportGeneratePayload): Promise<ReportDocument> => {
  const response = await request<unknown>({
    url: '/reports/generate',
    method: 'POST',
    data: {
      student_id: payload.studentId,
      job_id: payload.jobId,
      custom_instructions: payload.customInstructions,
      user_id: payload.userId ?? 'default'
    }
  })

  const record = isRecord(response) ? response : {}
  return {
    reportId: toOptionalNumber(getByKeys(record, ['report_id', 'reportId'])) ?? null,
    content: toStringSafe(getByKeys(record, ['content', 'report', 'text']), '')
  }
}

export const fetchReport = async (reportId: number): Promise<ReportDocument> => {
  const response = await request<unknown>({
    url: `/reports/${reportId}`,
    method: 'GET'
  })
  const record = isRecord(response) ? response : {}
  return {
    reportId: toOptionalNumber(getByKeys(record, ['report_id', 'reportId'])) ?? reportId,
    content: toStringSafe(getByKeys(record, ['content', 'report', 'text']), '')
  }
}

export const polishReport = async (
  reportId: number,
  payload: { text: string; paragraphIndex?: number }
): Promise<string> => {
  const response = await request<unknown>({
    url: `/reports/${reportId}/polish`,
    method: 'POST',
    data: {
      paragraph_index: payload.paragraphIndex ?? 0,
      text: payload.text
    }
  })

  if (typeof response === 'string') {
    return response
  }
  if (isRecord(response)) {
    return toStringSafe(getByKeys(response, ['content', 'text', 'result']), payload.text)
  }
  return payload.text
}

export const exportReport = async (reportId: number, format: 'pdf' | 'word' = 'pdf'): Promise<Blob> => {
  return request<Blob>({
    url: `/reports/${reportId}/export`,
    method: 'GET',
    params: { format },
    responseType: 'blob'
  })
}

export const fetchUserHistories = async (userId: string): Promise<UserHistoriesResult> => {
  const response = await request<unknown>({
    url: `/users/${userId}/histories`,
    method: 'GET'
  })

  const reports = pickRecordList(response, ['reports', 'histories', 'items', 'list']).map(normalizeReport)
  const growth = normalizeGrowth(response)

  return { reports, growth }
}

export const fetchHistorySnapshot = async (historyId: number): Promise<GrowthPoint[]> => {
  const response = await request<unknown>({
    url: `/histories/${historyId}/snapshot`,
    method: 'GET'
  })
  return normalizeGrowth(response)
}

export const fetchRecommendations = async (gap = ''): Promise<string[]> => {
  const response = await request<unknown>({
    url: '/recommendations',
    method: 'GET',
    params: { gap }
  })

  if (Array.isArray(response)) {
    return response.map((item) => toStringSafe(item)).filter(Boolean)
  }

  if (isRecord(response)) {
    return asArray(getByKeys(response, ['recommendations', 'items', 'tips']))
      .map((item) => toStringSafe(item))
      .filter(Boolean)
  }

  return []
}
