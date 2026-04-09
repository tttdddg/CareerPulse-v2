<template>
  <div class="path-page">
    <el-alert
      v-if="errorMessage"
      type="error"
      :title="errorMessage"
      show-icon
      class="error-alert"
      @close="errorMessage = ''"
    />

    <header class="page-head">
      <h2>职业发展路径图谱</h2>
      <p>先浏览全岗位关系图谱，点击任意岗位节点后，在下方左右查看该岗位的晋升与换岗路径。</p>
      <div class="head-metrics">
        <div class="metric-card">
          <span>总图节点</span>
          <strong>{{ overviewGraphData.nodes.length }}</strong>
        </div>
        <div class="metric-card">
          <span>总图关系</span>
          <strong>{{ overviewGraphData.edges.length }}</strong>
        </div>
        <div class="metric-card">
          <span>候选岗位</span>
          <strong>{{ candidateJobCount }}</strong>
        </div>
        <div class="metric-card metric-card-role">
          <span>当前岗位</span>
          <strong>{{ selectedJobLabel || '请先点击岗位节点' }}</strong>
        </div>
      </div>
    </header>

    <el-card class="panel graph-panel" v-loading="loading">
      <div class="panel-head">
        <h3>岗位关系总图谱</h3>
        <div class="panel-actions">
          <span class="hint">点击任意岗位节点，会自动展开下方的晋升/换岗路径</span>
          <el-button type="primary" plain size="small" @click="reloadGraph">刷新总图</el-button>
        </div>
      </div>
      <div class="legend-list">
        <div class="legend-item">
          <i class="dot dot-target"></i>
          <span>图谱中心</span>
        </div>
        <div class="legend-item">
          <i class="dot dot-job"></i>
          <span>岗位节点</span>
        </div>
      </div>
      <path-graph
        :nodes="overviewGraphData.nodes"
        :edges="overviewGraphData.edges"
        :height="640"
        variant="knowledge"
        @node-click="onOverviewNodeClick"
      />
    </el-card>

    <section v-if="selectedGraphLoaded" class="path-layout">
      <el-card class="panel graph-panel" v-loading="selectedLoading">
        <div class="panel-head">
          <h3>{{ selectedJobLabel }} · 路径拆解</h3>
          <div class="panel-actions">
            <span class="hint">左右图均可点击节点，右侧详情会同步更新</span>
            <el-button type="primary" plain size="small" :loading="selectedLoading" @click="reloadSelectedGraph">
              刷新当前岗位
            </el-button>
          </div>
        </div>
        <div class="legend-list">
          <div class="legend-item">
            <i class="dot dot-target"></i>
            <span>目标岗位</span>
          </div>
          <div class="legend-item">
            <i class="dot dot-vertical"></i>
            <span>晋升路径</span>
          </div>
          <div class="legend-item">
            <i class="dot dot-horizontal"></i>
            <span>换岗路径</span>
          </div>
        </div>
        <div class="split-graphs" v-if="selectedGraphData.nodes.length">
          <section class="split-graph-col split-graph-vertical">
            <div class="split-graph-head">
              <h4>晋升图谱</h4>
              <span class="split-graph-sub">纵向能力成长路径</span>
            </div>
            <path-graph
              :nodes="verticalGraphData.nodes"
              :edges="verticalGraphData.edges"
              :height="760"
              variant="knowledge"
              @node-click="onPathNodeClick"
            />
          </section>
          <section class="split-graph-col split-graph-horizontal">
            <div class="split-graph-head">
              <h4>换岗图谱</h4>
              <span class="split-graph-sub">横向岗位迁移路径</span>
            </div>
            <path-graph
              :nodes="horizontalGraphData.nodes"
              :edges="horizontalGraphData.edges"
              :height="760"
              variant="knowledge"
              @node-click="onPathNodeClick"
            />
          </section>
        </div>
        <el-empty v-else description="该岗位暂无可用路径图谱" />
      </el-card>

      <el-card class="panel detail-panel">
        <div class="detail-head">
          <h3>{{ activeNode?.label || '节点详情' }}</h3>
          <span class="relation-chip">{{ relationText(activeNode?.type, activeNode?.relation) }}</span>
        </div>
        <p class="desc">
          {{
            activeNode
              ? `已选节点：${activeNode.label}。建议优先补齐「${analysisStore.gaps[0] ?? '关键能力'}」相关能力。`
              : '点击图谱中的岗位节点可查看岗位描述、核心技能和薪资范围。'
          }}
        </p>

        <div v-if="activeNode" class="detail-info">
          <div class="info-card">
            <span class="label">岗位描述</span>
            <p>{{ activeNode.jobDescription || '暂未返回' }}</p>
          </div>
          <div class="info-grid">
            <div class="info-card">
              <span class="label">薪资范围</span>
              <p>{{ activeNode.salaryRange || '暂未返回' }}</p>
            </div>
            <div class="info-card">
              <span class="label">节点 ID</span>
              <p>{{ activeNode.id }}</p>
            </div>
          </div>
        </div>

        <div class="tag-list">
          <el-tag v-for="tag in nodeTags" :key="tag" effect="plain" class="skill-tag">{{ tag }}</el-tag>
        </div>
      </el-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAnalysisStore } from '../../stores/analysis'
