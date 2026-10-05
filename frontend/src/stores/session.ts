import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

export interface SessionUser {
  id: number
  username: string
  display_name: string
  role: 'supervisor' | 'staff' | null
  department: { id: number; code: string; name: string; name_zh: string } | null
  supervisor: { id: number; username: string; display_name: string } | null
  is_staff: boolean
}

export const useSessionStore = defineStore('session', () => {
  const user = ref<SessionUser | null>(null)
  const token = ref(localStorage.getItem('relay-access'))

  async function loadUser() {
    const { data } = await api.get<SessionUser>('/auth/user/')
    user.value = data
    return data
  }

  async function signIn(username: string, password: string) {
    const { data } = await api.post<{ access: string; refresh: string }>('/auth/login/', { username, password })
    localStorage.setItem('relay-access', data.access)
    localStorage.setItem('relay-refresh', data.refresh)
    token.value = data.access
    await loadUser()
  }

  function signOut() {
    localStorage.removeItem('relay-access')
    localStorage.removeItem('relay-refresh')
    token.value = null
    user.value = null
  }

  return { user, token, loadUser, signIn, signOut }
})