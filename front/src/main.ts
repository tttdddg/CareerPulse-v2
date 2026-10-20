import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/theme.scss'
import './styles/base.css'
import App from './App.vue'
import router from './router'
import { useUserStore } from './stores/user'
import { useHistoryStore } from './stores/history'
import { useAnalysisStore } from './stores/analysis'
import { isDemoMode } from './demo/demoMode'
import {
  DEMO_JOBS,
  DEMO_MATCH_ANALYSIS,
  DEMO_PRIMARY_JOB_ID,
  DEMO_REPORT_ID,
  DEMO_STUDENT_ID
} from './demo/careerDemoData'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(ElementPlus)

const userStore = useUserStore(pinia)
if (isDemoMode) {
  userStore.setDemoProfile({
    id: 'CP-2028-0928',
    name: '林晓宁',
    role: '学生用户',
    title: 'AI Agent开发方向'
  })

  const analysisStore = useAnalysisStore(pinia)
  const primaryJob = DEMO_JOBS[0]
  const recommendedJobs = [DEMO_JOBS[0], DEMO_JOBS[1], DEMO_JOBS[3]].map((job) => ({
    id: job.job_id,
    name: job.job_name,
    match: job.match_score,
    company: job.company_name,
    industry: job.industry,
    salaryRange: job.salary_range,
    requiredSkills: [...job.required_skills],
    requiredCerts: [...job.required_certs],
    softSkills: [...job.soft_skills],
    abilityDimensions: {
      innovation: job.ability_dimensions.innovation,
      learning: job.ability_dimensions.learning,
      stressTolerance: job.ability_dimensions.stress_tolerance,
      communication: job.ability_dimensions.communication,
      internship: job.ability_dimensions.internship
    },
    highlights: [...job.highlights],
    description: job.job_description
  }))
  analysisStore.setTargetKeyword(primaryJob.job_name)
  analysisStore.setCandidateJobs(recommendedJobs)
  analysisStore.setContext({
    sessionId: 'demo-session',
    studentId: DEMO_STUDENT_ID,
    jobId: DEMO_PRIMARY_JOB_ID,
    reportId: DEMO_REPORT_ID
  })
  analysisStore.setMatchScore(DEMO_MATCH_ANALYSIS.overall_score)
  analysisStore.setRadarData(
    DEMO_MATCH_ANALYSIS.dimensions.map((item) => ({ name: item.name, max: 100 })),
    [
      {
        name: '候选人',
        values: DEMO_MATCH_ANALYSIS.dimensions.map((item) => item.student_score)
      },
      {
        name: '目标岗位',
        values: DEMO_MATCH_ANALYSIS.dimensions.map((item) => item.job_required)
      }
    ]
  )
  analysisStore.setInsights(
    [...DEMO_MATCH_ANALYSIS.strengths],
    [...DEMO_MATCH_ANALYSIS.gaps],
    DEMO_MATCH_ANALYSIS.gap_analysis.map((item) => ({
      name: item.item,
      status: item.status,
      priority: item.priority,
      suggestion: item.suggestion
    }))
  )
  analysisStore.grantPathAccess(DEMO_PRIMARY_JOB_ID)
}
useHistoryStore(pinia).hydrateFromStorage()

app.use(router)

const bootstrap = async (): Promise<void> => {
  if (!isDemoMode) {
    await userStore.hydrateSession()
  }
  window.addEventListener('career-pulse:unauthorized', () => {
    userStore.clearSession('expired')
    if (router.currentRoute.value.name !== 'login') {
      void router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
    }
  })
  await router.isReady()
  app.mount('#app')
}

void bootstrap()
