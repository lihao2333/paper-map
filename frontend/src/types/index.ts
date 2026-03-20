export interface Paper {
  paper_id: string
  arxiv_id: string | null
  paper_url: string
  date: string | null
  alias: string
  full_name: string
  abstract: string
  summary: string
  arxiv_comments: string | null
  is_comment_used: boolean
  company_names: string[]
  university_names: string[]
  author_names: string[]
  tags: string[]
  github_url: string | null
}

export interface PaperListResponse {
  items: Paper[]
  total: number
  page: number
  page_size: number
}

export interface Tag {
  tag_id: number
  tag_name: string
  paper_count: number
}

export interface TagTreeNode {
  tag_id: number | null
  tag_name: string
  full_path: string
  children: TagTreeNode[]
  paper_count: number
}

export interface WatchedItem {
  id: number
  name: string
  match_rule: string
}

export interface MatrixCell {
  alias: string
  full_name: string
  summary: string
}

export interface PaperTag {
  tag_id: number
  tag_name: string
}

export interface HoverInfo {
  full_name?: string
  abstract?: string
  summary?: string
  company_names?: string[]
  university_names?: string[]
  author_names?: string[]
  tag_names?: string[]
  /** 含 tag_id，用于删除等操作 */
  tags?: PaperTag[]
  date?: string
  paper_id?: string
  arxiv_id?: string | null
  paper_url?: string
  github_url?: string | null
}

export interface MatrixRow {
  paper_id: string
  date: string
  arxiv_id: string | null
  paper_url: string
  cells: Record<string, MatrixCell>
  hover_info?: HoverInfo
}

export interface MatrixResponse {
  headers: string[]
  rows: MatrixRow[]
}

export interface Stats {
  total_papers: number
  total_tags: number
  watched_companies: number
  watched_universities: number
  watched_authors: number
}
