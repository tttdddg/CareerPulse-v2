<template>
  <div class="analysis-board">
    <el-alert
      v-if="errorMessage"
      type="error"
      :title="errorMessage"
      show-icon
      class="error-alert"
      @close="errorMessage = ''"
    />

    <section class="page-head">
      <h2>人岗匹配分析</h2>
      <p>基于多维度能力模型的智能匹配结果</p>
    </section>

    <el-card class="panel summary" v-loading="loading">
      <div class="summary-layout">
        <div class="summary-main">
          <div ref="gaugeEl" class="gauge"></div>
          <p class="target-role">
            <span>当前岗位</span>
            <strong>{{ formatJobName(currentJob?.name || '未选择岗位') }}</strong>
          </p>
        </div>
        <aside class="summary-rank">
          <div class="summary-rank-head">
            <h3>岗位排行榜</h3>
            <span>Top 3</span>
          </div>
          <el-empty v-if="!topRankedJobs.length" description="暂无岗位排行" :image-size="72" />
          <div v-else class="rank-list">
            <article
              v-for="(job, index) in topRankedJobs"
              :key="`${job.uid}-rank`"
              class="rank-item"
              :class="{ active: job.jobId === analysisStore.jobId }"
            >
              <div class="rank-index">{{ index + 1 }}</div>
              <div class="rank-body">
                <div class="rank-title-row">
                  <strong>{{ formatJobName(job.name) }}</strong>
                  <span class="rank-score">{{ Math.round(job.match || 0) }}%</span>
                </div>
                <div class="rank-bar">
                  <span class="rank-bar-fill" :style="{ width: `${Math.min(Math.max(job.match || 0, 0), 100)}%` }"></span>
                </div>
              </div>
            </article>
          </div>
        </aside>
      </div>
    </el-card>

    <el-card class="panel jobs-panel" v-loading="jobsLoading">
      <div class="panel-head">
        <h3>岗位画像列表（Top 10）</h3>
        <div class="head-actions">
          <el-button size="small" @click="toggleJobView">
            {{ isWordCloudView ? '切换卡片视图' : '切换词云视图' }}
          </el-button>
          <el-button type="primary" plain size="small" :loading="complianceLoading" @click="checkGraphCompliance">
            校验图谱约束
          </el-button>
          <el-button type="primary" plain size="small" @click="handleRefreshJobs">刷新岗位</el-button>
        </div>
      </div>
      <p class="compliance" v-if="complianceResult">{{ complianceResult }}</p>
      <el-empty v-if="isWordCloudView && !wordCloudData.length" description="暂无词云数据，请先回到数据输入中心完成分析" />
      <div v-else-if="isWordCloudView" ref="wordCloudEl" class="job-wordcloud"></div>
      <el-empty v-else-if="!jobProfiles.length" description="暂无岗位画像，请先回到数据输入中心完成分析" />
      <div v-else class="job-grid">
        <article
          v-for="job in jobProfiles"
          :key="job.uid"
          class="job-card"
          :class="{ active: job.jobId === analysisStore.jobId }"
        >
          <div class="job-head">
            <div class="job-title-group">
              <h4>{{ formatJobName(job.name) }}</h4>
              <p class="job-meta">{{ job.company || '企业信息待补充' }} · {{ job.industry || '行业未知' }}</p>
            </div>
            <span class="job-match">{{ Math.round(job.match || 0) }}%</span>
          </div>
          <div class="job-progress">
            <div class="job-progress-bar">
              <span class="job-progress-fill" :style="{ width: `${Math.min(Math.max(job.match || 0, 0), 100)}%` }"></span>
            </div>
            <span class="job-progress-text">当前匹配度</span>
          </div>
          <p v-if="job.description" class="job-summary">{{ job.description }}</p>
          <div class="job-portrait-grid">
            <div class="portrait-section">
              <span class="portrait-label">硬实力</span>
              <div class="tag-row">
                <el-tag
                  v-for="tag in getHardSkillTags(job)"
                  :key="`${job.uid}-hard-${tag}`"
                  effect="plain"
                >
                  {{ tag }}
                </el-tag>
                <span v-if="!getHardSkillTags(job).length" class="empty-inline">待补充</span>
              </div>
            </div>
            <div class="portrait-section">
              <span class="portrait-label">软实力</span>
              <div class="tag-row">
                <el-tag
                  v-for="tag in getSoftSkillTags(job)"
                  :key="`${job.uid}-soft-${tag}`"
                  effect="plain"
                  type="success"
                >
                  {{ tag }}
                </el-tag>
                <span v-if="!getSoftSkillTags(job).length" class="empty-inline">待补充</span>
              </div>
            </div>
          </div>
          <div class="portrait-section">
            <span class="portrait-label">能力维度</span>
            <div class="dimension-list">
              <span
                v-for="dimension in getAbilityDimensionTags(job)"
                :key="`${job.uid}-dimension-${dimension}`"
                class="dimension-chip"
              >
                {{ dimension }}
              </span>
              <span v-if="!getAbilityDimensionTags(job).length" class="empty-inline">待补充</span>
            </div>
          </div>
          <div class="job-actions">
            <el-button size="small" type="primary" plain :disabled="!job.jobId" @click="selectTargetJob(job)">
              设为目标
            </el-button>
            <el-button
              size="small"
              :disabled="analysisStore.jobId !== job.jobId"
              @click="jumpToAnalysis(job)"
            >
              查看画像
            </el-button>
          </div>
        </article>
      </div>
    </el-card>

    <section class="detail-grid">
      <el-card class="panel">
        <h3>能力维度对比分析</h3>
        <radar-chart
          v-if="analysisStore.hasRadar"
          :indicators="analysisStore.radarIndicators"
          :series="analysisStore.radarSeries"
          :height="360"
        />
        <el-empty v-else description="暂无雷达数据" />
      </el-card>

      <el-card class="panel gap-panel" v-loading="jobsLoading">
        <div class="panel-head">
          <h3>能力差距详细分析</h3>
          <el-button type="primary" plain size="small" @click="refreshRadar">刷新</el-button>
        </div>
        <el-empty v-if="!analysisStore.gaps.length" description="暂无差距项" />
        <div v-else class="gap-list">
          <article v-for="(gap, index) in analysisStore.gaps" :key="gap" class="gap-item">
            <div class="gap-icon">
              <el-icon><Warning /></el-icon>
            </div>
            <div class="gap-content">
              <div class="gap-title-row">
                <h4>{{ gap }}</h4>
                <el-tag :type="priorityMap[index % priorityMap.length].type" size="small">
                  {{ priorityMap[index % priorityMap.length].label }}
                </el-tag>
              </div>
              <p>{{ getGapDesc(gap) }}</p>
              <a href="javascript:void(0)" @click.prevent="goToPlan">查看详情 →</a>
            </div>
          </article>
        </div>
      </el-card>
    </section>

  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import 'echarts-wordcloud'
