import { request } from '../request'

export interface ReportSummary {
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

export interface HistorySummaryResult {
  reports: ReportSummary[]
  growth: GrowthPoint[]
}

type UnknownRecord = Record<string, unknown>

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === 'object' && value !== null

const toNumber = (value: unknown, fallback = 0): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value.replace(/%/g, '').trim())
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return fallback
}

const toStringSafe = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback

const normalizeGrowthPoint = (input: unknown): GrowthPoint | null => {
  if (!isRecord(input)) {
    return null
  }

  const date = toStringSafe(input.date ?? input.x ?? input.month, '').trim()
  const value = toNumber(input.value ?? input.score ?? input.y, Number.NaN)

  if (!date || !Number.isFinite(value)) {
    return null
  }

  return {
    date,
    value,
    label: toStringSafe(input.label, '') || undefined
  }
}

const normalizeGrowthSeries = (input: unknown): GrowthPoint[] => {
  if (!Array.isArray(input)) {
    return []
  }

  return input.map(normalizeGrowthPoint).filter((item): item is GrowthPoint => item !== null)
}

export const fetchHistorySummary = (): Promise<HistorySummaryResult> =>
  request<HistorySummaryResult>({
    url: '/history/summary',
    method: 'GET'
  })

export const fetchReportDetail = (reportId: string): Promise<ReportSummary> =>
  request<ReportSummary>({
    url: `/history/reports/${reportId}`,
    method: 'GET'
  })

export const fetchGrowthSeries = (): Promise<GrowthPoint[]> =>
  request<unknown>({
    url: '/history/growth',
    method: 'GET'
  }).then(normalizeGrowthSeries)

export const deleteHistoryReport = (reportId: string): Promise<void> =>
  request<void>({
    url: `/history/reports/${reportId}`,
    method: 'DELETE'
  })

export interface SaveReportPayload {
  userId: string
  title: string
  score: number
  tags: string[]
  matchScore: number
  radarIndicators: { name: string; max: number }[]
  radarSeries: { name: string; values: number[] }[]
  strengths: string[]
  gaps: string[]
  studentId?: number | null
  jobId?: number | null
}

export const saveAnalysisReport = (payload: SaveReportPayload): Promise<{ reportId: number }> =>
  request<{ reportId: number }>({
    url: '/history/reports',
    method: 'POST',
    data: payload
  })
