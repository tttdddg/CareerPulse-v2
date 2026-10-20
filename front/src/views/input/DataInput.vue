<template>
  <div class="data-input-page">
    <el-alert
      v-if="errorMessage"
      type="error"
      :title="errorMessage"
      show-icon
      class="error-alert"
      @close="errorMessage = ''"
    />

    <section class="page-head">
      <h1>数据输入中心</h1>
      <p>请填写您的职业信息,我们将为您提供专业的职业规划建议</p>
    </section>

    <el-card class="form-card" v-loading="loading">
      <resume-upload
        v-if="isDemoMode"
        class="resume-zone"
        :show-file-list="false"
        :max-size-m-b="10"
        @upload="handleResumeUpload"
        @error="handleUploadError"
      />

      <el-alert
        v-else
        class="feature-notice"
        type="info"
        title="简历文件解析功能暂未开放，将在 M3.2 提供；请先在下方手动填写个人画像"
        show-icon
        :closable="false"
      />

      <el-descriptions
        v-if="parsedProfile && !isDemoMode"
        class="parsed-profile"
        title="简历解析回填结果"
        :column="descriptionColumns"
        border
      >
        <el-descriptions-item label="姓名">{{ parsedProfile.name || '未填写姓名' }}</el-descriptions-item>
        <el-descriptions-item label="学历">{{ parsedProfile.education || '本科在读' }}</el-descriptions-item>
        <el-descriptions-item label="专业">{{ parsedProfile.major || '计算机相关专业' }}</el-descriptions-item>
        <el-descriptions-item label="目标岗位">{{ parsedProfile.targetJob || 'AI Agent开发工程师' }}</el-descriptions-item>
        <el-descriptions-item label="项目经历">{{ parsedProfile.projects || 'AI应用项目实践' }}</el-descriptions-item>
        <el-descriptions-item label="实习经历">{{ parsedProfile.internships || 'AI应用研发实践' }}</el-descriptions-item>
        <el-descriptions-item label="工作经历">{{ parsedProfile.workExperience || '项目型研发经历' }}</el-descriptions-item>
      </el-descriptions>

      <div class="field-grid">
        <section class="field-block">
          <h3><span class="field-mark"></span>专业技能</h3>
          <el-input
            v-model="form.skills"
            type="textarea"
            :rows="4"
            placeholder="请输入您掌握的专业技能,如:Java、Python、数据分析等"
          />
        </section>

        <section class="field-block">
          <h3><span class="field-mark"></span>证书资质</h3>
          <el-input
            v-model="form.certificates"
            type="textarea"
            :rows="4"
            placeholder="请输入您获得的证书和资质,如:PMP、CPA等"
          />
        </section>

        <section class="field-block">
          <h3><span class="field-mark"></span>实习经历</h3>
          <el-input
            v-model="form.experience"
            type="textarea"
            :rows="5"
            placeholder="请详细描述您的实习经历,包括公司名称、岗位职责、工作时间等"
          />
        </section>

        <section class="field-block">
          <h3><span class="field-mark"></span>自我评价</h3>
          <el-input
            v-model="form.selfEvaluation"
            type="textarea"
            :rows="5"
            placeholder="请简要介绍您的个人优势和职业目标"
          />
        </section>
      </div>
    </el-card>

    <el-card class="action-card">
      <div class="action-row">
        <label for="target-role" class="target-label">目标岗位:</label>
        <el-input
          id="target-role"
          v-model="form.targetRole"
          class="target-input"
          placeholder="搜索并选择目标岗位"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button
          type="primary"
          class="start-button"
          :loading="analysisLoading"
          :disabled="!canStartAnalysis || analysisLoading"
          @click="handleStartAnalysis"
        >
          开始分析
        </el-button>
        <el-button class="explore-button" @click="handleExploreJobs">
          无方向？先浏览岗位库
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { useAnalysisStore } from '../../stores/analysis'
import { useUserStore } from '../../stores/user'
import ResumeUpload from '../../components/business/ResumeUpload.vue'
import {
  analyzeWorkflowMatch,
  createWorkflow,
  fetchJobs,
  saveWorkflowProfile,
  saveWorkflowTargetJob,
  uploadStudentResume,
  type ProfileInput,
  type StudentUploadProfileResult
} from '../../api/modules/career'
import { getUserFacingErrorMessage } from '../../api/request'
import { pickDiverseTopJobs } from '../../utils/jobDiversity'
import { isDemoMode } from '../../demo/demoMode'

const router = useRouter()
const route = useRoute()
const analysisStore = useAnalysisStore()
const userStore = useUserStore()

