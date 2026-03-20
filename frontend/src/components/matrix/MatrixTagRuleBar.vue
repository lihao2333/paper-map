<script setup lang="ts">
import { Input, Button } from '@/components/ui'

const model = defineModel<string>({ default: 'venue.*' })
</script>

<template>
  <div class="flex items-center gap-1 shrink-0">
    <span class="text-xs text-muted-foreground hidden sm:inline whitespace-nowrap">标签规则</span>
    <Input
      v-model="model"
      class="h-8 w-[8.75rem] px-2 py-1 text-xs font-mono"
      placeholder="venue.*"
      title="标签名通配符（*、?），如 venue.*、architecture.*；空为不按标签筛选"
    />
    <Button type="button" variant="ghost" size="sm" class="h-8 px-2 text-xs" @click="model = ''">
      全部
    </Button>
    <Button type="button" variant="ghost" size="sm" class="h-8 px-2 text-xs" @click="model = 'venue.*'">
      顶会
    </Button>
  </div>
</template>