import { ElMessage } from 'element-plus'
import { Warning } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useAnalysisStore } from '../../stores/analysis'
import RadarChart from '../../components/business/RadarChart.vue'
import { fetchJobGraph, fetchJobProfile, matchingAnalyze, type JobItem } from '../../api/modules/career'

type JobPortraitCard = {
  uid: string
  jobId: number | null
  name: string
  match: number
  company: string
  industry: string
  salaryRange: string
  requiredSkills: string[]
  requiredCerts: string[]
  softSkills: string[]
  abilityDimensions: JobItem['abilityDimensions']
  highlights: string[]
  description: string
}

type JobPortraitPreset = Omit<JobPortraitCard, 'uid' | 'jobId' | 'name' | 'salaryRange' | 'highlights'> & {
  aliases?: string[]
}

const router = useRouter()
const analysisStore = useAnalysisStore()
const loading = ref(false)
const jobsLoading = ref(false)
const complianceLoading = ref(false)
const errorMessage = ref('')
const complianceResult = ref('')
const graphJobProfiles = ref<JobPortraitCard[]>([])

const gaugeEl = ref<HTMLDivElement | null>(null)
const wordCloudEl = ref<HTMLDivElement | null>(null)
let gaugeChart: echarts.ECharts | null = null
let wordCloudChart: echarts.ECharts | null = null
let wordCloudMaskImage: HTMLImageElement | null = null
const jobViewMode = ref<'wordcloud' | 'list'>('wordcloud')

const priorityMap = [
  { label: '紧急', type: 'danger' as const },
  { label: '重要', type: 'warning' as const },
  { label: '一般', type: 'success' as const }
]

