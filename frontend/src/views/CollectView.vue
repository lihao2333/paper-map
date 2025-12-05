<script setup lang="ts">
import { ref } from 'vue'
import { Card, Button, Input, Badge } from '@/components/ui'
import * as api from '@/api'
import { Plus, X, Check, AlertCircle, Link } from 'lucide-vue-next'

const paperUrl = ref('')
const paperAlias = ref('')
const tags = ref<string[]>([])
const newTag = ref('')
const loading = ref(false)
const result = ref<{ success: boolean; message: string; paperId?: string } | null>(null)

// Batch mode
const batchMode = ref(false)
const batchUrls = ref('')
const batchResults = ref<any[]>([])
const batchLoading = ref(false)

function addTag() {
  if (newTag.value.trim() && !tags.value.includes(newTag.value.trim())) {
    tags.value.push(newTag.value.trim())
    newTag.value = ''
  }
}

function removeTag(tag: string) {
  tags.value = tags.value.filter(t => t !== tag)
}

async function collectPaper() {
  if (!paperUrl.value.trim()) {
    result.value = { success: false, message: '请输入论文链接' }
    return
  }

  loading.value = true
  result.value = null

  try {
    const response = await api.collectPaper(
      paperUrl.value.trim(),
      paperAlias.value.trim() || undefined,
      tags.value.length > 0 ? tags.value : undefined
    )
    result.value = {
      success: true,
      message: `论文已收集成功！Paper ID: ${response.paper_id}`,
      paperId: response.paper_id
    }
    // Reset form
    paperUrl.value = ''
    paperAlias.value = ''
    tags.value = []
  } catch (error: any) {
    result.value = {
      success: false,
      message: error.response?.data?.detail || '收集失败，请检查链接是否正确'
    }
  } finally {
    loading.value = false
  }
}

async function batchCollect() {
  const urls = batchUrls.value
    .split('\n')
    .map(url => url.trim())
    .filter(url => url.length > 0)

  if (urls.length === 0) {
    return
  }

  batchLoading.value = true
  batchResults.value = []

  try {
    const response = await api.batchCollect(urls)
    batchResults.value = response.results
  } catch (error) {
    console.error('Batch collect failed:', error)
  } finally {
    batchLoading.value = false
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto space-y-6">
    <!-- Mode Toggle -->
    <div class="flex gap-2">
      <Button
        :variant="!batchMode ? 'default' : 'outline'"
        @click="batchMode = false"
      >
        单篇收集
      </Button>
      <Button
        :variant="batchMode ? 'default' : 'outline'"
        @click="batchMode = true"
      >
        批量收集
      </Button>
    </div>

    <!-- Single Paper Mode -->
    <Card v-if="!batchMode" class="p-6">
      <h2 class="text-lg font-semibold mb-4">收集论文</h2>
      
      <div class="space-y-4">
        <!-- URL Input -->
        <div>
          <label class="block text-sm font-medium mb-2">论文链接 *</label>
          <div class="relative">
            <Link class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              v-model="paperUrl"
              placeholder="https://arxiv.org/abs/xxxx.xxxxx"
              class="pl-10"
            />
          </div>
          <p class="text-xs text-muted-foreground mt-1">
            支持 arXiv, OpenReview, GitHub 等链接
          </p>
        </div>

        <!-- Alias Input -->
        <div>
          <label class="block text-sm font-medium mb-2">别名（可选）</label>
          <Input
            v-model="paperAlias"
            placeholder="例如: GaussianSplat"
          />
        </div>

        <!-- Tags -->
        <div>
          <label class="block text-sm font-medium mb-2">标签（可选）</label>
          <div class="flex flex-wrap gap-2 mb-2">
            <Badge
              v-for="tag in tags"
              :key="tag"
              variant="secondary"
              class="gap-1"
            >
              {{ tag }}
              <button @click="removeTag(tag)">
                <X class="h-3 w-3" />
              </button>
            </Badge>
          </div>
          <div class="flex gap-2">
            <Input
              v-model="newTag"
              placeholder="输入标签名称..."
              @keyup.enter="addTag"
            />
            <Button variant="outline" @click="addTag">
              <Plus class="h-4 w-4" />
            </Button>
          </div>
        </div>

        <!-- Submit -->
        <Button
          class="w-full"
          :loading="loading"
          @click="collectPaper"
        >
          收集论文
        </Button>

        <!-- Result -->
        <div
          v-if="result"
          :class="[
            'p-4 rounded-lg flex items-start gap-3',
            result.success ? 'bg-green-50 text-green-800 dark:bg-green-900/20 dark:text-green-400' : 'bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-400'
          ]"
        >
          <Check v-if="result.success" class="h-5 w-5 flex-shrink-0" />
          <AlertCircle v-else class="h-5 w-5 flex-shrink-0" />
          <span>{{ result.message }}</span>
        </div>
      </div>
    </Card>

    <!-- Batch Mode -->
    <Card v-else class="p-6">
      <h2 class="text-lg font-semibold mb-4">批量收集</h2>
      
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-2">论文链接（每行一个）</label>
          <textarea
            v-model="batchUrls"
            class="w-full h-48 px-3 py-2 text-sm border rounded-md bg-background resize-none focus:outline-none focus:ring-2 focus:ring-ring"
            placeholder="https://arxiv.org/abs/xxxx.xxxxx
https://arxiv.org/abs/yyyy.yyyyy
..."
          />
        </div>

        <Button
          class="w-full"
          :loading="batchLoading"
          @click="batchCollect"
        >
          批量收集
        </Button>

        <!-- Results -->
        <div v-if="batchResults.length > 0" class="space-y-2">
          <h3 class="font-medium">收集结果</h3>
          <div class="max-h-64 overflow-y-auto space-y-1">
            <div
              v-for="(item, index) in batchResults"
              :key="index"
              :class="[
                'p-2 rounded text-sm flex items-center gap-2',
                item.status === 'success' ? 'bg-green-50 dark:bg-green-900/20' :
                item.status === 'skipped' ? 'bg-yellow-50 dark:bg-yellow-900/20' :
                'bg-red-50 dark:bg-red-900/20'
              ]"
            >
              <Check v-if="item.status === 'success'" class="h-4 w-4 text-green-600" />
              <AlertCircle v-else class="h-4 w-4 text-yellow-600" />
              <span class="flex-1 truncate">{{ item.url }}</span>
              <span class="text-xs text-muted-foreground">{{ item.message || item.paper_id }}</span>
            </div>
          </div>
        </div>
      </div>
    </Card>
  </div>
</template>
