<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { formatDate } from '@/lib/utils'

export interface HoverInfo {
  full_name?: string
  abstract?: string
  summary?: string
  company_names?: string[]
  university_names?: string[]
  author_names?: string[]
  tag_names?: string[]
  date?: string
  paper_id?: string
  arxiv_id?: string | null
  paper_url?: string
}

interface Props {
  hoverInfo: HoverInfo | null | undefined
}

const props = defineProps<Props>()

const visible = ref(false)
const triggerEl = ref<HTMLElement | null>(null)
const tooltipEl = ref<HTMLElement | null>(null)
const pos = ref({ x: 0, y: 0 })
let hideTimer: ReturnType<typeof setTimeout> | null = null

/** 参考 dashboard generate_tooltip 格式 */
const tooltipTitle = computed(() => {
  const h = props.hoverInfo
  return h?.full_name ? `📄 ${h.full_name}` : ''
})

type TooltipBlock = { type: 'separator' } | { type: 'text'; content: string }

const tooltipBlocks = computed<TooltipBlock[]>(() => {
  const h = props.hoverInfo
  if (!h) return []
  const blocks: TooltipBlock[] = []

  const pushText = (text: string) => blocks.push({ type: 'text', content: text })

  if (h.paper_id || h.author_names?.length || h.date || h.summary || h.company_names?.length || h.university_names?.length || h.tag_names?.length) {
    if (h.full_name) blocks.push({ type: 'separator' })
  }
  if (h.paper_id) pushText(`🆔 Paper ID: ${h.paper_id}`)
  if (h.author_names?.length) pushText(`👤 作者: ${h.author_names.join(', ')}`)
  if (h.date) pushText(`📅 日期: ${formatDate(h.date)}`)
  if (h.summary) pushText(`📝 AI 总结: ${h.summary}`)
  if (h.company_names?.length || h.university_names?.length) {
    blocks.push({ type: 'separator' })
    if (h.company_names?.length) pushText(`🏢 公司: ${h.company_names.join(', ')}`)
    if (h.university_names?.length) pushText(`🎓 高校: ${h.university_names.join(', ')}`)
  }
  if (h.tag_names?.length) pushText(`🏷️ 标签: ${h.tag_names.join(', ')}`)

  return blocks
})

const hasContent = computed(() => !!tooltipTitle.value || tooltipBlocks.value.length > 0)

function onMouseMove(e: MouseEvent) {
  const tooltipWidth = 380
  const tooltipMaxH = 400
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

/** 取消延迟隐藏，用于鼠标移入 tooltip 时保持显示以便滚动 */
function clearHide() {
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}

function hide() {
  hideTimer = setTimeout(() => {
    visible.value = false
    hideTimer = null
  }, 150)
}

onUnmounted(() => {
  if (hideTimer) clearTimeout(hideTimer)
})
</script>

<template>
  <div
    ref="triggerEl"
    class="inline-block"
    @mouseenter="show"
    @mousemove="onMouseMove"
    @mouseleave="hide"
  >
    <slot />
  </div>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-150"
      leave-active-class="transition-opacity duration-150"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="visible && hasContent"
        ref="tooltipEl"
        class="fixed z-[9999] w-[380px] max-h-[70vh] overflow-y-auto px-3.5 py-3 text-sm border rounded-lg shadow-xl"
        style="background-color: hsl(var(--popover)); color: hsl(var(--popover-foreground)); border-color: hsl(var(--border));"
        :style="{ left: `${pos.x}px`, top: `${pos.y}px` }"
        @mouseenter="clearHide"
        @mouseleave="hide"
      >
        <div v-if="tooltipTitle" class="font-semibold shrink-0">{{ tooltipTitle }}</div>
        <div v-if="tooltipBlocks.length" class="mt-1 space-y-1">
          <template v-for="(block, i) in tooltipBlocks" :key="i">
            <div v-if="block.type === 'separator'" class="border-t border-foreground/60 shrink-0" />
            <div v-else class="whitespace-pre-wrap break-words">{{ block.content }}</div>
          </template>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
