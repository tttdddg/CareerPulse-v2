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
  request<GrowthPoint[]>({
    url: '/history/growth',
    method: 'GET'
  })
