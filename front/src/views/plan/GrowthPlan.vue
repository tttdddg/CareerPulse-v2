<template>
  <div class="growth-plan">
    <el-alert
      v-if="errorMessage"
      type="error"
      :title="errorMessage"
      show-icon
      class="error-alert"
      @close="errorMessage = ''"
    />

    <section class="page-head">
      <h2>成长计划 / 学习资源</h2>
      <p>围绕当前目标岗位与能力差距，整理可执行的学习任务和真实资源。</p>
    </section>

    <section class="overview-grid" aria-label="成长计划概览">
      <el-card v-for="item in overviewItems" :key="item.label" class="panel overview-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </el-card>
    </section>

    <section class="plan-layout">
      <el-card class="panel section-panel task-panel">
        <div class="section-head">
          <div>
            <h3>学习任务</h3>
            <p>任务仅根据当前真实能力差距整理，未返回的进度与投入信息保持为空。</p>
          </div>
        </div>
        <el-empty v-if="!learningTasks.length" description="暂无真实能力差距，暂不能生成学习任务">
          <el-button type="primary" plain @click="goToInput">去完成人岗匹配</el-button>
        </el-empty>
        <div v-else class="task-grid">
          <article v-for="task in learningTasks" :key="task.topic" class="content-card task-card">
            <div class="card-head">
              <div>
                <span class="eyebrow">学习主题</span>
                <h4>{{ task.topic }}</h4>
              </div>
              <el-tag effect="plain" type="info">{{ task.status || '暂无状态' }}</el-tag>
            </div>
            <dl class="detail-list">
              <div>
                <dt>对应能力 Gap</dt>
                <dd>{{ task.gap }}</dd>
              </div>
              <div>
                <dt>学习目标</dt>
                <dd>{{ task.objective || '暂无具体目标' }}</dd>
              </div>
              <div>
                <dt>建议动作</dt>
                <dd>{{ task.action || '暂无具体动作' }}</dd>
              </div>
              <div>
                <dt>预计投入</dt>
                <dd>{{ task.estimatedEffort || '暂无' }}</dd>
              </div>
            </dl>
          </article>
        </div>
      </el-card>

      <el-card class="panel section-panel" v-loading="resourcesLoading">
        <div class="section-head">
          <div>
            <h3>学习资源</h3>
            <p>来自现有推荐接口的真实返回结果。</p>
          </div>
        </div>
        <el-alert
          v-if="resourceErrorMessage"
          type="error"
          :title="resourceErrorMessage"
          :closable="false"
          show-icon
          class="resource-alert"
        />
        <el-empty v-else-if="!resourcesLoading && !resources.length" description="暂无真实学习资源" />
        <div v-else class="resource-grid">
          <article
            v-for="item in resources"
            :key="`${item.title}-${item.url || ''}`"
            class="content-card resource-card"
          >
            <div class="card-head">
              <h4>{{ item.title }}</h4>
              <el-tag size="small" effect="plain">{{ formatResourceType(item.type) }}</el-tag>
            </div>
            <dl class="detail-list resource-details">
              <div>
                <dt>对应能力</dt>
                <dd>{{ item.targetAbility || '暂无' }}</dd>
              </div>
              <div>
                <dt>推荐理由</dt>
                <dd>{{ item.reason || '后端未提供推荐理由' }}</dd>
              </div>
            </dl>
            <div class="resource-foot">
              <span>来源：{{ item.source || '未提供' }}</span>
              <el-link
                v-if="safeResourceUrl(item.url)"
                type="primary"
                :href="safeResourceUrl(item.url)"
                target="_blank"
                rel="noopener noreferrer"
              >
                查看资源
              </el-link>
              <span v-else class="link-unavailable">暂无链接</span>
            </div>
          </article>
        </div>
      </el-card>
    </section>

    <el-card class="panel section-panel job-resource-panel">
      <div class="section-head">
        <div>
          <h3>岗位资源</h3>
          <p>岗位推荐接口接入后将在这里展示。</p>
        </div>
      </div>
      <el-empty description="当前接口暂无岗位资源数据" />
    </el-card>

    <el-card class="panel report-panel" v-loading="loading">
      <div class="section-head report-head">
        <div>
          <h3>成长报告</h3>
          <p>保留原有报告生成、正文查看、智能润色与导出能力。</p>
        </div>
        <div v-if="hasMeaningfulContent(content)" class="actions">
          <export-button :loading="exporting" type="word" label="导出PDF/Word" @export="handleExport" />
        </div>
      </div>

      <rich-text-editor
        v-if="hasMeaningfulContent(content)"
        v-model="content"
        @polish="handlePolish"
        @check="handleCheck"
      />
      <el-empty v-else-if="!loading" :description="emptyMessage">
        <el-button v-if="canGenerateReport" type="primary" :loading="generating" @click="handleGenerateReport">
          生成成长报告
        </el-button>
        <el-button v-else type="primary" plain @click="goToInput">去完成画像与匹配</el-button>
      </el-empty>
    </el-card>

    <el-alert v-if="checkTips.length" type="warning" show-icon class="tips" title="内容检查建议">
      <ul>
        <li v-for="tip in checkTips" :key="tip">{{ tip }}</li>
      </ul>
    </el-alert>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAnalysisStore } from '../../stores/analysis'
