<template>
  <div class="job-library-page">
    <section class="page-head">
      <h2>岗位库查询</h2>
      <p>可按方向查询岗位和岗位要求；如果你还没明确方向，也可以先浏览热门岗位。</p>
    </section>

    <el-card class="panel query-panel">
      <div class="query-row">
        <el-input
          v-model="keyword"
          clearable
          placeholder="输入岗位方向，如：前端开发、测试工程师、产品经理"
          @keyup.enter="searchByKeyword"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" :loading="loading" @click="searchByKeyword">查询岗位</el-button>
        <el-button plain :loading="loading" @click="exploreWithoutDirection">先浏览热门岗位</el-button>
      </div>

      <div class="quick-tags">
        <span>快捷方向：</span>
        <el-tag
          v-for="tag in quickDirections"
          :key="tag"
          class="quick-tag"
          effect="plain"
          @click="applyDirection(tag)"
        >
          {{ tag }}
        </el-tag>
      </div>
    </el-card>

    <el-card class="panel list-panel" v-loading="loading">
      <div class="panel-head">
        <h3>岗位列表</h3>
      </div>

      <el-empty v-if="!jobs.length" description="暂无岗位数据，请先查询或浏览热门岗位" />

      <div v-else class="job-grid">
        <article v-for="job in jobs" :key="job.id" class="job-card">
          <div class="job-head">
            <div>
              <h4>{{ job.name }}</h4>
              <p>{{ job.company || '企业信息待补全' }} · {{ job.industry || '行业未知' }}</p>
            </div>
            <el-tag>{{ Math.round(job.match) }}%</el-tag>
          </div>

          <el-progress :percentage="Math.round(job.match)" :stroke-width="10" />

          <p class="desc">{{ job.description || '暂无岗位描述' }}</p>
          <p class="meta">薪资：{{ job.salaryRange || '待补全' }}</p>

          <div class="section">
            <span class="label">岗位要求</span>
            <div class="tag-row">
              <el-tag v-for="skill in job.requiredSkills.slice(0, 6)" :key="skill" effect="plain">{{ skill }}</el-tag>
            </div>
          </div>

          <div class="actions">
            <el-button size="small" type="primary" plain @click="pickDirection(job)">选这个方向</el-button>
            <el-button size="small" @click="goInputWithTarget(job)">去输入中心分析</el-button>
          </div>
        </article>
      </div>
    </el-card>

    <ai-assistant-drawer v-model="assistantOpen" title="AI 助手小吾" subtitle="告诉我你的疑问">
      <div class="assistant-content">
        <section class="assistant-messages">
          <p class="assistant-tip">你可以直接问：</p>
          <div class="qa-tags">
            <el-tag v-for="q in quickQuestions" :key="q" class="qa-tag" effect="plain" @click="askPreset(q)">
              {{ q }}
            </el-tag>
          </div>

          <div class="msg-row is-ai">
            <div class="msg-bubble">你好！我是 AI 助手小吾，可以帮你分析岗位方向和投递建议。</div>
          </div>

          <div v-if="lastQuestion" class="msg-row is-user">
            <div class="msg-bubble">{{ lastQuestion }}</div>
          </div>

          <div v-if="assistantAnswer" class="msg-row is-ai">
            <div class="msg-bubble">{{ assistantAnswer }}</div>
          </div>
        </section>

        <footer class="assistant-input-bar">
          <el-input
            v-model="assistantInput"
            type="textarea"
            :rows="2"
            resize="none"
            placeholder="请在此处输入你的问题"
            @keyup.enter.exact.prevent="submitAssistantQuestion"
          />
          <div class="assistant-actions">
            <el-button type="primary" :disabled="!assistantInput.trim()" @click="submitAssistantQuestion">发送</el-button>
          </div>
        </footer>
      </div>
    </ai-assistant-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchJobs, type JobItem } from '../../api/modules/career'
import { useAnalysisStore } from '../../stores/analysis'
import { pickDiverseTopJobs } from '../../utils/jobDiversity'
import AiAssistantDrawer from '../../components/business/AiAssistantDrawer.vue'