import PathGraph, { type PathNode } from '../../components/business/PathGraph.vue'
import { fetchJobGraph, fetchJobProfile } from '../../api/modules/career'

interface GraphNode {
  id: string
  label: string
  x?: number
  y?: number
  type?: string
  relation?: string
  relationStrength?: number
  jobDescription?: string
  coreSkills?: string[]
  salaryRange?: string
}

interface GraphEdge {
  source: string
  target: string
  label?: string
  type?: 'vertical' | 'horizontal' | 'target'
  weight?: number
}

const analysisStore = useAnalysisStore()
const router = useRouter()
const loading = ref(false)
const selectedLoading = ref(false)
const errorMessage = ref('')
const overviewGraphData = ref<{ nodes: GraphNode[]; edges: GraphEdge[] }>({ nodes: [], edges: [] })
const selectedGraphData = ref<{ nodes: GraphNode[]; edges: GraphEdge[] }>({ nodes: [], edges: [] })
const selectedJobId = ref<number | null>(null)
const selectedJobLabel = ref('')
const activeNode = ref<GraphNode | null>(null)

const selectedGraphLoaded = computed(() => selectedJobId.value !== null)
const candidateJobCount = computed(() => analysisStore.candidateJobs.length)

const inferEdgeType = (edge: GraphEdge): 'vertical' | 'horizontal' | 'target' => {
  if (edge.type === 'horizontal' || edge.type === 'target') {
    return edge.type
  }
  const label = `${edge.label ?? ''}`.trim()
  if (/转岗|横向|平级|跨岗|换岗|lateral|transfer|cross/i.test(label)) {
    return 'horizontal'
  }
  if (/目标|target/i.test(label)) {
    return 'target'
  }
  return 'vertical'
}

const splitGraphByType = (type: 'vertical' | 'horizontal'): { nodes: GraphNode[]; edges: GraphEdge[] } => {
  const target = selectedGraphData.value.nodes.find((node) => node.type === 'target') ?? selectedGraphData.value.nodes[0]
  if (!target) {
    return { nodes: [], edges: [] }
  }

  const selectedEdges = selectedGraphData.value.edges.filter((edge) => inferEdgeType(edge) === type)
  const nodeIds = new Set<string>([target.id])
  selectedEdges.forEach((edge) => {
    nodeIds.add(edge.source)
    nodeIds.add(edge.target)
  })

  const selectedNodes = selectedGraphData.value.nodes
    .filter((node) => nodeIds.has(node.id))
    .map((node) => {
      if (node.id === target.id) {
        return { ...node, type: 'target' as const, x: undefined, y: undefined }
      }
      return {
        ...node,
        type: type === 'vertical' ? ('vertical' as const) : ('horizontal' as const),
        x: undefined,
        y: undefined
      }
    })

  if (type === 'vertical') {
    const orderSeed = selectedGraphData.value.nodes
      .map((node, index) => ({ id: node.id, index, y: node.y }))
      .reduce<Record<string, { index: number; y?: number }>>((acc, item) => {
        acc[item.id] = { index: item.index, y: item.y }
        return acc
      }, {})

    const verticalNodes = selectedNodes
      .filter((node) => node.id !== target.id)
      .sort((a, b) => {
        const ay = orderSeed[a.id]?.y
        const by = orderSeed[b.id]?.y
        if (typeof ay === 'number' && typeof by === 'number' && ay !== by) {
          return ay - by
        }
        return (orderSeed[a.id]?.index ?? 0) - (orderSeed[b.id]?.index ?? 0)
      })

    const chainEdges: GraphEdge[] = []
    if (verticalNodes.length > 0) {
      chainEdges.push({
        source: target.id,
        target: verticalNodes[0].id,
        type: 'vertical'
      })
      for (let i = 1; i < verticalNodes.length; i += 1) {
        chainEdges.push({
          source: verticalNodes[i - 1].id,
          target: verticalNodes[i].id,
          type: 'vertical'
        })
      }
    }

    return { nodes: selectedNodes, edges: chainEdges }
  }

  return { nodes: selectedNodes, edges: selectedEdges.map((edge) => ({ ...edge, type })) }
}

