<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/lib/utils'

interface Tab {
  id: string
  label: string
  icon?: any
}

interface Props {
  tabs: Tab[]
  modelValue: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

function selectTab(id: string) {
  emit('update:modelValue', id)
}
</script>

<template>
  <div class="w-full">
    <div class="inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="cn(
          'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
          modelValue === tab.id ? 'bg-background text-foreground shadow-sm' : 'hover:bg-background/50'
        )"
        @click="selectTab(tab.id)"
      >
        <component :is="tab.icon" v-if="tab.icon" class="mr-2 h-4 w-4" />
        {{ tab.label }}
      </button>
    </div>
    <div class="mt-2">
      <slot />
    </div>
  </div>
</template>
