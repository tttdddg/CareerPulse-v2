<template>
  <div class="profile-page">
    <el-alert
      v-if="errorMessage"
      type="error"
      :title="errorMessage"
      show-icon
      class="error-alert"
      @close="errorMessage = ''"
    />

    <section class="profile-layout">
      <el-card class="panel profile-card" v-loading="loading">
        <div class="avatar-ring"></div>
        <h2>{{ userStore.profile?.name || 'John Doe' }}</h2>

        <div class="info-list">
          <div class="info-row">
            <span>Email</span>
            <strong>{{ profileEmail }}</strong>
          </div>
          <div class="info-row">
            <span>Member since</span>
            <strong>{{ memberSince }}</strong>
          </div>
          <div class="info-row">
            <span>Level</span>
            <strong>Premium</strong>
          </div>
          <div class="info-row">
            <span>Profile status</span>
            <strong class="status"><i></i>Online</strong>
          </div>
        </div>
      </el-card>

      <section class="right-col">
        <el-card class="panel report-panel" v-loading="loading">
          <div class="report-title">历史报告</div>
          <el-empty v-if="!historyStore.reports.length" description="暂无历史报告，先去数据输入中心发起分析" />
          <article
            v-for="report in historyStore.reports"
            :key="report.id"
            class="report-item"
            role="button"
            tabindex="0"
            @click="openReportDetail(report.id)"
            @keyup.enter="openReportDetail(report.id)"
          >
            <h3>岗位: {{ formatReportRole(report.title) }}</h3>
            <p>日期: {{ report.createdAt }}</p>
            <p>Match Score: {{ report.score }}% (匹配分)</p>
            <div class="score-bar">
              <span :style="{ width: `${report.score}%` }"></span>
            </div>
            <div class="report-item-actions">
              <el-button type="primary" text @click.stop="openReportDetail(report.id)">查看详情</el-button>
              <el-button
                type="danger"
                text
                :loading="deletingReportId === report.id"
                @click.stop="handleDeleteReport(report.id)"
              >
                删除
              </el-button>
            </div>
          </article>
        </el-card>

        <el-card class="panel curve-panel">
          <h3>能力成长曲线</h3>
          <growth-chart :series="growthSeries" :height="300" :show-legend="false" />
        </el-card>
      </section>
    </section>

    <el-dialog v-model="detailVisible" title="历史报告详情" width="560px">
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="activeReport">
          <h4 class="detail-role">岗位: {{ formatReportRole(activeReport.title) }}</h4>
          <p><strong>报告编号:</strong> {{ activeReport.id }}</p>
          <p><strong>生成日期:</strong> {{ activeReport.createdAt }}</p>
          <p><strong>匹配分:</strong> {{ activeReport.score }}%</p>
          <div class="detail-tags">
            <strong>标签:</strong>
            <el-tag v-for="tag in activeReport.tags" :key="tag" size="small" effect="plain" class="tag-item">{{ tag }}</el-tag>
            <span v-if="!activeReport.tags.length" class="tag-empty">暂无标签</span>
          </div>
        </template>
        <el-empty v-else description="暂无详情数据" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAnalysisStore } from '../../stores/analysis'
import { useHistoryStore } from '../../stores/history'
import { useUserStore } from '../../stores/user'
import GrowthChart from '../../components/business/GrowthChart.vue'
import { fetchUserHistories } from '../../api/modules/career'
import { deleteHistoryReport, fetchGrowthSeries, fetchHistorySummary, fetchReportDetail } from '../../api/modules/history'
import type { ReportSummary } from '../../stores/history'

const userStore = useUserStore()
const historyStore = useHistoryStore()
const analysisStore = useAnalysisStore()

const loading = ref(false)
const errorMessage = ref('')
const detailVisible = ref(false)
const detailLoading = ref(false)
const activeReport = ref<ReportSummary | null>(null)
const deletingReportId = ref<string | null>(null)

const profileEmail = computed(() => {
  const name = userStore.profile?.name?.trim() || 'user'
  return `${name.toLowerCase()}@example.com`
})

const memberSince = computed(() => historyStore.reports[0]?.createdAt ?? new Date().toISOString().slice(0, 10))

const normalizeGrowthInput = (
  points: { date: string; value: number; label?: string }[]
): { date: string; value: number; label?: string }[] =>
  points.filter((point) => typeof point.date === 'string' && point.date.trim().length > 0 && Number.isFinite(point.value))

const growthSeries = computed(() => [
  {
    name: '成长评分',
    data: historyStore.growthSeries.length
      ? historyStore.growthSeries
      : [
          { date: '01-01', value: 68 },
          { date: '02-01', value: 74 },
          { date: '03-01', value: 78 },
          { date: '04-01', value: analysisStore.matchScore || 82 }
        ]
  }
])

const mergeReports = (localReports: ReportSummary[], remoteReports: ReportSummary[]): ReportSummary[] => {
  const reportMap = new Map<string, ReportSummary>()
  const mergedReports = [...localReports, ...remoteReports]

  mergedReports.forEach((report) => {
    reportMap.set(report.id, report)
  })

  return Array.from(reportMap.values()).sort((a, b) => b.createdAt.localeCompare(a.createdAt))
}

