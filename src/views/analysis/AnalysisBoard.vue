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
        <span>当前目标岗位:</span>
        <strong>{{ currentJob?.name || '未选择岗位' }}</strong>
      </p>
    </el-card>

    <el-card class="panel jobs-panel" v-loading="jobsLoading">
      <div class="panel-head">
        <h3>岗位画像列表（Top 10）</h3>
        <div class="head-actions">
          <el-button type="primary" plain size="small" :loading="complianceLoading" @click="checkGraphCompliance">
            校验图谱约束
          </el-button>
          <el-button type="primary" plain size="small" @click="fetchJobs">刷新岗位</el-button>
        </div>
      </div>
      <p class="compliance" v-if="complianceResult">{{ complianceResult }}</p>
      <el-empty v-if="!jobProfiles.length" description="暂无岗位画像，请先回到数据输入中心完成分析" />
      <div v-else class="job-grid">
        <article
          v-for="job in jobProfiles"
          :key="job.id"
          class="job-card"
          :class="{ active: job.id === analysisStore.jobId }"
        >
          <div class="job-head">
            <h4>{{ job.name }}</h4>
            <el-tag type="success">{{ Math.round(job.match || 0) }}%</el-tag>
          </div>
          <p class="job-meta">{{ job.company || '企业信息待补充' }} · {{ job.industry || '行业未知' }}</p>
          <p class="job-meta">薪资：{{ job.salaryRange || '待补充' }}</p>
          <div class="tag-row">
            <el-tag v-for="tag in (job.requiredSkills.length ? job.requiredSkills.slice(0, 3) : job.highlights.slice(0, 3))" :key="tag" effect="plain">
              {{ tag }}
            </el-tag>
          </div>
          <div class="job-actions">
            <el-button size="small" type="primary" plain @click="selectTargetJob(job)">设为目标</el-button>
            <el-button size="small" @click="viewJobProfile(job)">查看画像</el-button>
          </div>
        </article>
      </div>
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
              <a href="javascript:void(0)" @click.prevent="goToPlan">查看详情 →</a>
            </div>
          </article>
        </div>
      </el-card>
    </section>

    <el-dialog v-model="profileDialogVisible" title="岗位画像详情" width="680px">
      <el-skeleton v-if="profileLoading" :rows="6" animated />
      <template v-else-if="profileDetail">
        <h3 class="dialog-title">{{ profileDetail.name }}</h3>
        <p class="dialog-desc">{{ profileDetail.description || '暂无岗位描述' }}</p>
        <p class="dialog-meta">薪资范围：{{ profileDetail.salaryRange || '待补充' }}</p>

        <div class="dialog-block">
          <strong>专业技能：</strong>
          <el-tag v-for="item in profileDetail.requiredSkills" :key="item" effect="plain">{{ item }}</el-tag>
        </div>
        <div class="dialog-block">
          <strong>证书要求：</strong>
          <el-tag v-for="item in profileDetail.requiredCerts" :key="item" type="success" effect="plain">{{ item }}</el-tag>
        </div>
        <div class="dialog-block dimensions">
          <strong>能力维度：</strong>
          <span>创新 {{ profileDetail.abilityDimensions.innovation }}</span>
          <span>学习 {{ profileDetail.abilityDimensions.learning }}</span>
          <span>抗压 {{ profileDetail.abilityDimensions.stressTolerance }}</span>
          <span>沟通 {{ profileDetail.abilityDimensions.communication }}</span>
          <span>实习 {{ profileDetail.abilityDimensions.internship }}</span>
        </div>
      </template>
      <el-empty v-else description="暂无画像详情" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { SuitcaseLine, Warning } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useAnalysisStore } from '../../stores/analysis'
import { useHistoryStore } from '../../stores/history'
import RadarChart from '../../components/business/RadarChart.vue'
import { fetchJobGraph, fetchJobProfile, fetchJobs as fetchJobsApi, matchingAnalyze, type JobItem } from '../../api/modules/career'

const router = useRouter()
const analysisStore = useAnalysisStore()
const historyStore = useHistoryStore()
const loading = ref(false)
const jobsLoading = ref(false)
const complianceLoading = ref(false)
const errorMessage = ref('')
const complianceResult = ref('')
const profileDialogVisible = ref(false)
const profileLoading = ref(false)
const profileDetail = ref<JobItem | null>(null)

const gaugeEl = ref<HTMLDivElement | null>(null)
let gaugeChart: echarts.ECharts | null = null

const priorityMap = [
  { label: '紧急', type: 'danger' as const },
  { label: '重要', type: 'warning' as const },
  { label: '一般', type: 'success' as const }
]

const jobProfiles = computed(() => analysisStore.candidateJobs.slice(0, 10))

const currentJob = computed(() => {
  if (!jobProfiles.value.length) {
    return null
  }
  return jobProfiles.value.find((item) => item.id === analysisStore.jobId) ?? jobProfiles.value[0]
})

const getGapDesc = (gap: string): string => {
  return `当前在「${gap}」维度仍有提升空间，建议通过专项练习与项目实践快速补强。`
}

