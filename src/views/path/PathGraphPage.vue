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
      <p>
        探索从 <strong>{{ targetRole }}</strong> 出发的职业可能性。向上查看晋升路径，向两侧探索转岗机会。
      </p>
    </header>

    <section class="path-layout">
      <el-card class="panel graph-panel" v-loading="loading">
        <path-graph :nodes="graphData.nodes" :edges="graphData.edges" :height="760" @node-click="handleNodeClick" />
      </el-card>

      <el-card class="panel detail-panel">
        <div class="detail-head">
          <h3>{{ activeNode?.label || '节点详情' }}</h3>
          <el-button type="primary" plain size="small" @click="reloadGraph">刷新路径</el-button>
        </div>
        <p class="desc">
          {{
            activeNode
              ? `已选节点：${activeNode.label}。建议优先补齐「${analysisStore.gaps[0] ?? '关键能力'}」相关能力。`
              : '点击图谱中的岗位节点可查看描述、建议技能和职业发展提示。'
          }}
        </p>

        <div class="tag-list">
          <el-tag v-for="tag in nodeTags" :key="tag" effect="plain">{{ tag }}</el-tag>
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
import { fetchJobGraph } from '../../api/modules/career'

interface GraphNode {
  id: string
  label: string
  x?: number
  y?: number
  type?: 'vertical' | 'horizontal' | 'target'
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

const targetRole = computed(() => {
  const latestTitle = historyStore.latestReport?.title ?? ''
  if (!latestTitle) {
    return '目标岗位'
  }
  return latestTitle.replace('匹配报告', '').trim()
})

const nodeTags = computed(() => {
  if (!activeNode.value) {
    return ['Docker', 'Kubernetes', '系统设计', '协作沟通']
  }

  if (activeNode.value.type === 'target') {
    return ['技术领导力', '跨团队协同', '架构设计']
  }

  if (activeNode.value.type === 'horizontal') {
    return ['云原生', 'DevOps', '工程效率']
  }

  return ['编码能力', '测试质量', '业务理解']
})

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
      errorMessage.value = '后端暂未返回完整图谱数据，当前展示默认路径示意图'
    } else {
      errorMessage.value = ''
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '路径图谱加载失败'
  } finally {
    loading.value = false
  }
}

const handleNodeClick = (node: GraphNode): void => {
  activeNode.value = node
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
}

.page-head {
  text-align: center;
  max-width: 980px;
  margin: 0 auto;
}

.page-head h2 {
  margin: 0;
  font-size: 24px;
  color: #12233d;
}

.page-head p {
  margin: 12px 0 0;
  font-size: 15px;
  color: #687691;
  line-height: 1.45;
}

.page-head strong {
  color: #1f5de6;
}

.path-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.5fr);
  gap: 18px;
  align-items: start;
}

.panel {
  border-radius: 18px;
  border: 1px solid #e3e7f0;
}

.graph-panel :deep(.path-graph) {
  border: 0;
  border-radius: 12px;
  background: #fcfdff;
}

.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.detail-head h3 {
  margin: 0;
  font-size: 20px;
}

.desc {
  color: #6c7790;
  font-size: 14px;
  line-height: 1.7;
  margin: 14px 0;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.error-alert {
  margin-bottom: 2px;
}

@media (max-width: 1200px) {
  .path-layout {
    grid-template-columns: 1fr;
  }
}
</style>