const frontendPortraitPresets: Record<string, JobPortraitPreset> = {
  高级前端开发工程师: {
    match: 88,
    company: '上海云岚数字科技有限公司',
    industry: '企业数字化',
    requiredSkills: ['React/Vue工程化', '复杂状态管理', '大规模TypeScript应用'],
    requiredCerts: ['性能优化'],
    softSkills: ['跨团队沟通', '任务拆解协同'],
    abilityDimensions: { innovation: 83, learning: 86, stressTolerance: 78, communication: 80, internship: 82 },
    description: '负责核心前端模块建设与工程规范推进，支撑复杂业务场景的稳定交付。'
  },
  前端技术专家: {
    match: 84,
    company: '杭州视界交互科技有限公司',
    industry: '互联网平台',
    requiredSkills: ['前端架构治理', '复杂交互性能', '跨平台技术设计'],
    requiredCerts: [],
    softSkills: ['技术布道', '快速学习'],
    abilityDimensions: { innovation: 88, learning: 87, stressTolerance: 76, communication: 79, internship: 80 },
    description: '聚焦技术难点攻坚与前端架构演进，提升大型项目的可扩展性与体验质量。'
  },
  前端架构师: {
    match: 82,
    company: '深圳智链软件工程有限公司',
    industry: '计算机软件',
    requiredSkills: ['前端平台架构', '设计系统治理', '微前端策略'],
    requiredCerts: [],
    softSkills: ['方案评审', '架构协同'],
    abilityDimensions: { innovation: 90, learning: 84, stressTolerance: 80, communication: 82, internship: 79 },
    description: '主导前端技术栈规划、基础设施建设与团队最佳实践沉淀。'
  },
  前端研发经理: {
    match: 79,
    company: '北京灵动体验科技有限公司',
    industry: '消费互联网',
    requiredSkills: ['团队领导力', '跨团队协作', '质量治理'],
    requiredCerts: [],
    softSkills: ['项目推进', '人员培养'],
    abilityDimensions: { innovation: 80, learning: 78, stressTolerance: 84, communication: 88, internship: 77 },
    description: '统筹前端研发团队交付节奏，平衡业务目标、人员成长与工程质量。'
  },
  前端体验技术总监: {
    match: 76,
    company: '广州星帆产品体验有限公司',
    industry: '用户体验服务',
    requiredSkills: ['体验技术战略', '多端体验规划', '组织级工程治理'],
    requiredCerts: [],
    softSkills: ['业务洞察', '决策沟通'],
    abilityDimensions: { innovation: 86, learning: 80, stressTolerance: 82, communication: 90, internship: 75 },
    description: '负责体验技术方向规划，推动产品体验、设计系统与工程能力协同升级。'
  },
  全栈开发工程师: {
    match: 74,
    company: '成都新页信息技术有限公司',
    industry: '企业服务',
    requiredSkills: ['前端框架', '后端开发', '数据库设计'],
    requiredCerts: [],
    softSkills: ['全局思维', '需求理解'],
    abilityDimensions: { innovation: 79, learning: 85, stressTolerance: 81, communication: 75, internship: 83 },
    description: '覆盖前后端一体化交付，适合具备页面开发基础并希望扩展服务端能力的人才。'
  },
  'UI/UX设计师': {
    aliases: ['UIUX设计师', 'UI / UX设计师'],
    match: 70,
    company: '苏州像素创意设计有限公司',
    industry: '设计服务',
    requiredSkills: ['用户研究', '原型设计', '交互设计'],
    requiredCerts: [],
    softSkills: ['同理心', '视觉表达'],
    abilityDimensions: { innovation: 87, learning: 81, stressTolerance: 74, communication: 82, internship: 72 },
    description: '偏重用户体验洞察与界面设计输出，适合希望向设计协同方向拓展的前端人才。'
  },
  技术经理: {
    match: 68,
    company: '南京数智协同科技有限公司',
    industry: '软件研发管理',
    requiredSkills: ['团队管理', '项目管理', '技术决策'],
    requiredCerts: [],
    softSkills: ['目标管理', '风险控制'],
    abilityDimensions: { innovation: 76, learning: 77, stressTolerance: 86, communication: 89, internship: 74 },
    description: '面向研发管理与跨团队协调，强调交付、资源统筹与技术决策能力。'
  },
  移动端开发工程师: {
    match: 66,
    company: '武汉云帆移动科技有限公司',
    industry: '移动互联网',
    requiredSkills: ['Android/iOS开发', '跨平台框架', '网络编程'],
    requiredCerts: [],
    softSkills: ['问题定位', '持续迭代'],
    abilityDimensions: { innovation: 78, learning: 82, stressTolerance: 79, communication: 73, internship: 81 },
    description: '聚焦原生与跨端移动应用开发，适合希望从 Web 端延展到移动端生态的人才。'
  }
}

const formatJobName = (name: string): string => {
  const trimmed = name.trim()
  if (!trimmed) {
    return '未命名岗位'
  }
  if (/^java$/i.test(trimmed)) {
    return 'JAVA后端'
  }
  return trimmed
}

const findFrontendPreset = (name: string): JobPortraitPreset | null => {
  const trimmed = name.trim()
  if (!trimmed) {
    return null
  }

  for (const [presetName, preset] of Object.entries(frontendPortraitPresets)) {
    const aliases = [presetName, ...(preset.aliases ?? [])]
    if (aliases.some((alias) => alias.trim().toLowerCase() === trimmed.toLowerCase())) {
      return preset
    }
  }

  return null
}

const applyFrontendShowcasePreset = (
  jobs: JobPortraitCard[],
  targetJobId: number | null,
  targetJobName: string
): JobPortraitCard[] => {
  const isFrontendScene = /前端开发/.test(targetJobName)
  if (!isFrontendScene) {
    return jobs
  }

  return jobs.map((job) => {
    if (job.jobId === targetJobId) {
      return job
    }

    const preset = findFrontendPreset(job.name)
    if (!preset) {
      return job
    }

    return {
      ...job,
      match: preset.match,
      company: preset.company,
      industry: preset.industry,
      requiredSkills: preset.requiredSkills,
      requiredCerts: preset.requiredCerts,
      softSkills: preset.softSkills,
      abilityDimensions: preset.abilityDimensions,
      highlights: preset.softSkills,
      description: preset.description
    }
  })
}

const normalizeName = (name: string): string => name.trim().toLowerCase().replace(/\s+/g, '')

const tryExtractJobId = (rawId: string | number): number | null => {
  if (typeof rawId === 'number' && Number.isFinite(rawId) && rawId > 0) {
    return rawId
  }
  const text = `${rawId ?? ''}`.trim()
  if (!text) {
    return null
  }
  // 仅接受纯数字 id，避免将 n1、node-2 这类图谱节点误识别为岗位 ID。
  if (/^\d+$/.test(text)) {
    const direct = Number(text)
    if (Number.isFinite(direct) && direct > 0) {
      return direct
    }
  }
  return null
}

