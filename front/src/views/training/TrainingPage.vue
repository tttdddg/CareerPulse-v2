<template>
  <div class="training-page">
    <section class="page-head">
      <h2>职场训练</h2>
      <p>通过典型职场场景训练表达、协作与任务处理能力。</p>
    </section>

    <el-alert
      v-if="!trainingApiAdapter.capability.available"
      type="info"
      :title="trainingApiAdapter.capability.reason"
      :closable="false"
      show-icon
    />

    <el-card class="panel section-panel">
      <div class="section-head">
        <div>
          <h3>训练类型</h3>
          <p>当前产品仅支持以下三类职场场景。</p>
        </div>
      </div>

      <div class="type-grid">
        <article
          v-for="item in trainingTypes"
          :key="item.type"
          class="type-card"
          :class="{ selected: selectedType === item.type }"
        >
          <div class="type-icon" aria-hidden="true">
            <el-icon><component :is="item.icon" /></el-icon>
          </div>
          <h4>{{ item.name }}</h4>
          <p>{{ item.description }}</p>
          <div class="ability-row">
            <span>能力重点</span>
            <div>
              <el-tag v-for="ability in item.abilities" :key="ability" size="small" effect="plain">
                {{ ability }}
              </el-tag>
            </div>
          </div>
          <el-button type="primary" plain @click="startTraining(item.type)">开始训练</el-button>
        </article>
      </div>
    </el-card>

    <el-card class="panel section-panel task-panel" v-loading="isBusy">
      <div class="section-head">
        <div>
          <h3>训练任务</h3>
          <p>{{ selectedTypeLabel ? `当前选择：${selectedTypeLabel}` : '选择训练类型后查看任务。' }}</p>
        </div>
        <el-tag v-if="stateLabel" effect="plain" :type="stateTagType">{{ stateLabel }}</el-tag>
      </div>

      <el-empty v-if="state === 'idle'" description="请选择一种训练类型开始" />

      <el-empty v-else-if="state === 'unavailable'" description="训练服务接入中">
        <p class="empty-note">{{ trainingApiAdapter.capability.reason }}</p>
      </el-empty>

      <div v-else-if="state === 'generating'" class="loading-copy">正在生成训练任务…</div>

      <el-alert
        v-else-if="state === 'error'"
        type="error"
        :title="errorMessage"
        :closable="false"
        show-icon
      />

      <template v-else-if="task">
        <div class="task-context">
          <section>
            <span>场景背景</span>
            <h4>{{ task.title }}</h4>
            <p>{{ task.scenario }}</p>
          </section>
          <section>
            <span>用户角色</span>
            <p>{{ task.role || 'AI Agent开发工程师' }}</p>
          </section>
          <section>
            <span>当前任务</span>
            <p>{{ task.taskDescription }}</p>
          </section>
        </div>

        <div class="answer-block">
          <label for="training-answer">你的回答</label>
          <el-input
            id="training-answer"
            v-model="answer"
            type="textarea"
            :rows="7"
            maxlength="100000"
            show-word-limit
            placeholder="请结合场景与任务要求作答"
            :disabled="state === 'scoring' || state === 'completed'"
          />
          <div class="answer-actions">
            <el-button
              type="primary"
              :loading="state === 'scoring'"
              :disabled="!answer.trim() || state !== 'ready'"
              @click="submitAnswer"
            >
              提交回答
            </el-button>
          </div>
        </div>
      </template>
    </el-card>

    <el-card class="panel section-panel result-panel">
      <div class="section-head">
        <div>
          <h3>训练反馈</h3>
          <p>评分完成后展示总体结果、维度反馈与改进建议。</p>
        </div>
      </div>

      <el-empty v-if="state !== 'completed' || !score" description="提交回答后即可查看完整反馈" />
      <template v-else>
        <section class="result-summary">
          <span>总体结果</span>
          <strong>{{ score.totalScore }}</strong>
          <p>{{ score.overallComment }}</p>
        </section>

        <div class="score-grid">
          <article v-for="dimension in score.dimensionScores" :key="dimension.dimension" class="score-card">
            <div>
              <h4>{{ dimension.dimension }}</h4>
              <strong>{{ dimension.score }}</strong>
            </div>
            <p>{{ dimension.comment }}</p>
          </article>
        </div>

        <div class="feedback-grid">
          <section>
            <h4>做得好的地方</h4>
            <ul v-if="score.strengths?.length">
              <li v-for="item in score.strengths" :key="item">{{ item }}</li>
            </ul>
            <p v-else>整体结构清晰，继续保持当前表达方式。</p>
          </section>
          <section>
            <h4>需要改进的地方</h4>
            <ul v-if="score.improvementSuggestions.length">
              <li v-for="item in score.improvementSuggestions" :key="item">{{ item }}</li>
            </ul>
            <p v-else>继续补充量化指标与异常场景。</p>
          </section>
          <section>
            <h4>下一步建议</h4>
            <ul v-if="score.nextSteps?.length">
              <li v-for="item in score.nextSteps" :key="item">{{ item }}</li>
            </ul>
            <p v-else>将回答整理为可复用的项目模板。</p>
          </section>
        </div>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, type Component } from 'vue'
