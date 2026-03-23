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
      <div class="head-badge">CAREER KNOWLEDGE MAP</div>
      <h2>职业发展路径图谱</h2>
      <p>
        探索从 <strong>{{ targetRole }}</strong> 出发的职业可能性。向上查看晋升路径，向两侧探索转岗机会。
      </p>
      <div class="head-metrics">
        <div class="metric-card">
          <span>节点总数</span>
          <strong>{{ graphData.nodes.length }}</strong>
        </div>
        <div class="metric-card">
          <span>连接关系</span>
          <strong>{{ graphData.edges.length }}</strong>
        </div>
        <div class="metric-card">
          <span>晋升节点</span>
          <strong>{{ verticalNodeCount }}</strong>
        </div>
        <div class="metric-card">
          <span>转岗节点</span>
          <strong>{{ horizontalNodeCount }}</strong>
        </div>
      </div>
    </header>

    <section class="path-layout">
      <el-card class="panel graph-panel" v-loading="loading">
        <div class="panel-head">
          <h3>路径关系网络</h3>
          <div class="panel-actions">
            <span class="hint">滚轮 + Ctrl / Cmd 缩放</span>
            <el-button type="primary" plain size="small" @click="reloadGraph">刷新路径</el-button>
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
            <span>转岗路径</span>
          </div>
        </div>
        <path-graph :nodes="graphData.nodes" :edges="graphData.edges" :height="760" @node-click="handleNodeClick" />
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
import { useHistoryStore } from '../../stores/history'
import PathGraph from '../../components/business/PathGraph.vue'
import { fetchJobGraph, fetchJobProfile } from '../../api/modules/career'

interface GraphNode {
  id: string
  label: string
  x?: number
  y?: number
  type?: 'vertical' | 'horizontal' | 'target'
  relation?: string
  jobDescription?: string
  coreSkills?: string[]
  salaryRange?: string
}

interface GraphEdge {
  source: string
  target: string
  label?: string
  type?: 'vertical' | 'horizontal' | 'target'
}

const analysisStore = useAnalysisStore()
const historyStore = useHistoryStore()
const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const graphData = ref<{ nodes: GraphNode[]; edges: GraphEdge[] }>({ nodes: [], edges: [] })
const activeNode = ref<GraphNode | null>(null)

const verticalNodeCount = computed(() => graphData.value.nodes.filter((node) => node.type === 'vertical').length)
const horizontalNodeCount = computed(() => graphData.value.nodes.filter((node) => node.type === 'horizontal').length)

const targetRole = computed(() => {
  const latestTitle = historyStore.latestReport?.title ?? ''
  if (!latestTitle) {
    return '目标岗位'
  }
  return latestTitle.replace('匹配报告', '').trim()
})

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

const reloadGraph = async (): Promise<void> => {
  if (!analysisStore.jobId) {
    errorMessage.value = '未找到目标岗位，请先回到数据输入中心完成分析'
    return
  }

  try {
    loading.value = true
    const data = await fetchJobGraph(analysisStore.jobId)
    graphData.value = data

    if (!data.nodes.length || !data.edges.length) {
      errorMessage.value = '后端未返回完整图谱数据，请补齐岗位关联图谱后重试'
      activeNode.value = null
      return
    }

    errorMessage.value = ''
    const targetNode = data.nodes.find((item) => item.type === 'target') ?? data.nodes[0]
    activeNode.value = await patchNodeDetailFromProfile(targetNode)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '路径图谱加载失败'
  } finally {
    loading.value = false
  }
}

const handleNodeClick = async (node: GraphNode): Promise<void> => {
  activeNode.value = await patchNodeDetailFromProfile(node)
  ElMessage.info(`已选择 ${node.label}`)
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
  background:
    radial-gradient(circle at 12% 0%, rgba(77, 143, 255, 0.14), transparent 38%),
    radial-gradient(circle at 86% 18%, rgba(0, 197, 198, 0.12), transparent 34%),
    linear-gradient(180deg, #f5f8ff 0%, #f8fbff 100%);
  border-radius: 24px;
  font-family: 'Outfit', 'DIN Alternate', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.page-head {
  text-align: center;
  max-width: 1080px;
  margin: 0 auto;
  padding: 8px 16px 2px;
}

.head-badge {
  width: fit-content;
  margin: 0 auto 10px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 11px;
  letter-spacing: 0.12em;
  color: #1250b7;
  border: 1px solid rgba(18, 80, 183, 0.22);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(6px);
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

.page-head strong {
  color: #205fda;
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
  background: linear-gradient(130deg, #154ecc, #3f7bff);
}

.dot-vertical {
  background: linear-gradient(130deg, #295bd1, #67a3ff);
}

.dot-horizontal {
  background: linear-gradient(130deg, #00a9b3, #43d8dc);
}

.graph-panel :deep(.path-graph) {
  border: 0;
  border-radius: 16px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(239, 247, 255, 0.9)),
    radial-gradient(circle at 0% 100%, rgba(114, 160, 255, 0.12), transparent 45%);
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
