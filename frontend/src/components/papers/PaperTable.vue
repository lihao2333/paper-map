<script setup lang="ts">
import type { Paper } from '@/types'
import { Badge, Tooltip, PaperTooltip } from '@/components/ui'
import VenueTagChips from '@/components/papers/VenueTagChips.vue'
import { formatDate, truncate, generateArxivLink, paperDisplayTitle } from '@/lib/utils'
import { ExternalLink, Github } from 'lucide-vue-next'

interface Props {
  papers: Paper[]
  loading?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'select', paper: Paper): void
}>()
</script>

<template>
  <div class="border rounded-xl overflow-hidden bg-card shadow-sm">
    <div class="overflow-x-auto">
      <table class="w-full">
        <thead>
          <tr class="border-b bg-muted">
            <th class="px-4 py-2.5 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider w-24">
              日期
            </th>
            <th class="px-4 py-2.5 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider w-32">
              ID
            </th>
            <th class="px-4 py-2.5 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              标题
            </th>
            <th class="px-4 py-2.5 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider w-36">
              作者
            </th>
            <th class="px-4 py-2.5 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider w-40">
              摘要
            </th>
            <th class="px-4 py-2.5 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider w-48">
              AI 总结
            </th>
            <th class="px-4 py-2.5 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider w-40">
              机构
            </th>
            <th class="px-4 py-2.5 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider w-40">
              标签
            </th>
            <th class="px-4 py-2.5 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider w-16">
              链接
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="paper in papers"
            :key="paper.paper_id"
            class="hover:bg-primary/[0.04] cursor-pointer transition-colors"
            @click="emit('select', paper)"
          >
            <td class="px-4 py-3 text-sm text-muted-foreground whitespace-nowrap border-b border-dashed border-border/40">
              {{ formatDate(paper.date) }}
            </td>
            <td class="px-4 py-3 text-sm font-mono">
              <Tooltip :content="paper.paper_id">
                <span class="text-primary">{{ paper.arxiv_id || truncate(paper.paper_id, 10) }}</span>
              </Tooltip>
            </td>
            <td class="px-4 py-3">
              <Tooltip :content="paper.full_name || paper.alias">
                <div>
                  <div class="flex flex-wrap items-baseline gap-1.5 gap-y-1">
                    <VenueTagChips :tag-source="paper.tags" />
                    <span class="text-sm font-medium text-foreground">
                      {{ paperDisplayTitle(paper.alias || truncate(paper.full_name, 40)) }}
                    </span>
                  </div>
                  <div v-if="paper.alias && paper.full_name" class="text-xs text-muted-foreground">
                    {{ truncate(paper.full_name, 60) }}
                  </div>
                </div>
              </Tooltip>
            </td>
            <td class="px-4 py-3 text-sm text-muted-foreground">
              <Tooltip :content="paper.author_names.join(', ')">
                <span>{{ paper.author_names.length ? truncate(paper.author_names.join(', '), 30) : '—' }}</span>
              </Tooltip>
            </td>
            <td class="px-4 py-3 text-sm text-muted-foreground">
              <PaperTooltip
                :hover-info="
                  paper.abstract || paper.arxiv_comments
                    ? {
                        full_name: paper.full_name || paper.alias,
                        abstract: paper.abstract,
                        arxiv_comments: paper.arxiv_comments || undefined,
                        github_url: paper.github_url,
                      }
                    : null
                "
              >
                <span>{{ truncate(paper.abstract, 50) || '—' }}</span>
              </PaperTooltip>
            </td>
            <td class="px-4 py-3 text-sm text-muted-foreground">
              <PaperTooltip
                :hover-info="
                  paper.summary || paper.arxiv_comments
                    ? {
                        full_name: paper.full_name || paper.alias,
                        summary: paper.summary,
                        arxiv_comments: paper.arxiv_comments || undefined,
                        github_url: paper.github_url,
                      }
                    : null
                "
              >
                <span>{{ truncate(paper.summary, 50) || '—' }}</span>
              </PaperTooltip>
            </td>
            <td class="px-4 py-3">
              <div class="flex flex-wrap gap-1">
                <Badge
                  v-for="company in paper.company_names.slice(0, 2)"
                  :key="company"
                  variant="secondary"
                  class="text-xs"
                >
                  {{ company }}
                </Badge>
                <Badge
                  v-for="university in paper.university_names.slice(0, 2)"
                  :key="university"
                  variant="outline"
                  class="text-xs"
                >
                  {{ university }}
                </Badge>
              </div>
            </td>
            <td class="px-4 py-3">
              <div class="flex flex-wrap gap-1">
                <Badge
                  v-for="tag in paper.tags.slice(0, 3)"
                  :key="tag"
                  class="text-xs"
                >
                  {{ tag }}
                </Badge>
                <span v-if="paper.tags.length > 3" class="text-xs text-muted-foreground">
                  +{{ paper.tags.length - 3 }}
                </span>
              </div>
            </td>
            <td class="px-4 py-3">
              <a
                :href="generateArxivLink(paper.arxiv_id, paper.paper_url)"
                target="_blank"
                rel="noopener noreferrer"
                class="link-visualized inline-flex p-1 hover:bg-accent rounded transition-colors"
                @click.stop
              >
                <ExternalLink class="h-4 w-4" />
              </a>
              <a
                v-if="paper.github_url"
                :href="paper.github_url"
                target="_blank"
                rel="noopener noreferrer"
                class="link-visualized inline-flex p-1 hover:bg-accent rounded transition-colors"
                title="GitHub"
                @click.stop
              >
                <Github class="h-4 w-4 text-muted-foreground" />
              </a>
            </td>
          </tr>
          <tr v-if="papers.length === 0 && !loading">
            <td colspan="9" class="px-4 py-8 text-center text-muted-foreground">
              暂无论文数据
            </td>
          </tr>
          <tr v-if="loading">
            <td colspan="9" class="px-4 py-8 text-center text-muted-foreground">
              <div class="flex items-center justify-center gap-2">
                <svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
                  <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                加载中...
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
