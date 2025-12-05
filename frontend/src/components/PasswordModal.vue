<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, Button, Input } from '@/components/ui'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ submit: [password: string] }>()

const password = ref('')

watch(
  () => props.open,
  (open) => {
    if (open) password.value = ''
  }
)

function submit() {
  const pwd = password.value.trim()
  if (pwd) {
    emit('submit', pwd)
  }
}
</script>

<template>
  <Dialog
    :open="open"
    title="修改操作需验证"
    @update:open="(v) => !v && $emit('cancel')"
  >
    <div class="space-y-4">
      <p class="text-sm text-muted-foreground">
        请输入口令以执行修改操作
      </p>
      <Input
        v-model="password"
        type="password"
        placeholder="口令"
        class="w-full"
        autocomplete="current-password"
        @keyup.enter="submit"
      />
      <div class="flex gap-2 justify-end">
        <Button variant="outline" @click="$emit('cancel')">取消</Button>
        <Button :disabled="!password.trim()" @click="submit">确认</Button>
      </div>
    </div>
  </Dialog>
</template>
