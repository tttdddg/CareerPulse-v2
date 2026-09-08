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

    <section class="page-head">
      <h2>成长档案</h2>
      <p>沉淀画像、匹配、学习、训练与反馈产生的长期成长记录。</p>
    </section>

    <section class="overview-grid" aria-label="成长档案概览">
      <el-card v-for="item in overviewItems" :key="item.label" class="panel overview-card" v-loading="loading">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </el-card>
    </section>

    <section class="profile-layout">
      <el-card class="panel profile-card" v-loading="loading">
        <div class="avatar-ring"></div>
        <h2>{{ userStore.profile?.name || '未设置用户名' }}</h2>

        <div class="info-list">
          <div class="info-row">
            <span>用户标识</span>
            <strong>{{ userStore.profile?.id || '暂无' }}</strong>
          </div>
          <div class="info-row">
            <span>账号角色</span>
            <strong>{{ userStore.profile?.role || '暂无' }}</strong>
          </div>
          <div class="info-row">
            <span>最近记录</span>
            <strong>{{ latestRecordDate }}</strong>
          </div>
          <div class="info-row">
            <span>历史记录</span>
            <strong>{{ historyLoaded ? `${visibleReports.length} 条` : '暂无' }}</strong>
          </div>
        </div>
      </el-card>

      <section class="right-col">
        <el-card class="panel curve-panel" v-loading="loading">
          <div class="section-head">
            <div>
              <h3>能力变化</h3>
              <p>当前接口可展示历史匹配分变化；其他能力维度有真实数据后再补充。</p>
            </div>
          </div>
          <growth-chart
            v-if="historyLoaded && growthSeries.length"
            :series="growthSeries"
            :height="300"
            :show-legend="false"
          />
          <el-empty v-else-if="historyLoaded" description="暂无真实成长数据" />
          <el-empty v-else-if="!loading" description="历史成长数据暂不可用" />
        </el-card>
      </section>
    </section>

    <section class="record-grid">
      <el-card class="panel record-panel">
        <div class="section-head">
          <div>
            <h3>学习记录</h3>
            <p>记录学习主题、资源、状态与时间。</p>
          </div>
        </div>
        <el-empty description="暂无真实学习行为记录" />
      </el-card>

      <el-card class="panel record-panel">
        <div class="section-head">
          <div>
            <h3>训练记录</h3>
            <p>记录训练类型、评分与核心反馈。</p>
          </div>
        </div>
        <el-empty description="训练历史接口尚未接入" />
      </el-card>

      <el-card class="panel record-panel">
        <div class="section-head">
          <div>
            <h3>成长反馈</h3>
            <p>记录满意度、用户反馈与相关能力。</p>
          </div>
        </div>
        <el-empty description="成长反馈查询接口尚未接入" />
      </el-card>
    </section>

    <el-card class="panel report-panel" v-loading="loading">
      <div class="section-head">
        <div>
          <h3>历史分析</h3>
          <p>继续使用现有历史列表与服务端快照查看能力。</p>
        </div>
      </div>
      <el-empty v-if="!loading && !historyLoaded" description="历史分析数据暂不可用" />
      <el-empty
        v-else-if="historyLoaded && !visibleReports.length"
        description="暂无真实历史记录，先去数据输入中心发起分析"
      />
      <div v-else-if="historyLoaded" class="report-grid">
        <article
          v-for="report in visibleReports"
          :key="report.id"
          class="report-item"
          role="button"
          tabindex="0"
          @click="openReportDetail(report.id)"
          @keyup.enter="openReportDetail(report.id)"
        >
          <h3>岗位: {{ formatReportRole(report.title) }}</h3>
          <p>日期: {{ report.createdAt }}</p>
          <p>匹配分: {{ report.score === null ? '暂无' : `${report.score}%` }}</p>
          <div v-if="report.score !== null" class="score-bar">
            <span :style="{ width: `${report.score}%` }"></span>
          </div>
          <div class="report-item-actions">
            <el-button type="primary" text @click.stop="openReportDetail(report.id)">查看详情</el-button>
          </div>
        </article>
      </div>
    </el-card>

    <el-dialog v-model="detailVisible" title="历史报告详情" width="min(560px, calc(100vw - 32px))">
      <div v-loading="detailLoading" class="detail-body">
        <el-alert
          v-if="detailErrorMessage"
          type="error"
          :title="detailErrorMessage"
          :closable="false"
          show-icon
          class="detail-error"
        />
        <template v-if="activeReport">
          <h4 class="detail-role">岗位: {{ formatReportRole(activeReport.title) }}</h4>
          <p><strong>报告编号:</strong> {{ activeReport.id }}</p>
          <p><strong>生成日期:</strong> {{ activeReport.createdAt }}</p>
          <p><strong>匹配分:</strong> {{ activeReport.score === null ? '暂无' : `${activeReport.score}%` }}</p>
          <div v-if="activeReport.content" class="detail-content">
            <strong>报告内容:</strong>
            <p>{{ activeReport.content }}</p>
          </div>
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
import { useAnalysisStore } from '../../stores/analysis'
import { useHistoryStore } from '../../stores/history'
import { useUserStore } from '../../stores/user'
import GrowthChart from '../../components/business/GrowthChart.vue'
import { fetchHistorySnapshot, fetchUserHistories } from '../../api/modules/career'
import { getUserFacingErrorMessage } from '../../api/request'
import type { ReportSummary } from '../../stores/history'

