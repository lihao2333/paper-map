import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { HoverInfo } from '@/types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | null | undefined): string {
  if (!date) return '-'
  if (date.length === 6) {
    const year = date.substring(0, 4)
    const month = date.substring(4, 6)
    return `${year}-${month}`
  }
  return date
}

/** 从日期提取月份 key，用于分组 (YYYY-MM) */
export function getMonthKey(date: string | null | undefined): string {
  if (!date) return ''
  const s = String(date).trim()
  // yyyyMM (6 位)
  if (s.length >= 6 && /^\d{6}/.test(s)) {
    return `${s.substring(0, 4)}-${s.substring(4, 6)}`
  }
  // yyyy-MM 或 yyyy-MM-dd
  const m = s.match(/^(\d{4})-(\d{1,2})/)
  if (m) return `${m[1]}-${m[2].padStart(2, '0')}`
  return s
}

/** 格式化月份显示 (YYYY年M月) */
export function formatMonth(date: string | null | undefined): string {
  if (!date) return '-'
  const key = getMonthKey(date)
  if (!key) return '-'
  const [y, m] = key.split('-')
  return `${y}年${parseInt(m, 10)}月`
}

export function truncate(str: string, length: number): string {
  if (!str) return ''
  if (str.length <= length) return str
  return str.substring(0, length) + '...'
}

export function generateArxivLink(arxivId: string | null, paperUrl: string): string {
  if (arxivId) {
    return `https://arxiv.org/abs/${arxivId}`
  }
  return paperUrl
}

/** 与标题并排展示的高亮标签：顶会 venue.*（琥珀）与 Hugging Face hf.*（紫罗兰，避免与顶会混淆） */
export const PROMINENT_TAG_PREFIXES = ['venue.', 'hf.'] as const

export function isProminentTagName(name: string): boolean {
  return PROMINENT_TAG_PREFIXES.some((p) => name.startsWith(p))
}

function collectProminentTagNamesFromHover(h: HoverInfo): string[] {
  const names = new Set<string>()
  for (const t of h.tags ?? []) {
    if (isProminentTagName(t.tag_name)) names.add(t.tag_name)
  }
  for (const n of h.tag_names ?? []) {
    if (isProminentTagName(n)) names.add(n)
  }
  return [...names].sort()
}

function collectProminentTagNamesFromStrings(tags: string[]): string[] {
  return [...new Set(tags.filter((t) => isProminentTagName(t)))].sort()
}

/** 标题旁芯片：venue.* + hf.* */
export function getProminentTagNames(
  tagSource: string[] | HoverInfo | null | undefined,
): string[] {
  if (!tagSource) return []
  if (Array.isArray(tagSource)) return collectProminentTagNamesFromStrings(tagSource)
  return collectProminentTagNamesFromHover(tagSource)
}

/** 芯片短文案：venue.NeurIPS → NEURIPS；hf.daily → DAILY */
export function prominentTagShortLabel(full: string): string {
  for (const p of PROMINENT_TAG_PREFIXES) {
    if (full.startsWith(p)) return full.slice(p.length)
  }
  return full
}

/** 矩阵/列表标题旁小芯片 */
export const venueTagChipTriggerClass =
  'venue-chip inline-flex shrink-0 select-none items-center rounded-md border border-amber-400/70 bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-950 shadow-sm dark:border-amber-600/80 dark:bg-amber-950/55 dark:text-amber-50'

export const hfTagChipTriggerClass =
  'hf-chip inline-flex shrink-0 select-none items-center rounded-md border border-violet-400/70 bg-violet-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-violet-950 shadow-sm dark:border-violet-600/80 dark:bg-violet-950/55 dark:text-violet-50'

/** Hover 面板内标签 pill（与触发器同色） */
export const venueTagChipPanelClass =
  'inline-flex items-center gap-1 rounded-md border border-amber-400/80 bg-amber-100 px-2 py-1 text-xs font-bold uppercase tracking-wide text-amber-950 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-50'

export const hfTagChipPanelClass =
  'inline-flex items-center gap-1 rounded-md border border-violet-400/80 bg-violet-100 px-2 py-1 text-xs font-bold uppercase tracking-wide text-violet-950 dark:border-violet-700 dark:bg-violet-950/50 dark:text-violet-50'

/** 详情弹窗 Badge */
export const venueTagChipBadgeClass =
  'rounded-md border border-amber-400/80 bg-amber-100 text-[11px] font-bold uppercase tracking-wide text-amber-950 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-50'

export const hfTagChipBadgeClass =
  'rounded-md border border-violet-400/80 bg-violet-100 text-[11px] font-bold uppercase tracking-wide text-violet-950 dark:border-violet-700 dark:bg-violet-950/50 dark:text-violet-50'

export function prominentTagTriggerClassFor(tagName: string): string {
  if (tagName.startsWith('venue.')) return venueTagChipTriggerClass
  if (tagName.startsWith('hf.')) return hfTagChipTriggerClass
  return ''
}

export function prominentTagPanelClassFor(tagName: string): string {
  if (tagName.startsWith('venue.')) return venueTagChipPanelClass
  if (tagName.startsWith('hf.')) return hfTagChipPanelClass
  return ''
}

export function prominentTagBadgeClassFor(tagName: string): string {
  if (tagName.startsWith('venue.')) return venueTagChipBadgeClass
  if (tagName.startsWith('hf.')) return hfTagChipBadgeClass
  return ''
}

export function paperDisplayTitle(abbrev: string | null | undefined): string {
  return (abbrev ?? '').trim()
}
