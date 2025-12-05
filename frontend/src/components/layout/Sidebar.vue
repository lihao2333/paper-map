<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import {
  FileText,
  Building2,
  GraduationCap,
  User,
  Tags,
  Plus,
  Settings,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
} from 'lucide-vue-next'
import { cn } from '@/lib/utils'
import * as api from '@/api'

const router = useRouter()
const route = useRoute()
const appStore = useAppStore()

const topLevelTags = ref<{ tag_name: string; tag_id: number | null }[]>([])

const mainNavItems = [
  { path: '/', icon: Building2, label: '关注公司' },
  { path: '/universities', icon: GraduationCap, label: '关注高校' },
  { path: '/authors', icon: User, label: '关注作者' },
  { path: '/papers', icon: FileText, label: '论文列表' },
  { path: '/tags', icon: Tags, label: '标签树' },
]

const bottomNavItems = [
  { path: '/collect', icon: Plus, label: '收集论文' },
  { path: '/settings', icon: Settings, label: '设置' },
]

const isActive = (path: string) => {
  if (path === '/') return route.path === '/' || route.path === '/companies'
  return route.path.startsWith(path)
}

function navigate(path: string) {
  router.push(path)
}

onMounted(async () => {
  try {
    topLevelTags.value = await api.getTopLevelTags()
  } catch (error) {
    console.error('Failed to load top level tags:', error)
  }
})
</script>

<template>
  <aside
    :class="cn(
      'flex flex-col h-screen transition-all duration-300',
      appStore.sidebarCollapsed ? 'w-16' : 'w-60'
    )"
    style="background-color: hsl(var(--sidebar)); color: hsl(var(--sidebar-foreground));"
  >
    <!-- Logo -->
    <div class="flex items-center h-14 px-4">
      <div class="flex items-center justify-center h-8 w-8 rounded-lg flex-shrink-0" style="background-color: hsl(var(--sidebar-accent));">
        <LayoutDashboard class="h-4 w-4 text-white" />
      </div>
      <span
        v-if="!appStore.sidebarCollapsed"
        class="ml-3 font-semibold text-base tracking-tight text-white"
      >
        PaperMap
      </span>
    </div>

    <!-- Main Navigation -->
    <nav class="flex-1 overflow-y-auto py-3 px-2">
      <div class="mb-1">
        <p
          v-if="!appStore.sidebarCollapsed"
          class="text-[10px] font-semibold uppercase tracking-widest px-3 mb-2"
          style="color: hsl(var(--sidebar-foreground) / 0.4);"
        >
          导航
        </p>
        <div class="space-y-0.5">
          <button
            v-for="item in mainNavItems"
            :key="item.path"
            :class="cn(
              'w-full flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-all duration-150',
              isActive(item.path)
                ? 'text-white'
                : 'hover:text-white'
            )"
            :style="isActive(item.path)
              ? 'background-color: hsl(var(--sidebar-accent)); box-shadow: 0 1px 3px hsl(var(--sidebar-accent) / 0.4);'
              : 'color: hsl(var(--sidebar-foreground) / 0.7);'"
            @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = isActive(item.path) ? '' : 'hsl(var(--sidebar-muted))'"
            @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = isActive(item.path) ? 'hsl(var(--sidebar-accent))' : ''"
            @click="navigate(item.path)"
          >
            <component :is="item.icon" class="h-[18px] w-[18px] flex-shrink-0" />
            <span v-if="!appStore.sidebarCollapsed" class="ml-3">{{ item.label }}</span>
          </button>
        </div>
      </div>

      <!-- Tag Matrix Links -->
      <div v-if="topLevelTags.length > 0" class="mt-5">
        <p
          v-if="!appStore.sidebarCollapsed"
          class="text-[10px] font-semibold uppercase tracking-widest px-3 mb-2"
          style="color: hsl(var(--sidebar-foreground) / 0.4);"
        >
          标签矩阵
        </p>
        <div class="space-y-0.5">
          <button
            v-for="tag in topLevelTags"
            :key="tag.tag_name"
            :class="cn(
              'w-full flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-all duration-150',
              route.path === `/tags/${tag.tag_name}`
                ? 'text-white'
                : 'hover:text-white'
            )"
            :style="route.path === `/tags/${tag.tag_name}`
              ? 'background-color: hsl(var(--sidebar-accent)); box-shadow: 0 1px 3px hsl(var(--sidebar-accent) / 0.4);'
              : 'color: hsl(var(--sidebar-foreground) / 0.7);'"
            @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = route.path === `/tags/${tag.tag_name}` ? '' : 'hsl(var(--sidebar-muted))'"
            @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = route.path === `/tags/${tag.tag_name}` ? 'hsl(var(--sidebar-accent))' : ''"
            @click="navigate(`/tags/${tag.tag_name}`)"
          >
            <Tags class="h-4 w-4 flex-shrink-0" />
            <span v-if="!appStore.sidebarCollapsed" class="ml-3 truncate">{{ tag.tag_name }}</span>
          </button>
        </div>
      </div>
    </nav>

    <!-- Bottom Navigation -->
    <div class="py-3 px-2" style="border-top: 1px solid hsl(var(--sidebar-muted));">
      <div class="space-y-0.5">
        <button
          v-for="item in bottomNavItems"
          :key="item.path"
          :class="cn(
            'w-full flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-all duration-150',
            isActive(item.path)
              ? 'text-white'
              : 'hover:text-white'
          )"
          :style="isActive(item.path)
            ? 'background-color: hsl(var(--sidebar-accent));'
            : 'color: hsl(var(--sidebar-foreground) / 0.7);'"
          @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = isActive(item.path) ? '' : 'hsl(var(--sidebar-muted))'"
          @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = isActive(item.path) ? 'hsl(var(--sidebar-accent))' : ''"
          @click="navigate(item.path)"
        >
          <component :is="item.icon" class="h-[18px] w-[18px] flex-shrink-0" />
          <span v-if="!appStore.sidebarCollapsed" class="ml-3">{{ item.label }}</span>
        </button>
      </div>
    </div>

    <!-- Collapse Button -->
    <button
      class="flex items-center justify-center h-9 transition-colors"
      style="border-top: 1px solid hsl(var(--sidebar-muted)); color: hsl(var(--sidebar-foreground) / 0.5);"
      @click="appStore.toggleSidebar()"
    >
      <ChevronLeft v-if="!appStore.sidebarCollapsed" class="h-4 w-4" />
      <ChevronRight v-else class="h-4 w-4" />
    </button>
  </aside>
</template>
