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

const toStringArray = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value
      .map((item) => toStringSafe(item).trim())
      .filter(Boolean)
  }
  if (typeof value === 'string') {
    return value
      .split(/[;,，；\n]/)
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return []
}

const normalizeReport = (input: unknown): ReportSummary | null => {
  if (!isRecord(input)) {
    return null
  }

  const id = toStringSafe(input.id ?? input.report_id ?? input.reportId, '').trim()
  const title = toStringSafe(input.title ?? input.report_title ?? input.job_name, '').trim()
  if (!id || !title) {
    return null
  }

  return {
    id,
    title,
    createdAt: toStringSafe(input.createdAt ?? input.created_at ?? input.date, new Date().toISOString().slice(0, 10)).slice(0, 10),
    score: Math.max(0, Math.min(100, toNumber(input.score ?? input.matchScore ?? input.match_score, 0))),
    tags: toStringArray(input.tags ?? input.labels)
  }
}

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

const pickArrayByKeys = (source: unknown, keys: string[]): unknown[] => {
  if (Array.isArray(source)) {
    return source
  }
  if (!isRecord(source)) {
    return []
  }

  for (const key of keys) {
    const value = source[key]
    if (Array.isArray(value)) {
      return value
    }
  }

  return []
}

const normalizeHistorySummary = (input: unknown): HistorySummaryResult => {
  const reports = pickArrayByKeys(input, ['reports', 'histories', 'items', 'list'])
    .map(normalizeReport)
    .filter((item): item is ReportSummary => item !== null)

  const growthSource = pickArrayByKeys(input, ['growth', 'growth_series', 'series', 'points'])
  const growth = normalizeGrowthSeries(growthSource)

  return { reports, growth }
}

const extractReportId = (input: unknown): number => {
  if (typeof input === 'number' && Number.isFinite(input)) {
    return input
  }
  if (typeof input === 'string') {
    const parsed = Number(input)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  if (isRecord(input)) {
    const direct = extractReportId(input.reportId ?? input.report_id ?? input.id)
    if (direct > 0) {
      return direct
    }

    for (const key of ['data', 'result', 'payload']) {
      const nested = extractReportId(input[key])
      if (nested > 0) {
        return nested
      }
    }
  }
  return 0
}

export const fetchHistorySummary = async (): Promise<HistorySummaryResult> => {
  const response = await request<unknown>({
    url: '/history/summary',
    method: 'GET'
  })
  return normalizeHistorySummary(response)
}

export const fetchReportDetail = async (reportId: string): Promise<ReportSummary> => {
  const response = await request<unknown>({
    url: `/history/reports/${reportId}`,
    method: 'GET'
  })

  const normalized = normalizeReport(response)
  if (normalized) {
    return normalized
  }

  return {
    id: reportId,
    title: '历史报告',
    createdAt: new Date().toISOString().slice(0, 10),
    score: 0,
    tags: []
  }
}

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

export const saveAnalysisReport = async (payload: SaveReportPayload): Promise<{ reportId: number }> => {
  const response = await request<unknown>({
    url: '/history/reports',
    method: 'POST',
    data: payload
  })

  const reportId = extractReportId(response)
  if (reportId > 0) {
    return { reportId }
  }

  throw new Error('保存成功但未返回 reportId，请检查后端返回结构')
}
