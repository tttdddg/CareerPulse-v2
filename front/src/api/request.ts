import axios, {
  AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse
} from 'axios'
import { demoRequest } from '../demo/demoRequest'
import { isDemoMode } from '../demo/demoMode'

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

export const getUserFacingErrorMessage = (error: unknown, fallback: string): string => {
  if (!(error instanceof ApiError)) {
    return fallback
  }

  if (error.status === 400 || error.status === 422) {
    return '提交的数据无法处理，请检查填写内容后重试'
  }
  if (error.status === 401 || error.status === 403) {
    return '当前会话无权执行此操作，请重新登录后重试'
  }
  if (error.status === 404) {
    return '未找到对应数据，请刷新或重新完成前置步骤'
  }
  if (error.status && error.status >= 500) {
    return '服务暂时不可用，请稍后重试'
  }

  return fallback
}

const API_BASE_URL = import.meta.env.DEV ? '/api' : (import.meta.env.VITE_API_BASE_URL ?? '/api')
const CSRF_COOKIE_NAME = import.meta.env.VITE_CSRF_COOKIE_NAME ?? 'careerpulse_csrf'

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
    const axiosError = error as AxiosError<{
      message?: string
      msg?: string
      code?: number
      detail?: { message?: string; code?: string }
    }>
    const status = axiosError.response?.status
    if (axiosError.code === 'ECONNABORTED' || axiosError.message.toLowerCase().includes('timeout')) {
      return new ApiError('Request timed out. Backend did not respond within the timeout window.', undefined, status)
    }
    if (!axiosError.response) {
      return new ApiError('No response from backend. Please check backend service or gateway forwarding.')
    }
    const message =
      axiosError.response?.data?.detail?.message ??
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
  timeout: 15000,
  withCredentials: true,
  xsrfCookieName: CSRF_COOKIE_NAME,
  xsrfHeaderName: 'X-CSRF-Token'
})

// 业务请求一律携带 Cookie 会话与 CSRF，不再提供跳过认证的开关。
type RequestConfigWithAuth = AxiosRequestConfig

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
  (error) => {
    if (
      axios.isAxiosError(error) &&
      error.response?.status === 401 &&
      error.config?.url !== '/auth/login' &&
      typeof window !== 'undefined'
    ) {
      window.dispatchEvent(new CustomEvent('career-pulse:unauthorized'))
    }
    return Promise.reject(normalizeError(error))
  }
)

export const request = async <T>(config: RequestConfigWithAuth): Promise<T> => {
  if (isDemoMode) {
    return demoRequest<T>(config)
  }
  return instance.request<unknown, T>(config)
}

export default instance

