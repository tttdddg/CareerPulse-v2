import { defineStore } from 'pinia'
import {
  fetchCurrentUser,
  loginAccount,
  logoutSession,
  registerAccount,
  type AuthUserDto,
  type LoginPayload,
  type RegisterPayload
} from '../api/modules/auth'

export interface UserProfile {
  id: string
  name: string
  role: string
  email?: string
  avatarUrl?: string
  title?: string
}

export type AuthStatus = 'unknown' | 'anonymous' | 'authenticated' | 'expired'

export interface UserState {
  profile: UserProfile | null
  status: AuthStatus
}

const toProfile = (user: AuthUserDto): UserProfile => ({
  id: user.id,
  name: user.username,
  role: user.role,
  email: user.email
})
export const useUserStore = defineStore('user', {
  state: (): UserState => ({
    profile: null,
    status: 'unknown'
  }),
  getters: {
    isAuthenticated: (state): boolean => state.status === 'authenticated' && state.profile !== null,
    displayName: (state): string => state.profile?.name ?? '访客'
  },
  actions: {
    setDemoProfile(profile: UserProfile): void {
      this.profile = profile
      this.status = 'authenticated'
    },

    clearSession(status: AuthStatus = 'anonymous'): void {
      this.profile = null
      this.status = status
    },

    async hydrateSession(): Promise<void> {
      if (this.status !== 'unknown') {
        return
      }
      try {
        this.profile = toProfile(await fetchCurrentUser())
        this.status = 'authenticated'
      } catch {
        this.clearSession('anonymous')
      }
    },

    async login(payload: LoginPayload): Promise<void> {
      this.profile = toProfile(await loginAccount(payload))
      this.status = 'authenticated'
    },

    async register(payload: RegisterPayload): Promise<void> {
      await registerAccount(payload)
    },

    async logout(): Promise<void> {
      try {
        await logoutSession()
      } finally {
        this.clearSession('anonymous')
      }
    }
  }
})
