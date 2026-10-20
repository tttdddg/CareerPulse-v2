import { request } from '../request'

export interface AuthUserDto {
  id: string
  username: string
  email: string
  role: string
  created_at: string
}

interface AuthResponseDto {
  user: AuthUserDto
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
}

export interface LoginPayload {
  identifier: string
  password: string
}

export const registerAccount = async (payload: RegisterPayload): Promise<AuthUserDto> => {
  const response = await request<AuthResponseDto>({
    url: '/auth/register',
    method: 'POST',
    data: payload
  })
  return response.user
}

export const loginAccount = async (payload: LoginPayload): Promise<AuthUserDto> => {
  const response = await request<AuthResponseDto>({
    url: '/auth/login',
    method: 'POST',
    data: payload
  })
  return response.user
}

export const fetchCurrentUser = async (): Promise<AuthUserDto> => {
  const response = await request<AuthResponseDto>({
    url: '/auth/me',
    method: 'GET'
  })
  return response.user
}

export const logoutSession = async (): Promise<void> => {
  await request<void>({
    url: '/auth/logout',
    method: 'POST'
  })
}