const userStore = useUserStore()
const historyStore = useHistoryStore()
const analysisStore = useAnalysisStore()

const loading = ref(false)
const errorMessage = ref('')
const historyLoaded = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailErrorMessage = ref('')
const activeReport = ref<ReportSummary | null>(null)

const visibleReports = computed(() => (historyLoaded.value ? historyStore.reports : []))
const latestRecordDate = computed(() => visibleReports.value[0]?.createdAt ?? '暂无')

function formatReportRole(title: string): string {
  return title.replace('匹配报告', '').trim()
}

const currentTargetRole = computed(() => {
  const selectedJob = analysisStore.candidateJobs.find((job) => job.id === analysisStore.jobId)
  if (selectedJob?.name) {
    return selectedJob.name
  }
  if (analysisStore.targetKeyword) {
    return analysisStore.targetKeyword
  }
  const latestTitle = visibleReports.value[0]?.title
  return latestTitle ? formatReportRole(latestTitle) : '暂无'
})

const latestMatchScore = computed(() => {
  const historyScore = visibleReports.value[0]?.score
  if (historyScore !== null && historyScore !== undefined) {
    return `${historyScore}%`
  }
  return analysisStore.hasMatchResult ? `${analysisStore.matchScore}%` : '暂无'
})

const overviewItems = computed(() => [
  { label: '当前目标岗位', value: currentTargetRole.value },
  { label: '最近一次匹配分', value: latestMatchScore.value },
  { label: '历史分析次数', value: historyLoaded.value ? `${visibleReports.value.length} 次` : '暂无' },
  { label: '最近成长记录时间', value: latestRecordDate.value }
])

const normalizeGrowthInput = (
  points: { date: string; value: number; label?: string }[]
): { date: string; value: number; label?: string }[] =>
  points.filter((point) => typeof point.date === 'string' && point.date.trim().length > 0 && Number.isFinite(point.value))

const growthSeries = computed(() =>
  historyStore.growthSeries.length
    ? [{ name: '匹配分', data: historyStore.growthSeries }]
    : []
)

const openReportDetail = async (reportId: string): Promise<void> => {
  detailVisible.value = true
  detailLoading.value = true
  detailErrorMessage.value = ''
  historyStore.setLastViewedReport(reportId)

  const localReport = historyStore.reports.find((report) => report.id === reportId) ?? null
  activeReport.value = localReport

  const historyId = Number(reportId)
  if (!Number.isInteger(historyId) || historyId <= 0) {
    detailErrorMessage.value = '该记录没有可用的服务端历史编号'
    detailLoading.value = false
    return
  }

  try {
    const detail = await fetchHistorySnapshot(historyId)
    activeReport.value = detail
  } catch (error) {
    detailErrorMessage.value = getUserFacingErrorMessage(error, '历史详情加载失败，请稍后重试')
  } finally {
    detailLoading.value = false
  }
}

onMounted(async () => {
  try {
    loading.value = true
    errorMessage.value = ''
    const result = await fetchUserHistories(userStore.profile?.id ?? 'default')
    historyStore.setReports(result.reports)
    historyStore.setGrowthSeries(normalizeGrowthInput(result.growth))
    historyLoaded.value = true
  } catch (error) {
    historyLoaded.value = false
    errorMessage.value = getUserFacingErrorMessage(error, '历史数据加载失败，请稍后重试')
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

.page-head h2 {
  margin: 0 0 8px;
  font-size: 28px;
  color: #1f2b3d;
}

.page-head p,
.section-head p {
  margin: 0;
  color: #667089;
  font-size: 14px;
  line-height: 1.6;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.overview-card :deep(.el-card__body) {
  min-height: 104px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}

.overview-card span {
  color: #6a748c;
  font-size: 13px;
}

.overview-card strong {
  color: #243047;
  font-size: 20px;
  line-height: 1.4;
  overflow-wrap: anywhere;
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

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.section-head h3 {
  margin: 0 0 6px;
  font-size: 22px;
  color: #1f2a3f;
}

.curve-panel {
  height: 100%;
}

.record-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.record-panel :deep(.el-card__body) {
  height: 100%;
}

.record-panel :deep(.el-empty) {
  padding-block: 18px;
}

.report-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.report-item {
  border: 1px solid #dce3ef;
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 0;
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

.detail-content p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.error-alert {
  margin-bottom: 4px;
}

@media (max-width: 1199px) {
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .profile-layout {
    grid-template-columns: 1fr;
  }

  .record-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .profile-page {
    gap: 14px;
  }

  .page-head h2 {
    font-size: 24px;
  }

  .overview-grid,
  .report-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .section-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .profile-card {
    padding: 18px 12px;
  }

  .avatar-ring {
    width: 112px;
    height: 112px;
  }

  .info-row {
    align-items: flex-start;
    flex-direction: column;
    gap: 5px;
  }

  .info-row strong,
  .report-item h3,
  .report-item p,
  .detail-body {
    max-width: 100%;
    overflow-wrap: anywhere;
  }
}
</style>