const loading = ref(false)
const analysisLoading = ref(false)
const errorMessage = ref('')
const uploadedStudentId = ref<number | null>(null)
const parsedProfile = ref<StudentUploadProfileResult | null>(null)
const descriptionColumns = ref(2)

const form = reactive({
  role: '',
  skills: '',
  industry: '',
  targetRole: '',
  certificates: '',
  experience: '',
  selfEvaluation: ''
})

const hasManualProfileInput = computed(() =>
  Boolean(
    form.role.trim() ||
      form.skills.trim() ||
      form.certificates.trim() ||
      form.experience.trim() ||
      form.selfEvaluation.trim()
  )
)

const hasResumeSource = computed(() => uploadedStudentId.value !== null)

const canStartAnalysis = computed(() => Boolean(form.targetRole.trim() && (hasManualProfileInput.value || hasResumeSource.value)))

const handleUploadError = (message: string): void => {
  errorMessage.value = message
}

const applyParsedProfile = (parsed: StudentUploadProfileResult): void => {
  parsedProfile.value = parsed
  uploadedStudentId.value = parsed.studentId
  form.role = parsed.name || form.role
  form.skills = parsed.skills || form.skills
  form.certificates = parsed.certificates || form.certificates
  const experienceParts = [parsed.internships, parsed.workExperience, parsed.projects].filter(Boolean)
  form.experience = experienceParts.join('\n\n') || form.experience
  form.targetRole = parsed.targetJob || form.targetRole
  form.selfEvaluation = parsed.selfEvaluation || form.selfEvaluation
}

const handleResumeUpload = async (payload: {
  file: File
  formData: FormData
  onSuccess?: (response?: unknown) => void
  onError?: (error: Error) => void
}): Promise<void> => {
  errorMessage.value = ''

  try {
    loading.value = true
    const parsed = await uploadStudentResume(payload.formData)
    applyParsedProfile(parsed)
    payload.onSuccess?.(parsed)
    ElMessage.success('简历解析完成')
  } catch (error) {
    const uploadError = error instanceof Error ? error : new Error('简历解析失败')
    errorMessage.value = getUserFacingErrorMessage(error, '简历解析失败，请稍后重试')
    payload.onError?.(uploadError)
  } finally {
    loading.value = false
  }
}

const buildProfilePayload = (): ProfileInput => {
  const payload: ProfileInput = {}
  if (form.skills.trim()) payload.skills = form.skills
  if (form.certificates.trim()) payload.certificates = form.certificates
  if (form.experience.trim()) payload.internships = form.experience
  if (form.selfEvaluation.trim()) payload.supplementary_info = form.selfEvaluation

  const formFields: Record<string, unknown> = {}
  if (form.targetRole.trim()) formFields.target_job = form.targetRole.trim()
  if (form.industry.trim()) formFields.target_industry = form.industry.trim()
  if (Object.keys(formFields).length > 0) {
    payload.form_fields = formFields
  }
  return payload
}

const handleStartAnalysis = async (): Promise<void> => {
  errorMessage.value = ''

  if (!form.targetRole.trim()) {
    errorMessage.value = '请填写目标岗位'
    return
  }

  if (!hasManualProfileInput.value && !hasResumeSource.value) {
    errorMessage.value = '请至少填写一项个人信息或上传简历'
    return
  }

  if (form.targetRole.trim().length < 2) {
    errorMessage.value = '目标岗位至少输入 2 个字符'
    return
  }

  try {
    analysisLoading.value = true
    const topJobs = await pickDiverseTopJobs(form.targetRole, fetchJobs, 10)
    analysisStore.setTargetKeyword(form.targetRole)
    analysisStore.setCandidateJobs(topJobs)

    const topJob = topJobs[0]
    if (!topJob) {
      throw new Error('未查询到可分析的目标岗位，请调整岗位关键词后重试')
    }

    // 业务身份只来自后端会话：浏览器仅持有 sessionId，不提交 user_id。
    const sessionId = analysisStore.sessionId ?? (await createWorkflow()).session_id
    if (!sessionId) {
      throw new Error('未能创建职业分析会话，请稍后重试')
    }

    const profilePayload = buildProfilePayload()
    if (Object.keys(profilePayload).length > 0) {
      await saveWorkflowProfile(sessionId, profilePayload)
    }

    await saveWorkflowTargetJob(sessionId, {
      job_id: topJob.id,
      job_title: topJob.name
    })
    const analyzeResult = await analyzeWorkflowMatch(sessionId)

    analysisStore.setMatchScore(analyzeResult.matchScore)
    analysisStore.setRadarData(analyzeResult.radarIndicators, analyzeResult.radarSeries)
    analysisStore.setInsights(analyzeResult.strengths, analyzeResult.gaps, analyzeResult.gapDetails)
    analysisStore.setContext({
      sessionId,
      jobId: topJob.id
    })
    analysisStore.grantPathAccess(topJob.id)

    ElMessage.success('分析完成')

    await router.push('/app/analysis')
  } catch (error) {
    errorMessage.value = getUserFacingErrorMessage(error, '启动分析失败，请稍后重试')
  } finally {
    analysisLoading.value = false
  }
}