const goToPlan = async (): Promise<void> => {
  await router.push('/app/plan')
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
  if (!analysisStore.studentId || !analysisStore.jobId) {
    errorMessage.value = '缺少分析上下文，请先在数据输入中心完成一次分析'
    return
  }

  try {
    loading.value = true
    const result = await matchingAnalyze({
      studentId: analysisStore.studentId,
      jobId: analysisStore.jobId
    })
    analysisStore.setMatchScore(result.matchScore)
    analysisStore.setRadarData(result.radarIndicators, result.radarSeries)
    analysisStore.setInsights(result.strengths, result.gaps)
    if (result.reportId) {
      analysisStore.setContext({ reportId: result.reportId })
    }
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

    if (analysisStore.candidateJobs.length >= 10) {
      if (!analysisStore.jobId) {
        analysisStore.setContext({ jobId: analysisStore.candidateJobs[0].id })
      }
      return
    }

    const keywordFromHistory = (historyStore.latestReport?.title ?? '').replace('匹配报告', '').trim()
    const keyword = analysisStore.targetKeyword || keywordFromHistory || '产品经理'
    const jobs = await fetchJobsApi({
      keyword,
      page: 1,
      size: 20
    })

    const topJobs = [...jobs].sort((a, b) => b.match - a.match).slice(0, 10)
    analysisStore.setCandidateJobs(topJobs)
    analysisStore.setTargetKeyword(keyword)

    if (!analysisStore.jobId && topJobs[0]) {
      analysisStore.setContext({ jobId: topJobs[0].id })
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载岗位画像失败'
  } finally {
    jobsLoading.value = false
  }
}

const selectTargetJob = async (job: JobItem): Promise<void> => {
  if (analysisStore.jobId === job.id) {
    return
  }

  analysisStore.setContext({ jobId: job.id })

  if (!analysisStore.studentId) {
    ElMessage.warning('缺少学生画像上下文，已切换目标岗位，请先返回数据输入中心完成分析')
    return
  }

  try {
    loading.value = true
    const result = await matchingAnalyze({
      studentId: analysisStore.studentId,
      jobId: job.id
    })
    analysisStore.setMatchScore(result.matchScore)
    analysisStore.setRadarData(result.radarIndicators, result.radarSeries)
    analysisStore.setInsights(result.strengths, result.gaps)
    if (result.reportId) {
      analysisStore.setContext({ reportId: result.reportId })
    }
    renderGauge()
    ElMessage.success(`已切换目标岗位：${job.name}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '切换岗位失败'
  } finally {
    loading.value = false
  }
}

const viewJobProfile = async (job: JobItem): Promise<void> => {
  profileDialogVisible.value = true
  profileDetail.value = job

  try {
    profileLoading.value = true
    const detail = await fetchJobProfile(job.id)
    profileDetail.value = detail
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : '岗位画像详情加载失败')
  } finally {
    profileLoading.value = false
  }
}

const checkGraphCompliance = async (): Promise<void> => {
  if (jobProfiles.value.length < 5) {
    complianceResult.value = `当前仅 ${jobProfiles.value.length} 个岗位画像，不满足“至少5个可换岗岗位”校验条件。`
    return
  }

  try {
    complianceLoading.value = true
    const graphs = await Promise.all(jobProfiles.value.map((job) => fetchJobGraph(job.id)))
    const switchableCount = graphs.filter((graph) => graph.nodes.filter((node) => node.type === 'horizontal').length >= 2).length
    const detailReady = graphs.every((graph) =>
      graph.nodes.every((node) => Boolean(node.jobDescription && node.salaryRange && (node.coreSkills?.length ?? 0) > 0))
    )

    const switchablePass = switchableCount >= 5
    complianceResult.value = `换岗路径达标岗位数：${switchableCount}/${jobProfiles.value.length}（要求至少5个岗位且每个不少于2条）；节点详情完整：${detailReady ? '是' : '否'}`

    if (switchablePass && detailReady) {
      ElMessage.success('图谱约束校验通过')
    } else {
      ElMessage.warning('图谱约束未完全通过，请补充后端图谱数据')
    }
  } catch (error) {
    complianceResult.value = error instanceof Error ? error.message : '图谱约束校验失败'
  } finally {
    complianceLoading.value = false
  }
}

const handleResize = (): void => {
  gaugeChart?.resize()
}

onMounted(async () => {
  await fetchJobs()
  if (!analysisStore.hasRadar && analysisStore.studentId && analysisStore.jobId) {
    await refreshRadar()
  }
  renderGauge()
  window.addEventListener('resize', handleResize)
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

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.head-actions {
  display: flex;
  gap: 8px;
}

.compliance {
  margin: 0 0 12px;
  font-size: 13px;
  color: #475569;
}

.job-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}

.job-card {
  border: 1px solid #e2e6ef;
  border-radius: 14px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.job-card.active {
  border-color: #5f5ee7;
  box-shadow: 0 0 0 2px rgba(95, 94, 231, 0.1);
}

.job-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.job-head h4 {
  margin: 0;
  font-size: 16px;
  color: #1f2a3f;
}

.job-meta {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 28px;
}

.job-actions {
  display: flex;
  gap: 8px;
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

.dialog-title {
  margin: 0;
  font-size: 18px;
}

.dialog-desc,
.dialog-meta {
  color: #475569;
  line-height: 1.6;
}

.dialog-block {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.dialog-block.dimensions span {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 12px;
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
