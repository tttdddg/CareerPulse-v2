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

interface ResourceItem {
  title: string
  desc: string
}

const defaultResources: ResourceItem[] = []
const resources = ref<ResourceItem[]>([...defaultResources])

const hasMeaningfulContent = (value: string): boolean => {
  const plainText = value
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/\s+/g, '')
  return plainText.length > 0
}

const downloadBlob = (blob: Blob, fileName: string): void => {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  anchor.click()
  URL.revokeObjectURL(url)
}

const exportCurrentContentLocally = (payload: { type: 'pdf' | 'word'; fileName: string }): void => {
  const html = `<!doctype html><html><head><meta charset="utf-8" /></head><body>${content.value || ''}</body></html>`
  const isWord = payload.type === 'word'
  const blob = new Blob([html], { type: isWord ? 'application/msword;charset=utf-8' : 'text/html;charset=utf-8' })
  const fileName = isWord ? payload.fileName.replace(/\.docx$/i, '.doc') : payload.fileName.replace(/\.pdf$/i, '.html')
  downloadBlob(blob, fileName)
}

const handlePolish = async (value: string): Promise<void> => {
  if (!hasMeaningfulContent(value)) {
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
  if (!hasMeaningfulContent(content.value)) {
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
  try {
    exporting.value = true
    if (!reportId.value) {
      reportId.value = await resolveReportId()
    }
    if (!reportId.value) {
      throw new Error('缺少报告编号，请先生成报告后再导出')
    }

    const blob = await exportReport(reportId.value, payload.type)
    downloadBlob(blob, payload.fileName)
  } catch (error) {
    const status = (error as { status?: number })?.status
    if (status === 404 || status === 405) {
      exportCurrentContentLocally(payload)
      ElMessage.warning('后端导出接口不可用，已为你导出当前页面内容（本地兜底）')
      return
    }
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

const pickLatestNumericReportId = (): number | null => {
  const candidates = [
    historyStore.lastViewedReportId,
    historyStore.latestReport?.id ?? null,
    ...historyStore.reports.map((item) => item.id)
  ]

  for (const id of candidates) {
    const parsed = parseReportId(id)
    if (parsed) {
      return parsed
    }
  }

  return null
}

const resolveReportId = async (): Promise<number | null> => {
  const cached = analysisStore.reportId ?? pickLatestNumericReportId()
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

const sleep = (ms: number): Promise<void> => new Promise((resolve) => window.setTimeout(resolve, ms))

const fetchReportWithRetry = async (id: number): Promise<string> => {
  for (let i = 0; i < 3; i += 1) {
    try {
      const result = await fetchReport(id)
      if (result.content.trim()) {
        return result.content
      }
    } catch (error) {
      const status = (error as { status?: number })?.status
      // 报告不存在时让上层走 generateReport 兜底，而不是直接中断页面初始化。
      if (status === 404 || status === 405) {
        return ''
      }
      throw error
    }
    if (i < 2) {
      await sleep(800)
    }
  }
  return ''
}

const loadResources = async (): Promise<void> => {
  try {
    const tips = await fetchRecommendations(analysisStore.gaps[0] ?? '')
    if (!tips.length) {
      resources.value = [...defaultResources]
      return
    }

    resources.value = tips.slice(0, 6).map((tip, index) => ({
      title: `学习建议 ${index + 1}`,
      desc: tip
    }))
  } catch {
    resources.value = [...defaultResources]
  }
}

onMounted(async () => {
  try {
    loading.value = true
    reportId.value = await resolveReportId()
    if (!reportId.value) {
      errorMessage.value = '暂无可用报告，已为你加载默认成长规划模板，可先编辑后保存'
      content.value = [
        '<h3>职业成长规划（模板）</h3>',
        '<p><strong>阶段目标（1-3 个月）：</strong>明确目标岗位核心能力模型，完成差距盘点。</p>',
        '<p><strong>行动计划：</strong>每周学习 2 个知识点，完成 1 个项目实践并复盘。</p>',
        '<p><strong>评估方式：</strong>以作品质量、面试反馈和阶段测评结果作为迭代依据。</p>'
      ].join('')
      await loadResources()
      return
    }

    if (!hasMeaningfulContent(content.value)) {
      content.value = await fetchReportWithRetry(reportId.value)
    }

    if (!hasMeaningfulContent(content.value) && analysisStore.studentId && analysisStore.jobId) {
      const generated = await generateReport({
        studentId: analysisStore.studentId,
        jobId: analysisStore.jobId,
        userId: userStore.profile?.id ?? 'default'
      })
      if (generated.reportId) {
        reportId.value = generated.reportId
        analysisStore.setContext({ reportId: generated.reportId })
        historyStore.setLastViewedReport(String(generated.reportId))
      }
      content.value = generated.content || ''
    }

    if (!hasMeaningfulContent(content.value)) {
      content.value = '<p>暂无成长计划内容，请点击内容检查获取建议。</p>'
    }

    await loadResources()
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
