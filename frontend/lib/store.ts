import { create } from 'zustand'

interface User {
  id: number
  name: string
  email: string
  username: string
  nickname: string
  role: 'MEMBER' | 'PRO' | 'ADMIN' | 'member' | 'pro' | 'admin'
  balance: number
  created_at: string
}

interface AuthState {
  user: User | null
  token: string | null
  theme: 'light' | 'dark'
  setAuth: (user: User, token: string) => void
  clearAuth: () => void
  isPro: () => boolean
  isAdmin: () => boolean
  toggleTheme: () => void
  setTheme: (theme: 'light' | 'dark') => void
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  theme: 'dark', // Default to dark
  setAuth: (user, token) => {
    set({ user, token })
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
    if (typeof document !== 'undefined') {
      document.cookie = `token=${token}; path=/; max-age=86400`
    }
  },
  clearAuth: () => {
    set({ user: null, token: null })
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    if (typeof document !== 'undefined') {
      document.cookie = 'token=; path=/; max-age=0'
    }
  },
  isPro: () => {
    const user = get().user
    if (!user) return false
    const role = user.role.toLowerCase()
    return role === 'pro' || role === 'admin'
  },
  isAdmin: () => {
    const user = get().user
    if (!user) return false
    return user.role.toLowerCase() === 'admin'
  },
  toggleTheme: () => {
    const newTheme = get().theme === 'dark' ? 'light' : 'dark'
    set({ theme: newTheme })
    localStorage.setItem('theme', newTheme)
    if (typeof document !== 'undefined') {
      if (newTheme === 'dark') {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    }
  },
  setTheme: (theme) => {
    set({ theme })
    localStorage.setItem('theme', theme)
    if (typeof document !== 'undefined') {
      if (theme === 'dark') {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    }
  },
}))
