<template>
  <div class="recommend-page">
    <section class="page-head">
      <h2>岗位推荐</h2>
      <p>基于你的简历信息与目标方向，推荐更适合的岗位并展示匹配度。</p>
    </section>

    <el-card class="panel query-panel">
      <div class="query-row">
        <el-input v-model="keyword" placeholder="输入目标方向，例如：前端开发 / 产品经理 / 测试工程师">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" :loading="loading" @click="loadRecommendations">生成推荐</el-button>
        <el-button plain @click="goExploreJobs">无方向？先浏览岗位库</el-button>
      </div>
      <p class="query-tip">当前推荐关键词：{{ keyword || '未填写' }}</p>
    </el-card>

    <section class="stats-grid">
      <el-card class="panel stat-card">
        <span>推荐岗位数</span>
        <strong>{{ jobs.length }}</strong>
      </el-card>
      <el-card class="panel stat-card">
        <span>平均匹配度</span>
        <strong>{{ avgMatch }}%</strong>
      </el-card>
      <el-card class="panel stat-card">
        <span>最高匹配度</span>
        <strong>{{ maxMatch }}%</strong>
      </el-card>
    </section>

    <el-card class="panel list-panel" v-loading="loading">
      <div class="panel-head">
        <h3>适配岗位列表</h3>
      </div>
      <el-empty v-if="!jobs.length" description="暂无岗位推荐，请先输入关键词并生成推荐" />
      <div v-else class="job-list">
        <article v-for="job in jobs" :key="job.id" class="job-item">
          <div class="job-top">
            <div>
              <h4>{{ job.name }}</h4>
              <p>{{ job.company || '企业信息待补充' }} · {{ job.industry || '行业未知' }}</p>
            </div>
            <el-tag type="success">{{ Math.round(job.match) }}%</el-tag>
          </div>
          <el-progress :percentage="Math.round(job.match)" :stroke-width="12" />
          <p class="job-meta">薪资范围：{{ job.salaryRange || '待补充' }}</p>
          <div class="tag-row">
            <el-tag v-for="tag in job.requiredSkills.slice(0, 5)" :key="tag" effect="plain">{{ tag }}</el-tag>
          </div>
          <div class="actions">
            <el-button size="small" type="primary" plain @click="setAsDirection(job)">设为方向</el-button>
            <el-button size="small" @click="goToAnalysis(job)">去分析看板</el-button>
          </div>
        </article>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchJobs, type JobItem } from '../../api/modules/career'
import { useAnalysisStore } from '../../stores/analysis'
import { pickDiverseTopJobs } from '../../utils/jobDiversity'

const router = useRouter()
const route = useRoute()
const analysisStore = useAnalysisStore()
const loading = ref(false)
const keyword = ref('')
const jobs = ref<JobItem[]>([])

const fallbackJobs: JobItem[] = [
  {
    id: 90001,
    name: '前端开发工程师',
    match: 84,
    company: '示例科技',
    industry: '互联网',
    salaryRange: '12k-22k',
    requiredSkills: ['Vue', 'TypeScript', '工程化'],
    requiredCerts: [],
    softSkills: ['沟通协作'],
    abilityDimensions: { innovation: 78, learning: 82, stressTolerance: 72, communication: 75, internship: 70 },
    highlights: ['页面交互', '组件化'],
    description: '负责 Web 端业务开发与体验优化'
  },
  {
    id: 90002,
    name: '产品经理',
    match: 80,
    company: '示例科技',
    industry: '互联网',
    salaryRange: '14k-26k',
    requiredSkills: ['需求分析', '原型设计', '数据分析'],
    requiredCerts: [],
    softSkills: ['跨团队协作'],
    abilityDimensions: { innovation: 80, learning: 78, stressTolerance: 70, communication: 83, internship: 68 },
    highlights: ['需求拆解', '增长意识'],
    description: '负责产品规划与业务闭环设计'
  },
  {
    id: 90003,
    name: '测试工程师',
    match: 76,
    company: '示例科技',
    industry: '企业服务',
    salaryRange: '10k-18k',
    requiredSkills: ['测试用例', '接口测试', '自动化测试'],
    requiredCerts: [],
    softSkills: ['细节意识'],
    abilityDimensions: { innovation: 70, learning: 75, stressTolerance: 80, communication: 72, internship: 74 },
    highlights: ['质量保障', '流程规范'],
    description: '负责功能质量保障与自动化测试建设'
  }
]

const avgMatch = computed(() => {
  if (!jobs.value.length) {
    return 0
  }
  const total = jobs.value.reduce((sum, item) => sum + item.match, 0)
  return Math.round(total / jobs.value.length)
})

const maxMatch = computed(() => {
  if (!jobs.value.length) {
    return 0
  }
  return Math.round(Math.max(...jobs.value.map((item) => item.match)))
})

const applyJobs = (nextJobs: JobItem[]): void => {
  jobs.value = nextJobs
  analysisStore.setCandidateJobs(nextJobs)
}

const loadRecommendations = async (): Promise<void> => {
  const nextKeyword = keyword.value.trim() || analysisStore.targetKeyword || '产品经理'
  keyword.value = nextKeyword
  try {
    loading.value = true
    const result = await pickDiverseTopJobs(nextKeyword, fetchJobs, 12)
    if (!result.length) {
      applyJobs(fallbackJobs)
      ElMessage.warning('后端暂无推荐数据，已展示演示岗位')
      return
    }
    applyJobs(result)
    analysisStore.setTargetKeyword(nextKeyword)
  } catch {
    applyJobs(fallbackJobs)
    ElMessage.warning('推荐接口异常，已展示演示岗位')
  } finally {
    loading.value = false
  }
}

const setAsDirection = (job: JobItem): void => {
  keyword.value = job.name
  analysisStore.setTargetKeyword(job.name)
  ElMessage.success(`已设置方向：${job.name}`)
}

const goToAnalysis = async (job: JobItem): Promise<void> => {
  analysisStore.setTargetKeyword(job.name)
  analysisStore.setContext({ jobId: job.id })
  await router.push('/app/analysis')
}

const goExploreJobs = async (): Promise<void> => {
  await router.push('/app/jobs?mode=explore')
}

onMounted(async () => {
  const queryKeyword = typeof route.query.keyword === 'string' ? route.query.keyword : ''
  keyword.value = queryKeyword || analysisStore.targetKeyword || ''
  if (analysisStore.candidateJobs.length > 0) {
    jobs.value = analysisStore.candidateJobs.slice(0, 12)
    return
  }
  await loadRecommendations()
})
</script>

<style scoped>
.recommend-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-head h2 {
  margin: 0 0 8px;
  color: #1f2b3d;
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
  grid-template-columns: minmax(0, 1fr) 128px 180px;
  gap: 10px;
}

.query-tip {
  margin: 10px 0 0;
  color: #6a738a;
  font-size: 13px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-card span {
  color: #69748b;
  font-size: 13px;
}

.stat-card strong {
  font-size: 28px;
  color: #2b3550;
}

.panel-head h3 {
  margin: 0 0 12px;
}

.job-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.job-item {
  border: 1px solid #dfe5f0;
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.job-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.job-top h4 {
  margin: 0;
  color: #24314d;
}

.job-top p {
  margin: 6px 0 0;
  color: #6a738a;
  font-size: 13px;
}

.job-meta {
  margin: 0;
  color: #5f6a82;
  font-size: 13px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 28px;
}

.actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 980px) {
  .query-row {
    grid-template-columns: 1fr;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
