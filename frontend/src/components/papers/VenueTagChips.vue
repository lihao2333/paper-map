<script setup lang="ts">
import { computed } from 'vue'
import type { HoverInfo } from '@/types'
import {
  getProminentTagNames,
  prominentTagShortLabel,
  prominentTagTriggerClassFor,
} from '@/lib/utils'

const props = defineProps<{
  tagSource: string[] | HoverInfo | null | undefined
}>()

const tags = computed(() => getProminentTagNames(props.tagSource))
</script>

<template>
  <template v-if="tags.length">
    <span
      v-for="v in tags"
      :key="v"
      :title="v"
      :class="prominentTagTriggerClassFor(v)"
    >
      {{ prominentTagShortLabel(v) }}
    </span>
  </template>
</template>
