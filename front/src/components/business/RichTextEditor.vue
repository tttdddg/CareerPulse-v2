<template>
  <div class="editor-shell">
    <div class="editor-actions">
      <div class="action-left">
        <span class="title">成长计划编辑</span>
        <span class="subtitle">支持智能润色与内容检查</span>
      </div>
      <div class="action-right">
        <el-button type="primary" plain @click="handlePolish">智能润色</el-button>
        <el-button type="primary" @click="handleCheck">内容检查</el-button>
      </div>
    </div>

    <Toolbar class="editor-toolbar" :editor="editorRef" :defaultConfig="toolbarConfig" />
    <Editor
      class="editor-body"
      v-model="contentValue"
      :defaultConfig="editorConfig"
      :mode="mode"
      @onCreated="handleCreated"
      @onChange="handleChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import type { IDomEditor, IEditorConfig, IToolbarConfig } from '@wangeditor/editor'
import '@wangeditor/editor/dist/css/style.css'

export interface RichTextEditorProps {
  modelValue: string
  placeholder?: string
  disabled?: boolean
  mode?: 'default' | 'simple'
}

const props = withDefaults(defineProps<RichTextEditorProps>(), {
  placeholder: '请输入你的成长计划内容…',
  disabled: false,
  mode: 'default'
})

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'polish', value: string): void
  (event: 'check', value: string): void
}>()

const editorRef = shallowRef<IDomEditor | null>(null)
const contentValue = ref(props.modelValue)

const toolbarConfig: Partial<IToolbarConfig> = {}

const editorConfig = computed<Partial<IEditorConfig>>(() => ({
  placeholder: props.placeholder,
  readOnly: props.disabled
}))

const handleCreated = (editor: IDomEditor): void => {
  editorRef.value = editor
}

const handleChange = (editor: IDomEditor): void => {
  const html = editor.getHtml()
  contentValue.value = html
  emit('update:modelValue', html)
}

const handlePolish = (): void => {
  emit('polish', contentValue.value)
}

const handleCheck = (): void => {
  emit('check', contentValue.value)
}

watch(
  () => props.modelValue,
  (value) => {
    if (value !== contentValue.value) {
      contentValue.value = value
      editorRef.value?.setHtml(value)
    }
  }
)

onBeforeUnmount(() => {
  editorRef.value?.destroy()
  editorRef.value = null
})
</script>

<style scoped>
.editor-shell {
  border: 1px solid var(--cp-border);
  border-radius: 16px;
  overflow: hidden;
  background: #ffffff;
}

.editor-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: var(--cp-surface-subtle);
  border-bottom: 1px solid var(--cp-border);
}

.action-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.action-left .title {
  font-weight: 600;
}

.action-left .subtitle {
  font-size: 12px;
  color: var(--cp-text-muted);
}

.editor-toolbar {
  border-bottom: 1px solid var(--cp-border) !important;
}

.editor-body {
  min-height: 260px;
  padding: 0 20px;
}

.editor-shell :deep(.w-e-toolbar) {
  flex-wrap: wrap;
}

.editor-shell :deep(.w-e-text-container img) {
  max-width: 100%;
  height: auto;
}

.editor-shell :deep(.w-e-text-container table),
.editor-shell :deep(.w-e-text-container pre) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
}

.editor-shell :deep(.w-e-text-container a),
.editor-shell :deep(.w-e-text-container p) {
  overflow-wrap: anywhere;
}

@media (max-width: 767px) {
  .editor-actions {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
    padding: 14px 16px;
  }

  .action-right {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .action-right :deep(.el-button) {
    width: 100%;
    margin-left: 0;
  }

  .editor-body {
    min-height: 240px;
    padding: 0 12px;
  }
}

@media (max-width: 320px) {
  .action-right {
    grid-template-columns: 1fr;
  }
}
</style>
