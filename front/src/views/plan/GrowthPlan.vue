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
      <p>围绕当前目标岗位与能力差距，整理可执行的学习任务、岗位机会和技术资源。</p>
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
            <p>按优先级安排能力补强、项目实践和可验证交付成果。</p>
          </div>
        </div>
        <el-empty v-if="!learningTasks.length" description="完成岗位匹配后即可生成学习任务">
          <el-button type="primary" plain @click="goToInput">去完成人岗匹配</el-button>
        </el-empty>
        <div v-else class="task-grid">
          <article v-for="task in learningTasks" :key="task.topic" class="content-card task-card">
            <div class="card-head">
              <div>
                <span class="eyebrow">学习主题</span>
                <h4>{{ task.topic }}</h4>
              </div>
              <el-tag effect="plain" :type="task.status === '进行中' ? 'warning' : 'info'">{{ task.status }}</el-tag>
            </div>
            <dl class="detail-list">
              <div>
                <dt>对应能力 Gap</dt>
                <dd>{{ task.gap }}</dd>
              </div>
              <div>
                <dt>学习目标</dt>
                <dd>{{ task.objective }}</dd>
              </div>
              <div>
                <dt>建议动作</dt>
                <dd>{{ task.action }}</dd>
              </div>
              <div>
                <dt>预计投入</dt>
                <dd>{{ task.estimatedEffort }}</dd>
              </div>
            </dl>
          </article>
        </div>
      </el-card>

      <el-card class="panel section-panel" v-loading="resourcesLoading">
        <div class="section-head">
          <div>
            <h3>学习资源</h3>
            <p>优先选择官方文档与可直接落地的工程实践。</p>
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
        <el-empty v-else-if="!resourcesLoading && !resources.length" description="完成能力分析后即可获得学习资源" />
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
                <dd>{{ item.targetAbility || '综合工程能力' }}</dd>
              </div>
              <div>
                <dt>推荐理由</dt>
                <dd>{{ item.reason || '用于补强当前岗位所需的核心工程能力。' }}</dd>
              </div>
            </dl>
            <div class="resource-foot">
              <span>来源：{{ item.source || 'CareerPulse学习资源库' }}</span>
              <el-link
                v-if="safeResourceUrl(item.url)"
                type="primary"
                :href="safeResourceUrl(item.url)"
                target="_blank"
                rel="noopener noreferrer"
              >
                查看资源
              </el-link>
              <span v-else class="link-unavailable">已加入学习计划</span>
            </div>
          </article>
        </div>
      </el-card>
    </section>

    <el-card class="panel section-panel job-resource-panel">
      <div class="section-head">
        <div>
          <h3>岗位资源</h3>
          <p>围绕 AI Agent 开发方向保留主目标与可迁移岗位。</p>
        </div>
      </div>
      <div class="job-resource-grid">
        <article v-for="job in jobResources" :key="job.id" class="content-card job-resource-card">
          <div class="card-head">
            <div>
              <span class="eyebrow">{{ job.company }}</span>
              <h4>{{ job.name }}</h4>
            </div>
            <strong>{{ job.match }}%</strong>
          </div>
          <p>{{ job.description }}</p>
          <div class="job-meta">
            <span>{{ job.salary }}</span>
            <el-tag v-for="skill in job.skills" :key="skill" size="small" effect="plain">{{ skill }}</el-tag>
          </div>
        </article>
      </div>
    </el-card>

    <el-card class="panel report-panel" v-loading="loading">
      <div class="section-head report-head">
        <div>
          <h3>成长报告</h3>
          <p>保留原有报告生成、正文查看、智能润色与导出能力。</p>
        </div>
        <div v-if="!isDemoMode && hasMeaningfulContent(content)" class="actions">
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
import { isDemoMode } from '../../demo/demoMode'
import { DEMO_JOBS } from '../../demo/careerDemoData'

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

interface TaskBlueprint {
  action: string
  status: '进行中' | '待开始'
  estimatedEffort: string
}

interface JobResource {
  id: number
  name: string
  company: string
  salary: string
  match: number
  skills: string[]
  description: string
}

