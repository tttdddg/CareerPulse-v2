import { request } from '../request'

export interface LoginPayload {
  account: string
  password: string
}

export interface RegisterPayload {
  account: string
  password: string
  inviteCode?: string
}

export interface UserProfile {
  id: string
  name: string
  role: string
  avatarUrl?: string
  title?: string
}

export interface AuthResult {
  token: string
  profile: UserProfile
}

export interface UpdateProfilePayload {
  name?: string
  role?: string
  avatarUrl?: string
  title?: string
}

export const login = (payload: LoginPayload): Promise<AuthResult> =>
  request<AuthResult>({
    url: '/user/login',
    method: 'POST',
    data: payload
  })

export const register = (payload: RegisterPayload): Promise<AuthResult> =>
  request<AuthResult>({
    url: '/user/register',
    method: 'POST',
    data: payload
  })

export const fetchProfile = (): Promise<UserProfile> =>
  request<UserProfile>({
    url: '/user/profile',
    method: 'GET'
  })

export const updateProfile = (payload: UpdateProfilePayload): Promise<UserProfile> =>
  request<UserProfile>({
    url: '/user/profile',
    method: 'PUT',
    data: payload
  })
