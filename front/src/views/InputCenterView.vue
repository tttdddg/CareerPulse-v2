<template>
  <div class="input-center">
    <el-card class="progress-card">
      <div class="card-head">
        <div>
          <h2>画像构建进度</h2>
          <p>完成基础信息后进入分析看板</p>
        </div>
        <el-button type="primary" plain>保存草稿</el-button>
      </div>
      <el-steps :active="1" finish-status="success" align-center>
        <el-step title="基础信息" />
        <el-step title="技能与兴趣" />
        <el-step title="目标岗位" />
        <el-step title="完成" />
      </el-steps>
    </el-card>

    <div class="input-grid">
      <el-card class="form-card">
        <h3>个人信息</h3>
        <el-form :model="form" label-position="top" class="input-form">
          <el-form-item label="当前身份">
            <el-select v-model="form.role" placeholder="请选择">
              <el-option label="在校学生" value="student" />
              <el-option label="应届毕业" value="grad" />
              <el-option label="职场从业" value="professional" />
            </el-select>
          </el-form-item>
          <el-form-item label="核心技能">
            <el-input v-model="form.skills" placeholder="例如：数据分析 / 产品设计 / 前端开发" />
          </el-form-item>
          <el-form-item label="目标行业">
            <el-select v-model="form.industry" placeholder="请选择">
              <el-option label="互联网" value="internet" />
              <el-option label="金融" value="finance" />
              <el-option label="教育" value="edu" />
            </el-select>
          </el-form-item>
          <el-form-item label="职业关键词">
            <el-input v-model="form.keywords" placeholder="例如：增长 / B 端 / AI" />
          </el-form-item>
          <el-button type="primary" size="large">下一步</el-button>
        </el-form>
      </el-card>

      <el-card class="summary-card">
        <h3>画像摘要</h3>
        <p>实时汇总输入内容，形成职业画像</p>
        <div class="summary-tags">
          <el-tag type="info">可视化思维</el-tag>
          <el-tag type="info">产品洞察</el-tag>
          <el-tag type="info">数据驱动</el-tag>
        </div>
        <div class="summary-block">
          <span class="label">匹配度预估</span>
          <span class="value">78%</span>
        </div>
        <div class="summary-block">
          <span class="label">目标岗位</span>
          <span class="value">AI 产品经理</span>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'

const form = reactive({
  role: '',
  skills: '',
  industry: '',
  keywords: ''
})
</script>

<style scoped>
.input-center {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.progress-card {
  border-radius: 16px;
  border: 1px solid var(--cp-border);
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-head h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.card-head p {
  color: var(--cp-text-muted);
  margin: 0;
}

.input-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 24px;
}

.form-card,
.summary-card {
  border-radius: 16px;
  border: 1px solid var(--cp-border);
}

.input-form {
  margin-top: 12px;
}

.summary-card p {
  color: var(--cp-text-muted);
}

.summary-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 16px 0;
}

.summary-block {
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  border-top: 1px solid var(--cp-border);
  font-size: 14px;
}

.summary-block .label {
  color: var(--cp-text-muted);
}

.summary-block .value {
  font-weight: 600;
}

@media (max-width: 1100px) {
  .input-grid {
    grid-template-columns: 1fr;
  }
}
</style>
