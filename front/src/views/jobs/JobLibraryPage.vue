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

      <el-alert
        v-if="!loading && errorMessage"
        type="error"
        :title="errorMessage"
        :closable="false"
        show-icon
        class="result-state"
      >
        <el-button type="primary" link @click="retryLastRequest">重试</el-button>
      </el-alert>

      <el-empty v-else-if="!loading && !jobs.length" description="当前条件未匹配到岗位">
        <el-button type="primary" plain @click="retryLastRequest">重新查询</el-button>
      </el-empty>

      <div v-else class="job-grid">
        <article v-for="job in jobs" :key="job.id" class="job-card">
          <div class="job-head">
            <div>
              <h4>{{ job.name }}</h4>
              <p>{{ job.company || '企业信息待补全' }} · {{ job.industry || '行业未知' }}</p>
            </div>
            <el-tag>相关度 {{ Math.round(job.match) }}%</el-tag>
          </div>

          <el-progress :percentage="Math.round(job.match)" :stroke-width="10" />

          <p class="desc">{{ job.description || '该岗位重视工程实践、协作能力与可验证项目成果。' }}</p>
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

    <ai-assistant-drawer v-model="assistantOpen" title="AI 职业伙伴" subtitle="Agent 岗位规划与项目建议">
      <div v-if="isDemoMode" class="assistant-content">
        <section class="assistant-context" aria-label="当前分析上下文">
          <div class="context-icon">AI</div>
          <div>
            <strong>已读取当前职业画像</strong>
            <p>目标：AI Agent开发工程师 · 匹配度 82%</p>
          </div>
          <span class="context-status">分析完成</span>
        </section>

        <section ref="assistantThread" class="assistant-thread" aria-live="polite">
          <article
            v-for="message in assistantMessages"
            :key="message.id"
            class="assistant-message"
            :class="`is-${message.role}`"
          >
            <div class="message-avatar">{{ message.role === 'assistant' ? 'AI' : '你' }}</div>
            <p>{{ message.content }}</p>
          </article>

          <article v-if="assistantThinking" class="assistant-message is-assistant">
            <div class="message-avatar">AI</div>
            <div class="typing-indicator" aria-label="正在整理建议">
              <i></i><i></i><i></i>
            </div>
          </article>
        </section>

        <footer class="assistant-composer">
          <div class="quick-questions" aria-label="快捷问题">
            <button
              v-for="question in ASSISTANT_QUICK_QUESTIONS"
              :key="question"
              type="button"
              :disabled="assistantThinking"
              @click="askAssistant(question)"
            >
              {{ question }}
            </button>
          </div>
          <div class="composer-row">
            <el-input
              v-model="assistantInput"
              maxlength="120"
              placeholder="问问岗位选择、项目优化或面试准备"
              @keyup.enter="askAssistant()"
            />
            <el-button
              type="primary"
              :loading="assistantThinking"
              :disabled="!assistantInput.trim()"
              @click="askAssistant()"
            >
              发送
            </el-button>
          </div>
          <p class="composer-hint">建议已结合当前岗位画像、能力差距与项目经历整理</p>
        </footer>
      </div>
      <div v-else class="assistant-content assistant-unavailable">
        <p>可围绕岗位要求、能力差距与项目证据整理下一步行动建议。</p>
      </div>
    </ai-assistant-drawer>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchJobs, type JobItem } from '../../api/modules/career'
import { useAnalysisStore } from '../../stores/analysis'
import { pickDiverseTopJobs } from '../../utils/jobDiversity'
import AiAssistantDrawer from '../../components/business/AiAssistantDrawer.vue'
import { getUserFacingErrorMessage } from '../../api/request'
import { isDemoMode, waitForDemoResponse } from '../../demo/demoMode'
import {
  ASSISTANT_QUICK_QUESTIONS,
  ASSISTANT_WELCOME_MESSAGE,
  getAssistantPresetResponse
} from '../../demo/assistantDemo'

interface AssistantMessage {
  id: number
  role: 'assistant' | 'user'
  content: string
}

const router = useRouter()
const route = useRoute()
const analysisStore = useAnalysisStore()

const loading = ref(false)
const keyword = ref('')
const jobs = ref<JobItem[]>([])
const errorMessage = ref('')
const lastRequestMode = ref<'search' | 'explore'>('explore')

const assistantOpen = ref(false)
const assistantInput = ref('')
const assistantThinking = ref(false)
const assistantThread = ref<HTMLElement | null>(null)
const assistantMessages = ref<AssistantMessage[]>([
  { id: 1, role: 'assistant', content: ASSISTANT_WELCOME_MESSAGE }
])
let assistantMessageId = 1

