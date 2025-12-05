import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Paper, PaperListResponse } from '@/types'
import * as api from '@/api'

export const usePapersStore = defineStore('papers', () => {
  const papers = ref<Paper[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(50)
  const loading = ref(false)
  const search = ref('')
  const filterTag = ref('')
  const filterCompany = ref('')
  const filterUniversity = ref('')
  const filterAuthor = ref('')

  const hasMore = computed(() => papers.value.length < total.value)

  async function fetchPapers(reset = false) {
    if (reset) {
      page.value = 1
      papers.value = []
    }

    loading.value = true
    try {
      const response = await api.getPapers({
        page: page.value,
        page_size: pageSize.value,
        search: search.value || undefined,
        tag: filterTag.value || undefined,
        company: filterCompany.value || undefined,
        university: filterUniversity.value || undefined,
        author: filterAuthor.value || undefined,
      })

      if (reset) {
        papers.value = response.items
      } else {
        papers.value = [...papers.value, ...response.items]
      }
      total.value = response.total
    } catch (error) {
      console.error('Failed to fetch papers:', error)
    } finally {
      loading.value = false
    }
  }

  async function loadMore() {
    if (loading.value || !hasMore.value) return
    page.value++
    await fetchPapers()
  }

  function setSearch(value: string) {
    search.value = value
    fetchPapers(true)
  }

  function setFilters(filters: {
    tag?: string
    company?: string
    university?: string
    author?: string
  }) {
    filterTag.value = filters.tag || ''
    filterCompany.value = filters.company || ''
    filterUniversity.value = filters.university || ''
    filterAuthor.value = filters.author || ''
    fetchPapers(true)
  }

  function clearFilters() {
    filterTag.value = ''
    filterCompany.value = ''
    filterUniversity.value = ''
    filterAuthor.value = ''
    search.value = ''
    fetchPapers(true)
  }

  return {
    papers,
    total,
    page,
    pageSize,
    loading,
    search,
    filterTag,
    filterCompany,
    filterUniversity,
    filterAuthor,
    hasMore,
    fetchPapers,
    loadMore,
    setSearch,
    setFilters,
    clearFilters,
  }
})
