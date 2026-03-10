import { defineStore } from 'pinia'

// 基础用户信息模型
export interface UserProfile {
  id: string
  name: string
  role: string
  avatarUrl?: string
  title?: string
}

export type AuthStatus = 'anonymous' | 'authenticated' | 'expired'

export interface AuthPayload {
  token: string
  profile: UserProfile | null
  savedAt: string
}

export interface UserState {
  token: string | null
  profile: UserProfile | null
  status: AuthStatus
}

const STORAGE_KEY = 'career-pulse:auth'

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null

const parseProfile = (value: unknown): UserProfile | null => {
  if (!isRecord(value)) {
    return null
  }

  const id = typeof value.id === 'string' ? value.id : ''
  const name = typeof value.name === 'string' ? value.name : ''
  const role = typeof value.role === 'string' ? value.role : ''

  if (!id || !name) {
    return null
  }

  return {
    id,
    name,
    role,
    avatarUrl: typeof value.avatarUrl === 'string' ? value.avatarUrl : undefined,
    title: typeof value.title === 'string' ? value.title : undefined
  }
}

const parseAuthPayload = (raw: string | null): AuthPayload | null => {
  if (!raw) {
    return null
  }

  try {
    const parsed = JSON.parse(raw) as unknown
    if (!isRecord(parsed)) {
      return null
    }

    const token = typeof parsed.token === 'string' && parsed.token.length > 0 ? parsed.token : null
    if (!token) {
      return null
    }

    const savedAt = typeof parsed.savedAt === 'string' ? parsed.savedAt : new Date().toISOString()

    return {
      token,
      profile: parseProfile(parsed.profile),
      savedAt
    }
  } catch {
    return null
  }
}

const persistAuthPayload = (payload: AuthPayload | null): void => {
  if (typeof window === 'undefined') {
    return
  }

  if (!payload) {
    window.localStorage.removeItem(STORAGE_KEY)
    return
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
}

export const useUserStore = defineStore('user', {
  state: (): UserState => ({
    token: null,
    profile: null,
    status: 'anonymous'
  }),
  getters: {
    isAuthenticated: (state): boolean => Boolean(state.token),
    displayName: (state): string => state.profile?.name ?? '访客',
    authHeader: (state): Record<string, string> =>
      state.token ? { Authorization: `Bearer ${state.token}` } : {}
  },
  actions: {
    // 从本地存储恢复登录状态
    hydrateFromStorage(): void {
      const payload = parseAuthPayload(
        typeof window === 'undefined' ? null : window.localStorage.getItem(STORAGE_KEY)
      )

      if (payload) {
        this.token = payload.token
        this.profile = payload.profile
        this.status = 'authenticated'
        return
      }

      this.token = null
      this.profile = null
      this.status = 'anonymous'
    },

    // 设置 token 并可选持久化
    setToken(token: string, persist = true): void {
      this.token = token
      this.status = token ? 'authenticated' : 'anonymous'

      if (persist) {
        persistAuthPayload({
          token,
          profile: this.profile,
          savedAt: new Date().toISOString()
        })
      }
    },

    // 更新用户档案并可选持久化
    setProfile(profile: UserProfile | null, persist = true): void {
      this.profile = profile

      if (persist && this.token) {
        persistAuthPayload({
          token: this.token,
          profile,
          savedAt: new Date().toISOString()
        })
      }
    },

    // 清理登录状态
    logout(): void {
      this.token = null
      this.profile = null
      this.status = 'anonymous'
      persistAuthPayload(null)
    }
  }
})