const formatReportRole = (title: string): string => title.replace('匹配报告', '').trim()

const handleDeleteReport = async (reportId: string): Promise<void> => {
  const target = historyStore.reports.find((report) => report.id === reportId)
  const roleName = target ? formatReportRole(target.title) : reportId
  try {
    await ElMessageBox.confirm(`确认删除「${roleName}」历史报告吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  deletingReportId.value = reportId
  try {
    await deleteHistoryReport(reportId)
    historyStore.removeReport(reportId)
    if (activeReport.value?.id === reportId) {
      activeReport.value = null
      detailVisible.value = false
    }
    ElMessage.success('历史报告已删除')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '删除失败，请稍后重试')
  } finally {
    deletingReportId.value = null
  }
}

const openReportDetail = async (reportId: string): Promise<void> => {
  detailVisible.value = true
  detailLoading.value = true
  historyStore.setLastViewedReport(reportId)

  const localReport = historyStore.reports.find((report) => report.id === reportId) ?? null
  activeReport.value = localReport

  try {
    const detail = await fetchReportDetail(reportId)
    activeReport.value = detail
  } catch {
    // 静默降级到本地缓存数据，避免打断阅读体验
  } finally {
    detailLoading.value = false
  }
}

onMounted(async () => {
  const localReports = [...historyStore.reports]

  const applyHistoryData = (reports: ReportSummary[], growth: { date: string; value: number; label?: string }[]): void => {
    historyStore.setReports(mergeReports(localReports, reports))
    historyStore.setGrowthSeries(normalizeGrowthInput(growth))
  }

  try {
    loading.value = true
    // 优先从后端加载用户历史报告
    const result = await fetchUserHistories(userStore.profile?.id ?? 'default')
    const hasRemoteData = result.reports.length > 0 || result.growth.length > 0
    if (hasRemoteData) {
      applyHistoryData(result.reports, result.growth)
      return
    }

    // 如果后端没有数据，尝试从备用接口加载
    const [summary, growthSeries] = await Promise.all([fetchHistorySummary(), fetchGrowthSeries()])
    applyHistoryData(summary.reports, growthSeries.length ? growthSeries : summary.growth)
  } catch (error) {
    console.error('加载远程历史数据失败:', error)
    // 降级处理：使用本地缓存数据
    if (localReports.length > 0) {
      historyStore.setReports(localReports)
      errorMessage.value = ''
    } else {
      errorMessage.value = '加载历史数据失败，请检查网络连接'
    }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.profile-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.profile-layout {
  display: grid;
  grid-template-columns: minmax(280px, 0.38fr) minmax(0, 0.62fr);
  gap: 16px;
}

.panel {
  border-radius: 16px;
  border: 1px solid #e3e8f1;
  background: #ffffff;
}

.profile-card {
  background: linear-gradient(180deg, #eff3ff 0%, #f5f7ff 100%);
  text-align: center;
  padding: 26px;
}

.avatar-ring {
  width: 140px;
  height: 140px;
  margin: 0 auto 18px;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, #6474ef, #424ac7);
  box-shadow: 0 0 0 6px rgba(93, 104, 232, 0.2), 0 16px 30px rgba(67, 76, 188, 0.25);
}

.profile-card h2 {
  margin: 0 0 14px;
  font-size: 20px;
}

.info-list {
  text-align: left;
  border-top: 1px solid #d9dfeb;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #d9dfeb;
  color: #364057;
  font-size: 14px;
}

.info-row strong {
  font-weight: 600;
}

.status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.status i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #55bf74;
}

.right-col {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.report-title {
  margin-bottom: 12px;
  padding: 10px;
  border-radius: 10px;
  background: #e9effa;
  text-align: center;
  color: #63708e;
  font-weight: 700;
}

.report-item {
  border: 1px solid #dce3ef;
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.report-item:hover,
.report-item:focus-visible {
  border-color: #7892ff;
  box-shadow: 0 10px 24px rgba(59, 93, 201, 0.12);
}

.report-item h3 {
  margin: 0 0 8px;
  font-size: 17px;
}

.report-item p {
  margin: 0 0 6px;
  color: #5f6980;
  font-size: 14px;
}

.score-bar {
  margin-top: 8px;
  height: 8px;
  border-radius: 999px;
  background: #e3e8f2;
  overflow: hidden;
}

.score-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #4d6df2 0%, #a55de4 100%);
}

.report-item-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 8px;
}

.detail-error {
  margin-bottom: 12px;
}

.detail-body {
  min-height: 180px;
}

.detail-role {
  margin: 0 0 12px;
  font-size: 18px;
}

.detail-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-item {
  margin-right: 0;
}

.tag-empty {
  color: #7b8396;
  font-size: 13px;
}

.curve-panel h3 {
  margin: 0 0 8px;
  font-size: 22px;
}

.error-alert {
  margin-bottom: 4px;
}

@media (max-width: 1150px) {
  .profile-layout {
    grid-template-columns: 1fr;
  }
}
</style>
