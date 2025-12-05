import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Stats, Tag } from '@/types'
import * as api from '@/api'

export const useAppStore = defineStore('app', () => {
  const stats = ref<Stats | null>(null)
  const tags = ref<Tag[]>([])
  const loading = ref(false)
  const sidebarCollapsed = ref(false)

  async function fetchStats() {
    try {
      stats.value = await api.getStats()
    } catch (error) {
      console.error('Failed to fetch stats:', error)
    }
  }

  async function fetchTags() {
    try {
      tags.value = await api.getTags()
    } catch (error) {
      console.error('Failed to fetch tags:', error)
    }
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  return {
    stats,
    tags,
    loading,
    sidebarCollapsed,
    fetchStats,
    fetchTags,
    toggleSidebar,
  }
})
