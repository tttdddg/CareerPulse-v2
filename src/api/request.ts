import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { useUserStore } from '../stores/user'

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export class ApiError extends Error {
  public readonly code?: number
  public readonly status?: number

  constructor(message: string, code?: number, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

const resolveToken = (): string | null => {
  try {
    const store = useUserStore()
    if (store.token) {
      return store.token
    }
  } catch {
    // ignore store access errors (e.g., pinia not initialized yet)
  }

  if (typeof window === 'undefined') {
    return null
  }

  try {
    const raw = window.localStorage.getItem('career-pulse:auth')
    if (!raw) {
      return null
    }
    const parsed = JSON.parse(raw) as { token?: unknown }
    return typeof parsed.token === 'string' && parsed.token.length > 0 ? parsed.token : null
  } catch {
    return null
  }
}

const isApiResponse = <T>(value: unknown): value is ApiResponse<T> => {
  if (!value || typeof value !== 'object') {
    return false
  }

  const record = value as Record<string, unknown>
  return typeof record.code === 'number' && typeof record.message === 'string' && 'data' in record
}

const normalizeError = (error: unknown): ApiError => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ message?: string; code?: number }>
    const status = axiosError.response?.status
    const message =
      axiosError.response?.data?.message ?? axiosError.message ?? 'Request failed with unknown error'
    const code = axiosError.response?.data?.code
    return new ApiError(message, code, status)
  }

  if (error instanceof Error) {
    return new ApiError(error.message)
  }

  return new ApiError('Unexpected error')
}

const instance: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000
})

instance.interceptors.request.use(
  (config) => {
    const token = resolveToken()
    if (token) {
      config.headers = {
        ...config.headers,
        Authorization: `Bearer ${token}`
      }
    }
    return config
  },
  (error) => Promise.reject(normalizeError(error))
)

instance.interceptors.response.use(
  (response: AxiosResponse) => {
    const data = response.data
    if (isApiResponse<unknown>(data)) {
      if (data.code !== 0) {
        throw new ApiError(data.message, data.code, response.status)
      }
      return data.data
    }
    return data
  },
  (error) => Promise.reject(normalizeError(error))
)

export const request = async <T>(config: AxiosRequestConfig): Promise<T> =>
  instance.request<unknown, T>(config)

export default instance
