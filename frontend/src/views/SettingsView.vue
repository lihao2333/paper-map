<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { WatchedItem } from '@/types'
import { Card, Button, Input, Badge, Dialog } from '@/components/ui'
import * as api from '@/api'
import { Plus, Trash2, Edit2, Building2, GraduationCap, User, RefreshCw } from 'lucide-vue-next'

type WatchedType = 'company' | 'university' | 'author'

const activeTab = ref<WatchedType>('company')

const companies = ref<WatchedItem[]>([])
const universities = ref<WatchedItem[]>([])
const authors = ref<WatchedItem[]>([])
const loading = ref(false)

// Dialog state
const dialogOpen = ref(false)
const editingItem = ref<WatchedItem | null>(null)
const formName = ref('')
const formMatchRule = ref('')

const tabConfig = {
  company: {
    icon: Building2,
    label: '关注公司',
    data: companies,
    getAll: api.getWatchedCompanies,
    create: api.createWatchedCompany,
    update: api.updateWatchedCompany,
    delete: api.deleteWatchedCompany,
  },
  university: {
    icon: GraduationCap,
    label: '关注高校',
    data: universities,
    getAll: api.getWatchedUniversities,
    create: api.createWatchedUniversity,
    update: api.updateWatchedUniversity,
    delete: api.deleteWatchedUniversity,
  },
  author: {
    icon: User,
    label: '关注作者',
    data: authors,
    getAll: api.getWatchedAuthors,
    create: api.createWatchedAuthor,
    update: api.updateWatchedAuthor,
    delete: api.deleteWatchedAuthor,
  },
}

async function fetchAll() {
  loading.value = true
  try {
    const [c, u, a] = await Promise.all([
      api.getWatchedCompanies(),
      api.getWatchedUniversities(),
      api.getWatchedAuthors(),
    ])
    companies.value = c
    universities.value = u
    authors.value = a
  } catch (error) {
    console.error('Failed to fetch watched items:', error)
  } finally {
    loading.value = false
  }
}

function openAddDialog() {
  editingItem.value = null
  formName.value = ''
  formMatchRule.value = ''
  dialogOpen.value = true
}

function openEditDialog(item: WatchedItem) {
  editingItem.value = item
  formName.value = item.name
  formMatchRule.value = item.match_rule
  dialogOpen.value = true
}

async function saveItem() {
  if (!formName.value.trim() || !formMatchRule.value.trim()) return

  const config = tabConfig[activeTab.value]

  try {
    if (editingItem.value) {
      await config.update(editingItem.value.id, {
        name: formName.value.trim(),
        match_rule: formMatchRule.value.trim(),
      })
    } else {
      await config.create({
        name: formName.value.trim(),
        match_rule: formMatchRule.value.trim(),
      })
    }
    dialogOpen.value = false
    fetchAll()
  } catch (error) {
    console.error('Failed to save item:', error)
  }
}

async function deleteItem(item: WatchedItem) {
  if (!confirm(`确定要删除 "${item.name}" 吗？`)) return

  const config = tabConfig[activeTab.value]

  try {
    await config.delete(item.id)
    fetchAll()
  } catch (error) {
    console.error('Failed to delete item:', error)
  }
}

function groupByName(items: WatchedItem[]): Record<string, WatchedItem[]> {
  return items.reduce((acc, item) => {
    if (!acc[item.name]) acc[item.name] = []
    acc[item.name].push(item)
    return acc
  }, {} as Record<string, WatchedItem[]>)
}

onMounted(fetchAll)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold">设置</h2>
      <Button variant="outline" :disabled="loading" @click="fetchAll">
        <RefreshCw :class="['h-4 w-4 mr-2', loading && 'animate-spin']" />
        刷新
      </Button>
    </div>

    <!-- Tabs -->
    <div class="flex gap-2">
      <Button
        v-for="(config, key) in tabConfig"
        :key="key"
        :variant="activeTab === key ? 'default' : 'outline'"
        @click="activeTab = key as WatchedType"
      >
        <component :is="config.icon" class="h-4 w-4 mr-2" />
        {{ config.label }}
      </Button>
    </div>

    <!-- Content -->
    <Card class="p-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-medium">{{ tabConfig[activeTab].label }}</h3>
        <Button size="sm" @click="openAddDialog">
          <Plus class="h-4 w-4 mr-2" />
          添加
        </Button>
      </div>

      <div v-if="loading" class="py-8 text-center text-muted-foreground">
        加载中...
      </div>

      <div v-else-if="tabConfig[activeTab].data.value.length === 0" class="py-8 text-center text-muted-foreground">
        暂无数据
      </div>

      <div v-else class="space-y-4">
        <div
          v-for="(items, name) in groupByName(tabConfig[activeTab].data.value)"
          :key="name"
          class="border rounded-lg p-4"
        >
          <div class="flex items-center justify-between mb-2">
            <h4 class="font-medium">{{ name }}</h4>
          </div>
          <div class="space-y-2">
            <div
              v-for="item in items"
              :key="item.id"
              class="flex items-center justify-between py-2 px-3 bg-muted/30 rounded"
            >
              <code class="text-sm">{{ item.match_rule }}</code>
              <div class="flex items-center gap-2">
                <Button variant="ghost" size="icon" @click="openEditDialog(item)">
                  <Edit2 class="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" @click="deleteItem(item)">
                  <Trash2 class="h-4 w-4 text-destructive" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Card>

    <!-- Add/Edit Dialog -->
    <Dialog v-model:open="dialogOpen" :title="editingItem ? '编辑' : '添加'">
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-2">名称</label>
          <Input v-model="formName" placeholder="例如: 蔚来" />
        </div>
        <div>
          <label class="block text-sm font-medium mb-2">匹配规则</label>
          <Input v-model="formMatchRule" placeholder="例如: NIO" />
          <p class="text-xs text-muted-foreground mt-1">
            支持通配符: * (匹配任意字符), ? (匹配单个字符)
          </p>
        </div>
        <div class="flex justify-end gap-2">
          <Button variant="outline" @click="dialogOpen = false">取消</Button>
          <Button @click="saveItem">保存</Button>
        </div>
      </div>
    </Dialog>
  </div>
</template>