const jobProfiles = computed(() => graphJobProfiles.value.slice(0, 10))
const isWordCloudView = computed(() => jobViewMode.value === 'wordcloud')

const wordCloudData = computed<Array<{ name: string; value: number; source: string }>>(() => {
  const addWord = (bucket: Map<string, { name: string; value: number; source: string }>, rawName: string, value: number, source: string): void => {
    const name = rawName.trim()
    if (!name || name.length < 2) {
      return
    }
    const existing = bucket.get(name)
    if (existing) {
      existing.value += value
      return
    }
    bucket.set(name, { name, value, source })
  }

  const tokenizeByPhrase = (text: string): string[] => {
    const value = text.trim()
    if (!value) {
      return []
    }
    const parts = value
      .split(/[、,，。；;|/\\\s]+/)
      .map((item) => item.trim())
      .filter((item) => item.length >= 2)
    if (parts.length > 1) {
      return parts
    }

    const onlyCn = value.replace(/[^\u4e00-\u9fa5]/g, '')
    if (onlyCn.length >= 4) {
      const chunks: string[] = []
      for (let i = 0; i < onlyCn.length - 1; i += 1) {
        chunks.push(onlyCn.slice(i, i + 2))
      }
      return chunks
    }
    return [value]
  }

  const bucket = new Map<string, { name: string; value: number; source: string }>()
  const seededJobs = [
    ...jobProfiles.value,
    ...analysisStore.candidateJobs.map((job) => ({
      uid: `seed-${job.id}`,
      jobId: job.id,
      name: job.name,
      match: job.match,
      company: job.company,
      industry: job.industry,
      salaryRange: job.salaryRange,
      requiredSkills: job.requiredSkills,
      highlights: job.highlights
    }))
  ]

  seededJobs.forEach((job) => {
    const matchBoost = Math.max(Math.round(job.match || 0), 30)
    addWord(bucket, job.name, 72 + Math.round(matchBoost * 0.7), '岗位')
    tokenizeByPhrase(job.name).forEach((token, index) => {
      addWord(bucket, token, 20 - index, '岗位分词')
    })

    if (job.company && !/待补充|未知/.test(job.company)) {
      addWord(bucket, job.company, 24 + Math.round(matchBoost * 0.1), '企业')
      tokenizeByPhrase(job.company).forEach((token, index) => {
        addWord(bucket, token, 14 - index, '企业分词')
      })
    }
    if (job.industry && !/未知/.test(job.industry)) {
      addWord(bucket, job.industry, 22 + Math.round(matchBoost * 0.08), '行业')
      tokenizeByPhrase(job.industry).forEach((token, index) => {
        addWord(bucket, token, 12 - index, '行业分词')
      })
    }

    job.requiredSkills.slice(0, 8).forEach((skill, index) => {
      addWord(bucket, skill, 26 - index * 2 + Math.round(matchBoost * 0.06), '技能')
      tokenizeByPhrase(skill).forEach((token, tokenIdx) => {
        addWord(bucket, token, 10 - tokenIdx, '技能分词')
      })
    })

    job.highlights.slice(0, 6).forEach((highlight, index) => {
      addWord(bucket, highlight, 18 - index + Math.round(matchBoost * 0.04), '亮点')
      tokenizeByPhrase(highlight).forEach((token, tokenIdx) => {
        addWord(bucket, token, 8 - tokenIdx, '亮点分词')
      })
    })
  })

  const baseWords = [...bucket.values()]
    .map((item) => ({ ...item, value: Math.max(item.value, 3) }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 220)

  // 低权重重复词补点：视觉上同词重复，内部用零宽字符区分，专门用于填满轮廓边缘与脖子区域。
  const denseFillWords: Array<{ name: string; value: number; source: string }> = []
  const topSeed = baseWords.slice(0, 60)
  topSeed.forEach((item, idx) => {
    const repeatCount = idx < 20 ? 6 : idx < 40 ? 4 : 2
    for (let i = 0; i < repeatCount; i += 1) {
      denseFillWords.push({
        name: `${item.name}${'\u200b'.repeat(i + 1)}`,
        value: Math.max(2, Math.round(item.value * 0.16) - i),
        source: `${item.source}填充`
      })
    }
  })

  return [...baseWords, ...denseFillWords]
    .sort((a, b) => b.value - a.value)
    .slice(0, 520)
})

const currentJob = computed(() => {
  if (!jobProfiles.value.length) {
    return null
  }
  return jobProfiles.value.find((item) => item.jobId === analysisStore.jobId) ?? jobProfiles.value[0]
})

const currentDisplayMatch = computed(() => {
  if (currentJob.value) {
    return Math.round(currentJob.value.match || 0)
  }
  return Math.round(analysisStore.matchScore || 0)
})

const topRankedJobs = computed(() =>
  [...jobProfiles.value]
    .sort((a, b) => (b.match || 0) - (a.match || 0))
    .slice(0, 3)
)

const getGapDesc = (gap: string): string => {
  return `当前在「${gap}」维度仍有提升空间，建议通过专项练习与项目实践快速补强。`
}

const getHardSkillTags = (job: JobPortraitCard): string[] => {
  const merged = [...job.requiredSkills, ...job.requiredCerts]
  return [...new Set(merged.filter(Boolean))].slice(0, 3)
}

const getSoftSkillTags = (job: JobPortraitCard): string[] => {
  return [...new Set(job.softSkills.filter(Boolean))].slice(0, 2)
}

const abilityDimensionLabelMap: Array<{ key: keyof JobItem['abilityDimensions']; label: string }> = [
  { key: 'innovation', label: '创新能力' },
  { key: 'learning', label: '学习能力' },
  { key: 'stressTolerance', label: '抗压能力' },
  { key: 'communication', label: '沟通能力' },
  { key: 'internship', label: '实践能力' }
]

const getAbilityDimensionTags = (job: JobPortraitCard): string[] => {
  return abilityDimensionLabelMap
    .filter(({ key }) => (job.abilityDimensions?.[key] ?? 0) > 0)
    .sort((a, b) => (job.abilityDimensions?.[b.key] ?? 0) - (job.abilityDimensions?.[a.key] ?? 0))
    .slice(0, 3)
    .map(({ key, label }) => `${label} ${(job.abilityDimensions?.[key] ?? 0).toFixed(0)}`)
}

const goToPlan = async (): Promise<void> => {
  await router.push('/app/plan')
}

const renderGauge = (): void => {
  if (!gaugeEl.value) {
    return
  }

  if (!gaugeChart) {
    gaugeChart = echarts.init(gaugeEl.value)
  }

  gaugeChart.setOption({
    title: {
      text: '整体匹配度',
      left: 'center',
      top: '64%',
      textStyle: {
        color: '#8a92a6',
        fontWeight: 500,
        fontSize: 16
      }
    },
    series: [
      {
        type: 'gauge',
        startAngle: 90,
        endAngle: -270,
        radius: '80%',
        progress: {
          show: true,
          width: 16,
          roundCap: true,
          itemStyle: {
            color: '#6c63f5'
          }
        },
        axisLine: {
          lineStyle: {
            width: 16,
            color: [[1, '#e6e9f2']]
          }
        },
        pointer: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        detail: {
          valueAnimation: true,
          formatter: '{value}%',
          color: '#5f5ee7',
          fontSize: 62,
          fontWeight: 700,
          offsetCenter: [0, '-6%']
        },
        data: [{ value: currentDisplayMatch.value }]
      }
    ]
  })
}

const renderWordCloud = (): void => {
  if (!wordCloudEl.value || !wordCloudData.value.length) {
    return
  }

  if (!wordCloudChart) {
    wordCloudChart = echarts.init(wordCloudEl.value)
  }

  const hashWord = (text: string): number => {
    let hash = 0
    for (let i = 0; i < text.length; i += 1) {
      hash = (hash * 31 + text.charCodeAt(i)) % 2147483647
    }
    return Math.abs(hash)
  }

  const ensureHeadMask = (): Promise<HTMLImageElement> => {
    if (wordCloudMaskImage) {
      return Promise.resolve(wordCloudMaskImage)
    }

    const headMaskSvg = `
      <svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" viewBox="0 0 1000 1000">
        <rect width="100%" height="100%" fill="white"/>
        <g fill="black">
          <ellipse cx="500" cy="360" rx="360" ry="330"/>
          <rect x="360" y="620" width="280" height="260" rx="100"/>
          <ellipse cx="500" cy="890" rx="270" ry="105"/>
        </g>
      </svg>
    `.trim()

    const svgUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(headMaskSvg)}`
    return new Promise((resolve) => {
      const image = new Image()
      image.onload = () => {
        wordCloudMaskImage = image
        resolve(image)
      }
      image.src = svgUrl
    })
  }

  void ensureHeadMask().then((maskImage) => {
    if (!wordCloudChart) {
      return
    }

    wordCloudChart.setOption({
      tooltip: {
        formatter: (params: { name: string; value: number; data?: { source?: string } }) =>
          `${params.name}<br/>来源：${params.data?.source ?? '岗位画像'}<br/>权重：${params.value}`
      },
      series: [
        {
          type: 'wordCloud',
          shape: 'square',
          maskImage,
          keepAspect: true,
          width: '100%',
          height: '100%',
          left: 'center',
          top: 'center',
          gridSize: 1,
          sizeRange: [4, 52],
          rotationRange: [-15, 15],
          rotationStep: 15,
          drawOutOfBound: false,
          shrinkToFit: true,
          textStyle: {
            color: (_: unknown, params?: { name?: string }) => {
              const palette = [
                '#4338ca', '#2563eb', '#0284c7', '#0891b2', '#059669', '#65a30d',
                '#ca8a04', '#ea580c', '#dc2626', '#be185d', '#7c3aed'
              ]
              const idx = hashWord(params?.name ?? '') % palette.length
              return palette[idx]
            }
          },
          emphasis: {
            textStyle: {
              shadowBlur: 12,
              shadowColor: 'rgba(0, 0, 0, 0.3)'
            }
          },
          data: wordCloudData.value
        }
      ]
    } as echarts.EChartsOption)
  })
}

const toggleJobView = async (): Promise<void> => {
  jobViewMode.value = jobViewMode.value === 'wordcloud' ? 'list' : 'wordcloud'
  if (isWordCloudView.value) {
    await nextTick()
    renderWordCloud()
  }
}

const refreshRadar = async (): Promise<void> => {
  if (!analysisStore.studentId || !analysisStore.jobId) {
    errorMessage.value = '缺少分析上下文，请先在数据输入中心完成一次分析'
    return
  }

  try {
    loading.value = true
    const result = await matchingAnalyze({
      studentId: analysisStore.studentId,
      jobId: analysisStore.jobId
    })
    analysisStore.setMatchScore(result.matchScore)
    analysisStore.setRadarData(result.radarIndicators, result.radarSeries)
    analysisStore.setInsights(result.strengths, result.gaps)
    if (result.reportId) {
      analysisStore.setContext({ reportId: result.reportId })
    }
    ElMessage.success('分析结果已更新')
    renderGauge()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '刷新失败'
  } finally {
    loading.value = false
  }
}

const fetchJobs = async (force = true): Promise<void> => {
  try {
    jobsLoading.value = true

    if (!force && graphJobProfiles.value.length >= 10) {
      if (!analysisStore.jobId) {
        const firstAvailable = graphJobProfiles.value.find((item) => item.jobId !== null)
        if (firstAvailable?.jobId) {
          analysisStore.setContext({ jobId: firstAvailable.jobId })
        }
      }
      return
    }

    const targetJobId =
      analysisStore.jobId ??
      analysisStore.candidateJobs[0]?.id ??
      null

    if (!targetJobId) {
      errorMessage.value = '缺少目标岗位上下文，请先回到数据输入中心完成分析'
      return
    }

    const graph = await fetchJobGraph(targetJobId)
    const seedById = new Map<number, JobItem>()
    const seedByName = new Map<string, JobItem>()
    analysisStore.candidateJobs.forEach((job) => {
      seedById.set(job.id, job)
      seedByName.set(normalizeName(job.name), job)
    })

    const graphJobs: JobPortraitCard[] = []
    const seenUid = new Set<string>()
    graph.nodes.forEach((node, index) => {
      const uid = (node.id || `${node.label}-${index}`).trim()
      if (!uid || seenUid.has(uid)) {
        return
      }
      seenUid.add(uid)
      const jobId = tryExtractJobId(node.id)
      const seed =
        (jobId ? seedById.get(jobId) : undefined) ??
        seedByName.get(normalizeName(node.label))

      graphJobs.push({
        uid,
        jobId,
        name: node.label || seed?.name || `岗位节点 ${index + 1}`,
        match: seed?.match ?? (node.type === 'target' ? 100 : 0),
        company: seed?.company ?? '',
        industry: seed?.industry ?? '',
        salaryRange: node.salaryRange || seed?.salaryRange || '',
        requiredSkills: (node.coreSkills?.length ? node.coreSkills : seed?.requiredSkills) ?? [],
        requiredCerts: seed?.requiredCerts ?? [],
        softSkills: seed?.softSkills ?? [],
        abilityDimensions: seed?.abilityDimensions ?? {
          innovation: 0,
          learning: 0,
          stressTolerance: 0,
          communication: 0,
          internship: 0
        },
        highlights: seed?.highlights ?? []
        ,
        description: seed?.description ?? ''
      })
    })

    const orderedGraphJobs = [
      ...graphJobs.filter((job) => job.jobId === targetJobId),
      ...graphJobs.filter((job) => job.jobId !== targetJobId)
    ].slice(0, 10)

    const hydratedGraphJobs = await Promise.all(
      orderedGraphJobs.map(async (job) => {
        if (!job.jobId) {
          return job
        }

        try {
          const profile = await fetchJobProfile(job.jobId)
          return {
            ...job,
            name: profile.name || job.name,
            company: profile.company || job.company,
            industry: profile.industry || job.industry,
            requiredSkills: profile.requiredSkills.length ? profile.requiredSkills : job.requiredSkills,
            requiredCerts: profile.requiredCerts.length ? profile.requiredCerts : job.requiredCerts,
            softSkills: profile.softSkills.length ? profile.softSkills : job.softSkills,
            abilityDimensions: profile.abilityDimensions,
            highlights: profile.highlights.length ? profile.highlights : job.highlights,
            description: profile.description || job.description
          }
        } catch {
          return job
        }
      })
    )

    const showcasedGraphJobs = applyFrontendShowcasePreset(
      hydratedGraphJobs,
      targetJobId,
      formatJobName(seedById.get(targetJobId)?.name ?? hydratedGraphJobs[0]?.name ?? '')
    )

    graphJobProfiles.value = showcasedGraphJobs

    const candidateTopJobs: JobItem[] = showcasedGraphJobs
      .filter((item): item is typeof item & { jobId: number } => item.jobId !== null)
      .map((item) => {
        const seeded = seedById.get(item.jobId)
        return (
          seeded ?? {
            id: item.jobId,
            name: item.name,
            match: item.match,
            company: item.company,
            industry: item.industry,
            salaryRange: item.salaryRange,
            requiredSkills: item.requiredSkills,
            requiredCerts: item.requiredCerts,
            softSkills: item.softSkills,
            abilityDimensions: item.abilityDimensions,
            highlights: item.highlights,
            description: item.description
          }
        )
      })
    analysisStore.setCandidateJobs(candidateTopJobs)

    if (!analysisStore.jobId && candidateTopJobs[0]) {
      analysisStore.setContext({ jobId: candidateTopJobs[0].id })
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载岗位画像失败'
  } finally {
    jobsLoading.value = false
  }
}

const handleRefreshJobs = (): void => {
  void fetchJobs(true)
}

const selectTargetJob = async (job: { jobId: number | null; name: string }): Promise<void> => {
  if (!job.jobId) {
    ElMessage.warning('该图谱节点缺少岗位 ID，暂不支持设为目标')
    return
  }

  if (analysisStore.jobId === job.jobId) {
    return
  }

  analysisStore.setContext({ jobId: job.jobId })

  if (!analysisStore.studentId) {
    ElMessage.warning('缺少学生画像上下文，已切换目标岗位，请先返回数据输入中心完成分析')
    return
  }

  try {
    loading.value = true
    const result = await matchingAnalyze({
      studentId: analysisStore.studentId,
      jobId: job.jobId
    })
    analysisStore.setMatchScore(result.matchScore)
    analysisStore.setRadarData(result.radarIndicators, result.radarSeries)
    analysisStore.setInsights(result.strengths, result.gaps)
    if (result.reportId) {
      analysisStore.setContext({ reportId: result.reportId })
    }
    await fetchJobs(true)
    renderGauge()
    ElMessage.success(`已切换目标岗位：${job.name}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '切换岗位失败'
  } finally {
    loading.value = false
  }
}

