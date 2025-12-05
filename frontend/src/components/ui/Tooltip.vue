<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  content: string
  side?: 'top' | 'right' | 'bottom' | 'left'
}

const props = withDefaults(defineProps<Props>(), {
  side: 'top',
})

const visible = ref(false)
</script>

<template>
  <div
    class="relative inline-block"
    @mouseenter="visible = true"
    @mouseleave="visible = false"
  >
    <slot />
    <Transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="visible && content"
        :class="[
          'absolute z-50 max-w-xs px-3 py-2 text-sm bg-popover text-popover-foreground border rounded-md shadow-md whitespace-pre-wrap',
          side === 'top' && 'bottom-full left-1/2 -translate-x-1/2 mb-2',
          side === 'bottom' && 'top-full left-1/2 -translate-x-1/2 mt-2',
          side === 'left' && 'right-full top-1/2 -translate-y-1/2 mr-2',
          side === 'right' && 'left-full top-1/2 -translate-y-1/2 ml-2',
        ]"
      >
        {{ content }}
      </div>
    </Transition>
  </div>
</template>