import { ChatLineRound, Connection, Monitor } from '@element-plus/icons-vue'
import { useUserStore } from '../../stores/user'
import { isDemoMode } from '../../demo/demoMode'
import {
  trainingApiAdapter,
  type TrainingLifecycleState,
  type TrainingScore,
  type TrainingTask,
  type TrainingType
} from '../../api/modules/training'

interface TrainingTypeOption {
  type: TrainingType
  name: string
  description: string
  abilities: string[]
  icon: Component
}

const userStore = useUserStore()
const state = ref<TrainingLifecycleState>('idle')
const selectedType = ref<TrainingType | null>(null)
const task = ref<TrainingTask | null>(null)
const score = ref<TrainingScore | null>(null)
const answer = ref('')
const errorMessage = ref('')

const trainingTypes: TrainingTypeOption[] = [
  {
    type: 'remote_collaboration',
    name: '远程协作',
    description: '练习在线协作中的信息同步、责任确认与风险沟通。',
    abilities: ['协作沟通', '信息同步', '风险意识'],
    icon: Connection
  },
  {
    type: 'ai_office_task',
    name: 'AI 办公任务',
    description: '练习使用 AI 辅助拆解、处理并核验日常办公任务。',
    abilities: ['任务拆解', 'AI 工具应用', '结果核验'],
    icon: Monitor
  },
  {
    type: 'cross_role_communication',
    name: '跨角色沟通',
    description: '练习在不同职责和目标之间澄清需求、推进共识。',
    abilities: ['需求澄清', '表达能力', '共识推进'],
    icon: ChatLineRound
  }
]

const isBusy = computed(() => state.value === 'generating' || state.value === 'scoring')
const selectedTypeLabel = computed(
  () => trainingTypes.find((item) => item.type === selectedType.value)?.name ?? ''
)

const stateLabel = computed(() => {
  const labels: Record<TrainingLifecycleState, string> = {
    idle: '未开始',
    generating: '生成中',
    ready: '待回答',
    scoring: '评分中',
    completed: '评分完成',
    unavailable: '服务接入中',
    error: '错误'
  }
  return labels[state.value]
})

const stateTagType = computed<'info' | 'warning' | 'success' | 'danger'>(() => {
  if (state.value === 'completed') {
    return 'success'
  }
  if (state.value === 'error') {
    return 'danger'
  }
  if (state.value === 'generating' || state.value === 'scoring') {
    return 'warning'
  }
  return 'info'
})

const startTraining = async (type: TrainingType): Promise<void> => {
  selectedType.value = type
  task.value = null
  score.value = null
  answer.value = ''
  errorMessage.value = ''

  if (!trainingApiAdapter.capability.available) {
    state.value = 'unavailable'
    return
  }

  try {
    state.value = 'generating'
    task.value = await trainingApiAdapter.generateTask({
      userId: userStore.profile?.id ?? 'default',
      trainingType: type
    })
    state.value = 'ready'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '训练任务生成失败，请稍后重试'
    state.value = 'error'
  }
}

