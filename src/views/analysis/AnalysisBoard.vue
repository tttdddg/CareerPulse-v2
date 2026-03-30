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
      <div ref="gaugeEl" class="gauge"></div>
      <p class="target-role">
        <el-icon><SuitcaseLine /></el-icon>
        <span>当前目标岗位:</span>
        <strong>{{ currentJob?.name || '未选择岗位' }}</strong>
      </p>
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
            <h4>{{ job.name }}</h4>
            <el-tag type="success">{{ Math.round(job.match || 0) }}%</el-tag>
          </div>
          <p class="job-meta">{{ job.company || '企业信息待补充' }} · {{ job.industry || '行业未知' }}</p>
          <p class="job-meta">薪资：{{ job.salaryRange || '待补充' }}</p>
          <div class="tag-row">
            <el-tag v-for="tag in (job.requiredSkills.length ? job.requiredSkills.slice(0, 3) : job.highlights.slice(0, 3))" :key="tag" effect="plain">
              {{ tag }}
            </el-tag>
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
import { SuitcaseLine, Warning } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useAnalysisStore } from '../../stores/analysis'
import RadarChart from '../../components/business/RadarChart.vue'
import { fetchJobGraph, matchingAnalyze, type JobItem } from '../../api/modules/career'

const router = useRouter()
const analysisStore = useAnalysisStore()
const loading = ref(false)
const jobsLoading = ref(false)
const complianceLoading = ref(false)
const errorMessage = ref('')
const complianceResult = ref('')
const graphJobProfiles = ref<
  Array<{
    uid: string
    jobId: number | null
    name: string
    match: number
    company: string
    industry: string
    salaryRange: string
    requiredSkills: string[]
    highlights: string[]
  }>
>([])

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

const getGapDesc = (gap: string): string => {
  return `当前在「${gap}」维度仍有提升空间，建议通过专项练习与项目实践快速补强。`
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
        data: [{ value: analysisStore.matchScore || 0 }]
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

    const graphJobs: Array<{
      uid: string
      jobId: number | null
      name: string
      match: number
      company: string
      industry: string
      salaryRange: string
      requiredSkills: string[]
      highlights: string[]
    }> = []
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
        highlights: seed?.highlights ?? []
      })
    })

    const orderedGraphJobs = [
      ...graphJobs.filter((job) => job.jobId === targetJobId),
      ...graphJobs.filter((job) => job.jobId !== targetJobId)
    ].slice(0, 10)

    graphJobProfiles.value = orderedGraphJobs

    const candidateTopJobs: JobItem[] = orderedGraphJobs
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
            requiredCerts: [],
            softSkills: [],
            abilityDimensions: {
              innovation: 0,
              learning: 0,
              stressTolerance: 0,
              communication: 0,
              internship: 0
            },
            highlights: item.highlights,
            description: ''
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
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 420px;
}

.gauge {
  width: min(100%, 500px);
  height: 320px;
}

.target-role {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  color: #2e3648;
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
  gap: 10px;
}

.job-card.active {
  border-color: #5f5ee7;
  box-shadow: 0 0 0 2px rgba(95, 94, 231, 0.1);
}

.job-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.job-head h4 {
  margin: 0;
  font-size: 16px;
  color: #1f2a3f;
}

.job-meta {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 28px;
}

.job-actions {
  display: flex;
  gap: 8px;
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
