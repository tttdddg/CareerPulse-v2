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

      <el-empty v-else-if="!loading && !jobs.length" description="未查询到真实岗位数据">
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

    <ai-assistant-drawer v-model="assistantOpen" title="AI 职业伙伴" subtitle="百宝箱 Agent 接入准备中">
      <div class="assistant-content assistant-unavailable">
        <el-empty description="真实 AI 职业伙伴将在下一阶段接入百宝箱 Agent 后开放" />
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
import { getUserFacingErrorMessage } from '../../api/request'

const router = useRouter()
const route = useRoute()
const analysisStore = useAnalysisStore()

const loading = ref(false)
const keyword = ref('')
const jobs = ref<JobItem[]>([])
const errorMessage = ref('')
const lastRequestMode = ref<'search' | 'explore'>('explore')

const assistantOpen = ref(false)

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
  background: #f6f8fc;
}

.assistant-unavailable {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
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