const handleExploreJobs = async (): Promise<void> => {
  await router.push('/app/jobs?mode=explore')
}

const syncResponsiveState = (): void => {
  descriptionColumns.value = window.innerWidth < 768 ? 1 : 2
}

onMounted(() => {
  syncResponsiveState()
  window.addEventListener('resize', syncResponsiveState)
  const targetFromQuery = typeof route.query.target === 'string' ? route.query.target.trim() : ''
  if (targetFromQuery) {
    form.targetRole = targetFromQuery
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncResponsiveState)
})
</script>

<style scoped>
.data-input-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-head h1 {
  margin: 0;
  font-size: 28px;
  color: #1f2b3d;
}

.page-head p {
  margin: 8px 0 0;
  color: #737f95;
  font-size: 14px;
}

.form-card,
.action-card {
  border: 1px solid #e4e7ef;
  border-radius: 16px;
  background: #fbfcff;
}

.resume-zone {
  margin-bottom: 18px;
}

:deep(.resume-zone .el-upload-dragger) {
  width: 100%;
  min-height: 176px;
  border: 2px dashed #7164f6;
  border-radius: 14px;
  background: #f7f8ff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
}

:deep(.resume-zone .upload-icon) {
  font-size: 56px;
  color: #6357f0;
}

:deep(.resume-zone .upload-text p) {
  margin-top: 8px;
  font-size: 18px;
  color: #2f3547;
}

:deep(.resume-zone .upload-text span) {
  font-size: 14px;
  color: #808aa3;
}

:deep(.resume-zone .el-upload__tip) {
  display: none;
}

.field-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 20px 24px;
}

.field-block h3 {
  margin: 0 0 10px;
  font-size: 16px;
  color: #2a344b;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.field-mark {
  width: 16px;
  height: 16px;
  border: 1.5px solid #6458f1;
  border-radius: 4px;
  display: inline-block;
  position: relative;
}

.field-mark::after {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #6458f1;
  position: absolute;
  top: 4px;
  left: 4px;
}

:deep(.field-block .el-textarea__inner) {
  border-radius: 10px;
  border-color: #d9deea;
  box-shadow: none;
  padding: 12px 14px;
  font-size: 14px;
}

.action-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) 210px 190px;
  align-items: center;
  gap: 20px;
}

.target-label {
  color: #35415a;
  font-size: 16px;
  font-weight: 600;
}

:deep(.target-input .el-input__wrapper) {
  border-radius: 10px;
  border: 1px solid #d9deea;
  box-shadow: none;
  min-height: 52px;
  background: #ffffff;
}

.start-button {
  height: 56px;
  border: 0;
  border-radius: 12px;
  font-size: 18px;
  font-weight: 700;
  background: linear-gradient(135deg, #5d68e8 0%, #7b52ef 100%);
  box-shadow: 0 14px 28px rgba(93, 104, 232, 0.25);
}

.explore-button {
  height: 56px;
  border-radius: 12px;
  border: 1px solid #f59e0b;
  color: #9a3412;
  background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
  font-size: 17px;
  font-weight: 700;
  box-shadow: 0 10px 22px rgba(245, 158, 11, 0.18);
}

.explore-button:hover {
  color: #7c2d12;
  border-color: #ea580c;
  background: linear-gradient(135deg, #ffedd5 0%, #fed7aa 100%);
}

.error-alert {
  margin-bottom: 4px;
}

@media (max-width: 1199px) {
  .field-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .data-input-page {
    gap: 14px;
  }

  .page-head h1 {
    font-size: 24px;
  }

  :deep(.resume-zone .el-upload-dragger) {
    min-height: 148px;
    padding: 18px 12px;
  }

  :deep(.resume-zone .upload-icon) {
    font-size: 44px;
  }

  :deep(.resume-zone .upload-text) {
    max-width: 100%;
    text-align: center;
  }

  :deep(.resume-zone .upload-text p) {
    font-size: 16px;
  }

  :deep(.resume-zone .upload-text span) {
    overflow-wrap: anywhere;
    font-size: 13px;
  }

  .field-grid {
    gap: 16px;
  }

  .action-row {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .start-button,
  .explore-button {
    width: 100%;
    height: 50px;
    margin-left: 0;
    font-size: 16px;
  }
}
</style>
