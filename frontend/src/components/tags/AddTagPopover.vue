<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Button, Input } from '@/components/ui'
import * as api from '@/api'
import type { Tag } from '@/types'

interface Props {
  paperId: string
  /** 论文已有标签名称，用于从搜索结果中排除 */
  currentTagNames?: string[]
}

const props = withDefaults(defineProps<Props>(), {
  currentTagNames: () => [],
})

const emit = defineEmits<{
  (e: 'added'): void
}>()

const newTag = ref('')
const adding = ref(false)
const error = ref('')
const allTags = ref<Tag[]>([])

const currentSet = computed(() => new Set((props.currentTagNames ?? []).map((n) => n.toLowerCase())))

/** 模糊搜索：输入包含于标签名（不区分大小写），排除已有标签，最多 10 条 */
const matchedTags = computed(() => {
  const q = newTag.value.trim().toLowerCase()
  if (!q || !allTags.value.length) return []
  const exclude = currentSet.value
  const out: Tag[] = []
  for (const t of allTags.value) {
    if (out.length >= 10) break
    const name = t.tag_name.toLowerCase()
    if (name.includes(q) && !exclude.has(name)) {
      out.push(t)
    }
  }
  return out
})

onMounted(async () => {
  try {
    allTags.value = await api.getTags()
  } catch {
    /* ignore */
  }
})

watch(
  () => props.paperId,
  () => {
    newTag.value = ''
    error.value = ''
  }
)

async function addTag(tagName?: string) {
  const name = (tagName ?? newTag.value.trim()).trim()
  if (!name) return

  adding.value = true
  error.value = ''
  try {
    await api.addTagToPaper(props.paperId, name)
    newTag.value = ''
    emit('added')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '添加失败'
  } finally {
    adding.value = false
  }
}
</script>

<template>
  <div class="p-2 space-y-2 min-w-[200px]">
    <div class="relative flex gap-2">
      <div class="relative flex-1 min-w-0">
        <Input
          v-model="newTag"
          placeholder="添加标签...（输入可搜索已有标签）"
          class="flex-1 min-w-0"
          :disabled="adding"
          @keyup.enter="addTag()"
        />
        <!-- 模糊搜索下拉 -->
        <div
          v-if="matchedTags.length > 0"
          class="absolute left-0 right-0 top-full mt-0.5 z-50 max-h-40 overflow-auto rounded-md border border-gray-200 bg-white py-1 shadow-lg"
        >
          <button
            v-for="tag in matchedTags"
            :key="tag.tag_id"
            type="button"
            class="w-full cursor-pointer px-3 py-1.5 text-left text-sm text-gray-800 hover:bg-gray-100"
            :disabled="adding"
            @click="addTag(tag.tag_name)"
          >
            {{ tag.tag_name }}
          </button>
        </div>
      </div>
      <Button
        size="sm"
        variant="default"
        :disabled="adding"
        class="cursor-pointer shrink-0"
        @click="addTag()"
      >
        {{ adding ? '...' : '添加' }}
      </Button>
    </div>
    <p
      v-if="error"
      class="text-xs text-destructive"
    >
      {{ error }}
    </p>
  </div>
</template>
