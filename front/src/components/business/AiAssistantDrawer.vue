<template>
  <div class="assistant-shell">
    <button
      v-show="!visible"
      class="float-trigger"
      type="button"
      @click="openPanel"
      aria-label="打开 AI 助手"
    >
      <el-icon><ChatDotRound /></el-icon>
      <span>AI 助手</span>
    </button>

    <Transition name="assistant-slide">
      <aside v-show="visible" class="chat-panel" role="dialog" aria-label="AI 助手面板">
        <header class="panel-header">
          <div class="header-title">
            <el-icon><MagicStick /></el-icon>
            <div>
              <h3>{{ title }}</h3>
              <p>{{ subtitle }}</p>
            </div>
          </div>
          <el-button text @click="closePanel">收起</el-button>
        </header>

        <section class="panel-body">
          <slot />
        </section>
      </aside>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ChatDotRound, MagicStick } from '@element-plus/icons-vue'

interface AiAssistantDrawerProps {
  modelValue?: boolean
  title?: string
  subtitle?: string
}

const props = withDefaults(defineProps<AiAssistantDrawerProps>(), {
  modelValue: false,
  title: 'AI 助手',
  subtitle: '岗位方向与求职问题智能解答'
})

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
}>()

const visible = computed(() => props.modelValue)

const openPanel = (): void => {
  emit('update:modelValue', true)
}

const closePanel = (): void => {
  emit('update:modelValue', false)
}
</script>

<style scoped>
.assistant-shell {
  position: fixed;
  right: 0;
  bottom: 16vh;
  z-index: 3100;
}

.float-trigger {
  width: 132px;
  height: 48px;
  border: 0;
  border-radius: 8px 0 0 8px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transform: translateX(calc(100% - 48px));
  transition: transform 0.28s ease, background-color 0.2s ease;
}

.float-trigger:hover {
  transform: translateX(0);
  background: linear-gradient(135deg, #4f8dff 0%, #2d6ef5 100%);
}

.chat-panel {
  position: fixed;
  right: 10px;
  bottom: 32px;
  width: min(420px, calc(100vw - 20px));
  height: 72vh;
  background: #fff;
  border: 1px solid #dde5f1;
  border-radius: 14px;
  box-shadow: 0 14px 32px rgba(40, 73, 140, 0.2);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid #e5ebf3;
  background: #f8fbff;
}

.header-title {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #2558a7;
}

.header-title h3 {
  margin: 0;
  font-size: 16px;
  color: #1c2d4a;
}

.header-title p {
  margin: 3px 0 0;
  color: #667089;
  font-size: 12px;
}

.header-title div,
.header-title h3,
.header-title p {
  min-width: 0;
  overflow-wrap: anywhere;
}

.panel-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 0;
  overflow-wrap: anywhere;
}

.panel-body :deep(img),
.panel-body :deep(video),
.panel-body :deep(canvas) {
  max-width: 100%;
  height: auto;
}

.panel-body :deep(pre),
.panel-body :deep(table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
}

.assistant-slide-enter-active,
.assistant-slide-leave-active {
  transition: all 0.34s cubic-bezier(0.22, 1, 0.36, 1);
}

.assistant-slide-enter-from,
.assistant-slide-leave-to {
  opacity: 0;
  transform: translateY(70px) scale(0.82);
}

@media (max-width: 767px) {
  .assistant-shell {
    bottom: 12vh;
  }

  .chat-panel {
    right: 12px;
    bottom: 12px;
    width: calc(100vw - 24px);
    height: min(78vh, calc(100dvh - 24px));
    max-height: 720px;
  }

  .panel-header {
    align-items: flex-start;
    padding: 12px;
  }

  .panel-header :deep(.el-button) {
    flex: none;
    margin-left: 0;
  }
}
</style>