import { useUserStore } from '../../stores/user'
import RichTextEditor from '../../components/business/RichTextEditor.vue'
import ExportButton from '../../components/business/ExportButton.vue'
import {
  exportReport,
  fetchRecommendations,
  fetchReport,
  generateReport,
  polishReport,
  type LearningResource,
  type MatchingGap
} from '../../api/modules/career'
import { getUserFacingErrorMessage } from '../../api/request'

const router = useRouter()
const analysisStore = useAnalysisStore()
const userStore = useUserStore()
const loading = ref(false)
const generating = ref(false)
const exporting = ref(false)
const resourcesLoading = ref(false)
const errorMessage = ref('')
const resourceErrorMessage = ref('')
const content = ref('')
const emptyMessage = ref('请先完成学生画像与人岗匹配，再生成成长计划')
const checkTips = ref<string[]>([])
const reportId = ref<number | null>(null)

interface LearningTask {
  topic: string
  gap: string
  objective: string
  action: string
  status: string
  estimatedEffort: string
}

const resources = ref<LearningResource[]>([])

const currentTargetRole = computed(() => {
  const selectedJob = analysisStore.candidateJobs.find((job) => job.id === analysisStore.jobId)
  return selectedJob?.name || analysisStore.targetKeyword || '暂无'
})

const primaryGap = computed(() => analysisStore.gapDetails[0]?.name || analysisStore.gaps[0] || '暂无')
const canGenerateReport = computed(() => analysisStore.studentId !== null && analysisStore.jobId !== null)

const learningTasks = computed<LearningTask[]>(() => {
  const details: MatchingGap[] = analysisStore.gapDetails.length
    ? analysisStore.gapDetails
    : analysisStore.gaps.map((name) => ({ name }))
  const seen = new Set<string>()

  return details
    .filter((item) => {
      const name = item.name.trim()
      if (!name || seen.has(name)) {
        return false
      }
      seen.add(name)
      return true
    })
    .map((item) => ({
      topic: item.name,
      gap: item.name,
      objective: item.suggestion ?? '',
      action: '',
      status: item.status ?? '',
      estimatedEffort: ''
    }))
})

const overviewItems = computed(() => [
  { label: '当前目标岗位', value: currentTargetRole.value },
  { label: '当前主要 Skill Gap', value: primaryGap.value },
  { label: '当前学习阶段', value: '暂无' },
  { label: '已完成任务数量', value: '暂无' }
])

const resourceTypeLabels: Record<string, string> = {
  course: '课程',
  practice: '实践',
  certificate: '证书',
  article: '文章',
  book: '书籍',
  video: '视频'
}