const verticalGraphData = computed(() => splitGraphByType('vertical'))
const horizontalGraphData = computed(() => splitGraphByType('horizontal'))

const nodeTags = computed(() => {
  if (!activeNode.value) {
    return ['等待选择岗位节点']
  }

  const skills = activeNode.value.coreSkills ?? []
  if (skills.length > 0) {
    return skills
  }

  if (activeNode.value.type === 'target') {
    return ['技术领导力', '跨团队协同', '架构设计']
  }

  if (activeNode.value.type === 'horizontal') {
    return ['云原生', 'DevOps', '工程效率']
  }

  return ['编码能力', '测试质量', '业务理解']
})

const relationText = (type?: GraphNode['type'], relation?: string): string => {
  if (relation) {
    return relation
  }
  if (type === 'target') {
    return '目标岗位'
  }
  if (type === 'horizontal') {
    return '换岗路径'
  }
  return '晋升路径'
}

const tryExtractJobId = (nodeId: string): number | null => {
  const direct = Number(nodeId)
  if (Number.isFinite(direct) && direct > 0) {
    return direct
  }

  const matched = nodeId.match(/\d+/)
  if (!matched) {
    return null
  }
  const parsed = Number(matched[0])
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

const patchNodeDetailFromProfile = async (node: GraphNode): Promise<GraphNode> => {
  if (node.jobDescription && node.salaryRange && (node.coreSkills?.length ?? 0) > 0) {
    return node
  }

  const jobId = tryExtractJobId(node.id)
  if (!jobId) {
    return node
  }

  try {
    const profile = await fetchJobProfile(jobId)
    return {
      ...node,
      jobDescription: node.jobDescription || profile.description,
      salaryRange: node.salaryRange || profile.salaryRange,
      coreSkills: (node.coreSkills?.length ?? 0) > 0 ? node.coreSkills : profile.requiredSkills
    }
  } catch {
    return node
  }
}

const buildOverviewGraph = (graphs: Array<{ nodes: GraphNode[]; edges: GraphEdge[] }>): { nodes: GraphNode[]; edges: GraphEdge[] } => {
  const centerId = 'all-jobs-center'
  const centerNode: GraphNode = {
    id: centerId,
    label: '岗位图谱',
    x: 520,
    y: 320,
    type: 'target'
  }

  const jobsById = new Map<number, string>()
  const jobsByName = new Set<string>()

  graphs.forEach((graph) => {
    graph.nodes.forEach((node) => {
      const jobId = tryExtractJobId(node.id)
      if (jobId) {
        if (!jobsById.has(jobId)) {
          jobsById.set(jobId, node.label || `岗位 ${jobId}`)
        }
      } else if (node.label.trim()) {
        jobsByName.add(node.label.trim())
      }
    })
  })

  analysisStore.candidateJobs.forEach((job) => {
    if (!jobsById.has(job.id)) {
      jobsById.set(job.id, job.name)
    }
  })

  const jobNodes: GraphNode[] = [
    ...[...jobsById.entries()].map(([jobId, name]) => ({ id: `job-${jobId}`, label: name, type: 'horizontal' as const })),
    ...[...jobsByName.values()].map((name) => ({ id: `job-name-${name}`, label: name, type: 'horizontal' as const }))
  ].slice(0, 24)

  const radiusX = 380
  const radiusY = 250
  const withPositions = jobNodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(jobNodes.length, 1)
    return {
      ...node,
      x: 520 + Math.round(Math.cos(angle) * radiusX),
      y: 320 + Math.round(Math.sin(angle) * radiusY)
    }
  })

  return {
    nodes: [centerNode, ...withPositions],
    edges: withPositions.map((node) => ({
      source: centerId,
      target: node.id,
      label: '关联',
      type: 'target'
    }))
  }
}

