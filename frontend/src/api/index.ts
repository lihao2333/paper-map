import axios from 'axios'
import type { Paper, PaperListResponse, Tag, TagTreeNode, WatchedItem, Stats } from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// Papers
export async function getPapers(params?: {
  page?: number
  page_size?: number
  search?: string
  tag?: string
  company?: string
  university?: string
  author?: string
}): Promise<PaperListResponse> {
  const { data } = await api.get('/papers', { params })
  return data
}

export async function getPaper(paperId: string): Promise<Paper> {
  const { data } = await api.get(`/papers/${paperId}`)
  return data
}

export async function createPaper(paper: Partial<Paper>): Promise<Paper> {
  const { data } = await api.post('/papers', paper)
  return data
}

export async function updatePaper(paperId: string, paper: Partial<Paper>): Promise<Paper> {
  const { data } = await api.put(`/papers/${paperId}`, paper)
  return data
}

export async function deletePaper(paperId: string): Promise<void> {
  await api.delete(`/papers/${paperId}`)
}

/** 补全缺少作者信息的论文（从 arXiv API 拉取） */
export async function completeAuthors(): Promise<{ completed: number; total: number; message: string }> {
  const { data } = await api.post('/papers/complete-authors')
  return data
}

/** 补全缺少 AI 总结的论文（调用 AI 生成） */
export async function completeSummaries(): Promise<{ completed: number; total: number; message: string }> {
  const { data } = await api.post('/papers/complete-summaries', null, { timeout: 120000 })
  return data
}

/** 矩阵标签参数：多条规则逗号拼接，OR 语义；空数组/未传表示不按标签筛选 */
function matrixTagRulesParam(rules: string[] | undefined): string {
  if (rules === undefined || rules.length === 0) return ''
  return rules.join(',')
}

// Matrix（tag_rules：多个 glob 逗号分隔；空表示不按标签筛选；仍支持旧参数 tag_rule）
export async function getCompanyMatrix(opts?: {
  tag_rules?: string[]
}): Promise<{ companies: string[]; papers: any[] }> {
  const tag_rules = matrixTagRulesParam(opts?.tag_rules)
  const { data } = await api.get('/matrix/companies', { params: { tag_rules } })
  return data
}

export async function getUniversityMatrix(opts?: {
  tag_rules?: string[]
}): Promise<{ universities: string[]; papers: any[] }> {
  const tag_rules = matrixTagRulesParam(opts?.tag_rules)
  const { data } = await api.get('/matrix/universities', { params: { tag_rules } })
  return data
}

export async function getAuthorMatrix(opts?: {
  tag_rules?: string[]
}): Promise<{ authors: string[]; papers: any[] }> {
  const tag_rules = matrixTagRulesParam(opts?.tag_rules)
  const { data } = await api.get('/matrix/authors', { params: { tag_rules } })
  return data
}

// Tags
export async function getTags(): Promise<Tag[]> {
  const { data } = await api.get('/tags')
  return data
}

export async function getTagTree(): Promise<TagTreeNode[]> {
  const { data } = await api.get('/tags/tree')
  return data
}

export async function getTopLevelTags(): Promise<{ tag_name: string; tag_id: number | null }[]> {
  const { data } = await api.get('/tags/top-level')
  return data
}

export async function getTagPapers(tagId: number): Promise<Paper[]> {
  const { data } = await api.get(`/tags/${tagId}/papers`)
  return data
}

export async function getTagMatrix(prefix: string): Promise<{ tags: string[]; papers: any[] }> {
  const { data } = await api.get(`/tags/prefix/${prefix}/matrix`)
  return data
}

export async function createTag(tagName: string): Promise<Tag> {
  const { data } = await api.post('/tags', { tag_name: tagName })
  return data
}

export async function updateTag(tagId: number, tagName: string): Promise<void> {
  await api.put(`/tags/${tagId}`, { tag_name: tagName })
}

export async function deleteTag(tagId: number): Promise<void> {
  await api.delete(`/tags/${tagId}`)
}

export async function addTagToPaper(paperId: string, tagName: string): Promise<void> {
  await api.post('/tags/paper', { paper_id: paperId, tag_name: tagName })
}

export async function removeTagFromPaper(paperId: string, tagId: number): Promise<void> {
  await api.delete(`/tags/paper/${paperId}/${tagId}`)
}

// Watched
export async function getWatchedCompanies(): Promise<WatchedItem[]> {
  const { data } = await api.get('/watched/companies')
  return data
}

export async function createWatchedCompany(item: Omit<WatchedItem, 'id'>): Promise<WatchedItem> {
  const { data } = await api.post('/watched/companies', item)
  return data
}

export async function updateWatchedCompany(id: number, item: Partial<WatchedItem>): Promise<void> {
  await api.put(`/watched/companies/${id}`, item)
}

export async function deleteWatchedCompany(id: number): Promise<void> {
  await api.delete(`/watched/companies/${id}`)
}

export async function getWatchedUniversities(): Promise<WatchedItem[]> {
  const { data } = await api.get('/watched/universities')
  return data
}

export async function createWatchedUniversity(item: Omit<WatchedItem, 'id'>): Promise<WatchedItem> {
  const { data } = await api.post('/watched/universities', item)
  return data
}

export async function updateWatchedUniversity(id: number, item: Partial<WatchedItem>): Promise<void> {
  await api.put(`/watched/universities/${id}`, item)
}

export async function deleteWatchedUniversity(id: number): Promise<void> {
  await api.delete(`/watched/universities/${id}`)
}

export async function getWatchedAuthors(): Promise<WatchedItem[]> {
  const { data } = await api.get('/watched/authors')
  return data
}

export async function createWatchedAuthor(item: Omit<WatchedItem, 'id'>): Promise<WatchedItem> {
  const { data } = await api.post('/watched/authors', item)
  return data
}

export async function updateWatchedAuthor(id: number, item: Partial<WatchedItem>): Promise<void> {
  await api.put(`/watched/authors/${id}`, item)
}

export async function deleteWatchedAuthor(id: number): Promise<void> {
  await api.delete(`/watched/authors/${id}`)
}

// Collect
export async function collectPaper(url: string, alias?: string, tags?: string[]): Promise<{ paper_id: string }> {
  const { data } = await api.post('/collect', { url, alias, tags })
  return data
}

export async function batchCollect(urls: string[]): Promise<any> {
  const { data } = await api.post('/collect/batch', urls)
  return data
}

// Stats
export async function getStats(): Promise<Stats> {
  const { data } = await api.get('/stats')
  return data
}
