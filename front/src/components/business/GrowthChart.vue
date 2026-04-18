<template>
  <div class="growth-chart" :style="containerStyle" ref="chartEl"></div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

// 单点能力值
export interface GrowthPoint {
  date: string
  value: number
  label?: string
}

// 成长曲线序列
export interface GrowthSeries {
  name: string
  data: GrowthPoint[]
  color?: string
}

export interface GrowthChartProps {
  series: GrowthSeries[]
  height?: number | string
  smooth?: boolean
  showLegend?: boolean
  area?: boolean
}

const props = withDefaults(defineProps<GrowthChartProps>(), {
  height: 240,
  smooth: true,
  showLegend: true,
  area: true
})

const chartEl = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const defaultColors = ['#6366F1', '#8B5CF6', '#0EA5E9']

const containerStyle = computed(() => ({
  height: typeof props.height === 'number' ? `${props.height}px` : props.height
}))

const buildOption = (): EChartsOption => {
  const categories = props.series[0]?.data.map((point) => point.label ?? point.date) ?? []

  return {
    tooltip: { trigger: 'axis' },
    legend: {
      show: props.showLegend,
      top: 0,
      textStyle: { color: '#475569', fontSize: 12 }
    },
    grid: { left: 24, right: 24, top: 36, bottom: 24, containLabel: true },
    xAxis: {
      type: 'category',
      data: categories,
      axisLine: { lineStyle: { color: '#E2E8F0' } },
      axisLabel: { color: '#64748B' },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#64748B' },
      splitLine: { lineStyle: { color: '#E2E8F0' } }
    },
    series: props.series.map((item, index) => {
      const color = item.color ?? defaultColors[index % defaultColors.length]
      return {
        type: 'line',
        name: item.name,
        data: item.data.map((point) => point.value),
        smooth: props.smooth,
        showSymbol: false,
        lineStyle: { width: 2, color },
        areaStyle: props.area ? { color, opacity: 0.12 } : undefined,
        itemStyle: { color }
      }
    })
  }
}

const renderChart = (): void => {
  if (!chartEl.value) {
    return
  }

  if (!chart) {
    chart = echarts.init(chartEl.value)
  }

  chart.setOption(buildOption(), true)
}

const handleResize = (): void => {
  chart?.resize()
}

onMounted(() => {
  renderChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})

watch(
  () => [props.series, props.smooth, props.area, props.showLegend],
  () => renderChart(),
  { deep: true }
)
</script>

<style scoped>
.growth-chart {
  width: 100%;
}
</style>
