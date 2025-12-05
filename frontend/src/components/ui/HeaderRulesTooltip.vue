<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'

interface Props {
  header: string
  rules: string[]
}

const props = defineProps<Props>()

const visible = ref(false)
const pos = ref({ x: 0, y: 0 })
let hideTimer: ReturnType<typeof setTimeout> | null = null

const hasContent = computed(() => props.rules?.length > 0)

function onMouseMove(e: MouseEvent) {
  const tooltipWidth = 280
  const tooltipMaxH = 300
  const offset = 12
  let x = e.clientX + offset
  let y = e.clientY + offset

  if (x + tooltipWidth > window.innerWidth - 8) {
    x = e.clientX - tooltipWidth - offset
  }
  if (y + tooltipMaxH > window.innerHeight - 8) {
    y = e.clientY - tooltipMaxH - offset
  }
  x = Math.max(8, x)
  y = Math.max(8, y)

  pos.value = { x, y }
}

function show(e: MouseEvent) {
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
  onMouseMove(e)
  visible.value = true
}

function hide() {
  hideTimer = setTimeout(() => {
    visible.value = false
    hideTimer = null
  }, 100)
}

onUnmounted(() => {
  if (hideTimer) clearTimeout(hideTimer)
})
</script>

<template>
  <div
    class="inline-block max-w-full"
    @mouseenter="show"
    @mousemove="onMouseMove"
    @mouseleave="hide"
  >
    <slot />
  </div>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-150"
      leave-active-class="transition-opacity duration-100"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="visible && hasContent"
        class="fixed z-[9999] w-[280px] px-3.5 py-3 text-sm border rounded-lg shadow-xl pointer-events-none"
        style="background-color: hsl(var(--popover)); color: hsl(var(--popover-foreground)); border-color: hsl(var(--border));"
        :style="{ left: `${pos.x}px`, top: `${pos.y}px` }"
      >
        <div class="font-semibold text-foreground">{{ header }}</div>
        <div class="text-xs text-muted-foreground mt-0.5">匹配规则</div>
        <div class="border-t border-foreground/60 mt-2 pt-2"></div>
        <ul class="mt-2 space-y-1.5 text-muted-foreground">
          <li
            v-for="(rule, i) in rules"
            :key="i"
            class="flex gap-2 text-[13px] leading-relaxed"
          >
            <span class="text-foreground/60 shrink-0">•</span>
            <span class="break-words font-mono text-[12px]">{{ rule }}</span>
          </li>
        </ul>
      </div>
    </Transition>
  </Teleport>
</template>
