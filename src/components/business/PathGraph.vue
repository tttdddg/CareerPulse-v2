<template>
  <div class="path-graph" :style="containerStyle" ref="graphEl"></div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Graph } from '@antv/x6'

export type PathNodeType = 'vertical' | 'horizontal' | 'target'

// 路径节点定义
export interface PathNode {
  id: string
  label: string
  x?: number
  y?: number
  type?: PathNodeType
  meta?: Record<string, string>
}

// 路径连线定义
export interface PathEdge {
  id?: string
  source: string
  target: string
  label?: string
  type?: PathNodeType
}

export interface PathGraphProps {
  nodes?: PathNode[]
  edges?: PathEdge[]
  height?: number | string
}

const props = withDefaults(defineProps<PathGraphProps>(), {
  height: 420
})

const emit = defineEmits<{
  (event: 'node-click', node: PathNode): void
  (event: 'node-hover', node: PathNode): void
}>()

const graphEl = ref<HTMLDivElement | null>(null)
let graph: Graph | null = null

const containerStyle = computed(() => ({
  height: typeof props.height === 'number' ? `${props.height}px` : props.height
}))

const getDefaultData = (): { nodes: PathNode[]; edges: PathEdge[] } => {
  const nodes: PathNode[] = [
    { id: 'n1', label: '助理岗位', x: 60, y: 60, type: 'vertical' },
    { id: 'n2', label: '初级岗位', x: 60, y: 160, type: 'vertical' },
    { id: 'n3', label: '资深岗位', x: 60, y: 260, type: 'vertical' },
    { id: 'n4', label: '管理岗位', x: 60, y: 360, type: 'target' },
    { id: 'n5', label: '横向岗位 A', x: 260, y: 160, type: 'horizontal' },
    { id: 'n6', label: '横向岗位 B', x: 260, y: 260, type: 'horizontal' }
  ]

  const edges: PathEdge[] = [
    { source: 'n1', target: 'n2', type: 'vertical' },
    { source: 'n2', target: 'n3', type: 'vertical' },
    { source: 'n3', target: 'n4', type: 'vertical' },
    { source: 'n2', target: 'n5', type: 'horizontal' },
    { source: 'n3', target: 'n6', type: 'horizontal' }
  ]

  return { nodes, edges }
}

const getNodeStyle = (type: PathNodeType | undefined): { stroke: string; fill: string } => {
  if (type === 'target') {
    return { stroke: '#6366F1', fill: '#EEF2FF' }
  }
  if (type === 'horizontal') {
    return { stroke: '#8B5CF6', fill: '#F5F3FF' }
  }
  return { stroke: '#CBD5F5', fill: '#FFFFFF' }
}

const getEdgeColor = (type: PathNodeType | undefined): string => {
  if (type === 'horizontal') {
    return '#8B5CF6'
  }
  return '#6366F1'
}

const renderGraph = (): void => {
  if (!graphEl.value) {
    return
  }

  if (!graph) {
    graph = new Graph({
      container: graphEl.value,
      background: { color: '#FFFFFF' },
      grid: { size: 12, visible: true, type: 'dot', args: { color: '#EEF2FF' } },
      panning: true,
      mousewheel: { enabled: true, modifiers: ['ctrl', 'meta'] },
      interacting: { nodeMovable: false }
    })

    graph.on('node:mouseenter', ({ node }) => {
      const data = node.getData() as PathNode
      node.attr('body/stroke', '#6366F1')
      node.attr('body/strokeWidth', 2)
      emit('node-hover', data)
    })

    graph.on('node:mouseleave', ({ node }) => {
      const data = node.getData() as PathNode
      const style = getNodeStyle(data.type)
      node.attr('body/stroke', style.stroke)
      node.attr('body/strokeWidth', 1)
    })

    graph.on('node:click', ({ node }) => {
      emit('node-click', node.getData() as PathNode)
    })
  }

  graph.clearCells()

  const { nodes, edges } = props.nodes && props.edges ? { nodes: props.nodes, edges: props.edges } : getDefaultData()

  nodes.forEach((node) => {
    const style = getNodeStyle(node.type)
    graph?.addNode({
      id: node.id,
      x: node.x ?? 0,
      y: node.y ?? 0,
      width: 140,
      height: 44,
      attrs: {
        body: {
          rx: 10,
          ry: 10,
          stroke: style.stroke,
          strokeWidth: 1,
          fill: style.fill
        },
        label: {
          text: node.label,
          fill: '#0F172A',
          fontSize: 13,
          fontWeight: 600
        }
      },
      data: node
    })
  })

  edges.forEach((edge, index) => {
    const color = getEdgeColor(edge.type)
    graph?.addEdge({
      id: edge.id ?? `edge-${index}`,
      source: edge.source,
      target: edge.target,
      router: { name: 'orth' },
      connector: { name: 'rounded' },
      attrs: {
        line: {
          stroke: color,
          strokeWidth: 2,
          targetMarker: {
            name: 'classic',
            size: 8,
            fill: color
          }
        }
      },
      labels: edge.label
        ? [
            {
              attrs: {
                label: { text: edge.label, fill: '#475569', fontSize: 12 },
                body: { fill: '#FFFFFF', stroke: '#E2E8F0' }
              }
            }
          ]
        : undefined
    })
  })
}

const resizeObserver = new ResizeObserver(() => {
  graph?.resize(graphEl.value?.clientWidth ?? 0, graphEl.value?.clientHeight ?? 0)
})

onMounted(() => {
  renderGraph()
  if (graphEl.value) {
    resizeObserver.observe(graphEl.value)
  }
})

onBeforeUnmount(() => {
  resizeObserver.disconnect()
  graph?.dispose()
  graph = null
})

watch(
  () => [props.nodes, props.edges],
  () => renderGraph(),
  { deep: true }
)
</script>

<style scoped>
.path-graph {
  width: 100%;
  border: 1px dashed rgba(99, 102, 241, 0.3);
  border-radius: 16px;
  background: #ffffff;
}
</style>
