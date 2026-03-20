<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { HeaderRulesTooltip } from '@/components/ui'
import PaperCellPanel from '@/components/matrix/PaperCellPanel.vue'
import type { HoverInfo } from '@/types'
import * as api from '@/api'
import { formatAbbrevWithVenueTags, formatMonth, generateArxivLink, getMonthKey } from '@/lib/utils'

const STORAGE_KEY = 'matrix-table-col-widths'
const VISITED_KEY = 'matrix-table-visited-papers'
const DEFAULT_MONTH_WIDTH = 96
const DEFAULT_COL_WIDTH = 176
const MIN_COL_WIDTH = 100

interface MatrixCell {
  alias: string
  full_name: string
  summary: string
}

interface MatrixRow {
  paper_id: string
  date: string
  arxiv_id: string | null
  paper_url: string
  cells: Record<string, MatrixCell>
  hover_info?: HoverInfo
}

interface Props {
  headers: string[]
  rows: MatrixRow[]
  loading?: boolean
  /** 表头匹配规则，用于 hover 显示：header 名称 -> 匹配规则列表 */
  headerRules?: Record<string, string[]>
  /** 是否为分层表头（标签用 dot 分隔层级，如 architecture.diffusion） */
  hierarchicalHeaders?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  headerRules: () => ({}),
  hierarchicalHeaders: false,
})

const emit = defineEmits<{
  (e: 'tag-added'): void
}>()

/** 已打开过的论文 paper_id 集合，用于着色（蓝=未打开，红=已打开） */
const visitedPapers = ref<Set<string>>(new Set())

function loadVisited() {
  try {
    const raw = localStorage.getItem(VISITED_KEY)
    if (raw) {
      const arr = JSON.parse(raw) as string[]
      visitedPapers.value = new Set(arr ?? [])
    }
  } catch {
    /* ignore */
  }
}

function markVisited(paperId: string) {
  visitedPapers.value.add(paperId)
  try {
    localStorage.setItem(VISITED_KEY, JSON.stringify([...visitedPapers.value]))
  } catch {
    /* ignore */
  }
}

function isVisited(paperId: string): boolean {
  return visitedPapers.value.has(paperId)
}

onMounted(loadVisited)

/** 列宽：月份列 + 各公司列，持久化到 localStorage */
const monthWidth = ref(DEFAULT_MONTH_WIDTH)
const colWidths = ref<Record<string, number>>({})

function loadWidths() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const data = JSON.parse(raw)
      if (typeof data.month === 'number') monthWidth.value = Math.max(MIN_COL_WIDTH, data.month)
      if (data.cols && typeof data.cols === 'object') {
        colWidths.value = { ...data.cols }
        for (const k of Object.keys(colWidths.value)) {
          colWidths.value[k] = Math.max(MIN_COL_WIDTH, colWidths.value[k])
        }
      }
    }
  } catch {
    /* ignore */
  }
}

function saveWidths() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ month: monthWidth.value, cols: colWidths.value }))
}

function getColWidth(header: string): number {
  return colWidths.value[header] ?? DEFAULT_COL_WIDTH
}

watch(
  () => props.headers,
  (headers) => {
    for (const h of headers) {
      if (!(h in colWidths.value)) colWidths.value[h] = DEFAULT_COL_WIDTH
    }
  },
  { immediate: true }
)
onMounted(loadWidths)

/** 拖拽调整列宽：拖拽期间直接更新 DOM 并节流，避免 Vue 响应式导致的大表重绘卡顿 */
const colgroupEl = ref<HTMLTableColElement | null>(null)
let resizing: { type: 'month' | 'col'; key?: string; startX: number; startW: number; lastW: number } | null = null
let rafId: number | null = null

function getColEl(index: number): HTMLTableColElement | null {
  const cg = colgroupEl.value
  if (!cg) return null
  const col = cg.querySelectorAll('col')[index]
  return (col as HTMLTableColElement) || null
}

function applyResizeWidth() {
  if (!resizing) return
  rafId = null
  const newW = resizing.lastW
  const colIdx = resizing.type === 'month' ? 0 : (props.headers.indexOf(resizing.key!) + 1)
  const col = getColEl(colIdx)
  if (col) col.style.width = `${newW}px`
}

function onResizeStart(e: MouseEvent, type: 'month' | 'col', key?: string) {
  e.preventDefault()
  const w = type === 'month' ? monthWidth.value : (key ? getColWidth(key) : DEFAULT_COL_WIDTH)
  resizing = { type, key, startX: e.clientX, startW: w, lastW: w }
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup', onResizeEnd)
}

