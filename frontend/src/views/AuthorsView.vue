<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { watchDebounced } from '@vueuse/core'
import MatrixTable from '@/components/matrix/MatrixTable.vue'
import MatrixTagRuleBar from '@/components/matrix/MatrixTagRuleBar.vue'
import { Button, Badge } from '@/components/ui'
import * as api from '@/api'
import { RefreshCw, User } from 'lucide-vue-next'

const headers = ref<string[]>([])
const rows = ref<any[]>([])
const headerRules = ref<Record<string, string[]>>({})
const loading = ref(false)
const matrixTagRules = ref<string[]>([])

/** 按名称分组，收集所有 match_rule */
function buildHeaderRules(items: { name: string; match_rule: string }[]): Record<string, string[]> {
  const map: Record<string, string[]> = {}
  for (const item of items) {
    if (!map[item.name]) map[item.name] = []
    map[item.name].push(item.match_rule)
  }
  return map
}

async function fetchData() {
  loading.value = true
  try {
    const [matrixData, watched] = await Promise.all([
      api.getAuthorMatrix({ tag_rules: matrixTagRules.value }),
      api.getWatchedAuthors(),
    ])
    headers.value = matrixData.authors
    rows.value = matrixData.papers
    headerRules.value = buildHeaderRules(watched)
  } catch (error) {
    console.error('Failed to fetch author matrix:', error)
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)

watchDebounced(matrixTagRules, () => fetchData(), { debounce: 400, deep: true })
</script>

<template>
  <div class="flex flex-col flex-1 min-h-0">
    <Teleport to="#header-authors-teleport">
      <div class="flex w-full flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
        <div class="flex items-center gap-3 min-w-0">
          <div class="flex items-center justify-center h-8 w-8 rounded-lg bg-violet-500/10 shrink-0">
            <User class="h-4 w-4 text-violet-600 dark:text-violet-400" />
          </div>
          <h1 class="text-base font-semibold tracking-tight text-foreground truncate">
            关注作者 <span class="text-muted-foreground font-normal">· 显示关注作者发表的论文矩阵</span>
          </h1>
        </div>
        <div class="flex w-full min-w-0 flex-col items-stretch gap-2 sm:w-auto sm:max-w-none sm:flex-row sm:flex-wrap sm:items-start sm:justify-end">
          <MatrixTagRuleBar v-model="matrixTagRules" class="min-w-0 max-w-full flex-1" />
          <div class="flex flex-wrap items-center justify-end gap-2 shrink-0">
          <Badge variant="secondary">{{ headers.length }} 位作者</Badge>
          <Badge variant="outline">{{ rows.length }} 篇论文</Badge>
          <Button variant="outline" size="sm" :disabled="loading" @click="fetchData">
            <RefreshCw :class="['h-3.5 w-3.5 mr-1.5', loading && 'animate-spin']" />
            刷新
          </Button>
          </div>
        </div>
      </div>
    </Teleport>

    <MatrixTable
      :headers="headers"
      :rows="rows"
      :header-rules="headerRules"
      :loading="loading"
      @tag-added="fetchData"
    />
  </div>
</template>
