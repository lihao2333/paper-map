<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { usePapersStore } from '@/stores/papers'
import { Input, Button, Badge } from '@/components/ui'
import PaperTable from '@/components/papers/PaperTable.vue'
import PaperDetail from '@/components/papers/PaperDetail.vue'
import type { Paper } from '@/types'
import { Search, X, Filter } from 'lucide-vue-next'
import { useIntersectionObserver } from '@vueuse/core'
import * as api from '@/api'

const papersStore = usePapersStore()

const searchInput = ref('')
const selectedPaper = ref<Paper | null>(null)
const detailOpen = ref(false)
const loadMoreTrigger = ref<HTMLElement | null>(null)

const activeFilters = ref<{
  tag: string
  company: string
  university: string
  author: string
}>({
  tag: '',
  company: '',
  university: '',
  author: '',
})

function handleSearch() {
  papersStore.setSearch(searchInput.value)
}

function clearSearch() {
  searchInput.value = ''
  papersStore.setSearch('')
}

function selectPaper(paper: Paper) {
  selectedPaper.value = paper
  detailOpen.value = true
}

async function addTagToPaper(tagName: string) {
  if (selectedPaper.value) {
    try {
      await api.addTagToPaper(selectedPaper.value.paper_id, tagName)
      // Refresh paper data
      const updated = await api.getPaper(selectedPaper.value.paper_id)
      selectedPaper.value = updated
      papersStore.fetchPapers(true)
    } catch (error) {
      console.error('Failed to add tag:', error)
    }
  }
}

function clearFilters() {
  activeFilters.value = { tag: '', company: '', university: '', author: '' }
  papersStore.clearFilters()
}

const completeAuthorsLoading = ref(false)
const completeSummariesLoading = ref(false)

async function onCompleteAuthors() {
  completeAuthorsLoading.value = true
  try {
    const res = await api.completeAuthors()
    papersStore.fetchPapers(true)
    alert(res.total === 0 ? '暂无需补全的论文' : `已补全 ${res.completed}/${res.total} 篇论文的作者`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || '补全失败')
  } finally {
    completeAuthorsLoading.value = false
  }
}

async function onCompleteSummaries() {
  completeSummariesLoading.value = true
  try {
    const res = await api.completeSummaries()
    papersStore.fetchPapers(true)
    alert(res.total === 0 ? '暂无需补全的论文' : `已补全 ${res.completed}/${res.total} 篇论文的 AI 总结`)
  } catch (e: any) {
    alert(e?.response?.data?.detail || '补全失败')
  } finally {
    completeSummariesLoading.value = false
  }
}

// Infinite scroll
useIntersectionObserver(
  loadMoreTrigger,
  ([{ isIntersecting }]) => {
    if (isIntersecting && papersStore.hasMore && !papersStore.loading) {
      papersStore.loadMore()
    }
  },
  { threshold: 0.1 }
)

onMounted(() => {
  papersStore.fetchPapers(true)
})

watch(searchInput, (val) => {
  if (val === '') {
    papersStore.setSearch('')
  }
})
</script>

<template>
  <div class="space-y-4">
    <!-- Search and Filters -->
    <div class="flex items-center gap-4">
      <div class="relative flex-1 max-w-md">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          v-model="searchInput"
          placeholder="搜索论文标题、ID、摘要..."
          class="pl-10 pr-10"
          @keyup.enter="handleSearch"
        />
        <button
          v-if="searchInput"
          class="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          @click="clearSearch"
        >
          <X class="h-4 w-4" />
        </button>
      </div>
      <Button @click="handleSearch">搜索</Button>
      <Button variant="outline" @click="papersStore.fetchPapers(true)">刷新</Button>
      <Button
        variant="outline"
        :disabled="completeAuthorsLoading"
        @click="onCompleteAuthors"
      >
        {{ completeAuthorsLoading ? '补全中...' : '补全作者' }}
      </Button>
      <Button
        variant="outline"
        :disabled="completeSummariesLoading"
        @click="onCompleteSummaries"
      >
        {{ completeSummariesLoading ? '补全中...' : '补全AI总结' }}
      </Button>
    </div>

    <!-- Active Filters -->
    <div
      v-if="papersStore.filterTag || papersStore.filterCompany || papersStore.filterUniversity || papersStore.filterAuthor"
      class="flex items-center gap-2"
    >
      <Filter class="h-4 w-4 text-muted-foreground" />
      <Badge v-if="papersStore.filterTag" variant="secondary" class="gap-1">
        标签: {{ papersStore.filterTag }}
        <button @click="papersStore.setFilters({ ...activeFilters, tag: '' })">
          <X class="h-3 w-3" />
        </button>
      </Badge>
      <Badge v-if="papersStore.filterCompany" variant="secondary" class="gap-1">
        公司: {{ papersStore.filterCompany }}
        <button @click="papersStore.setFilters({ ...activeFilters, company: '' })">
          <X class="h-3 w-3" />
        </button>
      </Badge>
      <Badge v-if="papersStore.filterUniversity" variant="secondary" class="gap-1">
        高校: {{ papersStore.filterUniversity }}
        <button @click="papersStore.setFilters({ ...activeFilters, university: '' })">
          <X class="h-3 w-3" />
        </button>
      </Badge>
      <Badge v-if="papersStore.filterAuthor" variant="secondary" class="gap-1">
        作者: {{ papersStore.filterAuthor }}
        <button @click="papersStore.setFilters({ ...activeFilters, author: '' })">
          <X class="h-3 w-3" />
        </button>
      </Badge>
      <Button variant="ghost" size="sm" @click="clearFilters">
        清除全部
      </Button>
    </div>

    <!-- Stats -->
    <div class="flex items-center gap-4 text-sm text-muted-foreground">
      <span>共 {{ papersStore.total }} 篇论文</span>
      <span>·</span>
      <span>已加载 {{ papersStore.papers.length }} 篇</span>
    </div>

    <!-- Table -->
    <PaperTable
      :papers="papersStore.papers"
      :loading="papersStore.loading"
      @select="selectPaper"
    />

    <!-- Load More Trigger -->
    <div ref="loadMoreTrigger" class="h-10 flex items-center justify-center">
      <span v-if="papersStore.loading" class="text-sm text-muted-foreground">
        加载更多...
      </span>
      <span v-else-if="!papersStore.hasMore && papersStore.papers.length > 0" class="text-sm text-muted-foreground">
        已加载全部
      </span>
    </div>

    <!-- Paper Detail Dialog -->
    <PaperDetail
      :paper="selectedPaper"
      :open="detailOpen"
      @update:open="detailOpen = $event"
      @add-tag="addTagToPaper"
    />
  </div>
</template>
