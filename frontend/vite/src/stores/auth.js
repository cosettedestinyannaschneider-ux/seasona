import { defineStore } from 'pinia'
import { getMe, logout as logoutRequest } from '../api/auth'

function storedUser() {
  try {
    return JSON.parse(window.localStorage.getItem('seasona_user') || 'null')
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: window.localStorage.getItem('seasona_token') || '',
    role: window.localStorage.getItem('seasona_role') || 'buyer',
    user: storedUser(),
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
    displayName: (state) => state.user?.nickname || state.user?.username || '我的',
  },
  actions: {
    setSession({ token, role, user }) {
      this.token = token
      this.role = role || user?.role || 'buyer'
      this.user = user
      window.localStorage.setItem('seasona_token', token)
      window.localStorage.setItem('seasona_role', this.role)
      window.localStorage.setItem('seasona_user', JSON.stringify(user || null))
    },
    async loadMe() {
      if (!this.token) return null
      const user = await getMe()
      this.user = user
      this.role = user.role || this.role
      window.localStorage.setItem('seasona_role', this.role)
      window.localStorage.setItem('seasona_user', JSON.stringify(user))
      return user
    },
    async logout() {
      if (this.token) {
        await logoutRequest()
      }
      this.clearSession()
    },
    clearSession() {
      this.token = ''
      this.role = 'buyer'
      this.user = null
      window.localStorage.removeItem('seasona_token')
      window.localStorage.removeItem('seasona_role')
      window.localStorage.removeItem('seasona_user')
    },
  },
})
