<template>
  <el-container class="app-shell">
    <el-aside width="240px" class="sidebar">
      <div class="brand">
        <img :src="brandLogo" alt="Logo" class="brand-logo" />
      </div>
      <el-menu :default-active="activeMenu" router class="nav-menu">
        <el-menu-item index="/app/input">
          <el-icon><EditPen /></el-icon>
          <span>数据输入</span>
        </el-menu-item>
        <el-menu-item index="/app/analysis">
          <el-icon><TrendCharts /></el-icon>
          <span>岗位匹配</span>
        </el-menu-item>
        <el-menu-item index="/app/path">
          <el-icon><Share /></el-icon>
          <span>职业分析</span>
        </el-menu-item>
        <el-menu-item index="/app/plan">
          <el-icon><DocumentChecked /></el-icon>
          <span>成长规划</span>
        </el-menu-item>
        <el-menu-item index="/app/profile">
          <el-icon><User /></el-icon>
          <span>历史记录</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container class="shell-main">
      <el-header class="topbar">
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
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import brandLogo from '@/assets/logoo.png'
import {
  EditPen,
  TrendCharts,
  Share,
  DocumentChecked,
  User,
  SwitchButton
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const handleLogout = (): void => {
  userStore.logout()
  router.push('/login')
}

const activeMenu = computed(() => route.path)
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

.logout-button {
  color: #606a7d;
  font-size: 17px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.main-area {
  padding: 26px 30px 32px;
  background: #f2f4f8;
}

@media (max-width: 1024px) {
  .brand-text {
    font-size: 28px;
  }

  :deep(.el-menu-item) {
    font-size: 15px;
  }
}

@media (max-width: 900px) {
  .app-shell {
    display: block;
  }

  .sidebar {
    width: 100%;
  }

  .topbar {
    height: 68px;
  }

  :deep(.el-menu-item) {
    font-size: 14px;
    height: 46px;
  }
}
</style>