const loadSelectedGraph = async (jobId: number): Promise<void> => {
  try {
    selectedLoading.value = true
    const data = await fetchJobGraph(jobId)
    selectedGraphData.value = data

    if (!data.nodes.length || !data.edges.length) {
      errorMessage.value = '后端未返回完整路径数据，请补齐岗位关联图谱后重试'
      activeNode.value = null
      return
    }

    errorMessage.value = ''
    const targetNode = data.nodes.find((item) => item.type === 'target') ?? data.nodes[0]
    activeNode.value = await patchNodeDetailFromProfile(targetNode)
    selectedJobId.value = jobId
    selectedJobLabel.value = targetNode.label || `岗位 ${jobId}`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '岗位路径加载失败'
  } finally {
    selectedLoading.value = false
  }
}

const reloadSelectedGraph = async (): Promise<void> => {
  if (!selectedJobId.value) {
    return
  }
  await loadSelectedGraph(selectedJobId.value)
}

const reloadGraph = async (): Promise<void> => {
  const jobIds = [
    ...new Set(
      analysisStore.candidateJobs
        .map((job) => job.id)
        .filter((id): id is number => Number.isFinite(id) && id > 0)
    )
  ]

  if (!jobIds.length && !analysisStore.jobId) {
    errorMessage.value = '未找到岗位上下文，请先回到数据输入中心完成分析'
    return
  }

  const idsToLoad = jobIds.length ? jobIds : [analysisStore.jobId as number]

  try {
    loading.value = true
    const results = await Promise.allSettled(idsToLoad.map((jobId) => fetchJobGraph(jobId)))
    const graphs = results.flatMap((item) => (item.status === 'fulfilled' ? [item.value] : []))

    if (!graphs.length) {
      errorMessage.value = '未拉取到岗位图谱数据，请稍后重试'
      return
    }

    overviewGraphData.value = buildOverviewGraph(graphs)
    errorMessage.value = ''

    const defaultJobId = analysisStore.jobId && idsToLoad.includes(analysisStore.jobId) ? analysisStore.jobId : idsToLoad[0]
    if (defaultJobId) {
      await loadSelectedGraph(defaultJobId)
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '图谱加载失败'
  } finally {
    loading.value = false
  }
}

const handleOverviewNodeClick = async (node: PathNode): Promise<void> => {
  const parsedNode = node as GraphNode
  if (parsedNode.id === 'all-jobs-center') {
    return
  }

  const fromNodeId = tryExtractJobId(parsedNode.id)
  const fromName = analysisStore.candidateJobs.find((job) => job.name === parsedNode.label)?.id ?? null
  const jobId = fromNodeId ?? fromName

  if (!jobId) {
    ElMessage.warning('该节点未绑定可用岗位 ID')
    return
  }

  await loadSelectedGraph(jobId)
  ElMessage.success(`已选择岗位：${parsedNode.label}`)
}

const handleNodeClick = async (node: PathNode): Promise<void> => {
  const parsedNode = node as GraphNode
  activeNode.value = await patchNodeDetailFromProfile(parsedNode)
  ElMessage.info(`已选择 ${parsedNode.label}`)
}

const onOverviewNodeClick = (node: PathNode): void => {
  void handleOverviewNodeClick(node)
}

const onPathNodeClick = (node: PathNode): void => {
  void handleNodeClick(node)
}

onMounted(async () => {
  if (!analysisStore.hasRadar) {
    ElMessage.warning('尚未完成分析，已为你跳转到数据输入中心')
    await router.replace('/app/input')
    return
  }
  await reloadGraph()
})
</script>

<style scoped>
.path-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 8px;
  border-radius: 24px;
  font-family: 'Outfit', 'DIN Alternate', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.page-head {
  text-align: center;
  max-width: 1200px;
  margin: 0 auto;
  padding: 8px 16px 2px;
}

.page-head h2 {
  margin: 0;
  font-size: 30px;
  color: #0f254e;
  letter-spacing: 0.01em;
}

.page-head p {
  margin: 12px 0 0;
  font-size: 15px;
  color: #4f5f82;
  line-height: 1.45;
}

.head-metrics {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  padding: 12px 10px;
  border-radius: 14px;
  border: 1px solid rgba(84, 123, 217, 0.2);
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.95), rgba(242, 248, 255, 0.92));
  box-shadow: 0 10px 30px rgba(63, 100, 180, 0.08);
}

