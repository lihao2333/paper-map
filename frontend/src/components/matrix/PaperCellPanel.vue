<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { PopoverRoot, PopoverTrigger, PopoverAnchor, PopoverPortal, PopoverContent } from 'radix-vue'
import AddTagPopover from '@/components/tags/AddTagPopover.vue'
import type { HoverInfo } from '@/types'
import { formatDate, generateArxivLink } from '@/lib/utils'
import { Tag, X } from 'lucide-vue-next'

interface Props {
  hoverInfo: HoverInfo | null
  cellContent: string
  isVisited: boolean
  paperId: string
  onOpenLink: () => void
  onRemoveTag: (paperId: string, tagId: number) => void
}

const props = defineProps<Props>()
const emit = defineEmits<{ (e: 'tag-added'): void }>()

const open = ref(false)
const pinned = ref(false)
let closeTimer: ReturnType<typeof setTimeout> | null = null

function clearCloseTimer() {
  if (closeTimer) {
    clearTimeout(closeTimer)
    closeTimer = null
  }
}

/** hover 时显示；点击后固定，可操作 */
function onTriggerEnter() {
  clearCloseTimer()
  open.value = true
}

function onTriggerLeave() {
  if (!pinned.value) {
    closeTimer = setTimeout(() => {
      if (!pinned.value) open.value = false
      closeTimer = null
    }, 150)
  }
}

function onTriggerClick(e: MouseEvent) {
  if (e.ctrlKey || e.metaKey) {
    props.onOpenLink()
    return
  }
  pinned.value = true
  open.value = true
}

function onContentEnter() {
  clearCloseTimer()
}

function onContentLeave() {
  if (!pinned.value) {
    closeTimer = setTimeout(() => {
      if (!pinned.value) open.value = false
      closeTimer = null
    }, 150)
  }
}

onUnmounted(clearCloseTimer)

function onOpenChange(v: boolean) {
  if (!v) {
    pinned.value = false
  }
  open.value = v
}

/** 论文详情区块（原 hover 内容），含 emoji 与 PaperTooltip 格式一致 */
const infoBlocks = computed(() => {
  const h = props.hoverInfo
  if (!h) return []
  const blocks: { type: 'title' | 'separator' | 'text'; content?: string }[] = []
  if (h.full_name) {
    blocks.push({ type: 'title', content: h.full_name })
  }
  if (h.paper_id || h.author_names?.length || h.date || h.summary || h.abstract || h.company_names?.length || h.university_names?.length || h.tag_names?.length) {
    if (h.full_name) blocks.push({ type: 'separator' })
  }
  if (h.paper_id) blocks.push({ type: 'text', content: `🆔 Paper ID: ${h.paper_id}` })
  if (h.author_names?.length) {
    blocks.push({ type: 'text', content: `👤 作者: ${h.author_names.join(', ')}` })
  }
  if (h.date) blocks.push({ type: 'text', content: `📅 日期: ${formatDate(h.date)}` })
  if (h.abstract) blocks.push({ type: 'text', content: `📄 摘要: ${h.abstract}` })
  if (h.summary) blocks.push({ type: 'text', content: `📝 AI 总结: ${h.summary}` })
  if (h.company_names?.length || h.university_names?.length) {
    blocks.push({ type: 'separator' })
    if (h.company_names?.length) {
      blocks.push({ type: 'text', content: `🏢 公司: ${h.company_names.join(', ')}` })
    }
    if (h.university_names?.length) {
      blocks.push({ type: 'text', content: `🎓 高校: ${h.university_names.join(', ')}` })
    }
  }
  if (h.tag_names?.length) {
    blocks.push({ type: 'text', content: `🏷️ 标签: ${h.tag_names.join(', ')}` })
  }
  return blocks
})

const paperLink = computed(() => {
  const h = props.hoverInfo
  if (!h) return ''
  return generateArxivLink(h.arxiv_id ?? null, h.paper_url ?? '')
})
</script>

<template>
  <PopoverRoot v-model:open="open" @update:open="onOpenChange">
    <PopoverAnchor as-child>
      <PopoverTrigger
        as-child
        class="inline-block w-fit max-w-full text-left"
      >
        <button
        type="button"
        :class="[
          'hover:underline underline-offset-2 inline-block w-fit max-w-full truncate text-left text-[13px] font-medium cursor-pointer transition-colors',
          isVisited ? 'paper-link-visited' : 'paper-link-unvisited'
        ]"
        @mouseenter="onTriggerEnter"
        @mouseleave="onTriggerLeave"
        @click="onTriggerClick"
      >
        {{ cellContent }}
      </button>
    </PopoverTrigger>
    </PopoverAnchor>
    <PopoverPortal>
      <PopoverContent
        align="start"
        side="right"
        :side-offset="24"
        :align-offset="-4"
        class="w-[380px] max-h-[85vh] overflow-y-auto overflow-x-hidden bg-white text-gray-900 border border-gray-200 shadow-xl rounded-lg p-4"
        @mouseenter="onContentEnter"
        @mouseleave="onContentLeave"
      >
        <!-- 论文详情，标题为超链接 -->
        <div v-if="infoBlocks.length" class="space-y-1.5 text-sm mb-4">
          <template v-for="(b, i) in infoBlocks" :key="i">
            <a
              v-if="b.type === 'title' && paperLink"
              :href="paperLink"
              target="_blank"
              rel="noopener noreferrer"
              class="font-semibold text-base text-blue-600 hover:text-blue-800 hover:underline block"
              @click="onOpenLink"
            >
              📄 {{ b.content }}
            </a>
            <div v-else-if="b.type === 'title'" class="font-semibold text-base">
              📄 {{ b.content }}
            </div>
            <div v-else-if="b.type === 'separator'" class="border-t border-gray-200 my-1" />
            <div v-else class="text-gray-700 whitespace-pre-wrap break-words">
              {{ b.content }}
            </div>
          </template>
        </div>

        <div class="border-t border-gray-200 my-3" />

        <!-- 当前标签 -->
        <div class="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2">
          <Tag class="h-3.5 w-3.5" />
          当前标签
        </div>
        <div class="flex flex-wrap gap-1.5 mb-3 min-h-[28px]">
          <template v-if="(hoverInfo?.tags?.length ?? 0) > 0">
            <span
              v-for="t in (hoverInfo?.tags ?? [])"
              :key="t.tag_id"
              class="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-gray-100 text-gray-800 text-xs"
            >
              {{ t.tag_name }}
              <button
                type="button"
                class="rounded p-0.5 hover:bg-red-100 text-gray-500 hover:text-red-600 transition-colors"
                aria-label="删除标签"
                @click="onRemoveTag(paperId, t.tag_id)"
              >
                <X class="h-3 w-3" />
              </button>
            </span>
          </template>
          <span v-else class="text-xs text-gray-400">暂无标签</span>
        </div>

        <div class="border-t border-gray-200 my-3" />

        <!-- 添加标签 -->
        <div class="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2">
          <Tag class="h-3.5 w-3.5" />
          添加标签
        </div>
        <AddTagPopover
          :paper-id="paperId"
          :current-tag-names="(hoverInfo?.tags ?? []).map((t) => t.tag_name)"
          @added="emit('tag-added')"
        />
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>
