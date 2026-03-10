import axios, {
  AxiosError,
  AxiosHeaders,
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse
} from 'axios'
import { useUserStore } from '../stores/user'

export interface ApiResponse<T> {
  code: number
  message?: string
  msg?: string
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

const API_BASE_URL = import.meta.env.DEV ? '/api' : (import.meta.env.VITE_API_BASE_URL ?? '')

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
  return typeof record.code === 'number' && 'data' in record
}

const normalizeError = (error: unknown): ApiError => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ message?: string; msg?: string; code?: number }>
    const status = axiosError.response?.status
    const message =
      axiosError.response?.data?.message ??
      axiosError.response?.data?.msg ??
      axiosError.message ??
      'Request failed with unknown error'
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

interface RequestConfigWithAuth extends AxiosRequestConfig {
  skipAuth?: boolean
}

instance.interceptors.request.use(
  (config) => {
    const requestConfig = config as RequestConfigWithAuth
    const token = resolveToken()
    if (token && !requestConfig.skipAuth) {
      const headers = AxiosHeaders.from(config.headers)
      headers.set('Authorization', `Bearer ${token}`)
      config.headers = headers
    }
    return config
  },
  (error) => Promise.reject(normalizeError(error))
)

instance.interceptors.response.use(
  (response: AxiosResponse) => {
    const data = response.data
    if (isApiResponse<unknown>(data)) {
      const success = data.code === 0 || data.code === 1 || data.code === 200
      if (!success) {
        throw new ApiError(data.message ?? data.msg ?? 'Request failed', data.code, response.status)
      }
      return data.data
    }
    return data
  },
  (error) => Promise.reject(normalizeError(error))
)

export const request = async <T>(config: RequestConfigWithAuth): Promise<T> =>
  instance.request<unknown, T>(config)

export default instance

