import { defineStore } from 'pinia'
import type { JobItem, MatchingGap } from '../api/modules/career'

// 雷达图维度定义
export interface RadarIndicator {
  name: string
  max: number
}

// 雷达图序列
export interface RadarSeries {
  name: string
  values: number[]
}

export interface AnalysisState {
  matchScore: number
  hasMatchResult: boolean
  radarIndicators: RadarIndicator[]
  radarSeries: RadarSeries[]
  strengths: string[]
  gaps: string[]
  gapDetails: MatchingGap[]
  targetKeyword: string
  candidateJobs: JobItem[]
  sessionId: string | null
  studentId: number | null
  jobId: number | null
  reportId: number | null
  pathAccessJobId: number | null
  updatedAt: string | null
}

export const useAnalysisStore = defineStore('analysis', {
  state: (): AnalysisState => ({
    matchScore: 0,
    hasMatchResult: false,
    radarIndicators: [],
    radarSeries: [],
    strengths: [],
    gaps: [],
    gapDetails: [],
    targetKeyword: '',
    candidateJobs: [],
    sessionId: null,
    studentId: null,
    jobId: null,
    reportId: null,
    pathAccessJobId: null,
    updatedAt: null
  }),
  getters: {
    hasRadar: (state): boolean => state.radarIndicators.length > 0 && state.radarSeries.length > 0,
    canVisitPathGraph: (state): boolean =>
      state.jobId !== null && state.pathAccessJobId !== null && state.pathAccessJobId === state.jobId
  },
  actions: {
    // 设置匹配度并限制在 0-100
    setMatchScore(score: number): void {
      const clamped = Math.min(Math.max(score, 0), 100)
      this.matchScore = clamped
      this.hasMatchResult = true
      this.updatedAt = new Date().toISOString()
    },

    // 更新雷达图数据（个人/岗位对比）
    setRadarData(indicators: RadarIndicator[], series: RadarSeries[]): void {
      this.radarIndicators = indicators
      this.radarSeries = series
      this.updatedAt = new Date().toISOString()
    },

    // 写入优势与差距维度
    setInsights(strengths: string[], gaps: string[], gapDetails: MatchingGap[] = []): void {
      this.strengths = strengths
      this.gaps = gaps
      this.gapDetails = gapDetails
      this.updatedAt = new Date().toISOString()
    },

    setTargetKeyword(keyword: string): void {
      this.targetKeyword = keyword.trim()
      this.updatedAt = new Date().toISOString()
    },

    setCandidateJobs(jobs: JobItem[]): void {
      this.candidateJobs = jobs
      this.pathAccessJobId = null
      this.updatedAt = new Date().toISOString()
    },

    // 保存当前分析上下文（workflow、学生、岗位、报告）
    setContext(payload: {
      sessionId?: string | null
      studentId?: number | null
      jobId?: number | null
      reportId?: number | null
    }): void {
      if (payload.sessionId !== undefined) {
        this.sessionId = payload.sessionId
      }
      if (payload.studentId !== undefined) {
        this.studentId = payload.studentId
      }
      if (payload.jobId !== undefined) {
        if (payload.jobId !== this.jobId) {
          this.pathAccessJobId = null
        }
        this.jobId = payload.jobId
      }
      if (payload.reportId !== undefined) {
        this.reportId = payload.reportId
      }
      this.updatedAt = new Date().toISOString()
    },

    grantPathAccess(jobId: number): void {
      this.pathAccessJobId = jobId
      this.updatedAt = new Date().toISOString()
    },

    // 重置分析数据
    reset(): void {
      this.matchScore = 0
      this.hasMatchResult = false
      this.radarIndicators = []
      this.radarSeries = []
      this.strengths = []
      this.gaps = []
      this.gapDetails = []
      this.targetKeyword = ''
      this.candidateJobs = []
      this.sessionId = null
      this.studentId = null
      this.jobId = null
      this.reportId = null
      this.pathAccessJobId = null
      this.updatedAt = null
    }
  }
})
