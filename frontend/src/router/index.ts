import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'companies',
      component: () => import('@/views/CompaniesView.vue'),
      meta: { title: '关注公司' },
      alias: ['/companies'],
    },
    {
      path: '/papers',
      name: 'papers',
      component: () => import('@/views/PapersView.vue'),
      meta: { title: '论文列表' },
    },
    {
      path: '/universities',
      name: 'universities',
      component: () => import('@/views/UniversitiesView.vue'),
      meta: { title: '关注高校' },
    },
    {
      path: '/authors',
      name: 'authors',
      component: () => import('@/views/AuthorsView.vue'),
      meta: { title: '关注作者' },
    },
    {
      path: '/tags',
      name: 'tags',
      component: () => import('@/views/TagsView.vue'),
      meta: { title: '标签树' },
    },
    {
      path: '/tags/:prefix',
      name: 'tag-matrix',
      component: () => import('@/views/TagMatrixView.vue'),
      meta: { title: '标签矩阵' },
    },
    {
      path: '/collect',
      name: 'collect',
      component: () => import('@/views/CollectView.vue'),
      meta: { title: '收集论文' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { title: '设置' },
    },
  ],
})

router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || 'PaperMap'} - PaperMap`
  next()
})

export default router