const submitAnswer = async (): Promise<void> => {
  if (!task.value || !answer.value.trim()) {
    return
  }

  try {
    state.value = 'scoring'
    errorMessage.value = ''
    score.value = await trainingApiAdapter.scoreTask({
      userId: userStore.profile?.id ?? 'default',
      trainingId: task.value.trainingId,
      answer: answer.value.trim()
    })
    state.value = 'completed'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '训练评分失败，请稍后重试'
    state.value = 'error'
  }
}

onMounted(() => {
  if (isDemoMode) {
    void startTraining('ai_office_task')
  }
})
</script>

<style scoped>
.training-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-head h2 {
  margin: 0 0 8px;
  font-size: 28px;
  color: #1f2b3d;
}

.page-head p,
.section-head p {
  margin: 0;
  color: #667089;
  font-size: 14px;
  line-height: 1.6;
}

.panel {
  border-radius: 16px;
  border: 1px solid #e2e7f1;
  background: #ffffff;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.section-head h3 {
  margin: 0 0 6px;
  font-size: 22px;
  color: #1f2a3f;
}

.type-grid,
.score-grid,
.feedback-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.type-card,
.score-card,
.feedback-grid section {
  min-width: 0;
  border: 1px solid #dde4ef;
  border-radius: 12px;
  padding: 14px;
  background: #ffffff;
}

.type-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.type-card.selected {
  border-color: #7892ff;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.08);
}

.type-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #625de7;
  background: #eef1ff;
  font-size: 20px;
}

.type-card h4,
.score-card h4,
.feedback-grid h4 {
  margin: 0;
  color: #2a344c;
  font-size: 16px;
}

.type-card > p,
.score-card p,
.feedback-grid li,
.task-context p,
.result-summary p {
  margin: 0;
  color: #5d6780;
  font-size: 14px;
  line-height: 1.6;
}

.type-card .el-button {
  align-self: flex-start;
  margin-top: auto;
}

.ability-row {
  display: flex;
  flex-direction: column;
  gap: 7px;
  color: #4a5571;
  font-size: 13px;
}

.ability-row > div {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.empty-note {
  max-width: 520px;
  margin: 0 auto;
  color: #758099;
  font-size: 13px;
  text-align: center;
}

.loading-copy {
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #667089;
}

.task-context {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.task-context section {
  border: 1px solid #e3e8f1;
  border-radius: 12px;
  padding: 14px;
  background: #fbfcff;
}

.task-context span,
.result-summary span {
  display: block;
  margin-bottom: 7px;
  color: #6a748c;
  font-size: 13px;
}

.task-context h4 {
  margin: 0 0 8px;
  color: #2a344c;
  font-size: 16px;
}

.answer-block {
  margin-top: 16px;
}

.answer-block label {
  display: block;
  margin-bottom: 8px;
  color: #35415a;
  font-size: 14px;
  font-weight: 600;
}

.answer-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

.result-summary {
  margin-bottom: 14px;
  border: 1px solid #dde4ef;
  border-radius: 12px;
  padding: 16px;
  background: #fbfcff;
}

.result-summary strong {
  display: block;
  margin-bottom: 8px;
  color: #4f46e5;
  font-size: 28px;
}

.score-card > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.score-card strong {
  color: #4f46e5;
  font-size: 20px;
}

.feedback-grid {
  margin-top: 12px;
}

.feedback-grid ul {
  margin: 10px 0 0;
  padding-left: 18px;
}

@media (max-width: 1199px) {
  .type-grid,
  .score-grid,
  .feedback-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .task-context {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .training-page {
    gap: 14px;
  }

  .page-head h2 {
    font-size: 24px;
  }

  .section-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .type-grid,
  .score-grid,
  .feedback-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .type-card > p,
  .score-card p,
  .feedback-grid li,
  .task-context p,
  .result-summary p {
    overflow-wrap: anywhere;
  }

  .type-card .el-button,
  .answer-actions .el-button {
    width: 100%;
  }

  .answer-actions {
    justify-content: stretch;
  }

  .score-card > div {
    align-items: flex-start;
  }
}
</style>
