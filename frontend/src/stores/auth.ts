import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export const useAuthStore = defineStore('auth', () => {
  const cachedPassword = ref<string | null>(null)
  const showModal = ref(false)
  let resolvePending: ((pwd: string) => void) | null = null

  /** 弹窗输入口令，返回后供请求携带 */
  async function requireAuth(): Promise<string> {
    if (cachedPassword.value) return cachedPassword.value
    return new Promise<string>((resolve, reject) => {
      resolvePending = (pwd: string | null) => {
        resolvePending = null
        showModal.value = false
        if (pwd) resolve(pwd)
        else reject(new Error('Auth cancelled'))
      }
      showModal.value = true
    })
  }

  function submitPassword(pwd: string) {
    if (resolvePending) resolvePending(pwd)
  }

  function cancelPassword() {
    if (resolvePending) resolvePending(null)
  }

  /** 清除缓存（如收到 403 时） */
  function clearCache() {
    cachedPassword.value = null
  }

  return {
    cachedPassword,
    showModal,
    requireAuth,
    submitPassword,
    cancelPassword,
    clearCache,
  }
})
