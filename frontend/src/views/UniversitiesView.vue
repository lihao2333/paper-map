<script setup lang="ts">
import { ref, onMounted } from 'vue'
import MatrixTable from '@/components/matrix/MatrixTable.vue'
import { Button, Badge } from '@/components/ui'
import * as api from '@/api'
import { RefreshCw, GraduationCap } from 'lucide-vue-next'

const headers = ref<string[]>([])
const rows = ref<any[]>([])
const headerRules = ref<Record<string, string[]>>({})
const loading = ref(false)

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
      api.getUniversityMatrix(),
      api.getWatchedUniversities(),
    ])
    headers.value = matrixData.universities
    rows.value = matrixData.papers
    headerRules.value = buildHeaderRules(watched)
  } catch (error) {
    console.error('Failed to fetch university matrix:', error)
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="flex flex-col flex-1 min-h-0">
    <Teleport to="#header-universities-teleport">
      <div class="flex items-center justify-between w-full gap-4">
        <div class="flex items-center gap-3 min-w-0">
          <div class="flex items-center justify-center h-8 w-8 rounded-lg bg-emerald-500/10 shrink-0">
            <GraduationCap class="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          </div>
          <h1 class="text-base font-semibold tracking-tight text-foreground truncate">
            关注高校 <span class="text-muted-foreground font-normal">· 显示关注高校发表的论文矩阵</span>
          </h1>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <Badge variant="secondary">{{ headers.length }} 所高校</Badge>
          <Badge variant="outline">{{ rows.length }} 篇论文</Badge>
          <Button variant="outline" size="sm" :disabled="loading" @click="fetchData">
            <RefreshCw :class="['h-3.5 w-3.5 mr-1.5', loading && 'animate-spin']" />
            刷新
          </Button>
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