const router = useRouter()
const route = useRoute()
const analysisStore = useAnalysisStore()

const loading = ref(false)
const keyword = ref('')
const jobs = ref<JobItem[]>([])

const assistantOpen = ref(false)
const assistantInput = ref('')
const lastQuestion = ref('')
const assistantAnswer = ref('')

const quickQuestions = [
  '我没方向，先从哪些岗位开始看？',
  '前端和测试哪个更适合应届生？',
  '产品经理岗位一般看重哪些能力？'
]

const quickDirections = ['前端开发', '后端开发', '测试工程师', '产品经理', '数据分析', '运维工程师']

const fallbackJobs: JobItem[] = [
  {
    id: 91001,
    name: '后端开发工程师',
    match: 83,
    company: '演示企业 A',
    industry: '互联网',
    salaryRange: '14k-24k',
    requiredSkills: ['Java', 'Spring Boot', 'MySQL', 'Redis'],
    requiredCerts: [],
    softSkills: ['沟通协作'],
    abilityDimensions: { innovation: 76, learning: 80, stressTolerance: 74, communication: 72, internship: 70 },
    highlights: ['服务治理'],
    description: '负责核心服务开发与稳定性优化'
  },
  {
    id: 91002,
    name: '数据分析师',
    match: 79,
    company: '演示企业 B',
    industry: '零售电商',
    salaryRange: '11k-20k',
    requiredSkills: ['SQL', 'Python', '可视化报表'],
    requiredCerts: [],
    softSkills: ['业务理解'],
    abilityDimensions: { innovation: 74, learning: 81, stressTolerance: 69, communication: 75, internship: 72 },
    highlights: ['数据洞察'],
    description: '负责业务数据分析与策略建议输出'
  },
  {
    id: 91003,
    name: '测试开发工程师',
    match: 77,
    company: '演示企业 C',
    industry: '企业服务',
    salaryRange: '10k-18k',
    requiredSkills: ['自动化测试', '接口测试', 'CI/CD'],
    requiredCerts: [],
    softSkills: ['质量意识'],
    abilityDimensions: { innovation: 70, learning: 76, stressTolerance: 82, communication: 70, internship: 73 },
    highlights: ['测试体系'],
    description: '负责自动化测试体系建设与质量保障'
  }
]

const mergeUniqueById = (input: JobItem[]): JobItem[] => {
  const map = new Map<number, JobItem>()
  input.forEach((job) => {
    if (!map.has(job.id) || (map.get(job.id)?.match ?? 0) < job.match) {
      map.set(job.id, job)
    }
  })
  return Array.from(map.values()).sort((a, b) => b.match - a.match)
}

const searchByKeyword = async (): Promise<void> => {
  const nextKeyword = keyword.value.trim()
  if (!nextKeyword) {
    ElMessage.warning('请输入岗位方向，或点击“先浏览热门岗位”')
    return
  }

  try {
    loading.value = true
    const result = await pickDiverseTopJobs(nextKeyword, fetchJobs, 24)
    jobs.value = result.length ? result : fallbackJobs
    analysisStore.setTargetKeyword(nextKeyword)
    analysisStore.setCandidateJobs(jobs.value.slice(0, 12))
    if (!result.length) {
      ElMessage.warning('查询结果为空，已展示演示岗位')
    }
  } catch {
    jobs.value = fallbackJobs
    ElMessage.warning('查询失败，已展示演示岗位')
  } finally {
    loading.value = false
  }
}

const exploreWithoutDirection = async (): Promise<void> => {
  try {
    loading.value = true
    const tasks = quickDirections.map((direction) => pickDiverseTopJobs(direction, fetchJobs, 8))
    const groups = await Promise.all(tasks)
    const merged = mergeUniqueById(groups.flat())
    jobs.value = merged.length ? merged.slice(0, 30) : fallbackJobs
    keyword.value = ''
    if (!merged.length) {
      ElMessage.warning('暂无热门岗位数据，已展示演示岗位')
    }
  } catch {
    jobs.value = fallbackJobs
    ElMessage.warning('浏览失败，已展示演示岗位')
  } finally {
    loading.value = false
  }
}

