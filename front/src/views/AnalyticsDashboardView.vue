<template>
  <div class="dashboard">
    <div class="kpi-grid">
      <el-card class="kpi-card">
        <span class="kpi-label">综合匹配度</span>
        <span class="kpi-value">82%</span>
      </el-card>
      <el-card class="kpi-card">
        <span class="kpi-label">优势能力</span>
        <span class="kpi-value">5 项</span>
      </el-card>
      <el-card class="kpi-card">
        <span class="kpi-label">推荐岗位</span>
        <span class="kpi-value">12 个</span>
      </el-card>
      <el-card class="kpi-card">
        <span class="kpi-label">成长建议</span>
        <span class="kpi-value">3 条</span>
      </el-card>
    </div>

    <div class="chart-grid">
      <el-card class="chart-card">
        <div class="chart-head">
          <div>
            <h3>能力雷达</h3>
            <p>关键维度匹配分析</p>
          </div>
          <el-tag type="info">实时更新</el-tag>
        </div>
        <div class="chart-placeholder">Radar Chart</div>
      </el-card>

      <el-card class="chart-card">
        <div class="chart-head">
          <div>
            <h3>岗位趋势</h3>
            <p>目标行业需求热度</p>
          </div>
          <el-button type="primary" plain size="small">切换行业</el-button>
        </div>
        <div class="chart-placeholder">Trend Chart</div>
      </el-card>
    </div>

    <el-card class="table-card">
      <div class="chart-head">
        <div>
          <h3>岗位推荐</h3>
          <p>与你画像匹配度最高的岗位</p>
        </div>
        <el-button type="primary" plain size="small">导出</el-button>
      </div>
      <el-table :data="tableData" stripe style="width: 100%">
        <el-table-column prop="role" label="岗位" />
        <el-table-column prop="match" label="匹配度" />
        <el-table-column prop="skills" label="关键技能" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
const tableData = [
  { role: 'AI 产品经理', match: '86%', skills: '需求洞察 / 数据分析' },
  { role: '增长策略分析', match: '82%', skills: '策略规划 / 实验设计' },
  { role: '用户研究顾问', match: '79%', skills: '访谈 / 洞察整理' }
]
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.kpi-card {
  border-radius: 14px;
  border: 1px solid var(--cp-border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kpi-label {
  color: var(--cp-text-muted);
  font-size: 13px;
}

.kpi-value {
  font-size: 22px;
  font-weight: 700;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.chart-card,
.table-card {
  border-radius: 16px;
  border: 1px solid var(--cp-border);
}

.chart-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.chart-head h3 {
  margin: 0 0 6px;
  font-size: 18px;
}

.chart-head p {
  margin: 0;
  color: var(--cp-text-muted);
}

.chart-placeholder {
  height: 240px;
  border-radius: 12px;
  border: 1px dashed rgba(99, 102, 241, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--cp-text-muted);
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.05), rgba(139, 92, 246, 0.08));
  font-weight: 500;
}

@media (max-width: 1100px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .chart-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