function onResizeMove(e: MouseEvent) {
  if (!resizing) return
  const delta = e.clientX - resizing.startX
  const newW = Math.max(MIN_COL_WIDTH, resizing.startW + delta)
  resizing.lastW = newW
  if (rafId === null) {
    rafId = requestAnimationFrame(applyResizeWidth)
  }
}

function onResizeEnd() {
  if (!resizing) return
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
  const finalW = resizing.lastW
  if (resizing.type === 'month') {
    monthWidth.value = finalW
  } else if (resizing.key) {
    colWidths.value[resizing.key] = finalW
  }
  resizing = null
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
  saveWidths()
}

onUnmounted(() => {
  if (rafId !== null) cancelAnimationFrame(rafId)
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
})

interface GroupedRow {
  monthKey: string
  monthDisplay: string
  papers: MatrixRow[]
  cells: Record<string, Array<{ cell: MatrixCell; row: MatrixRow }>>
}

/** 按月分组 */
const groupedRows = computed<GroupedRow[]>(() => {
  if (!props.rows.length) return []
  const byMonth = new Map<string, MatrixRow[]>()
  for (const row of props.rows) {
    const key = getMonthKey(row.date) || '_'
    if (!byMonth.has(key)) byMonth.set(key, [])
    byMonth.get(key)!.push(row)
  }
  const keys = [...byMonth.keys()].filter((k) => k !== '_').sort().reverse()
  if (byMonth.has('_')) keys.push('_')
  const result: GroupedRow[] = []
  for (const key of keys) {
    const papers = byMonth.get(key)!
    const cells: Record<string, Array<{ cell: MatrixCell; row: MatrixRow }>> = {}
    for (const h of props.headers) cells[h] = []
    for (const row of papers) {
      for (const h of props.headers) {
        const cell = row.cells[h]
        if (cell && (cell.alias || cell.full_name)) {
          cells[h].push({ cell, row })
        }
      }
    }
    result.push({
      monthKey: key,
      monthDisplay: key === '_' ? '未知' : formatMonth(key),
      papers,
      cells,
    })
  }
  return result
})

/** 每个月的 subRows：按最大列数展开，每行一个 subline，便于加全宽分隔线 */
const subRowsByGroup = computed(() => {
  return groupedRows.value.map((grp) => {
    const maxLen = Math.max(1, ...props.headers.map((h) => grp.cells[h]?.length ?? 0))
    const rows: Array<Record<string, { cell: MatrixCell; row: MatrixRow } | null>> = []
    for (let i = 0; i < maxLen; i++) {
      const row: Record<string, { cell: MatrixCell; row: MatrixRow } | null> = {}
      for (const h of props.headers) {
        const arr = grp.cells[h]
        row[h] = arr && arr[i] ? arr[i] : null
      }
      rows.push(row)
    }
    return { grp, subRows: rows }
  })
})

function openLink(row: MatrixRow) {
  markVisited(row.paper_id)
  const url = generateArxivLink(row.arxiv_id, row.paper_url)
  window.open(url, '_blank')
}

function getCellContent(cell: MatrixCell | undefined): string {
  if (!cell) return ''
  return cell.alias || cell.full_name || ''
}

function getCellDisplayContent(cell: MatrixCell | undefined, row: MatrixRow): string {
  const base = getCellContent(cell)
  return formatAbbrevWithVenueTags(base, row.hover_info ?? null)
}

/** 分层表头：支持多级标签（a、a.b、a.b.c 等），每行显示一级，含 colspan 分组 */
interface HeaderLevelCell {
  text: string
  colspan?: number
  headerKey?: string
}
const headerRows = computed<HeaderLevelCell[][]>(() => {
  if (!props.hierarchicalHeaders || !props.headers.length) return []
  const levels = props.headers.map((h) => h.split('.'))
  const maxDepth = Math.max(...levels.map((l) => l.length), 1)

  if (maxDepth < 2) {
    return [[...props.headers.map((h) => ({ text: h, headerKey: h }))]]
  }

  const rows: HeaderLevelCell[][] = []

  for (let r = 0; r < maxDepth; r++) {
    const row: HeaderLevelCell[] = []
    let i = 0
    while (i < props.headers.length) {
      const parts = levels[i]
      const prefix = parts.slice(0, r + 1).join('.')
      let colspan = 0
      while (i + colspan < props.headers.length) {
        const p = levels[i + colspan].slice(0, r + 1).join('.')
        if (p !== prefix) break
        colspan++
      }
      const text = parts.length > r ? parts[r] : ''
      const isLastRow = r === maxDepth - 1
      row.push({
        text,
        colspan: colspan > 1 ? colspan : undefined,
        headerKey: isLastRow ? props.headers[i] : undefined,
      })
      i += colspan
    }
    rows.push(row)
  }

  return rows
})

