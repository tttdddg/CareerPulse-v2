<template>
  <el-container class="app-shell">
    <el-aside width="240px" class="sidebar desktop-sidebar">
      <div class="brand">
        <img :src="brandLogo" alt="Logo" class="brand-logo" />
      </div>
      <el-menu :default-active="activeMenu" router class="nav-menu">
        <el-menu-item
          v-for="item in navigationItems"
          :key="item.index"
          :index="item.index"
          :disabled="item.index === '/app/path' && pathMenuDisabled"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container class="shell-main">
      <el-header class="topbar">
        <el-button text class="menu-button" aria-label="打开导航菜单" @click="mobileMenuOpen = true">
          <el-icon><Expand /></el-icon>
        </el-button>
        <span class="mobile-page-title">{{ route.meta.title || 'CareerPulse' }}</span>
        <div class="topbar-spacer"></div>
        <el-button text class="logout-button" @click="handleLogout">
          <el-icon><SwitchButton /></el-icon>
          <span>退出登录</span>
        </el-button>
      </el-header>
      <el-main class="main-area">
        <router-view />
      </el-main>
    </el-container>

    <el-drawer
      v-model="mobileMenuOpen"
      class="mobile-nav-drawer"
      direction="ltr"
      size="min(82vw, 300px)"
      :with-header="false"
      append-to-body
    >
      <nav class="mobile-sidebar" aria-label="主导航">
        <div class="brand">
          <img :src="brandLogo" alt="Logo" class="brand-logo" />
        </div>
        <el-menu :default-active="activeMenu" router class="nav-menu" @select="closeMobileMenu">
          <el-menu-item
            v-for="item in navigationItems"
            :key="item.index"
            :index="item.index"
            :disabled="item.index === '/app/path' && pathMenuDisabled"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </el-menu-item>
        </el-menu>
      </nav>
    </el-drawer>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { useAnalysisStore } from '../stores/analysis'
import { isDemoMode } from '../demo/demoMode'
import brandLogo from '@/assets/logoo.png'
import {
  EditPen,
  TrendCharts,
  Share,
  Briefcase,
  DocumentChecked,
  ChatLineSquare,
  User,
  SwitchButton,
  Expand
} from '@element-plus/icons-vue'

interface NavigationItem {
  index: string
  label: string
  icon: Component
}

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const analysisStore = useAnalysisStore()
const mobileMenuOpen = ref(false)

const navigationItems: NavigationItem[] = [
  { index: '/app/input', label: '数据输入', icon: EditPen },
  { index: '/app/analysis', label: '岗位匹配', icon: TrendCharts },
  { index: '/app/jobs', label: '岗位库', icon: Briefcase },
  { index: '/app/path', label: '职业路径', icon: Share },
  { index: '/app/plan', label: '成长计划', icon: DocumentChecked },
  { index: '/app/training', label: '职场训练', icon: ChatLineSquare },
  { index: '/app/profile', label: '成长档案', icon: User }
]

const handleLogout = (): void => {
  userStore.logout()
  router.push('/login')
}

const activeMenu = computed(() => route.path)
const pathMenuDisabled = computed(() => !isDemoMode && !analysisStore.canVisitPathGraph)

const closeMobileMenu = (): void => {
  mobileMenuOpen.value = false
}

watch(
  () => route.fullPath,
  () => closeMobileMenu()
)
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: #f2f4f8;
  color: var(--cp-text);
}

.sidebar {
  background: #f6f7fb;
  border-right: 1px solid #dde2ec;
  padding-bottom: 8px;
}

.mobile-sidebar {
  min-height: 100%;
  background: #f6f7fb;
}

.brand {
  height: 78px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  background: linear-gradient(135deg, #5a74e8 0%, #6570ea 100%);
  border-bottom: 1px solid #8496ef;
}

.brand-logo {
  height: 520px;
  width: auto;
  max-width: 100%;
  object-fit: contain;
  display: block;
  filter: drop-shadow(0 4px 10px rgba(35, 62, 170, 0.2));
}

.brand-text {
  color: #ffffff;
  font-size: 20px;
  line-height: 1;
  font-family: 'Manrope', 'Noto Sans SC', sans-serif;
  font-weight: 700;
}

.nav-menu {
  margin-top: 8px;
  border-right: 0;
  background: transparent;
}

:deep(.el-menu) {
  border-right: 0;
  background: transparent;
}

:deep(.el-menu-item) {
  height: 54px;
  margin: 2px 0;
  border-radius: 0;
  padding-left: 16px !important;
  font-size: 17px;
  color: #5a6476;
  font-weight: 500;
  gap: 8px;
}

:deep(.el-menu-item .el-icon) {
  font-size: 18px;
}

:deep(.el-menu-item.is-active) {
  background: #e8ecf9;
  color: #4f46e5;
  font-weight: 600;
}

:deep(.el-menu-item:hover) {
  background: #eceff8;
}

.shell-main {
  min-width: 0;
}

.topbar {
  background: #f6f7fb;
  border-bottom: 1px solid #d8d5f5;
  padding: 0 28px 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 74px;
}

.topbar-spacer {
  flex: 1;
}

.menu-button,
.mobile-page-title {
  display: none;
}

.logout-button {
  color: #606a7d;
  font-size: 17px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.main-area {
  min-width: 0;
  padding: 26px 30px 32px;
  background: #f2f4f8;
}

@media (max-width: 1199px) {
  .main-area {
    padding: 22px 20px 28px;
  }
}

@media (max-width: 767px) {
  .desktop-sidebar {
    display: none;
  }

  .topbar {
    height: 60px;
    padding: 0 12px;
  }

  .menu-button {
    display: inline-flex;
    margin-right: 4px;
    color: #556078;
    font-size: 21px;
  }

  .mobile-page-title {
    display: block;
    min-width: 0;
    max-width: calc(100vw - 150px);
    overflow: hidden;
    color: #344057;
    font-size: 15px;
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .logout-button {
    flex: none;
    font-size: 14px;
    gap: 5px;
  }

  .main-area {
    width: 100%;
    padding: 16px 12px 24px;
  }

  :global(.mobile-nav-drawer) {
    background: #f6f7fb;
  }

  :global(.mobile-nav-drawer .el-drawer__body) {
    padding: 0;
  }
}
</style>