const applyDirection = async (direction: string): Promise<void> => {
  keyword.value = direction
  await searchByKeyword()
}

const pickDirection = (job: JobItem): void => {
  keyword.value = job.name
  analysisStore.setTargetKeyword(job.name)
  ElMessage.success(`已选择方向：${job.name}`)
}

const askPreset = (question: string): void => {
  assistantInput.value = question
}

const submitAssistantQuestion = (): void => {
  const question = assistantInput.value.trim()
  if (!question) {
    return
  }

  const answerByRule = (): string => {
    if (/没方向|不知道做什么|先看/.test(question)) {
      return '建议先从“前端开发、测试工程师、产品经理”三类岗位入手：这三类岗位需求稳定、学习资源丰富，便于你快速建立比较基准。'
    }
    if (/前端|测试/.test(question)) {
      return '如果你更喜欢做界面与交互、能持续打磨体验，优先前端；如果你更偏向质量保障、流程规范和自动化思维，优先测试。你也可以先在岗位库对比两类岗位要求。'
    }
    if (/产品/.test(question)) {
      return '产品经理常见关注点：需求分析、业务理解、沟通协同、数据分析与方案落地。建议你在岗位列表里重点看“岗位要求”标签并逐项补齐。'
    }
    return '可以先在岗位库用 2-3 个关键词查询，再按匹配度前 5 的岗位对比岗位要求，最后回到数据输入中心开始分析。'
  }

  lastQuestion.value = question
  assistantAnswer.value = answerByRule()
  assistantInput.value = ''
}

const goInputWithTarget = async (job: JobItem): Promise<void> => {
  analysisStore.setTargetKeyword(job.name)
  await router.push({ path: '/app/input', query: { target: job.name } })
}

onMounted(async () => {
  const mode = typeof route.query.mode === 'string' ? route.query.mode : ''
  const target = typeof route.query.target === 'string' ? route.query.target : ''
  keyword.value = target || analysisStore.targetKeyword || ''

  if (mode === 'explore' || !keyword.value) {
    await exploreWithoutDirection()
    return
  }
  await searchByKeyword()
})
</script>

<style scoped>
.job-library-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-head h2 {
  margin: 0 0 8px;
}

.page-head p {
  margin: 0;
  color: #667089;
}

.panel {
  border-radius: 16px;
  border: 1px solid #e2e8f1;
}

.query-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 110px 150px;
  gap: 10px;
}

.quick-tags {
  margin-top: 12px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: #6a738b;
  font-size: 13px;
}

.quick-tag {
  cursor: pointer;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.panel-head h3 {
  margin: 0;
}

.job-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.job-card {
  border: 1px solid #dde4ef;
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.job-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.job-head h4 {
  margin: 0;
}

.job-head p {
  margin: 6px 0 0;
  font-size: 13px;
  color: #6a748c;
}

.desc {
  margin: 0;
  font-size: 13px;
  color: #5d6780;
  line-height: 1.5;
}

.meta {
  margin: 0;
  font-size: 13px;
  color: #5d6780;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.label {
  font-size: 13px;
  color: #4a5571;
  font-weight: 600;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.actions {
  display: flex;
  gap: 8px;
}

.assistant-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f6f8fc;
}

.assistant-messages {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.assistant-tip {
  margin: 0;
  color: #4b5672;
  font-size: 13px;
}

.qa-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.qa-tag {
  cursor: pointer;
}

.msg-row {
  display: flex;
}

.msg-row.is-user {
  justify-content: flex-end;
}

.msg-bubble {
  max-width: 88%;
  padding: 10px 12px;
  border-radius: 12px;
  line-height: 1.6;
  font-size: 14px;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-row.is-ai .msg-bubble {
  color: #26324d;
  background: #fff;
  border: 1px solid #e4e9f3;
}

.msg-row.is-user .msg-bubble {
  color: #fff;
  background: #3b6ef5;
}

.assistant-input-bar {
  border-top: 1px solid #dbe4f1;
  background: #f8fbff;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.assistant-actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 980px) {
  .query-row {
    grid-template-columns: 1fr;
  }

  .panel-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