const jumpToAnalysis = async (job: { jobId: number | null }): Promise<void> => {
  if (!job.jobId || analysisStore.jobId !== job.jobId) {
    ElMessage.warning('仅支持从目标岗位卡片进入职业分析图谱，请先点击“设为目标”')
    return
  }

  analysisStore.grantPathAccess(job.jobId)
  await router.push({
    path: '/app/path',
    query: { jobId: String(job.jobId) }
  })
}

const checkGraphCompliance = async (): Promise<void> => {
  const backendReadyJobs = jobProfiles.value.filter((job) => !!job.jobId).map((job) => job.jobId as number)
  if (backendReadyJobs.length < 5) {
    complianceResult.value = `当前仅 ${backendReadyJobs.length} 个岗位具备可校验 job_id，不满足“至少5个可换岗岗位”校验条件。`
    return
  }

  try {
    complianceLoading.value = true
    const graphs = await Promise.all(backendReadyJobs.map((jobId) => fetchJobGraph(jobId)))
    const switchableCount = graphs.filter((graph) => graph.nodes.filter((node) => node.type === 'horizontal').length >= 2).length
    const detailReady = graphs.every((graph) =>
      graph.nodes.every((node) => Boolean(node.jobDescription && node.salaryRange && (node.coreSkills?.length ?? 0) > 0))
    )

    const switchablePass = switchableCount >= 5
    complianceResult.value = `换岗路径达标岗位数：${switchableCount}/${backendReadyJobs.length}（要求至少5个岗位且每个不少于2条）；节点详情完整：${detailReady ? '是' : '否'}`

    if (switchablePass && detailReady) {
      ElMessage.success('图谱约束校验通过')
    } else {
      ElMessage.warning('图谱约束未完全通过，请补充后端图谱数据')
    }
  } catch (error) {
    complianceResult.value = error instanceof Error ? error.message : '图谱约束校验失败'
  } finally {
    complianceLoading.value = false
  }
}

