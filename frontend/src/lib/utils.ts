import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

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
