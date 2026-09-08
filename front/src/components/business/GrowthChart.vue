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
  const compact = (chartEl.value?.clientWidth ?? 999) < 480

  return {
    tooltip: { trigger: 'axis' },
    legend: {
      show: props.showLegend,
      type: 'scroll',
      top: 0,
      left: compact ? 4 : 'center',
      right: compact ? 4 : 'auto',
      textStyle: { color: '#475569', fontSize: compact ? 11 : 12 }
    },
    grid: { left: compact ? 8 : 24, right: compact ? 8 : 24, top: 36, bottom: compact ? 34 : 24, containLabel: true },
    xAxis: {
      type: 'category',
      data: categories,
      axisLine: { lineStyle: { color: '#E2E8F0' } },
      axisLabel: { color: '#64748B', hideOverlap: true, rotate: compact ? 28 : 0 },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#64748B', fontSize: compact ? 10 : 12 },
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
