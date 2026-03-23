import { defineStore } from 'pinia'
import type { JobItem } from '../api/modules/career'

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
  radarIndicators: RadarIndicator[]
  radarSeries: RadarSeries[]
  strengths: string[]
  gaps: string[]
  targetKeyword: string
  candidateJobs: JobItem[]
  studentId: number | null
  jobId: number | null
  reportId: number | null
  updatedAt: string | null
}

export const useAnalysisStore = defineStore('analysis', {
  state: (): AnalysisState => ({
    matchScore: 0,
    radarIndicators: [],
    radarSeries: [],
    strengths: [],
    gaps: [],
    targetKeyword: '',
    candidateJobs: [],
    studentId: null,
    jobId: null,
    reportId: null,
    updatedAt: null
  }),
  getters: {
    hasRadar: (state): boolean => state.radarIndicators.length > 0 && state.radarSeries.length > 0
  },
  actions: {
    // 设置匹配度并限制在 0-100
    setMatchScore(score: number): void {
      const clamped = Math.min(Math.max(score, 0), 100)
      this.matchScore = clamped
      this.updatedAt = new Date().toISOString()
    },

    // 更新雷达图数据（个人/岗位对比）
    setRadarData(indicators: RadarIndicator[], series: RadarSeries[]): void {
      this.radarIndicators = indicators
      this.radarSeries = series
      this.updatedAt = new Date().toISOString()
    },

    // 写入优势与差距维度
    setInsights(strengths: string[], gaps: string[]): void {
      this.strengths = strengths
      this.gaps = gaps
      this.updatedAt = new Date().toISOString()
    },

    setTargetKeyword(keyword: string): void {
      this.targetKeyword = keyword.trim()
      this.updatedAt = new Date().toISOString()
    },

    setCandidateJobs(jobs: JobItem[]): void {
      this.candidateJobs = jobs
      this.updatedAt = new Date().toISOString()
    },

    // 保存当前分析上下文（学生、岗位、报告）
    setContext(payload: { studentId?: number | null; jobId?: number | null; reportId?: number | null }): void {
      if (payload.studentId !== undefined) {
        this.studentId = payload.studentId
      }
      if (payload.jobId !== undefined) {
        this.jobId = payload.jobId
      }
      if (payload.reportId !== undefined) {
        this.reportId = payload.reportId
      }
      this.updatedAt = new Date().toISOString()
    },

    // 重置分析数据
    reset(): void {
      this.matchScore = 0
      this.radarIndicators = []
      this.radarSeries = []
      this.strengths = []
      this.gaps = []
      this.targetKeyword = ''
      this.candidateJobs = []
      this.studentId = null
      this.jobId = null
      this.reportId = null
      this.updatedAt = null
    }
  }
})
