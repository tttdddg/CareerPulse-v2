<template>
  <div class="radar-chart" :style="containerStyle" ref="chartEl"></div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

// 单维度指标
export interface RadarIndicator {
  name: string
  max: number
}

// 雷达图序列（个人/岗位）
export interface RadarSeries {
  name: string
  values: number[]
  color?: string
  areaOpacity?: number
}

export interface RadarChartProps {
  indicators: RadarIndicator[]
  series: RadarSeries[]
  height?: number | string
  title?: string
  showLegend?: boolean
}

const props = withDefaults(defineProps<RadarChartProps>(), {
  height: 260,
  showLegend: true,
  title: ''
})

const chartEl = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const defaultColors = ['#6366F1', '#8B5CF6', '#0EA5E9', '#22C55E']

const containerStyle = computed(() => ({
  height: typeof props.height === 'number' ? `${props.height}px` : props.height
}))

const buildOption = (): EChartsOption => ({
  ...(() => {
    const compact = (chartEl.value?.clientWidth ?? 999) < 480
    return {
      legend: {
        show: props.showLegend,
        type: 'scroll' as const,
        top: 0,
        left: compact ? 4 : 'center',
        right: compact ? 4 : 'auto',
        textStyle: { color: '#475569', fontSize: compact ? 11 : 12 }
      },
      radar: {
        indicator: props.indicators,
        center: ['50%', compact ? '58%' : '54%'],
        radius: compact ? '54%' : '65%',
        splitNumber: 4,
        axisName: { color: '#475569', fontSize: compact ? 10 : 12 },
        axisLine: { lineStyle: { color: '#E2E8F0' } },
        splitLine: { lineStyle: { color: ['#E2E8F0'] } },
        splitArea: {
          areaStyle: {
            color: ['rgba(99, 102, 241, 0.04)', 'rgba(139, 92, 246, 0.03)']
          }
        }
      }
    }
  })(),
  // 基础交互
  tooltip: { trigger: 'item' },
  // 数据序列
  series: [
    {
      type: 'radar',
      data: props.series.map((item, index) => {
        const color = item.color ?? defaultColors[index % defaultColors.length]
        return {
          name: item.name,
          value: item.values,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2, color },
          itemStyle: { color },
          areaStyle: { color, opacity: item.areaOpacity ?? 0.12 }
        }
      })
    }
  ]
})

const renderChart = (): void => {
  if (!chartEl.value) {
    return
  }

  if (!chart) {
    chart = echarts.init(chartEl.value)
  }

  chart.setOption(buildOption(), true)
}

const resizeObserver = new ResizeObserver(() => {
  chart?.resize()
  chart?.setOption(buildOption(), true)
})

onMounted(() => {
  renderChart()
  if (chartEl.value) {
    resizeObserver.observe(chartEl.value)
  }
})

onBeforeUnmount(() => {
  resizeObserver.disconnect()
  chart?.dispose()
  chart = null
})

watch(
  () => [props.indicators, props.series, props.showLegend, props.title],
  () => renderChart(),
  { deep: true }
)
</script>

<style scoped>
.radar-chart {
  width: 100%;
}
</style>
