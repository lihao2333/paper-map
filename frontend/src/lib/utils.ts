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

function collectVenueTagNamesFromHover(h: HoverInfo): string[] {
  const names = new Set<string>()
  for (const t of h.tags ?? []) {
    if (t.tag_name.startsWith('venue.')) names.add(t.tag_name)
  }
  for (const n of h.tag_names ?? []) {
    if (n.startsWith('venue.')) names.add(n)
  }
  return [...names].sort()
}

function collectVenueTagNamesFromStrings(tags: string[]): string[] {
  return [...new Set(tags.filter((t) => t.startsWith('venue.')))].sort()
}

/**
 * 若有以 venue. 开头的标签，在缩写/短标题前显示 [venue.xxx] …（多个 venue 则多个方括号，空格分隔）
 */
export function formatAbbrevWithVenueTags(
  abbrev: string,
  tagSource: string[] | HoverInfo | null | undefined,
): string {
  const base = (abbrev ?? '').trim()
  if (!base) return ''
  let venueNames: string[]
  if (!tagSource) {
    venueNames = []
  } else if (Array.isArray(tagSource)) {
    venueNames = collectVenueTagNamesFromStrings(tagSource)
  } else {
    venueNames = collectVenueTagNamesFromHover(tagSource)
  }
  if (!venueNames.length) return base
  const prefix = venueNames.map((v) => `[${v}]`).join(' ')
  return `${prefix} ${base}`
}
