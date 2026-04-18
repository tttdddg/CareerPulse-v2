import axios, {
  AxiosError,
  AxiosHeaders,
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse
} from 'axios'
import { useUserStore } from '../stores/user'

export interface ApiResponse<T> {
  code?: number | string
  status?: number | string
  success?: boolean
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

const API_BASE_URL = import.meta.env.DEV ? '/api' : (import.meta.env.VITE_API_BASE_URL ?? '/api')

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
  return 'data' in record && ('code' in record || 'status' in record || 'success' in record)
}

const parseNumericCode = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

const isSuccessCode = (value: unknown): boolean | null => {
  const parsed = parseNumericCode(value)
  if (parsed === null) {
    return null
  }
  return parsed === 0 || parsed === 1 || parsed === 200
}

const normalizeError = (error: unknown): ApiError => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ message?: string; msg?: string; code?: number }>
    const status = axiosError.response?.status
    if (axiosError.code === 'ECONNABORTED' || axiosError.message.toLowerCase().includes('timeout')) {
      return new ApiError('Request timed out. Backend did not respond within the timeout window.', undefined, status)
    }
    if (!axiosError.response) {
      return new ApiError('No response from backend. Please check backend service or gateway forwarding.')
    }
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
      const successByFlag = typeof data.success === 'boolean' ? data.success : null
      const successByCode = isSuccessCode(data.code)
      const successByStatus = isSuccessCode(data.status)
      const success = successByFlag ?? successByCode ?? successByStatus ?? true
      if (!success) {
        throw new ApiError(
          data.message ?? data.msg ?? 'Request failed',
          parseNumericCode(data.code ?? data.status) ?? undefined,
          response.status
        )
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

