import { defineStore } from 'pinia'
import { authApi } from '@/api'
import { canManageSystem } from '@/utils/permissions'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    token: localStorage.getItem('access_token') || null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    isAdmin: (s) => canManageSystem(s.user?.role),
  },
  actions: {
    async login(username, password) {
      const params = new URLSearchParams()
      params.append('username', username)
      params.append('password', password)
      try {
        const res = await authApi.login(params)
        this.token = res.data.access_token
        this.user = res.data.user
        localStorage.setItem('access_token', this.token)
      } catch (e) {
        this.token = null
        this.user = null
        localStorage.removeItem('access_token')
        throw e
      }
    },
    async fetchMe() {
      try {
        const res = await authApi.me()
        this.user = res.data
      } catch {
        this.logout()
        throw new Error('인증이 만료되었습니다.')
      }
    },
    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem('access_token')
    },
  },
})