const handleResize = (): void => {
  gaugeChart?.resize()
  wordCloudChart?.resize()
}

onMounted(async () => {
  await fetchJobs(true)
  if (!analysisStore.hasRadar && analysisStore.studentId && analysisStore.jobId) {
    await refreshRadar()
  }
  renderGauge()
  await nextTick()
  renderWordCloud()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  gaugeChart?.dispose()
  wordCloudChart?.dispose()
  gaugeChart = null
  wordCloudChart = null
})

watch(
  () => [wordCloudData.value, isWordCloudView.value],
  async () => {
    if (!isWordCloudView.value) {
      return
    }
    await nextTick()
    renderWordCloud()
  },
  { deep: true }
)
</script>

<style scoped>
.analysis-board {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.page-head h2 {
  margin: 0 0 6px;
  font-size: 24px;
  color: #1f2a3f;
}

.page-head p {
  margin: 0;
  color: #7a859c;
  font-size: 15px;
}

.panel {
  border-radius: 18px;
  border: 1px solid #e4e8f0;
  background: #ffffff;
}

.summary {
  min-height: 420px;
}

.summary-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.7fr);
  gap: 28px;
  align-items: stretch;
}

.summary-main {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.summary-rank {
  border-left: 1px solid #e8ebf3;
  padding-left: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  justify-content: center;
}

.summary-rank-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.summary-rank-head h3 {
  margin: 0;
  font-size: 20px;
  color: #1f2a3f;
}

.summary-rank-head span {
  font-size: 13px;
  color: #7a859c;
}

.rank-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rank-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid #e4e8f0;
  background: linear-gradient(180deg, #fbfcff 0%, #f5f8ff 100%);
}

.rank-item.active {
  border-color: #5f5ee7;
  box-shadow: 0 0 0 2px rgba(95, 94, 231, 0.08);
}

.rank-index {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: linear-gradient(180deg, #eef2ff 0%, #dfe7ff 100%);
  color: #4f46e5;
  font-size: 18px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.rank-body {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rank-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.rank-title-row strong {
  min-width: 0;
  color: #1f2a3f;
  font-size: 16px;
}

.rank-score {
  flex: none;
  color: #4f46e5;
  font-weight: 700;
  font-size: 16px;
}

.rank-body p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}

.rank-bar {
  position: relative;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: #e5eaf4;
}

.rank-bar-fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
  background: linear-gradient(90deg, #818cf8 0%, #38bdf8 100%);
}

.gauge {
  width: min(100%, 500px);
  height: 320px;
}

.target-role {
  margin: 4px 0 0;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  color: #2e3648;
  padding: 10px 16px;
  border-radius: 999px;
  background: #f4f7ff;
}

.target-role strong {
  color: #5f5ee7;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.head-actions {
  display: flex;
  gap: 8px;
}

.compliance {
  margin: 0 0 12px;
  font-size: 13px;
  color: #475569;
}

.job-wordcloud {
  width: 100%;
  height: 560px;
  border: 1px solid #e2e6ef;
  border-radius: 14px;
  background: linear-gradient(180deg, #fafbff 0%, #ffffff 60%);
}

.job-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}

.job-card {
  border: 1px solid #e2e6ef;
  border-radius: 14px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background:
    linear-gradient(180deg, rgba(248, 250, 255, 0.9) 0%, rgba(255, 255, 255, 0.98) 100%);
}

.job-card.active {
  border-color: #5f5ee7;
  box-shadow: 0 0 0 2px rgba(95, 94, 231, 0.1);
}

.job-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.job-title-group {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.job-head h4 {
  margin: 0;
  font-size: 16px;
  color: #1f2a3f;
}

.job-match {
  flex: none;
  min-width: 58px;
  padding: 7px 10px;
  border-radius: 12px;
  background: linear-gradient(180deg, #f2fdf4 0%, #eefbf0 100%);
  color: #4caf50;
  font-size: 22px;
  line-height: 1;
  font-weight: 700;
  text-align: center;
}

.job-meta {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.5;
}

.job-progress {
  display: flex;
  align-items: center;
  gap: 10px;
}

.job-progress-bar {
  position: relative;
  flex: 1;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: #e7ecf5;
}

.job-progress-fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
  background: linear-gradient(90deg, #60a5fa 0%, #34d399 100%);
}

.job-progress-text {
  flex: none;
  font-size: 12px;
  color: #64748b;
}

.job-summary {
  margin: 0;
  color: #334155;
  font-size: 13px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.portrait-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.job-portrait-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  align-items: start;
}

.portrait-label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  letter-spacing: 0.04em;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 24px;
}

.tag-row :deep(.el-tag) {
  max-width: 100%;
  height: auto;
  white-space: normal;
  line-height: 1.35;
  padding-top: 6px;
  padding-bottom: 6px;
}

.tag-row :deep(.el-tag__content) {
  display: inline-block;
  white-space: normal;
  word-break: break-word;
}

.dimension-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 28px;
}

.dimension-chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 12px;
  line-height: 1;
}

.empty-inline {
  font-size: 12px;
  color: #94a3b8;
}

.job-actions {
  display: flex;
  gap: 8px;
  margin-top: auto;
}

@media (max-width: 720px) {
  .summary-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .summary-rank {
    border-left: 0;
    border-top: 1px solid #e8ebf3;
    padding-left: 0;
    padding-top: 20px;
  }

  .job-portrait-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .job-match {
    font-size: 18px;
    min-width: 52px;
  }
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 22px;
}

.panel h3 {
  margin: 0 0 16px;
  font-size: 22px;
  color: #1f2a3f;
}

.gap-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.gap-item {
  border: 1px solid #e2e6ef;
  border-radius: 14px;
  padding: 18px;
  display: flex;
  gap: 14px;
}

.gap-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #eef1ff;
  color: #6862f5;
}

.gap-content {
  flex: 1;
}

.gap-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.gap-title-row h4 {
  margin: 0;
  font-size: 19px;
}

.gap-content p {
  margin: 0 0 8px;
  font-size: 14px;
  color: #6c768d;
  line-height: 1.55;
}

.gap-content a {
  color: #5f5ee7;
  font-weight: 600;
  text-decoration: none;
}

.dialog-title {
  margin: 0;
  font-size: 18px;
}

.dialog-desc,
.dialog-meta {
  color: #475569;
  line-height: 1.6;
}

.dialog-block {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.dialog-block.dimensions span {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 12px;
}

.error-alert {
  margin-bottom: 4px;
}

@media (max-width: 1100px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
