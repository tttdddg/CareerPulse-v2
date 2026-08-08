<template>
  <el-button
    :type="typeStyle"
    :loading="loading"
    :disabled="disabled"
    class="export-button"
    @click="handleExport"
  >
    <el-icon><Download /></el-icon>
    <span>{{ label }}</span>
  </el-button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Download } from '@element-plus/icons-vue'

export type ExportType = 'pdf' | 'word'

export interface ExportButtonProps {
  label?: string
  fileName?: string
  type?: ExportType
  disabled?: boolean
  loading?: boolean
  blob?: Blob | null
}

const props = withDefaults(defineProps<ExportButtonProps>(), {
  label: '导出报告',
  fileName: 'career-report',
  type: 'pdf',
  disabled: false,
  loading: false,
  blob: null
})

const emit = defineEmits<{
  (event: 'export', payload: { type: ExportType; fileName: string }): void
}>()

const typeStyle = computed(() => (props.type === 'word' ? 'success' : 'primary'))

const getExtension = (type: ExportType): string => (type === 'word' ? 'docx' : 'pdf')

const downloadBlob = (blob: Blob, fileName: string): void => {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  anchor.click()
  URL.revokeObjectURL(url)
}

const handleExport = (): void => {
  const fileName = `${props.fileName}.${getExtension(props.type)}`

  if (props.blob) {
    downloadBlob(props.blob, fileName)
    return
  }

  emit('export', { type: props.type, fileName })
}
</script>

<style scoped>
.export-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
</style>
