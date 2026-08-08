<template>
  <div class="login-page">
    <div class="hero">
      <div class="hero-line"></div>
      <h1>吾 AI 职导</h1>
      <p class="hero-subtitle">用数据描绘职业画像，用 AI 规划下一步。</p>
      <div class="hero-points">
        <span>岗位匹配</span>
        <span>路径图谱</span>
        <span>成长计划</span>
      </div>
    </div>
    <el-card class="login-card">
      <h2>欢迎回来</h2>
      <p class="card-subtitle">登录后继续你的职业规划进度</p>
      <el-form :model="form" label-position="top" class="login-form">
        <el-form-item label="邮箱/手机号">
          <el-input v-model="form.account" placeholder="name@company.com" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <div class="form-actions">
          <el-checkbox v-model="form.remember">记住我</el-checkbox>
          <el-link type="primary" :underline="false">忘记密码</el-link>
        </div>
        <el-button type="primary" size="large" class="login-button">登录</el-button>
      </el-form>
      <div class="alt-login">
        <span>没有账号？</span>
        <el-link type="primary" :underline="false">创建账号</el-link>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'

const form = reactive({
  account: '',
  password: '',
  remember: true
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1fr 420px;
  align-items: center;
  gap: 64px;
  padding: 72px 10vw;
  background: var(--cp-surface);
  position: relative;
}

.login-page::before {
  content: '';
  position: absolute;
  left: 8%;
  top: 12%;
  width: 240px;
  height: 240px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.12), transparent 70%);
}

.hero h1 {
  font-size: 36px;
  margin: 0 0 16px;
}

.hero-subtitle {
  font-size: 16px;
  color: var(--cp-text-muted);
  margin-bottom: 20px;
}

.hero-line {
  width: 44px;
  height: 3px;
  background: var(--cp-accent-gradient);
  margin-bottom: 20px;
}

.hero-points {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.hero-points span {
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--cp-border);
  font-size: 12px;
  color: var(--cp-text-muted);
}

.login-card {
  border-radius: 18px;
  border: 1px solid var(--cp-border);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
}

.login-card h2 {
  margin: 0 0 8px;
  font-size: 22px;
}

.card-subtitle {
  color: var(--cp-text-muted);
  margin-bottom: 20px;
}

.login-form {
  margin-top: 8px;
}

.form-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 8px 0 20px;
}

.login-button {
  width: 100%;
}

.alt-login {
  margin-top: 16px;
  display: flex;
  gap: 8px;
  justify-content: center;
  font-size: 13px;
  color: var(--cp-text-muted);
}

@media (max-width: 960px) {
  .login-page {
    grid-template-columns: 1fr;
    padding: 64px 8vw;
  }
}
</style>
