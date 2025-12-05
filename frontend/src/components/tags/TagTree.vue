<script setup lang="ts">
import { ref, computed } from 'vue'
import type { TagTreeNode } from '@/types'
import { ChevronRight, ChevronDown, Tag, Hash } from 'lucide-vue-next'
import { cn } from '@/lib/utils'

interface Props {
  nodes: TagTreeNode[]
  selectedTagId?: number | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'select', node: TagTreeNode): void
}>()

const expandedNodes = ref<Set<string>>(new Set())

function toggleExpand(fullPath: string) {
  if (expandedNodes.value.has(fullPath)) {
    expandedNodes.value.delete(fullPath)
  } else {
    expandedNodes.value.add(fullPath)
  }
}

function isExpanded(fullPath: string): boolean {
  return expandedNodes.value.has(fullPath)
}

function selectNode(node: TagTreeNode) {
  emit('select', node)
}
</script>

<template>
  <div class="space-y-1">
    <template v-for="node in nodes" :key="node.full_path">
      <div
        :class="cn(
          'flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer transition-colors',
          props.selectedTagId === node.tag_id
            ? 'bg-primary text-primary-foreground'
            : 'hover:bg-accent'
        )"
        @click="selectNode(node)"
      >
        <button
          v-if="node.children.length > 0"
          class="p-0.5 hover:bg-accent/50 rounded"
          @click.stop="toggleExpand(node.full_path)"
        >
          <ChevronDown v-if="isExpanded(node.full_path)" class="h-4 w-4" />
          <ChevronRight v-else class="h-4 w-4" />
        </button>
        <div v-else class="w-5" />
        
        <Tag v-if="node.tag_id" class="h-4 w-4 flex-shrink-0" />
        <Hash v-else class="h-4 w-4 flex-shrink-0 text-muted-foreground" />
        
        <span class="flex-1 text-sm truncate">{{ node.tag_name }}</span>
        <span class="text-xs text-muted-foreground">{{ node.paper_count }}</span>
      </div>
      
      <div v-if="node.children.length > 0 && isExpanded(node.full_path)" class="pl-4">
        <TagTree
          :nodes="node.children"
          :selected-tag-id="selectedTagId"
          @select="emit('select', $event)"
        />
      </div>
    </template>
  </div>
</template>
