import { defineStore } from 'pinia'

// 历史报告摘要
export interface ReportSummary {
  id: string
  title: string
  createdAt: string
  score: number
  tags: string[]
}

// 成长曲线节点
export interface GrowthPoint {
  date: string
  value: number
  label?: string
}

export interface HistoryState {
  reports: ReportSummary[]
  growthSeries: GrowthPoint[]
  lastViewedReportId: string | null
}

export const useHistoryStore = defineStore('history', {
  state: (): HistoryState => ({
    reports: [],
    growthSeries: [],
    lastViewedReportId: null
  }),
  getters: {
    latestReport: (state): ReportSummary | null => state.reports[0] ?? null
  },
  actions: {
    // 设置历史报告列表
    setReports(reports: ReportSummary[]): void {
      this.reports = reports
      this.lastViewedReportId = reports[0]?.id ?? null
    },

    // 追加单条报告
    addReport(report: ReportSummary): void {
      this.reports = [report, ...this.reports]
      this.lastViewedReportId = report.id
    },

    // 设置成长曲线数据
    setGrowthSeries(series: GrowthPoint[]): void {
      this.growthSeries = series
    },

    // 更新最后查看的报告
    setLastViewedReport(reportId: string | null): void {
      this.lastViewedReportId = reportId
    }
  }
})
