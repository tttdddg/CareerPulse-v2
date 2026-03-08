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
        class="resume-zone"
        :show-file-list="false"
        :max-size-m-b="10"
        @upload="handleResumeUpload"
        @error="handleUploadError"
      />

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
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useAnalysisStore } from '../../stores/analysis'
import { useHistoryStore } from '../../stores/history'
import ResumeUpload from '../../components/business/ResumeUpload.vue'
import { mockParseResume, mockStartAnalysis } from '../../services/mockApi'

const router = useRouter()
const analysisStore = useAnalysisStore()
const historyStore = useHistoryStore()

const loading = ref(false)
const analysisLoading = ref(false)
const errorMessage = ref('')

const form = reactive({
  role: '',
  skills: '',
  industry: '',
  targetRole: '',
  certificates: '',
  experience: '',
  selfEvaluation: ''
})

const canStartAnalysis = computed(() => Boolean(form.skills.trim() && form.targetRole.trim()))

const handleUploadError = (message: string): void => {
  errorMessage.value = message
}

const handleResumeUpload = async (payload: { file: File }): Promise<void> => {
  errorMessage.value = ''

  try {
    loading.value = true
    const parsed = await mockParseResume(payload.file.name)
    form.role = parsed.role
    form.skills = parsed.skills
    form.industry = parsed.industry
    form.targetRole = parsed.targetRole
    ElMessage.success('简历解析完成')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '简历解析失败'
  } finally {
    loading.value = false
  }
}

const handleStartAnalysis = async (): Promise<void> => {
  errorMessage.value = ''

  if (!form.skills || !form.targetRole) {
    errorMessage.value = '请完善技能与目标岗位信息'
    return
  }

  if (form.targetRole.trim().length < 2) {
    errorMessage.value = '目标岗位至少输入 2 个字符'
    return
  }

  try {
    analysisLoading.value = true
    const result = await mockStartAnalysis()
    analysisStore.setMatchScore(result.matchScore)
    analysisStore.setRadarData(result.radarIndicators, result.radarSeries)
    analysisStore.setInsights(result.strengths, result.gaps)

    historyStore.addReport({
      id: `report-${Date.now()}`,
      title: `${form.targetRole} 匹配报告`,
      createdAt: new Date().toISOString().slice(0, 10),
      score: result.matchScore,
      tags: [form.targetRole, form.industry || '行业未知']
    })

    ElMessage.success('分析任务已启动')
    await router.push('/app/analysis')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '启动分析失败'
  } finally {
    analysisLoading.value = false
  }
}
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
  grid-template-columns: auto minmax(0, 1fr) 210px;
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

.error-alert {
  margin-bottom: 4px;
}

@media (max-width: 1200px) {
  .field-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .action-row {
    grid-template-columns: 1fr;
  }

  .start-button {
    width: 100%;
  }
}
</style>
