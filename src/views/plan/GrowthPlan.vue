<template>
  <div class="growth-plan">
    <el-alert
      v-if="errorMessage"
      type="error"
      :title="errorMessage"
      show-icon
      class="error-alert"
      @close="errorMessage = ''"
    />

    <section class="plan-layout">
      <el-card class="panel editor-panel" v-loading="loading">
        <div class="editor-head">
          <h2>职业目标</h2>
          <div class="actions">
            <el-button class="tool-btn" type="primary" plain @click="handlePolish(content)">智能润色</el-button>
            <el-button class="tool-btn" type="primary" plain @click="handleCheck">内容检查</el-button>
            <export-button :loading="exporting" type="word" label="导出PDF/Word" @export="handleExport" />
          </div>
        </div>

        <rich-text-editor v-model="content" @polish="handlePolish" @check="handleCheck" />
      </el-card>

      <el-card class="panel resource-panel">
        <h3>学习资源</h3>
        <article v-for="item in resources" :key="item.title" class="resource-item">
          <h4>{{ item.title }}</h4>
          <p>{{ item.desc }}</p>
        </article>
      </el-card>
    </section>

    <el-alert v-if="checkTips.length" type="warning" show-icon class="tips" title="内容检查建议">
      <ul>
        <li v-for="tip in checkTips" :key="tip">{{ tip }}</li>
      </ul>
    </el-alert>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAnalysisStore } from '../../stores/analysis'
import { useHistoryStore } from '../../stores/history'
import { useUserStore } from '../../stores/user'
import RichTextEditor from '../../components/business/RichTextEditor.vue'
import ExportButton from '../../components/business/ExportButton.vue'
import {
  exportReport,
  fetchRecommendations,
  fetchReport,
  generateReport,
  polishReport
} from '../../api/modules/career'

const analysisStore = useAnalysisStore()
const historyStore = useHistoryStore()
const userStore = useUserStore()
const loading = ref(false)
const exporting = ref(false)
const errorMessage = ref('')
const content = ref('')
const checkTips = ref<string[]>([])
const reportId = ref<number | null>(null)

const resources = [
  {
    title: 'Coursera: 产品管理基础',
    desc: '课程覆盖需求分析与产品规划，适合系统建立岗位知识体系。'
  },
  {
    title: '《启示录》(Inspired)',
    desc: '产品经理经典读物，帮助理解从洞察到落地的完整链路。'
  },
  {
    title: 'Notion: 个人知识库模板',
    desc: '高效组织和管理学习笔记与项目复盘。'
  },
  {
    title: '人人都是产品经理 FM',
    desc: '行业案例解析，适合碎片时间跟进岗位趋势。'
  }
]

const handlePolish = async (value: string): Promise<void> => {
  if (!value.trim()) {
    ElMessage.warning('请先填写成长计划内容再润色')
    return
  }

  if (!reportId.value) {
    errorMessage.value = '缺少报告编号，请先生成报告后再润色'
    return
  }

  try {
    exporting.value = true
    content.value = await polishReport(reportId.value, { text: value, paragraphIndex: 0 })
    ElMessage.success('内容已润色')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '润色失败'
  } finally {
    exporting.value = false
  }
}

const handleCheck = async (): Promise<void> => {
  if (!content.value.trim()) {
    checkTips.value = ['先补充目标与行动计划，再进行内容检查']
    ElMessage.warning('暂无可检查内容')
    return
  }

  try {
    exporting.value = true
    const tips = await fetchRecommendations(analysisStore.gaps[0] ?? '')
    checkTips.value = tips.length ? tips : ['建议补充量化目标、时间节点与评估方式']
    ElMessage.success('内容检查完成')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检查失败'
  } finally {
    exporting.value = false
  }
}

const handleExport = async (payload: { type: 'pdf' | 'word'; fileName: string }): Promise<void> => {
  if (!reportId.value) {
    errorMessage.value = '缺少报告编号，请先生成报告后再导出'
    return
  }

  try {
    exporting.value = true
    const blob = await exportReport(reportId.value, payload.type)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = payload.fileName
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '导出失败'
  } finally {
    exporting.value = false
  }
}

const parseReportId = (value: string | null): number | null => {
  if (!value) {
    return null
  }
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

const resolveReportId = async (): Promise<number | null> => {
  const cached = analysisStore.reportId ?? parseReportId(historyStore.lastViewedReportId)
  if (cached) {
    return cached
  }

  if (!analysisStore.studentId || !analysisStore.jobId) {
    return null
  }

  const generated = await generateReport({
    studentId: analysisStore.studentId,
    jobId: analysisStore.jobId,
    userId: userStore.profile?.id ?? 'default'
  })

  if (!generated.reportId) {
    return null
  }

  analysisStore.setContext({ reportId: generated.reportId })
  historyStore.setLastViewedReport(String(generated.reportId))

  if (generated.content) {
    content.value = generated.content
  }

  return generated.reportId
}

onMounted(async () => {
  try {
    loading.value = true
    reportId.value = await resolveReportId()
    if (!reportId.value) {
      errorMessage.value = '暂无可用报告，请先在数据输入中心完成分析'
      return
    }

    if (!content.value.trim()) {
      const result = await fetchReport(reportId.value)
      content.value = result.content || '<p>暂无成长计划内容，请点击内容检查获取建议。</p>'
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载成长计划失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.growth-plan {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.plan-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 0.36fr);
  gap: 16px;
}

.panel {
  border-radius: 16px;
  border: 1px solid #e2e7f1;
  background: #ffffff;
}

.editor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.editor-head h2 {
  margin: 0;
  font-size: 24px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tool-btn {
  border-radius: 10px;
}

.resource-panel {
  background: linear-gradient(180deg, #f0f4ff 0%, #f8f8fe 100%);
}

.resource-panel h3 {
  margin: 0 0 14px;
  font-size: 24px;
}

.resource-item {
  background: #ffffff;
  border: 1px solid #e2e8f1;
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 10px;
}

.resource-item h4 {
  margin: 0 0 6px;
  font-size: 16px;
  color: #2a344c;
}

.resource-item p {
  margin: 0;
  color: #6c7690;
  font-size: 14px;
  line-height: 1.6;
}

.tips ul {
  margin: 8px 0 0;
  padding-left: 18px;
}

@media (max-width: 1200px) {
  .plan-layout {
    grid-template-columns: 1fr;
  }
}
</style>