.metric-card span {
  display: block;
  font-size: 12px;
  color: #5b6e95;
}

.metric-card strong {
  display: block;
  margin-top: 6px;
  font-size: 24px;
  color: #123467;
}

.metric-card-role strong {
  font-size: 16px;
  line-height: 1.4;
}

.path-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.55fr);
  gap: 18px;
  align-items: start;
}

.panel {
  border-radius: 20px;
  border: 1px solid rgba(133, 162, 224, 0.24);
  background: linear-gradient(170deg, rgba(255, 255, 255, 0.95), rgba(246, 250, 255, 0.92));
  box-shadow: 0 22px 44px rgba(69, 96, 152, 0.12);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.panel-head h3 {
  margin: 0;
  font-size: 20px;
  color: #173464;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hint {
  font-size: 12px;
  color: #5e739f;
}

.legend-list {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 14px;
  margin-bottom: 14px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #50668e;
  font-size: 13px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.dot-target {
  background: linear-gradient(130deg, #f59e0b, #f97316);
}

.dot-job {
  background: linear-gradient(130deg, #2563eb, #4f46e5);
}

.dot-vertical {
  background: linear-gradient(130deg, #2563eb, #4f46e5);
}

.dot-horizontal {
  background: linear-gradient(130deg, #2563eb, #4f46e5);
}

.graph-panel :deep(.path-graph) {
  border: 0;
  border-radius: 16px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(248, 251, 255, 0.9)),
    radial-gradient(circle at 0% 100%, rgba(114, 160, 255, 0.08), transparent 45%);
}

.split-graphs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.split-graph-col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px;
  border-radius: 16px;
  border: 1px solid rgba(128, 155, 216, 0.3);
  box-shadow: 0 12px 28px rgba(60, 95, 162, 0.09);
}

.split-graph-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding: 2px 2px 0;
}

.split-graph-col h4 {
  margin: 0;
  font-size: 17px;
  color: #204173;
}

.split-graph-sub {
  font-size: 12px;
  color: #5a729f;
}

.split-graph-vertical {
  border-color: rgba(77, 119, 211, 0.34);
}

.split-graph-horizontal {
  border-color: rgba(17, 152, 166, 0.34);
}

.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.detail-head h3 {
  margin: 0;
  font-size: 22px;
  color: #173464;
}

.relation-chip {
  padding: 5px 11px;
  border-radius: 999px;
  font-size: 12px;
  color: #1852bf;
  border: 1px solid rgba(33, 100, 226, 0.26);
  background: rgba(229, 239, 255, 0.72);
}

.desc {
  color: #5c6c8c;
  font-size: 14px;
  line-height: 1.7;
  margin: 14px 0;
}

.detail-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 4px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.info-card {
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(120, 150, 219, 0.2);
}

.info-card .label {
  font-size: 12px;
  color: #5c7197;
}

.info-card p {
  margin: 6px 0 0;
  color: #1f3358;
  line-height: 1.55;
  font-size: 14px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.skill-tag {
  border-radius: 999px;
  font-weight: 600;
  padding: 0 10px;
  color: #1b4da2;
  border-color: rgba(62, 112, 215, 0.33);
  background: rgba(235, 244, 255, 0.78);
}

.error-alert {
  margin-bottom: 2px;
}

@media (max-width: 1400px) {
  .head-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1200px) {
  .path-layout {
    grid-template-columns: 1fr;
  }

  .split-graphs {
    grid-template-columns: 1fr;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .path-page {
    padding: 4px;
  }

  .page-head {
    padding: 0 6px;
  }

  .page-head h2 {
    font-size: 24px;
  }

  .head-metrics {
    grid-template-columns: 1fr;
  }

  .panel-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
