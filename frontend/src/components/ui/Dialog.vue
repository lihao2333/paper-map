<script setup lang="ts">
import { ref, watch } from 'vue'
import { X } from 'lucide-vue-next'

interface Props {
  open: boolean
  title?: string
  /** 白底模式，弹窗内容区固定为白底黑字，更清晰 */
  light?: boolean
}

const props = withDefaults(defineProps<Props>(), { light: false })
const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

function close() {
  emit('update:open', false)
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    close()
  }
}

watch(() => props.open, (open) => {
  if (open) {
    document.addEventListener('keydown', handleKeydown)
    document.body.style.overflow = 'hidden'
  } else {
    document.removeEventListener('keydown', handleKeydown)
    document.body.style.overflow = ''
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div
          class="fixed inset-0 bg-black/80 backdrop-blur-md"
          @click="close"
        />
        <div
          :class="[
            'relative z-10 w-full max-w-xl max-h-[90vh] overflow-auto rounded-xl border-2 shadow-2xl p-6',
            light
              ? 'dialog-light bg-white text-gray-900 border-gray-200 ring-2 ring-gray-200/60'
              : 'bg-card text-card-foreground border-border ring-2 ring-border/40'
          ]"
        >
          <div class="flex items-center justify-between mb-5">
            <h2
              v-if="title"
              :class="['text-xl font-bold pr-8', light ? 'text-gray-900' : 'text-foreground']"
            >
              {{ title }}
            </h2>
            <button
              :class="[
                'absolute right-4 top-4 rounded-md p-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2',
                light
                  ? 'text-gray-500 hover:text-gray-900 hover:bg-gray-100 focus:ring-gray-400'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent/50 focus:ring-ring'
              ]"
              @click="close"
            >
              <X class="h-5 w-5" />
            </button>
          </div>
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* 白底模式：覆盖 CSS 变量使文字为深色 */
.dialog-light {
  --foreground: 222.2 84% 4.9%;
  --muted-foreground: 215.4 16.3% 46.9%;
}
</style>
