<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { TagTreeNode, Paper } from '@/types'
import TagTree from '@/components/tags/TagTree.vue'
import { Card, Button, Badge } from '@/components/ui'
import * as api from '@/api'
import { RefreshCw, ExternalLink, Github } from 'lucide-vue-next'
import {
  formatAbbrevWithVenueTags,
  formatDate,
  formatMonth,
  generateArxivLink,
  getMonthKey,
  truncate,
} from '@/lib/utils'

const tagTree = ref<TagTreeNode[]>([])
const selectedTag = ref<TagTreeNode | null>(null)
const tagPapers = ref<Paper[]>([])
const loading = ref(false)
const papersLoading = ref(false)

async function fetchTagTree() {
  loading.value = true
  try {
    tagTree.value = await api.getTagTree()
  } catch (error) {
    console.error('Failed to fetch tag tree:', error)
  } finally {
    loading.value = false
  }
}

async function fetchTagPapers(tagId: number) {
  papersLoading.value = true
  try {
    tagPapers.value = await api.getTagPapers(tagId)
  } catch (error) {
    console.error('Failed to fetch tag papers:', error)
    tagPapers.value = []
  } finally {
    papersLoading.value = false
  }
}

function selectTag(node: TagTreeNode) {
  selectedTag.value = node
  if (node.tag_id) {
    fetchTagPapers(node.tag_id)
  } else {
    tagPapers.value = []
  }
}

/** 按月分组，组内顶格排序 */
const papersByMonth = computed(() => {
  const papers = tagPapers.value
  if (!papers.length) return []
  const byMonth = new Map<string, Paper[]>()
  for (const p of papers) {
    const key = getMonthKey(p.date) || '_'
    if (!byMonth.has(key)) byMonth.set(key, [])
    byMonth.get(key)!.push(p)
  }
  const keys = [...byMonth.keys()].filter((k) => k !== '_').sort().reverse()
  if (byMonth.has('_')) keys.push('_')
  return keys.map((key) => ({
    monthKey: key,
    monthDisplay: key === '_' ? '未知' : formatMonth(key),
    papers: byMonth.get(key)!,
  }))
})

function openLink(paper: Paper) {
  const url = generateArxivLink(paper.arxiv_id, paper.paper_url)
  window.open(url, '_blank')
}

onMounted(fetchTagTree)
</script>

<template>
  <div class="flex gap-6 h-[calc(100vh-8rem)]">
    <!-- Tag Tree Panel -->
    <Card class="w-80 flex-shrink-0 flex flex-col">
      <div class="p-4 border-b flex items-center justify-between">
        <h3 class="font-semibold">标签树</h3>
        <Button variant="ghost" size="icon" :disabled="loading" @click="fetchTagTree">
          <RefreshCw :class="['h-4 w-4', loading && 'animate-spin']" />
        </Button>
      </div>
      <div class="flex-1 overflow-y-auto p-2">
        <div v-if="loading" class="flex items-center justify-center h-full">
          <svg class="animate-spin h-6 w-6 text-muted-foreground" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
            <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        </div>
        <TagTree
          v-else
          :nodes="tagTree"
          :selected-tag-id="selectedTag?.tag_id"
          @select="selectTag"
        />
      </div>
    </Card>

    <!-- Papers Panel -->
    <Card class="flex-1 flex flex-col">
      <div class="p-4 border-b">
        <div v-if="selectedTag" class="flex items-center gap-2">
          <h3 class="font-semibold">{{ selectedTag.full_path }}</h3>
          <Badge>{{ tagPapers.length }} 篇论文</Badge>
        </div>
        <div v-else class="text-muted-foreground">
          请选择一个标签查看关联论文
        </div>
      </div>
      <div class="flex-1 overflow-y-auto p-4">
        <div v-if="papersLoading" class="flex items-center justify-center h-full">
          <svg class="animate-spin h-6 w-6 text-muted-foreground" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
            <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        </div>
        <div v-else-if="!selectedTag" class="flex items-center justify-center h-full text-muted-foreground">
          点击左侧标签树选择标签
        </div>
        <div v-else-if="tagPapers.length === 0" class="flex items-center justify-center h-full text-muted-foreground">
          该标签下暂无论文
        </div>
        <div v-else class="space-y-6">
          <div
            v-for="grp in papersByMonth"
            :key="grp.monthKey"
            class="space-y-3"
          >
            <div class="text-xs font-semibold text-muted-foreground uppercase tracking-wider sticky top-0 bg-card py-2 px-1 border-b">
              {{ grp.monthDisplay }}（{{ grp.papers.length }} 篇）
            </div>
            <div class="flex flex-col gap-2 items-stretch">
              <div
                v-for="paper in grp.papers"
                :key="paper.paper_id"
                class="p-4 border rounded-xl hover:bg-primary/[0.04] hover:border-primary/20 transition-all"
              >
                <div class="flex items-start justify-between gap-4">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                      <span>{{ formatDate(paper.date) }}</span>
                      <span>·</span>
                      <span class="font-mono">{{ paper.arxiv_id || paper.paper_id }}</span>
                    </div>
                    <h4 class="font-medium mb-1">
                      {{ formatAbbrevWithVenueTags(paper.alias || paper.full_name, paper.tags) }}
                    </h4>
                    <p v-if="paper.summary" class="text-sm text-muted-foreground">
                      {{ truncate(paper.summary, 200) }}
                    </p>
                  </div>
                  <div class="flex items-center gap-1">
                    <Button variant="ghost" size="icon" @click="openLink(paper)">
                      <ExternalLink class="h-4 w-4" />
                    </Button>
                    <Button
                      v-if="paper.github_url"
                      variant="ghost"
                      size="icon"
                      as="a"
                      :href="paper.github_url"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Github class="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Card>
  </div>
</template>
