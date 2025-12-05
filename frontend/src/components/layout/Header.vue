<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { usePapersStore } from '@/stores/papers'
import { Search, Moon, Sun, RefreshCw } from 'lucide-vue-next'
import { Input, Button } from '@/components/ui'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const papersStore = usePapersStore()

const searchQuery = ref('')
const isDark = ref(false)

const pageTitle = computed(() => {
  return (route.meta.title as string) || 'PaperMap'
})

function toggleDarkMode() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

function handleSearch() {
  if (searchQuery.value.trim()) {
    router.push('/papers')
    papersStore.setSearch(searchQuery.value.trim())
  }
}

onMounted(() => {
  appStore.fetchStats()
  // Check saved theme preference
  const savedTheme = localStorage.getItem('theme')
  if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    isDark.value = true
    document.documentElement.classList.add('dark')
  }
})
</script>

<template>
  <header class="h-14 flex items-center justify-between px-6 border-b bg-card/80 backdrop-blur-md sticky top-0 z-20 shrink-0">
    <div class="flex items-center gap-4 min-w-0 flex-1">
      <template v-if="route.path === '/' || route.path === '/companies'">
        <div id="header-companies-teleport" class="contents" />
      </template>
      <template v-else-if="route.path === '/universities'">
        <div id="header-universities-teleport" class="contents" />
      </template>
      <template v-else-if="route.path === '/authors'">
        <div id="header-authors-teleport" class="contents" />
      </template>
      <template v-else>
        <h1 class="text-base font-semibold tracking-tight">{{ pageTitle }}</h1>
        <div v-if="appStore.stats" class="hidden sm:flex items-center gap-1.5 text-xs text-muted-foreground">
          <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-muted">
            {{ appStore.stats.total_papers }} 篇论文
          </span>
          <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-muted">
            {{ appStore.stats.total_tags }} 个标签
          </span>
        </div>
      </template>
    </div>

    <div class="flex items-center gap-2 shrink-0">
      <div class="relative">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          v-model="searchQuery"
          placeholder="搜索论文..."
          class="pl-9 w-56 h-8 text-sm bg-muted/50 border-transparent focus:border-primary/30 focus:bg-background transition-colors"
          @keyup.enter="handleSearch"
        />
      </div>

      <Button variant="ghost" size="icon" class="h-8 w-8" @click="appStore.fetchStats()">
        <RefreshCw class="h-3.5 w-3.5" />
      </Button>

      <Button variant="ghost" size="icon" class="h-8 w-8" @click="toggleDarkMode">
        <Moon v-if="!isDark" class="h-3.5 w-3.5" />
        <Sun v-else class="h-3.5 w-3.5" />
      </Button>
    </div>
  </header>
</template>