const hasHierarchicalHeader = computed(
  () => props.hierarchicalHeaders && headerRows.value.length >= 2
)

/** 获取有效的 hover 信息：优先用 hover_info，否则用 cell 构建简易版 */
function getEffectiveHoverInfo(row: MatrixRow, cell: MatrixCell): HoverInfo | null {
  const h = row.hover_info
  if (h && (h.full_name || h.summary || h.paper_id)) {
    return h
  }
  if (cell?.full_name || cell?.summary) {
    return {
      full_name: cell.full_name,
      summary: cell.summary,
      paper_id: row.paper_id,
      date: row.date,
    }
  }
  return null
}

async function removeTag(paperId: string, tagId: number) {
  try {
    await api.removeTagFromPaper(paperId, tagId)
    emit('tag-added')
  } catch {
    /* ignore */
  }
}
</script>

<template>
  <div class="flex-1 min-h-0 flex flex-col border rounded-xl overflow-auto bg-card shadow-sm">
      <table class="w-full border-separate border-spacing-0 flex-shrink-0" style="table-layout: fixed">
        <colgroup ref="colgroupEl">
          <col :style="{ width: monthWidth + 'px' }" />
          <col v-for="h in headers" :key="h" :style="{ width: getColWidth(h) + 'px' }" />
        </colgroup>
        <thead>
          <!-- 分层表头：支持多级标签（a、a.b、a.b.c 等），标签保持原样不大写 -->
          <template v-if="hasHierarchicalHeader">
            <tr
              v-for="(row, rowIdx) in headerRows"
              :key="'H' + rowIdx"
              class="bg-[hsl(var(--card))]"
            >
              <th
                v-if="rowIdx === 0"
                :rowspan="headerRows.length"
                class="sticky top-0 left-0 z-50 pl-4 pr-0 py-2.5 text-left text-sm font-semibold text-muted-foreground tracking-wider bg-[hsl(var(--card))] border-b border-r-2 border-border [border-right-style:solid] select-none relative"
                :style="{ width: monthWidth + 'px', minWidth: MIN_COL_WIDTH + 'px' }"
              >
                <span>月份</span>
                <div
                  class="resize-handle absolute right-0 top-0 bottom-0 w-3 cursor-col-resize hover:bg-primary/20 active:bg-primary/40 touch-none flex items-center justify-center z-10"
                  role="separator"
                  aria-label="调整列宽"
                  @mousedown="onResizeStart($event, 'month')"
                >
                  <span class="w-px h-5 bg-border/80" />
                </div>
              </th>
              <th
                v-for="(cell, cellIdx) in row"
                :key="'R' + rowIdx + '-' + (cell.headerKey ?? cellIdx)"
                :colspan="cell.colspan ?? 1"
                :class="[
                  'sticky top-0 z-40 px-2 py-2 text-center font-semibold text-muted-foreground tracking-wider bg-[hsl(var(--card))] border-b border-r-2 border-border [border-right-style:solid]',
                  rowIdx === 0 ? 'text-xs' : 'text-sm',
                  cell.headerKey && 'select-none relative'
                ]"
                :style="cell.headerKey ? { width: getColWidth(cell.headerKey) + 'px', minWidth: MIN_COL_WIDTH + 'px' } : {}"
              >
                <span class="truncate block">{{ cell.text }}</span>
                <div
                  v-if="cell.headerKey"
                  class="resize-handle absolute right-0 top-0 bottom-0 w-3 cursor-col-resize hover:bg-primary/20 active:bg-primary/40 touch-none flex items-center justify-center z-10"
                  role="separator"
                  aria-label="调整列宽"
                  @mousedown="onResizeStart($event, 'col', cell.headerKey)"
                >
                  <span class="w-px h-5 bg-border/80" />
                </div>
              </th>
            </tr>
          </template>
          <!-- 普通单行表头（标签模式不大写） -->
          <tr v-else class="bg-[hsl(var(--card))]">
            <th
              :class="[
                'sticky top-0 left-0 z-50 pl-4 pr-0 py-2.5 text-left text-sm font-semibold text-muted-foreground tracking-wider bg-[hsl(var(--card))] border-b border-r-2 border-border [border-right-style:solid] select-none relative',
                !hierarchicalHeaders && 'uppercase'
              ]"
              :style="{ width: monthWidth + 'px', minWidth: MIN_COL_WIDTH + 'px' }"
            >
              <span>月份</span>
              <div
                class="resize-handle absolute right-0 top-0 bottom-0 w-3 cursor-col-resize hover:bg-primary/20 active:bg-primary/40 touch-none flex items-center justify-center z-10"
                role="separator"
                aria-label="调整列宽"
                @mousedown="onResizeStart($event, 'month')"
              >
                <span class="w-px h-5 bg-border/80" />
              </div>
            </th>
            <th
              v-for="header in headers"
              :key="header"
              :class="[
                'sticky top-0 z-40 px-4 pr-0 py-2.5 text-center text-base font-semibold text-muted-foreground tracking-wider bg-[hsl(var(--card))] border-b border-r-2 border-border [border-right-style:solid] select-none relative',
                !hierarchicalHeaders && 'uppercase'
              ]"
              :style="{ width: getColWidth(header) + 'px', minWidth: MIN_COL_WIDTH + 'px' }"
            >
              <HeaderRulesTooltip
                v-if="headerRules?.[header]?.length"
                :header="header"
                :rules="headerRules[header] ?? []"
                class="inline-block max-w-full"
              >
                <span class="truncate block cursor-help">{{ header }}</span>
              </HeaderRulesTooltip>
              <span v-else class="truncate block">{{ header }}</span>
              <div
                class="resize-handle absolute right-0 top-0 bottom-0 w-3 cursor-col-resize hover:bg-primary/20 active:bg-primary/40 touch-none flex items-center justify-center z-10"
                role="separator"
                aria-label="调整列宽"
                @mousedown="onResizeStart($event, 'col', header)"
              >
                <span class="w-px h-5 bg-border/80" />
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="({ grp, subRows }, grpIdx) in subRowsByGroup" :key="grp.monthKey">
            <tr
              v-for="(subRow, subIdx) in subRows"
              :key="`${grp.monthKey}-${subIdx}`"
              :class="[
                'group/row transition-colors',
                grpIdx % 2 === 0 ? 'bg-card' : 'bg-background',
                'hover:bg-primary/[0.04]'
              ]"
            >
              <td
                v-if="subIdx === 0"
                :rowspan="subRows.length"
                :class="[
                  'px-4 py-2.5 text-sm whitespace-nowrap sticky left-0 z-30 border-r-2 border-border [border-right-style:solid] align-top transition-colors border-b-2 border-border',
                  grpIdx % 2 === 0 ? 'bg-[hsl(var(--card))]' : 'bg-[hsl(var(--background))]'
                ]"
              >
                <div class="font-semibold text-foreground/80 text-[13px]">{{ grp.monthDisplay }}</div>
                <div class="text-[11px] text-muted-foreground mt-0.5">{{ grp.papers.length }} 篇</div>
              </td>
              <td
                v-for="header in headers"
                :key="header"
                :class="[
                  'px-4 py-2.5 text-sm align-top border-r-2 border-border [border-right-style:solid] overflow-hidden',
                  subIdx === subRows.length - 1 ? 'border-b-[3px] border-border' : 'border-b border-dashed border-border/20'
                ]"
              >
                <!-- 统一使用 PaperCellPanel：hover 显示、左键固定、ctrl+左键打开链接、编辑标签，标签矩阵与关注矩阵逻辑一致 -->
                <PaperCellPanel
                  v-if="subRow[header]"
                  :hover-info="getEffectiveHoverInfo(subRow[header]!.row, subRow[header]!.cell)"
                  :cell-content="getCellDisplayContent(subRow[header]!.cell, subRow[header]!.row)"
                  :is-visited="isVisited(subRow[header]!.row.paper_id)"
                  :paper-id="subRow[header]!.row.paper_id"
                  :on-open-link="() => openLink(subRow[header]!.row)"
                  :on-remove-tag="removeTag"
                  @tag-added="emit('tag-added')"
                />
              </td>
            </tr>
          </template>
          <tr v-if="groupedRows.length === 0 && !loading">
            <td :colspan="headers.length + 1" class="px-4 py-12 text-center text-muted-foreground text-sm">
              暂无数据
            </td>
          </tr>
          <tr v-if="loading">
            <td :colspan="headers.length + 1" class="px-4 py-12 text-center text-muted-foreground">
              <div class="flex items-center justify-center gap-2 text-sm">
                <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
                  <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                加载中...
              </div>
            </td>
          </tr>
        </tbody>
      </table>
  </div>
</template>

<style scoped>
/* 论文链接着色：未打开=蓝，已打开=红，与 a.link-visualized 一致 */
.paper-link-unvisited {
  color: hsl(var(--link));
  transition: color 0.2s ease;
}
.paper-link-unvisited:hover {
  color: hsl(var(--link-hover));
}
.paper-link-visited {
  color: hsl(var(--link-visited));
  transition: color 0.2s ease;
}
.paper-link-visited:hover {
  color: hsl(var(--link-hover));
}
</style>
