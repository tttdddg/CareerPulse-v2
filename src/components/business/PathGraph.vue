<template>
  <div class="path-graph" :style="containerStyle" ref="graphEl"></div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Graph } from '@antv/x6'

export type PathNodeType = 'vertical' | 'horizontal' | 'target'

export interface PathNode {
  id: string
  label: string
  x?: number
  y?: number
  type?: PathNodeType
  meta?: Record<string, string>
}

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

interface NodeStyle {
  stroke: string
  fill: string
  text: string
  badge: string
  shadow: string
}

const getNodeStyle = (type: PathNodeType | undefined): NodeStyle => {
  if (type === 'target') {
    return {
      stroke: '#1D4ED8',
      fill: '#EAF1FF',
      text: '#0B2A62',
      badge: '#D7E6FF',
      shadow: '0 12px 30px rgba(29, 78, 216, 0.18)'
    }
  }
  if (type === 'horizontal') {
    return {
      stroke: '#0E9AA7',
      fill: '#E9FCFD',
      text: '#0D4451',
      badge: '#CEF3F5',
      shadow: '0 12px 30px rgba(14, 154, 167, 0.2)'
    }
  }
  return {
    stroke: '#2F67D8',
    fill: '#F7FAFF',
    text: '#1A386F',
    badge: '#E9F0FF',
    shadow: '0 10px 26px rgba(47, 103, 216, 0.14)'
  }
}

const getEdgeStyle = (type: PathNodeType | undefined): { color: string; dash?: string } => {
  if (type === 'horizontal') {
    return { color: '#0E9AA7', dash: '6 4' }
  }
  if (type === 'target') {
    return { color: '#1D4ED8' }
  }
  return { color: '#2F67D8' }
}

const renderGraph = (): void => {
  if (!graphEl.value) {
    return
  }

  if (!graph) {
    graph = new Graph({
      container: graphEl.value,
      background: {
        color: '#F8FBFF'
      },
      grid: {
        size: 20,
        visible: true,
        type: 'dot',
        args: { color: '#DCE7FA', thickness: 1 }
      },
      panning: true,
      mousewheel: { enabled: true, modifiers: ['ctrl', 'meta'], minScale: 0.65, maxScale: 1.75 },
      interacting: { nodeMovable: false }
    })

    graph.on('node:mouseenter', ({ node }) => {
      const data = node.getData() as PathNode
      const style = getNodeStyle(data.type)
      node.attr('body/stroke', '#0F172A')
      node.attr('body/strokeWidth', 2)
      node.attr('body/filter', {
        name: 'dropShadow',
        args: { dx: 0, dy: 8, blur: 16, color: style.stroke, opacity: 0.26 }
      })
      emit('node-hover', data)
    })

    graph.on('node:mouseleave', ({ node }) => {
      const data = node.getData() as PathNode
      const style = getNodeStyle(data.type)
      node.attr('body/stroke', style.stroke)
      node.attr('body/strokeWidth', 1.2)
      node.attr('body/filter', null)
    })

    graph.on('node:click', ({ node }) => {
      emit('node-click', node.getData() as PathNode)
    })
  }

  graph.clearCells()

  const nodes = (props.nodes ?? []) as PathNode[]
  const edges = (props.edges ?? []) as PathEdge[]

  nodes.forEach((node) => {
    const style = getNodeStyle(node.type)
    const width = node.type === 'target' ? 168 : 150
    const height = node.type === 'target' ? 52 : 46

    graph?.addNode({
      id: node.id,
      x: node.x ?? 0,
      y: node.y ?? 0,
      width,
      height,
      attrs: {
        body: {
          rx: 12,
          ry: 12,
          stroke: style.stroke,
          strokeWidth: 1.2,
          fill: style.fill,
          shadowColor: style.shadow
        },
        label: {
          text: node.label,
          fill: style.text,
          fontSize: node.type === 'target' ? 14 : 13,
          fontWeight: node.type === 'target' ? 700 : 600
        }
      },
      data: node
    })
  })

  edges.forEach((edge, index) => {
    const edgeStyle = getEdgeStyle(edge.type)

    graph?.addEdge({
      id: edge.id ?? `edge-${index}`,
      source: edge.source,
      target: edge.target,
      router: { name: 'orth' },
      connector: { name: 'rounded' },
      attrs: {
        line: {
          stroke: edgeStyle.color,
          strokeWidth: edge.type === 'target' ? 2.8 : 2.2,
          strokeDasharray: edgeStyle.dash,
          targetMarker: {
            name: 'classic',
            size: 9,
            fill: edgeStyle.color,
            stroke: edgeStyle.color
          }
        }
      },
      labels: edge.label
        ? [
            {
              attrs: {
                label: {
                  text: edge.label,
                  fill: '#334155',
                  fontSize: 12,
                  fontWeight: 600
                },
                body: {
                  fill: '#FFFFFF',
                  stroke: '#C9D8F7',
                  rx: 8,
                  ry: 8
                }
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
  border: 1px solid rgba(61, 112, 205, 0.18);
  border-radius: 18px;
  background:
    radial-gradient(circle at 10% 0%, rgba(84, 132, 230, 0.09), transparent 30%),
    radial-gradient(circle at 90% 100%, rgba(10, 167, 175, 0.09), transparent 32%),
    linear-gradient(180deg, #f8fbff 0%, #f3f8ff 100%);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.85);
  animation: graph-fade-in 360ms ease-out;
}

@keyframes graph-fade-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
