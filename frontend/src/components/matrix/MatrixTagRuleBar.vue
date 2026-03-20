<script setup lang="ts">
import { computed, ref } from 'vue'
import { Input, Button } from '@/components/ui'
import { Filter, Plus, X } from 'lucide-vue-next'
import { cn } from '@/lib/utils'

const rules = defineModel<string[]>({ default: () => [] })

const draft = ref('')

const PRESET_VENUE = 'venue.*'
const PRESET_HF = 'hf.*'

const hasVenue = computed(() => rules.value.includes(PRESET_VENUE))
const hasHf = computed(() => rules.value.includes(PRESET_HF))

function togglePreset(pattern: string) {
  if (rules.value.includes(pattern)) {
    rules.value = rules.value.filter((r) => r !== pattern)
  } else {
    rules.value = [...rules.value, pattern]
  }
}

function addDraft() {
  const t = draft.value.trim()
  if (!t) return
  if (rules.value.includes(t)) {
    draft.value = ''
    return
  }
  rules.value = [...rules.value, t]
  draft.value = ''
}

function removeAt(index: number) {
  rules.value = rules.value.filter((_, i) => i !== index)
}

function clearAll() {
  rules.value = []
}
</script>

<template>
  <div
    class="matrix-tag-filter max-w-full overflow-x-auto rounded-lg border border-border/70 bg-gradient-to-r from-muted/40 to-muted/20 px-2 py-1.5 shadow-sm dark:from-muted/20 dark:to-muted/10 dark:border-border/50"
    title="未选规则=展示全部论文；快捷项与多条 glob 为「或」关系"
  >
    <div class="flex w-max min-w-0 max-w-none items-center gap-1.5 sm:gap-2">
      <div class="flex shrink-0 items-center gap-1 text-muted-foreground">
        <span
          class="flex h-6 w-6 items-center justify-center rounded-md border border-border/50 bg-background/80"
        >
          <Filter class="h-3 w-3" aria-hidden="true" />
        </span>
        <span class="whitespace-nowrap text-[11px] font-semibold text-foreground/85">标签筛选</span>
      </div>

      <!-- 快捷：虚线框 = 可点选；实心主题色 = 已启用 -->
      <button
        type="button"
        :class="
          cn(
            'inline-flex h-7 shrink-0 items-center justify-center rounded-md px-2.5 text-[11px] font-mono font-medium transition-all duration-200',
            hasVenue
              ? 'border-2 border-primary bg-primary text-primary-foreground shadow-sm'
              : 'border-2 border-dashed border-muted-foreground/35 bg-transparent text-muted-foreground hover:border-primary/45 hover:bg-primary/5 hover:text-foreground',
          )
        "
        title="快捷：顶会类标签 venue.*"
        @click="togglePreset(PRESET_VENUE)"
      >
        venue.*
      </button>
      <button
        type="button"
        :class="
          cn(
            'inline-flex h-7 shrink-0 items-center justify-center rounded-md px-2.5 text-[11px] font-mono font-medium transition-all duration-200',
            hasHf
              ? 'border-2 border-primary bg-primary text-primary-foreground shadow-sm'
              : 'border-2 border-dashed border-muted-foreground/35 bg-transparent text-muted-foreground hover:border-primary/45 hover:bg-primary/5 hover:text-foreground',
          )
        "
        title="快捷：Hugging Face 相关 hf.*"
        @click="togglePreset(PRESET_HF)"
      >
        hf.*
      </button>

      <!-- 已选条件：圆角药丸 + 次级底，与快捷矩形虚线框区分 -->
      <template v-if="rules.length > 0">
        <span
          class="hidden h-4 w-px shrink-0 bg-border/60 sm:block"
          aria-hidden="true"
        />
        <span class="sr-only">当前筛选条件</span>
        <span
          v-for="(r, i) in rules"
          :key="`${r}-${i}`"
          class="inline-flex max-w-[10rem] shrink-0 items-center gap-0.5 rounded-full bg-secondary py-0.5 pl-2.5 pr-0.5 font-mono text-[10px] font-medium text-secondary-foreground ring-1 ring-border/60 dark:ring-border/40"
        >
          <span class="truncate" :title="r">{{ r }}</span>
          <button
            type="button"
            class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-destructive/15 hover:text-destructive"
            aria-label="移除此规则"
            @click="removeAt(i)"
          >
            <X class="h-3 w-3" />
          </button>
        </span>
      </template>

      <span class="h-4 w-px shrink-0 bg-border/60" aria-hidden="true" />

      <div
        class="flex h-7 w-[7.5rem] shrink-0 items-stretch overflow-hidden rounded-md border border-border/80 bg-background/95 shadow-sm focus-within:border-primary/40 focus-within:ring-1 focus-within:ring-primary/20 sm:w-[9.5rem]"
      >
        <Input
          v-model="draft"
          class="h-7 min-w-0 flex-1 border-0 bg-transparent px-2 py-0 text-[11px] font-mono shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
          placeholder="glob…"
          title="回车或 + 添加；*、? 通配"
          @keydown.enter.prevent="addDraft"
        />
        <div class="my-1 w-px shrink-0 bg-border/60" aria-hidden="true" />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          class="h-7 w-7 shrink-0 rounded-none p-0 text-muted-foreground hover:text-foreground"
          title="添加"
          @click="addDraft"
        >
          <Plus class="h-3.5 w-3.5" />
        </Button>
      </div>

      <button
        v-if="rules.length > 0"
        type="button"
        class="shrink-0 whitespace-nowrap px-1 text-[11px] font-medium text-muted-foreground hover:text-foreground hover:underline"
        @click="clearAll"
      >
        清空
      </button>
    </div>
  </div>
</template>
