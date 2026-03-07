import { defineStore } from 'pinia'

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
  updatedAt: string | null
}

export const useAnalysisStore = defineStore('analysis', {
  state: (): AnalysisState => ({
    matchScore: 0,
    radarIndicators: [],
    radarSeries: [],
    strengths: [],
    gaps: [],
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

    // 重置分析数据
    reset(): void {
      this.matchScore = 0
      this.radarIndicators = []
      this.radarSeries = []
      this.strengths = []
      this.gaps = []
      this.updatedAt = null
    }
  }
})