const formatResourceType = (type: string): string =>
  resourceTypeLabels[type.trim().toLowerCase()] || type.trim() || '类型未提供'

const safeResourceUrl = (url?: string): string => {
  if (!url) {
    return ''
  }
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.toString() : ''
  } catch {
    return ''
  }
}

const hasMeaningfulContent = (value: string): boolean => {
  const plainText = value
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/\s+/g, '')
  return plainText.length > 0
}

const downloadBlob = (blob: Blob, fileName: string): void => {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  anchor.click()
  URL.revokeObjectURL(url)
}

const handlePolish = async (value: string): Promise<void> => {
  if (!hasMeaningfulContent(value)) {
    ElMessage.warning('请先填写成长计划内容再润色')
    return
  }

  if (!reportId.value) {
    errorMessage.value = '缺少报告编号，请先生成报告后再润色'
    return
  }

  try {
    exporting.value = true
    content.value = await polishReport(reportId.value, { text: value, paragraphIndex: 0 })
    ElMessage.success('内容已润色')
  } catch (error) {
    errorMessage.value = getUserFacingErrorMessage(error, '内容润色失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

const handleCheck = async (): Promise<void> => {
  if (!hasMeaningfulContent(content.value)) {
    ElMessage.warning('暂无可检查内容')
    return
  }

  checkTips.value = []
  ElMessage.info('当前后端尚未提供报告内容检查能力')
}

const handleExport = async (payload: { type: 'pdf' | 'word'; fileName: string }): Promise<void> => {
  try {
    exporting.value = true
    if (!reportId.value) {
      reportId.value = await resolveReportId()
    }
    if (!reportId.value) {
      throw new Error('缺少报告编号，请先生成报告后再导出')
    }

    const blob = await exportReport(reportId.value, payload.type)
    downloadBlob(blob, payload.fileName)
  } catch (error) {
    errorMessage.value = getUserFacingErrorMessage(error, '报告导出失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

const resolveReportId = async (): Promise<number | null> => {
  if (analysisStore.reportId) {
    return analysisStore.reportId
  }

  if (!analysisStore.studentId || !analysisStore.jobId) {
    return null
  }

  const generated = await generateReport({
    studentId: analysisStore.studentId,
    jobId: analysisStore.jobId,
    userId: userStore.profile?.id ?? 'default'
  })

  if (!generated.reportId) {
    return null
  }

  analysisStore.setContext({ reportId: generated.reportId })

  if (generated.content) {
    content.value = generated.content
  }

  return generated.reportId
}

const sleep = (ms: number): Promise<void> => new Promise((resolve) => window.setTimeout(resolve, ms))

const fetchReportWithRetry = async (id: number): Promise<string> => {
  for (let i = 0; i < 3; i += 1) {
    try {
      const result = await fetchReport(id)
      if (result.content.trim()) {
        return result.content
      }
    } catch (error) {
      const status = (error as { status?: number })?.status
      // 报告不存在时结束读取，由页面展示明确空状态，避免伪造默认报告。
      if (status === 404 || status === 405) {
        return ''
      }
      throw error
    }
    if (i < 2) {
      await sleep(800)
    }
  }
  return ''
}

const loadResources = async (): Promise<void> => {
  try {
    resourcesLoading.value = true
    resourceErrorMessage.value = ''
    resources.value = (await fetchRecommendations(analysisStore.gaps[0] ?? '')).slice(0, 10)
  } catch (error) {
    resources.value = []
    resourceErrorMessage.value = getUserFacingErrorMessage(error, '学习资源加载失败，请稍后重试')
  } finally {
    resourcesLoading.value = false
  }
}

const goToInput = async (): Promise<void> => {
  await router.push('/app/input')
}

const handleGenerateReport = async (): Promise<void> => {
  if (!analysisStore.studentId || !analysisStore.jobId) {
    errorMessage.value = '请先完成学生画像与人岗匹配'
    return
  }

  try {
    generating.value = true
    errorMessage.value = ''
    const generated = await generateReport({
      studentId: analysisStore.studentId,
      jobId: analysisStore.jobId,
      userId: userStore.profile?.id ?? 'default'
    })
    if (!generated.reportId) {
      throw new Error('报告生成接口未返回报告编号')
    }

    reportId.value = generated.reportId
    analysisStore.setContext({ reportId: generated.reportId })
    content.value = generated.content || (await fetchReportWithRetry(generated.reportId))
    emptyMessage.value = hasMeaningfulContent(content.value)
      ? ''
      : '报告已生成，但后端暂未返回可展示内容'
    ElMessage.success('成长报告已生成')
  } catch (error) {
    content.value = ''
    errorMessage.value = getUserFacingErrorMessage(error, '成长报告生成失败，请稍后重试')
  } finally {
    generating.value = false
  }
}

const loadReport = async (): Promise<void> => {
  try {
    loading.value = true
    reportId.value = await resolveReportId()
    if (!reportId.value) {
      content.value = ''
      emptyMessage.value = '请先完成学生画像与人岗匹配，再生成成长计划'
      return
    }

    if (!hasMeaningfulContent(content.value)) {
      content.value = await fetchReportWithRetry(reportId.value)
    }

    if (!hasMeaningfulContent(content.value)) {
      content.value = ''
      emptyMessage.value = '报告已生成，但后端暂未返回可展示内容'
    }
  } catch (error) {
    content.value = ''
    errorMessage.value = getUserFacingErrorMessage(error, '成长计划加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadReport(), loadResources()])
})
</script>

<style scoped>
.growth-plan {
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

.plan-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}

.panel {
  border-radius: 16px;
  border: 1px solid #e2e7f1;
  background: #ffffff;
}

.section-head,
.card-head,
.report-head,
.resource-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-head {
  margin-bottom: 14px;
}

.section-head h3 {
  margin: 0 0 6px;
  font-size: 22px;
  color: #1f2a3f;
}

.task-grid,
.resource-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.content-card {
  min-width: 0;
  border: 1px solid #dde4ef;
  border-radius: 12px;
  padding: 14px;
  background: #ffffff;
}

.card-head {
  align-items: flex-start;
}

.card-head h4 {
  min-width: 0;
  margin: 0;
  color: #2a344c;
  font-size: 16px;
  overflow-wrap: anywhere;
}

.eyebrow {
  display: block;
  margin-bottom: 5px;
  color: #758099;
  font-size: 12px;
}

.detail-list {
  margin: 14px 0 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-list div {
  display: grid;
  grid-template-columns: 108px minmax(0, 1fr);
  gap: 10px;
}

.detail-list dt {
  color: #6a748c;
  font-size: 13px;
}

.detail-list dd {
  margin: 0;
  color: #364057;
  font-size: 14px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.resource-details div {
  grid-template-columns: 76px minmax(0, 1fr);
}

.resource-foot {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #edf0f5;
  color: #758099;
  font-size: 13px;
}

.link-unavailable {
  color: #9098a9;
}

.resource-alert {
  margin-bottom: 12px;
}

.job-resource-panel :deep(.el-empty) {
  padding-block: 20px;
}

.report-panel {
  min-width: 0;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tips ul {
  margin: 8px 0 0;
  padding-left: 18px;
}

@media (max-width: 1199px) {
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .plan-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .growth-plan {
    gap: 14px;
  }

  .page-head h2 {
    font-size: 24px;
  }

  .overview-grid {
    grid-template-columns: 1fr;
  }

  .section-head,
  .report-head,
  .resource-foot {
    align-items: flex-start;
    flex-direction: column;
  }

  .task-grid,
  .resource-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .detail-list div,
  .resource-details div {
    grid-template-columns: 1fr;
    gap: 4px;
  }

  .card-head {
    flex-wrap: wrap;
  }

  .resource-foot {
    width: 100%;
    overflow-wrap: anywhere;
  }

  .actions,
  .actions :deep(.el-button) {
    width: 100%;
  }
}
</style>
