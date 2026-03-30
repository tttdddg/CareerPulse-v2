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
  type?: PathNodeType | string
  meta?: Record<string, string>
}

export interface PathEdge {
  id?: string
  source: string
  target: string
  label?: string
  type?: PathNodeType | string
}

export interface PathGraphProps {
  nodes?: PathNode[]
  edges?: PathEdge[]
  height?: number | string
  variant?: 'default' | 'knowledge'
}

const props = withDefaults(defineProps<PathGraphProps>(), {
  height: 420,
  variant: 'default'
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

const normalizeNodeType = (type: PathNodeType | string | undefined): PathNodeType => {
  const normalized = `${type ?? ''}`.trim().toLowerCase()
  if (
    normalized === 'horizontal' ||
    normalized === 'lateral' ||
    normalized === 'transfer' ||
    normalized === 'cross' ||
    normalized === 'side'
  ) {
    return 'horizontal'
  }
  if (normalized === 'target' || normalized === 'center' || normalized === 'goal') {
    return 'target'
  }
  if (type === 'horizontal' || type === 'target') {
    return type
  }
  return 'vertical'
}

const knowledgeColors = ['#3B82F6', '#22C55E', '#14B8A6', '#A855F7', '#F43F5E', '#EAB308', '#0EA5E9', '#4F46E5']

const getNodeStyle = (type: PathNodeType | string | undefined, seed = ''): NodeStyle => {
  if (props.variant === 'knowledge') {
    if (normalizeNodeType(type) === 'target') {
      return {
        stroke: '#D97706',
        fill: '#F59E0B',
        text: '#FFFFFF',
        badge: '#FDE68A',
        shadow: '0 10px 24px rgba(217, 119, 6, 0.35)'
      }
    }
    const index = Math.abs(
      [...seed].reduce((acc, char) => ((acc * 33 + char.charCodeAt(0)) % 1024), 0)
    ) % knowledgeColors.length
    const color = knowledgeColors[index]
    return {
      stroke: color,
      fill: color,
      text: '#FFFFFF',
      badge: '#E2E8F0',
      shadow: '0 10px 24px rgba(37, 99, 235, 0.2)'
    }
  }

  const normalized = normalizeNodeType(type)
  if (normalized === 'target') {
    return {
      stroke: '#1D4ED8',
      fill: '#EAF1FF',
      text: '#0B2A62',
      badge: '#D7E6FF',
      shadow: '0 12px 30px rgba(29, 78, 216, 0.18)'
    }
  }
  if (normalized === 'horizontal') {
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

const getEdgeStyle = (type: PathNodeType | string | undefined): { color: string; dash?: string } => {
  if (props.variant === 'knowledge') {
    return { color: '#94A3B8' }
  }
  const normalized = normalizeNodeType(type)
  if (normalized === 'horizontal') {
    return { color: '#0E9AA7', dash: '6 4' }
  }
  if (normalized === 'target') {
    return { color: '#1D4ED8' }
  }
  return { color: '#2F67D8' }
}

const isFiniteNumber = (value: number | undefined): value is number =>
  typeof value === 'number' && Number.isFinite(value)

const inferEdgeType = (edge: PathEdge): PathNodeType => {
  const normalizedType = normalizeNodeType(edge.type)
  if (normalizedType === 'horizontal' || normalizedType === 'target') {
    return normalizedType
  }
  const text = `${edge.label ?? ''}`.trim()
  if (/转岗|横向|平级|跨岗|换岗|lateral|transfer|cross/i.test(text)) {
    return 'horizontal'
  }
  if (/目标|target/i.test(text)) {
    return 'target'
  }
  return 'vertical'
}

const mergeNode = (current: PathNode, incoming: PathNode): PathNode => {
  const incomingType = normalizeNodeType(incoming.type)
  const currentType = normalizeNodeType(current.type)
  const preferredType = currentType === 'target' || incomingType !== 'target' ? currentType : incomingType

  return {
    ...current,
    ...incoming,
    label: incoming.label || current.label,
    type: preferredType,
    x: isFiniteNumber(incoming.x) ? incoming.x : current.x,
    y: isFiniteNumber(incoming.y) ? incoming.y : current.y,
    meta: { ...(current.meta ?? {}), ...(incoming.meta ?? {}) }
  }
}

const uniqueNodes = (nodes: PathNode[]): PathNode[] => {
  const mapped = new Map<string, PathNode>()
  nodes.forEach((node) => {
    if (!node.id || !node.label) {
      return
    }
    const existing = mapped.get(node.id)
    if (existing) {
      mapped.set(node.id, mergeNode(existing, node))
      return
    }
    mapped.set(node.id, { ...node, type: normalizeNodeType(node.type) })
  })
  return [...mapped.values()]
}

const uniqueEdges = (edges: PathEdge[]): PathEdge[] => {
  const mapped = new Map<string, PathEdge>()
  edges.forEach((edge, index) => {
    if (!edge.source || !edge.target) {
      return
    }
    const resolvedType = inferEdgeType(edge)
    const label = edge.label?.trim() || undefined
    const key = `${edge.source}=>${edge.target}::${resolvedType}::${label ?? ''}`
    if (mapped.has(key)) {
      return
    }
    mapped.set(key, {
      id: edge.id ?? `edge-${index}`,
      source: edge.source,
      target: edge.target,
      label,
      type: resolvedType
    })
  })
  return [...mapped.values()]
}

const hasDenseOverlap = (nodes: PathNode[]): boolean => {
  const points = new Set<string>()
  for (const node of nodes) {
    if (!isFiniteNumber(node.x) || !isFiniteNumber(node.y)) {
      continue
    }
    const key = `${Math.round(node.x)}-${Math.round(node.y)}`
    if (points.has(key)) {
      return true
    }
    points.add(key)
  }
  return false
}

const buildAutoLayout = (nodes: PathNode[], edges: PathEdge[], width: number): PathNode[] => {
  if (nodes.length === 0) {
    return []
  }

  const sanitized = uniqueNodes(nodes)
  const nodeById = new Map(sanitized.map((node) => [node.id, node] as const))
  const filteredEdges = uniqueEdges(edges).filter((edge) => nodeById.has(edge.source) && nodeById.has(edge.target))

  const targetNode = sanitized.find((node) => node.type === 'target') ?? sanitized[0]
  const targetId = targetNode.id

  const incoming = new Map<string, string[]>()
  const outgoing = new Map<string, string[]>()
  const horizontalTargets = new Set<string>()
  sanitized.forEach((node) => {
    const relationText = `${node.meta?.relation ?? ''}${(node as PathNode & { relation?: string }).relation ?? ''}`
    if (/转岗|横向|平级|跨岗|换岗/i.test(relationText)) {
      horizontalTargets.add(node.id)
    }
  })
  filteredEdges.forEach((edge) => {
    const list = incoming.get(edge.target) ?? []
    list.push(edge.source)
    incoming.set(edge.target, list)
    const outList = outgoing.get(edge.source) ?? []
    outList.push(edge.target)
    outgoing.set(edge.source, outList)
    if (inferEdgeType(edge) === 'horizontal') {
      horizontalTargets.add(edge.source)
      horizontalTargets.add(edge.target)
    }
  })

  const distanceToTarget = new Map<string, number>([[targetId, 0]])
  const queue = [targetId]
  const shouldUseOutgoing = (incoming.get(targetId)?.length ?? 0) === 0 && (outgoing.get(targetId)?.length ?? 0) > 0
  while (queue.length > 0) {
    const current = queue.shift()
    if (!current) {
      continue
    }
    const currentDistance = distanceToTarget.get(current) ?? 0
    const neighbors = shouldUseOutgoing ? outgoing.get(current) ?? [] : incoming.get(current) ?? []
    neighbors.forEach((nextId) => {
      if (distanceToTarget.has(nextId)) {
        return
      }
      distanceToTarget.set(nextId, currentDistance + 1)
      queue.push(nextId)
    })
  }

  const safeWidth = Math.max(width, 360)
  const targetWidth = 168
  const branchNodeWidth = 150
  const horizontalPadding = 28
  const centerX = Math.round(safeWidth / 2)
  const targetX = Math.max(
    horizontalPadding,
    Math.min(centerX - Math.round(targetWidth / 2), safeWidth - targetWidth - horizontalPadding)
  )
  const leftBranchX = horizontalPadding
  const rightBranchX = Math.max(horizontalPadding, safeWidth - branchNodeWidth - horizontalPadding)
  const targetY = 64
  const rhythmStep = 124
  const verticalGap = rhythmStep
  const lateralGapY = rhythmStep
  const branchStartOffsetY = 2 * rhythmStep
  let verticalIndex = 0
  let horizontalIndex = 0
  const verticalRankOffset = new Map<number, number>()

  return sanitized.map((node) => {
    if (node.id === targetId) {
      return { ...node, type: 'target', x: targetX, y: targetY }
    }

    const inferredType =
      normalizeNodeType(node.type) === 'horizontal' ||
      horizontalTargets.has(node.id) ||
      filteredEdges.some((edge) => edge.source === targetId && edge.target === node.id && inferEdgeType(edge) === 'horizontal')
        ? 'horizontal'
        : 'vertical'
    if (inferredType === 'horizontal') {
      const side = horizontalIndex % 2 === 0 ? 1 : -1
      const row = Math.floor(horizontalIndex / 2)
      horizontalIndex += 1
      return {
        ...node,
        type: 'horizontal',
        x: side > 0 ? rightBranchX : leftBranchX,
        y: targetY + branchStartOffsetY + row * lateralGapY
      }
    }

    const rank = distanceToTarget.get(node.id) ?? 100 + verticalIndex
    const rankSlot = verticalRankOffset.get(rank) ?? 0
    verticalRankOffset.set(rank, rankSlot + 1)
    const y = targetY + rhythmStep + Math.max(0, rank - 1) * verticalGap + rankSlot * Math.round(rhythmStep / 2)
    verticalIndex += 1
    return {
      ...node,
      type: 'vertical',
      x: targetX,
      y
    }
  })
}

const resolveRenderNodes = (nodes: PathNode[], edges: PathEdge[], width: number): PathNode[] => {
  const sanitized = uniqueNodes(nodes)
  if (sanitized.length <= 1) {
    return sanitized
  }

  const positionedCount = sanitized.filter((node) => isFiniteNumber(node.x) && isFiniteNumber(node.y)).length
  const needsAutoLayout = positionedCount < sanitized.length || hasDenseOverlap(sanitized)
  if (!needsAutoLayout) {
    return sanitized
  }

  return buildAutoLayout(sanitized, edges, width)
}

const resolveEdgeLabel = (edge: PathEdge): string | undefined => {
  const label = edge.label?.trim()
  if (!label) {
    return undefined
  }
  const type = inferEdgeType(edge)
  if (type === 'vertical' && /^(晋升|升职|晋级)$/i.test(label)) {
    return undefined
  }
  if (type === 'horizontal' && /^(换岗|转岗|横向)$/i.test(label)) {
    return undefined
  }
  return label
}

const stableOffset = (seed: string, amplitude: number): number => {
  let hash = 0
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) >>> 0
  }
  return (hash % 2 === 0 ? 1 : -1) * amplitude
}

const renderGraph = (): void => {
  if (!graphEl.value) {
    return
  }

  if (!graph) {
    graph = new Graph({
      container: graphEl.value,
      background: {
        color: props.variant === 'knowledge' ? '#FFFFFF' : '#F8FBFF'
      },
      grid: {
        size: 20,
        visible: props.variant !== 'knowledge',
        type: 'dot',
        args: { color: '#DCE7FA', thickness: 1 }
      },
      panning: true,
      mousewheel: { enabled: true, modifiers: ['ctrl', 'meta'], minScale: 0.65, maxScale: 1.75 },
      interacting: { nodeMovable: false }
    })

    graph.on('node:mouseenter', ({ node }) => {
      const data = node.getData() as PathNode
      const style = getNodeStyle(data.type, data.id)
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
      const style = getNodeStyle(data.type, data.id)
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
  const edges = uniqueEdges((props.edges ?? []) as PathEdge[])
  const resolvedNodes = resolveRenderNodes(nodes, edges, graphEl.value.clientWidth)
  const nodeIds = new Set(resolvedNodes.map((node) => node.id))
  const resolvedEdges = edges
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .map((edge) => ({ ...edge, type: inferEdgeType(edge) }))
  const nodeMap = new Map(resolvedNodes.map((node) => [node.id, node] as const))

  resolvedNodes.forEach((node) => {
    const style = getNodeStyle(node.type, node.id)
    const isKnowledge = props.variant === 'knowledge'
    const width = isKnowledge ? (node.type === 'target' ? 108 : 86) : node.type === 'target' ? 168 : 150
    const height = isKnowledge ? width : node.type === 'target' ? 52 : 46

    graph?.addNode({
      id: node.id,
      x: node.x ?? 0,
      y: node.y ?? 0,
      width,
      height,
      shape: isKnowledge ? 'circle' : 'rect',
      zIndex: 20,
      attrs: {
        body: {
          rx: isKnowledge ? undefined : 12,
          ry: isKnowledge ? undefined : 12,
          stroke: style.stroke,
          strokeWidth: isKnowledge ? 0 : 1.2,
          fill: style.fill,
          shadowColor: style.shadow
        },
        label: {
          text: node.label,
          fill: style.text,
          fontSize: isKnowledge ? (node.type === 'target' ? 18 : 14) : node.type === 'target' ? 14 : 13,
          fontWeight: node.type === 'target' ? 700 : 600
        }
      },
      data: node
    })
  })

  resolvedEdges.forEach((edge, index) => {
    const edgeStyle = getEdgeStyle(edge.type)
    const displayLabel = resolveEdgeLabel(edge)
    const sourceNode = nodeMap.get(edge.source)
    const targetNode = nodeMap.get(edge.target)
    const sourceX = sourceNode?.x ?? 0
    const sourceY = sourceNode?.y ?? 0
    const targetX = targetNode?.x ?? 0
    const targetY = targetNode?.y ?? 0
    const sourceAnchor =
      Math.abs(targetX - sourceX) > 60
        ? { name: targetX > sourceX ? 'right' : 'left' }
        : { name: targetY >= sourceY ? 'bottom' : 'top' }
    const targetAnchor =
      Math.abs(targetX - sourceX) > 60
        ? { name: targetY >= sourceY ? 'top' : 'bottom' }
        : { name: targetY >= sourceY ? 'top' : 'bottom' }
    const key = `${edge.source}->${edge.target}::${edge.type ?? 'vertical'}`
    const sameColumn = Math.abs(targetX - sourceX) <= 4 && Math.abs(targetY - sourceY) > 40
    const edgeVertices =
      sameColumn && edge.type === 'horizontal'
        ? [
            {
              x: Math.round((sourceX + targetX) / 2 + stableOffset(key, 16)),
              y: Math.round((sourceY + targetY) / 2)
            }
          ]
        : undefined

    graph?.addEdge({
      id: edge.id ?? `edge-${index}`,
      source: edge.source,
      target: edge.target,
      sourceAnchor,
      targetAnchor,
      zIndex: 5,
      router: props.variant === 'knowledge' ? undefined : { name: 'orth' },
      connector: props.variant === 'knowledge' ? { name: 'smooth' } : { name: 'rounded' },
      vertices: edgeVertices,
      attrs: {
        line: {
          stroke: edgeStyle.color,
          strokeWidth: props.variant === 'knowledge' ? 1.4 : edge.type === 'target' ? 2.8 : 2.2,
          strokeDasharray: edgeStyle.dash,
          targetMarker: {
            name: 'classic',
            size: props.variant === 'knowledge' ? 7 : 9,
            fill: edgeStyle.color,
            stroke: edgeStyle.color
          }
        }
      },
      labels: displayLabel
        ? [
            {
              position: {
                distance: 0.5,
                offset: edge.type === 'horizontal' ? 12 : -10
              },
              attrs: {
                label: {
                  text: displayLabel,
                  fill: props.variant === 'knowledge' ? '#6B7280' : '#334155',
                  fontSize: props.variant === 'knowledge' ? 11 : 12,
                  fontWeight: props.variant === 'knowledge' ? 500 : 600
                },
                body: {
                  fill: props.variant === 'knowledge' ? 'transparent' : '#FFFFFF',
                  stroke: props.variant === 'knowledge' ? 'transparent' : '#C9D8F7',
                  rx: props.variant === 'knowledge' ? 0 : 8,
                  ry: props.variant === 'knowledge' ? 0 : 8
                }
              }
            }
          ]
        : undefined
    })
  })

  graph.centerContent({ padding: 20 })
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

watch(
  () => props.variant,
  () => {
    graph?.dispose()
    graph = null
    renderGraph()
  }
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
