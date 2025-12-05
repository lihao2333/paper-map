<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Paper } from '@/types'
import { Dialog, Badge, Button, Input } from '@/components/ui'
import { formatDate, generateArxivLink } from '@/lib/utils'
import { ExternalLink, Copy, Check, Tag, Building2, GraduationCap, User } from 'lucide-vue-next'

interface Props {
  paper: Paper | null
  open: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'addTag', tagName: string): void
  (e: 'removeTag', tagId: number): void
}>()

const copied = ref(false)
const newTag = ref('')

function copyId() {
  if (props.paper) {
    navigator.clipboard.writeText(props.paper.paper_id)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  }
}

function addTag() {
  if (newTag.value.trim()) {
    emit('addTag', newTag.value.trim())
    newTag.value = ''
  }
}

watch(() => props.open, (open) => {
  if (!open) {
    newTag.value = ''
  }
})
</script>

<template>
  <Dialog :open="open" :title="paper?.alias || paper?.full_name || 'Paper Details'" light @update:open="emit('update:open', $event)">
    <div v-if="paper" class="space-y-6">
      <!-- Header -->
      <div class="space-y-2">
        <div class="flex items-center gap-2 text-sm text-muted-foreground">
          <span>{{ formatDate(paper.date) }}</span>
          <span>·</span>
          <button
            class="flex items-center gap-1 font-mono hover:text-foreground transition-colors"
            @click="copyId"
          >
            {{ paper.arxiv_id || paper.paper_id }}
            <Copy v-if="!copied" class="h-3 w-3" />
            <Check v-else class="h-3 w-3 text-green-500" />
          </button>
        </div>
        <h3 class="text-xl font-bold text-foreground">{{ paper.full_name || paper.alias }}</h3>
        <a
          :href="generateArxivLink(paper.arxiv_id, paper.paper_url)"
          target="_blank"
          rel="noopener noreferrer"
          class="link-visualized inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground shadow-md transition-all hover:bg-primary/90 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <ExternalLink class="h-4 w-4 mr-2" />
          打开链接
        </a>
      </div>

      <!-- Authors -->
      <div v-if="paper.author_names.length > 0">
        <div class="flex items-center gap-2 text-sm font-semibold text-foreground mb-2">
          <User class="h-4 w-4" />
          作者
        </div>
        <p class="text-sm text-foreground/90 leading-relaxed">
          {{ paper.author_names.join(', ') }}
        </p>
      </div>

      <!-- Organizations -->
      <div class="grid grid-cols-2 gap-4">
        <div v-if="paper.company_names.length > 0">
          <div class="flex items-center gap-2 text-sm font-semibold text-foreground mb-2">
            <Building2 class="h-4 w-4" />
            公司
          </div>
          <div class="flex flex-wrap gap-1">
            <Badge v-for="company in paper.company_names" :key="company" variant="secondary">
              {{ company }}
            </Badge>
          </div>
        </div>
        <div v-if="paper.university_names.length > 0">
          <div class="flex items-center gap-2 text-sm font-semibold text-foreground mb-2">
            <GraduationCap class="h-4 w-4" />
            高校
          </div>
          <div class="flex flex-wrap gap-1">
            <Badge v-for="university in paper.university_names" :key="university" variant="outline">
              {{ university }}
            </Badge>
          </div>
        </div>
      </div>

      <!-- Tags -->
      <div>
        <div class="flex items-center gap-2 text-sm font-semibold text-foreground mb-2">
          <Tag class="h-4 w-4" />
          标签
        </div>
        <div class="flex flex-wrap gap-1 mb-2">
          <Badge v-for="tag in paper.tags" :key="tag">
            {{ tag }}
          </Badge>
          <span v-if="paper.tags.length === 0" class="text-sm text-muted-foreground">
            暂无标签
          </span>
        </div>
        <div class="flex gap-2">
          <Input
            v-model="newTag"
            placeholder="添加标签..."
            class="flex-1"
            @keyup.enter="addTag"
          />
          <Button size="sm" @click="addTag">添加</Button>
        </div>
      </div>

      <!-- Summary -->
      <div v-if="paper.summary">
        <div class="text-sm font-semibold text-foreground mb-2">摘要</div>
        <p class="text-sm text-foreground/90 leading-relaxed">
          {{ paper.summary }}
        </p>
      </div>

      <!-- Abstract -->
      <div v-if="paper.abstract">
        <div class="text-sm font-semibold text-foreground mb-2">Abstract</div>
        <p class="text-sm text-foreground/90 leading-relaxed max-h-48 overflow-y-auto">
          {{ paper.abstract }}
        </p>
      </div>
    </div>
  </Dialog>
</template>
