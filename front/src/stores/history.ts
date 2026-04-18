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
  deletedReportIds: string[]
}

interface PersistedHistoryState {
  reports: ReportSummary[]
  growthSeries: GrowthPoint[]
  lastViewedReportId: string | null
  deletedReportIds: string[]
}

const STORAGE_KEY = 'career-pulse:history'

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null

const toStringSafe = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback

const toNumberSafe = (value: unknown, fallback = 0): number => {
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

const isPlaceholderReportTitle = (title: string): boolean => title.trim().toLowerCase() === 'career report'

const sanitizeReports = (reports: ReportSummary[]): ReportSummary[] => {
  const reportMap = new Map<string, ReportSummary>()
  reports.forEach((report) => {
    if (!report.id || !report.title || isPlaceholderReportTitle(report.title)) {
      return
    }
    reportMap.set(report.id, report)
  })
  return Array.from(reportMap.values()).sort((a, b) => b.createdAt.localeCompare(a.createdAt))
}

const parseReport = (value: unknown): ReportSummary | null => {
  if (!isRecord(value)) {
    return null
  }

  const id = toStringSafe(value.id, '').trim()
  const title = toStringSafe(value.title, '').trim()
  if (!id || !title) {
    return null
  }

  const rawTags = Array.isArray(value.tags) ? value.tags : []
  const tags = rawTags.map((item) => toStringSafe(item, '').trim()).filter(Boolean)

  return {
    id,
    title,
    createdAt: toStringSafe(value.createdAt, new Date().toISOString().slice(0, 10)).slice(0, 10),
    score: Math.max(0, Math.min(100, toNumberSafe(value.score, 0))),
    tags
  }
}

const parseGrowth = (value: unknown): GrowthPoint | null => {
  if (!isRecord(value)) {
    return null
  }
  const date = toStringSafe(value.date, '').trim()
  if (!date) {
    return null
  }
  return {
    date,
    value: toNumberSafe(value.value, 0),
    label: toStringSafe(value.label, '') || undefined
  }
}

const persistState = (state: PersistedHistoryState): void => {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

const loadPersistedState = (): PersistedHistoryState | null => {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    const parsed = JSON.parse(raw) as unknown
    if (!isRecord(parsed)) {
      return null
    }

    const reports = sanitizeReports(
      (Array.isArray(parsed.reports) ? parsed.reports : [])
      .map(parseReport)
      .filter((item): item is ReportSummary => item !== null)
    )
    const growthSeries = (Array.isArray(parsed.growthSeries) ? parsed.growthSeries : [])
      .map(parseGrowth)
      .filter((item): item is GrowthPoint => item !== null)
    const lastViewedReportId = typeof parsed.lastViewedReportId === 'string' ? parsed.lastViewedReportId : null
    const deletedReportIds = (Array.isArray(parsed.deletedReportIds) ? parsed.deletedReportIds : [])
      .map((item) => toStringSafe(item, '').trim())
      .filter(Boolean)

    return {
      reports,
      growthSeries,
      lastViewedReportId,
      deletedReportIds
    }
  } catch {
    return null
  }
}

export const useHistoryStore = defineStore('history', {
  state: (): HistoryState => ({
    reports: [],
    growthSeries: [],
    lastViewedReportId: null,
    deletedReportIds: []
  }),
  getters: {
    latestReport: (state): ReportSummary | null => state.reports[0] ?? null
  },
  actions: {
    // 从本地存储恢复历史记录
    hydrateFromStorage(): void {
      const persisted = loadPersistedState()
      if (!persisted) {
        return
      }

      this.reports = sanitizeReports(persisted.reports)
      this.growthSeries = persisted.growthSeries
      this.deletedReportIds = persisted.deletedReportIds
      this.lastViewedReportId =
        persisted.lastViewedReportId && this.reports.some((report) => report.id === persisted.lastViewedReportId)
          ? persisted.lastViewedReportId
          : this.reports[0]?.id ?? null
      this.persist()
    },

    persist(): void {
      persistState({
        reports: this.reports,
        growthSeries: this.growthSeries,
        lastViewedReportId: this.lastViewedReportId,
        deletedReportIds: this.deletedReportIds
      })
    },

    // 设置历史报告列表
    setReports(reports: ReportSummary[]): void {
      const nextReports = sanitizeReports(reports).filter((report) => !this.deletedReportIds.includes(report.id))
      this.reports = nextReports
      this.lastViewedReportId = nextReports[0]?.id ?? null
      this.persist()
    },

    // 追加单条报告
    addReport(report: ReportSummary): void {
      if (this.deletedReportIds.includes(report.id)) {
        return
      }
      if (isPlaceholderReportTitle(report.title)) {
        return
      }
      const filtered = this.reports.filter((item) => item.id !== report.id)
      this.reports = sanitizeReports([report, ...filtered])
      this.lastViewedReportId = this.reports[0]?.id ?? null
      this.persist()
    },

    // 设置成长曲线数据
    setGrowthSeries(series: GrowthPoint[]): void {
      this.growthSeries = series
      this.persist()
    },

    // 更新最后查看的报告
    setLastViewedReport(reportId: string | null): void {
      this.lastViewedReportId = reportId
      this.persist()
    },

    // 删除单条历史报告
    removeReport(reportId: string): void {
      if (!this.deletedReportIds.includes(reportId)) {
        this.deletedReportIds = [...this.deletedReportIds, reportId]
      }
      this.reports = this.reports.filter((report) => report.id !== reportId)
      if (this.lastViewedReportId === reportId) {
        this.lastViewedReportId = this.reports[0]?.id ?? null
      }
      this.persist()
    },

    clearLocalHistory(): void {
      this.reports = []
      this.growthSeries = []
      this.lastViewedReportId = null
      this.deletedReportIds = []
      this.persist()
    }
  }
})