const taskBlueprints: Record<string, TaskBlueprint> = {
  Python: {
    action: '完成 FastAPI 异步接口、分层异常、结构化日志与自动化测试模板。',
    status: '进行中',
    estimatedEffort: '每周 6 小时，连续 4 周'
  },
  LLM应用开发: {
    action: '重构一个 Agent 服务，加入结构化输出、重试、状态追踪和质量评测。',
    status: '待开始',
    estimatedEffort: '每周 5 小时，连续 4 周'
  },
  RAG: {
    action: '构建 30 条质量评测集，记录召回、引用、拒答和失败类型。',
    status: '进行中',
    estimatedEffort: '每周 6 小时，连续 4 周'
  },
  后端开发: {
    action: '补齐鉴权、Redis 缓存、任务状态、接口测试与故障降级。',
    status: '待开始',
    estimatedEffort: '每周 5 小时，连续 3 周'
  },
  'Docker/K8s': {
    action: '完成 Dockerfile、健康检查、环境配置、日志采集和部署说明。',
    status: '待开始',
    estimatedEffort: '每周 4 小时，连续 2 周'
  },
  MCP: {
    action: '独立实现一个带参数校验、调用日志、失败测试和降级返回的 MCP 工具。',
    status: '待开始',
    estimatedEffort: '每周 4 小时，连续 2 周'
  }
}

const currentTargetRole = computed(() => {
  const selectedJob = analysisStore.candidateJobs.find((job) => job.id === analysisStore.jobId)
  return selectedJob?.name || analysisStore.targetKeyword || 'AI Agent开发工程师'
})

const primaryGap = computed(() => analysisStore.gapDetails[0]?.name || analysisStore.gaps[0] || 'Python工程化')
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
    .map((item) => {
      const blueprint = taskBlueprints[item.name] ?? {
        action: `围绕「${item.name}」完成一个可运行项目，并整理测试记录与技术复盘。`,
        status: '待开始' as const,
        estimatedEffort: '每周 4 小时，连续 2 周'
      }
      return {
        topic: item.name,
        gap: item.name,
        objective: item.suggestion ?? `补齐「${item.name}」的工程实践与可验证成果。`,
        action: blueprint.action,
        status: blueprint.status,
        estimatedEffort: blueprint.estimatedEffort
      }
    })
})

const overviewItems = computed(() => [
  { label: '当前目标岗位', value: currentTargetRole.value },
  { label: '当前主要 Skill Gap', value: primaryGap.value },
  { label: '当前学习阶段', value: '阶段一 · 工程化补强' },
  { label: '已完成任务数量', value: '2 项' }
])

const jobResources = computed<JobResource[]>(() => {
  if (isDemoMode) {
    return DEMO_JOBS.slice(0, 4).map((job) => ({
      id: job.job_id,
      name: job.job_name,
      company: job.company_name,
      salary: job.salary_range,
      match: job.match_score,
      skills: job.required_skills.slice(0, 3),
      description: job.job_description
    }))
  }

  return analysisStore.candidateJobs.slice(0, 4).map((job) => ({
    id: job.id,
    name: job.name,
    company: job.company || '目标企业',
    salary: job.salaryRange || '薪资面议',
    match: job.match,
    skills: job.requiredSkills.slice(0, 3),
    description: job.description || '与当前能力结构相关的岗位机会。'
  }))
})

const resourceTypeLabels: Record<string, string> = {
  course: '课程',
  practice: '实践',
  certificate: '证书',
  article: '文章',
  book: '书籍',
  video: '视频'
}

const formatResourceType = (type: string): string =>
  resourceTypeLabels[type.trim().toLowerCase()] || type.trim() || '综合资源'

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
    ElMessage.warning('请先填写需要检查的内容')
    return
  }

  checkTips.value = []
  ElMessage.info('内容检查能力正在准备中')
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
      : '报告正在整理中，请稍后刷新'
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
      emptyMessage.value = '报告正在整理中，请稍后刷新'
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
.resource-grid,
.job-resource-grid {
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
  color: #4f6b8a;
  font-weight: 600;
}

.resource-alert {
  margin-bottom: 12px;
}

.job-resource-card .card-head strong {
  color: #4f46e5;
  font-size: 18px;
}

.job-resource-card > p {
  margin: 12px 0;
  color: #5d6780;
  font-size: 14px;
  line-height: 1.65;
}

.job-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
}

.job-meta > span {
  margin-right: 3px;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
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
  .resource-grid,
  .job-resource-grid {
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
