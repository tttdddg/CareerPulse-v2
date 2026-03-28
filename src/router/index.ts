import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import DefaultLayout from '../layouts/DefaultLayout.vue'
import HomeLandingView from '../views/home/HomeLanding.vue'
import LoginView from '../views/login/Login.vue'
import DataInputView from '../views/input/DataInput.vue'
import AnalysisBoardView from '../views/analysis/AnalysisBoard.vue'
import PathGraphPageView from '../views/path/PathGraphPage.vue'
import GrowthPlanView from '../views/plan/GrowthPlan.vue'
import ProfileView from '../views/profile/Profile.vue'
import { useAnalysisStore } from '../stores/analysis'

const AUTH_STORAGE_KEY = 'career-pulse:auth'

const getStoredToken = (): string | null => {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    const parsed = JSON.parse(raw) as { token?: unknown }
    return typeof parsed.token === 'string' && parsed.token.length > 0 ? parsed.token : null
  } catch {
    return null
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'landing',
    component: HomeLandingView,
    meta: { title: '首页', public: true }
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { title: '登录', public: true }
  },
  {
    path: '/register',
    name: 'register',
    component: LoginView,
    meta: { title: '注册', public: true }
  },
  {
    path: '/app',
    component: DefaultLayout,
    redirect: '/app/input',
    children: [
      {
        path: 'input',
        name: 'input',
        component: DataInputView,
        meta: { title: '数据输入中心' }
      },
      {
        path: 'analysis',
        name: 'analysis',
        component: AnalysisBoardView,
        meta: { title: '人岗匹配分析看板' }
      },
      {
        path: 'path',
        name: 'path',
        component: PathGraphPageView,
        meta: { title: '职业路径图谱' }
      },
      {
        path: 'plan',
        name: 'plan',
        component: GrowthPlanView,
        meta: { title: '个性化成长计划' }
      },
      {
        path: 'profile',
        name: 'profile',
        component: ProfileView,
        meta: { title: '个人中心 / 历史记录' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to) => {
  const isPublic = Boolean(to.meta.public)
  const token = getStoredToken()

  if (!isPublic && !token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.name === 'path') {
    const analysisStore = useAnalysisStore()
    if (!analysisStore.canVisitPathGraph) {
      return { name: 'analysis' }
    }
  }

  if (typeof document !== 'undefined' && typeof to.meta.title === 'string') {
    document.title = `${to.meta.title} - 吾 AI 职导`
  }

  return true
})

export default router
