<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import MatrixTable from '@/components/matrix/MatrixTable.vue'
import { Button, Badge } from '@/components/ui'
import * as api from '@/api'
import { RefreshCw, Tags } from 'lucide-vue-next'

const route = useRoute()

const headers = ref<string[]>([])
const rows = ref<any[]>([])
const loading = ref(false)

const prefix = ref('')

async function fetchData() {
  if (!prefix.value) return
  
  loading.value = true
  try {
    const data = await api.getTagMatrix(prefix.value)
    headers.value = data.tags
    rows.value = data.papers
  } catch (error) {
    console.error('Failed to fetch tag matrix:', error)
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.prefix,
  (newPrefix) => {
    prefix.value = newPrefix as string
    fetchData()
  },
  { immediate: true }
)

onMounted(() => {
  prefix.value = route.params.prefix as string
  if (prefix.value) {
    fetchData()
  }
})
</script>

<template>
  <div class="space-y-5">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="flex items-center justify-center h-9 w-9 rounded-xl bg-amber-500/10">
          <Tags class="h-[18px] w-[18px] text-amber-600 dark:text-amber-400" />
        </div>
        <div>
          <h2 class="text-base font-semibold tracking-tight">标签矩阵: {{ prefix }}</h2>
          <p class="text-xs text-muted-foreground mt-0.5">
            显示 {{ prefix }} 标签下的论文矩阵
          </p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <Badge variant="secondary">{{ headers.length }} 个子标签</Badge>
        <Badge variant="outline">{{ rows.length }} 篇论文</Badge>
        <Button variant="outline" size="sm" :disabled="loading" @click="fetchData">
          <RefreshCw :class="['h-3.5 w-3.5 mr-1.5', loading && 'animate-spin']" />
          刷新
        </Button>
      </div>
    </div>

    <MatrixTable
      :headers="headers"
      :rows="rows"
      :loading="loading"
      hierarchical-headers
      @tag-added="fetchData"
    />
  </div>
</template>