const quickDirections = ['前端开发', '后端开发', '测试工程师', '产品经理', '数据分析', '运维工程师']

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
    errorMessage.value = ''
    lastRequestMode.value = 'search'
    const result = await pickDiverseTopJobs(nextKeyword, fetchJobs, 24)
    jobs.value = result
    analysisStore.setTargetKeyword(nextKeyword)
    analysisStore.setCandidateJobs(jobs.value.slice(0, 12))
  } catch (error) {
    jobs.value = []
    errorMessage.value = getUserFacingErrorMessage(error, '岗位查询失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

const exploreWithoutDirection = async (): Promise<void> => {
  try {
    loading.value = true
    errorMessage.value = ''
    lastRequestMode.value = 'explore'
    const tasks = quickDirections.map((direction) => pickDiverseTopJobs(direction, fetchJobs, 8))
    const groups = await Promise.all(tasks)
    const merged = mergeUniqueById(groups.flat())
    jobs.value = merged.slice(0, 30)
    keyword.value = ''
  } catch (error) {
    jobs.value = []
    errorMessage.value = getUserFacingErrorMessage(error, '岗位数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

const retryLastRequest = async (): Promise<void> => {
  if (lastRequestMode.value === 'search' && keyword.value.trim()) {
    await searchByKeyword()
    return
  }
  await exploreWithoutDirection()
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

const goInputWithTarget = async (job: JobItem): Promise<void> => {
  analysisStore.setTargetKeyword(job.name)
  await router.push({ path: '/app/input', query: { target: job.name } })
}

const scrollAssistantToBottom = async (): Promise<void> => {
  await nextTick()
  if (assistantThread.value) {
    assistantThread.value.scrollTop = assistantThread.value.scrollHeight
  }
}

const askAssistant = async (presetQuestion?: string): Promise<void> => {
  const question = (presetQuestion ?? assistantInput.value).trim()
  if (!question || assistantThinking.value) {
    return
  }

  assistantMessageId += 1
  assistantMessages.value.push({ id: assistantMessageId, role: 'user', content: question })
  assistantInput.value = ''
  assistantThinking.value = true
  await scrollAssistantToBottom()

  await waitForDemoResponse(720)
  assistantMessageId += 1
  assistantMessages.value.push({
    id: assistantMessageId,
    role: 'assistant',
    content: getAssistantPresetResponse(question)
  })
  assistantThinking.value = false
  await scrollAssistantToBottom()
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
  min-height: 0;
  display: flex;
  flex-direction: column;
  color: #17213a;
  background:
    radial-gradient(circle at 100% 0%, rgba(59, 130, 246, 0.1), transparent 36%),
    #f5f7fb;
}

.assistant-context {
  margin: 14px 14px 0;
  padding: 12px;
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  border: 1px solid #dce6f6;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 8px 24px rgba(41, 75, 137, 0.07);
}

.context-icon,
.message-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.context-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  color: #ffffff;
  background: linear-gradient(145deg, #1d4ed8, #38bdf8);
  box-shadow: 0 8px 16px rgba(37, 99, 235, 0.24);
}

.assistant-context strong {
  display: block;
  font-size: 13px;
}

.assistant-context p {
  margin: 3px 0 0;
  color: #68748d;
  font-size: 11px;
}

.context-status {
  padding: 4px 7px;
  border-radius: 999px;
  color: #087f5b;
  background: #dcfce7;
  font-size: 10px;
  font-weight: 700;
}

.assistant-thread {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  scrollbar-width: thin;
  scrollbar-color: #c5d3ea transparent;
}

.assistant-message {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  animation: message-rise 0.32s ease both;
}

.assistant-message.is-user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 28px;
  height: 28px;
  border-radius: 9px;
  color: #1d4ed8;
  background: #dbeafe;
  font-size: 10px;
}

.is-user .message-avatar {
  color: #ffffff;
  background: #64748b;
}

.assistant-message > p {
  max-width: calc(100% - 44px);
  margin: 0;
  padding: 10px 12px;
  border: 1px solid #dce5f3;
  border-radius: 5px 14px 14px 14px;
  color: #38455f;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 5px 16px rgba(36, 65, 118, 0.06);
  font-size: 13px;
  line-height: 1.72;
  white-space: pre-line;
}

.assistant-message.is-user > p {
  border-color: #2563eb;
  border-radius: 14px 5px 14px 14px;
  color: #ffffff;
  background: #2563eb;
}

.typing-indicator {
  height: 36px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid #dce5f3;
  border-radius: 5px 14px 14px 14px;
  background: #ffffff;
}

.typing-indicator i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3b82f6;
  animation: typing-pulse 1s ease-in-out infinite;
}

.typing-indicator i:nth-child(2) {
  animation-delay: 0.16s;
}

.typing-indicator i:nth-child(3) {
  animation-delay: 0.32s;
}

.assistant-composer {
  padding: 12px 14px 13px;
  border-top: 1px solid #dde5f1;
  background: rgba(255, 255, 255, 0.96);
}

.quick-questions {
  margin-bottom: 10px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.quick-questions button {
  min-width: 0;
  padding: 6px 9px;
  border: 1px solid #bfd3f4;
  border-radius: 999px;
  color: #28589d;
  background: #f5f9ff;
  font: inherit;
  font-size: 11px;
  white-space: nowrap;
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.quick-questions button:hover:not(:disabled) {
  border-color: #3b82f6;
  color: #1d4ed8;
  transform: translateY(-1px);
}

.quick-questions button:disabled {
  cursor: wait;
  opacity: 0.55;
}

.composer-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 62px;
  gap: 8px;
}

.composer-row :deep(.el-input__wrapper) {
  border-radius: 10px;
  box-shadow: 0 0 0 1px #dbe3f0 inset;
}

.composer-row :deep(.el-button) {
  width: 100%;
  margin-left: 0;
  border-radius: 10px;
}

.composer-hint {
  margin: 8px 0 0;
  color: #8b95a9;
  font-size: 10px;
  text-align: center;
}

.assistant-unavailable {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

@keyframes message-rise {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
}

@keyframes typing-pulse {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.45;
  }

  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

@media (max-width: 1199px) {
  .query-row {
    grid-template-columns: 1fr;
  }

  .panel-head {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 767px) {
  .page-head h2 {
    font-size: 24px;
  }

  .query-row :deep(.el-button) {
    width: 100%;
    margin-left: 0;
  }

  .quick-tags {
    align-items: flex-start;
  }

  .job-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .job-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .job-head > div {
    min-width: 0;
  }

  .job-head h4,
  .job-head p,
  .desc,
  .meta {
    overflow-wrap: anywhere;
  }

  .actions {
    flex-direction: column;
  }

  .actions :deep(.el-button) {
    width: 100%;
    margin-left: 0;
  }
}
</style>
