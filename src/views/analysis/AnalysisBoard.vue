<template>
  <div class="analysis-board">
    <el-alert
      v-if="errorMessage"
      type="error"
      :title="errorMessage"
      show-icon
      class="error-alert"
      @close="errorMessage = ''"
    />

    <section class="page-head">
      <h2>人岗匹配分析</h2>
      <p>基于多维度能力模型的智能匹配结果</p>
    </section>

    <el-card class="panel summary" v-loading="loading">
      <div ref="gaugeEl" class="gauge"></div>
      <p class="target-role">
        <el-icon><SuitcaseLine /></el-icon>
        <span>目标岗位:</span>
        <strong>{{ topJob?.name || '高级产品经理' }}</strong>
      </p>
    </el-card>

    <section class="detail-grid">
      <el-card class="panel">
        <h3>能力维度对比分析</h3>
        <radar-chart
          v-if="analysisStore.hasRadar"
          :indicators="analysisStore.radarIndicators"
          :series="analysisStore.radarSeries"
          :height="360"
        />
        <el-empty v-else description="暂无雷达数据" />
      </el-card>

      <el-card class="panel gap-panel" v-loading="jobsLoading">
        <div class="panel-head">
          <h3>能力差距详细分析</h3>
          <el-button type="primary" plain size="small" @click="refreshRadar">刷新</el-button>
        </div>
        <el-empty v-if="!analysisStore.gaps.length" description="暂无差距项" />
        <div v-else class="gap-list">
          <article v-for="(gap, index) in analysisStore.gaps" :key="gap" class="gap-item">
            <div class="gap-icon">
              <el-icon><Warning /></el-icon>
            </div>
            <div class="gap-content">
              <div class="gap-title-row">
                <h4>{{ gap }}</h4>
                <el-tag :type="priorityMap[index % priorityMap.length].type" size="small">
                  {{ priorityMap[index % priorityMap.length].label }}
                </el-tag>
              </div>
              <p>{{ getGapDesc(gap) }}</p>
              <a href="javascript:void(0)">查看详情 →</a>
            </div>
          </article>
        </div>
      </el-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { SuitcaseLine, Warning } from '@element-plus/icons-vue'
import { useAnalysisStore } from '../../stores/analysis'
import { useHistoryStore } from '../../stores/history'
import RadarChart from '../../components/business/RadarChart.vue'
import { mockFetchJobProfiles, mockStartAnalysis } from '../../services/mockApi'

interface JobProfile {
  id: string
  name: string
  match: number
  highlights: string[]
  description: string
}

const analysisStore = useAnalysisStore()
const historyStore = useHistoryStore()
const loading = ref(false)
const jobsLoading = ref(false)
const errorMessage = ref('')
const jobProfiles = ref<JobProfile[]>([])

const gaugeEl = ref<HTMLDivElement | null>(null)
let gaugeChart: echarts.ECharts | null = null

const priorityMap = [
  { label: '紧急', type: 'danger' as const },
  { label: '重要', type: 'warning' as const },
  { label: '一般', type: 'success' as const }
]

const topJob = computed(() => {
  if (jobProfiles.value[0]) {
    return jobProfiles.value[0]
  }

  const latestTitle = historyStore.latestReport?.title ?? ''
  return latestTitle ? { id: 'latest', name: latestTitle.replace('匹配报告', '').trim(), match: 0, highlights: [], description: '' } : null
})

const getGapDesc = (gap: string): string => {
  return `当前在「${gap}」维度仍有提升空间，建议通过专项练习与项目实践快速补强。`
}

const renderGauge = (): void => {
  if (!gaugeEl.value) {
    return
  }

  if (!gaugeChart) {
    gaugeChart = echarts.init(gaugeEl.value)
  }

  gaugeChart.setOption({
    title: {
      text: '整体匹配度',
      left: 'center',
      top: '64%',
      textStyle: {
        color: '#8a92a6',
        fontWeight: 500,
        fontSize: 16
      }
    },
    series: [
      {
        type: 'gauge',
        startAngle: 90,
        endAngle: -270,
        radius: '80%',
        progress: {
          show: true,
          width: 16,
          roundCap: true,
          itemStyle: {
            color: '#6c63f5'
          }
        },
        axisLine: {
          lineStyle: {
            width: 16,
            color: [[1, '#e6e9f2']]
          }
        },
        pointer: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        detail: {
          valueAnimation: true,
          formatter: '{value}%',
          color: '#5f5ee7',
          fontSize: 62,
          fontWeight: 700,
          offsetCenter: [0, '-6%']
        },
        data: [{ value: analysisStore.matchScore || 0 }]
      }
    ]
  })
}

const refreshRadar = async (): Promise<void> => {
  try {
    loading.value = true
    const result = await mockStartAnalysis()
    analysisStore.setMatchScore(result.matchScore)
    analysisStore.setRadarData(result.radarIndicators, result.radarSeries)
    analysisStore.setInsights(result.strengths, result.gaps)
    ElMessage.success('分析结果已更新')
    renderGauge()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '刷新失败'
  } finally {
    loading.value = false
  }
}

const fetchJobs = async (): Promise<void> => {
  try {
    jobsLoading.value = true
    const jobs = await mockFetchJobProfiles()
    jobProfiles.value = [...jobs].sort((a, b) => b.match - a.match)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载岗位画像失败'
  } finally {
    jobsLoading.value = false
  }
}

const handleResize = (): void => {
  gaugeChart?.resize()
}

onMounted(async () => {
  if (!analysisStore.hasRadar) {
    await refreshRadar()
  }
  renderGauge()
  window.addEventListener('resize', handleResize)
  await fetchJobs()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  gaugeChart?.dispose()
  gaugeChart = null
})
</script>

<style scoped>
.analysis-board {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.page-head h2 {
  margin: 0 0 6px;
  font-size: 24px;
  color: #1f2a3f;
}

.page-head p {
  margin: 0;
  color: #7a859c;
  font-size: 15px;
}

.panel {
  border-radius: 18px;
  border: 1px solid #e4e8f0;
  background: #ffffff;
}

.summary {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 420px;
}

.gauge {
  width: min(100%, 500px);
  height: 320px;
}

.target-role {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  color: #2e3648;
}

.target-role strong {
  color: #5f5ee7;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 22px;
}

.panel h3 {
  margin: 0 0 16px;
  font-size: 22px;
  color: #1f2a3f;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.gap-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.gap-item {
  border: 1px solid #e2e6ef;
  border-radius: 14px;
  padding: 18px;
  display: flex;
  gap: 14px;
}

.gap-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #eef1ff;
  color: #6862f5;
}

.gap-content {
  flex: 1;
}

.gap-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.gap-title-row h4 {
  margin: 0;
  font-size: 19px;
}

.gap-content p {
  margin: 0 0 8px;
  font-size: 14px;
  color: #6c768d;
  line-height: 1.55;
}

.gap-content a {
  color: #5f5ee7;
  font-weight: 600;
  text-decoration: none;
}

.error-alert {
  margin-bottom: 4px;
}

@media (max-width: 1100px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
