import type { AxiosRequestConfig } from 'axios'
import {
  DEMO_HISTORY_REPORTS,
  DEMO_JOBS,
  DEMO_MATCH_ANALYSIS,
  DEMO_PRIMARY_JOB_ID,
  DEMO_PROFILE_RESPONSE,
  DEMO_REPORT_HTML,
  DEMO_REPORT_ID,
  DEMO_RESOURCES,
  getDemoGraph,
  getDemoHistorySnapshot,
  getDemoJob,
  getDemoMatchAnalysis
} from './careerDemoData'
import { waitForDemoResponse } from './demoMode'

type UnknownRecord = Record<string, unknown>

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === 'object' && value !== null

const numericValue = (value: unknown, fallback: number): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : fallback
  }
  return fallback
}

const readJobId = (url: string): number | null => {
  const match = url.match(/^\/jobs\/(\d+)\/(profile|graph)$/)
  return match ? numericValue(match[1], 0) || null : null
}

const readHistoryId = (url: string): number | null => {
  const match = url.match(/^\/histories\/(\d+)\/snapshot$/)
  return match ? numericValue(match[1], 0) || null : null
}

const readReportId = (url: string): number | null => {
  const match = url.match(/^\/reports\/(\d+)(?:\/(polish|export))?$/)
  return match ? numericValue(match[1], 0) || null : null
}

const selectJobs = (config: AxiosRequestConfig) => {
  const params = isRecord(config.params) ? config.params : {}
  const keyword = typeof params.keyword === 'string' ? params.keyword.trim().toLowerCase() : ''

  if (keyword.includes('ai agent') || keyword.includes('aiagent') || keyword.includes('智能体开发')) {
    return [DEMO_JOBS[0], DEMO_JOBS[1], DEMO_JOBS[3]]
  }

  if (!keyword) {
    return DEMO_JOBS
  }

  const matched = DEMO_JOBS.filter((job) => {
    const source = `${job.job_name} ${job.industry} ${job.required_skills.join(' ')}`.toLowerCase()
    return source.includes(keyword) || keyword.split(/[\s/]+/).some((token) => token && source.includes(token))
  })
  return matched.length ? matched : DEMO_JOBS
}

const readWebJobId = (url: string, suffix: '' | '/graph' = ''): number | null => {
  const pattern = suffix
    ? /^\/web\/v1\/jobs\/(\d+)\/graph$/
    : /^\/web\/v1\/jobs\/(\d+)$/
  const match = url.match(pattern)
  return match ? numericValue(match[1], 0) || null : null
}

const readWorkflowPath = (url: string): { sessionId: string; step: string } | null => {
  const match = url.match(
    /^\/web\/v1\/workflows\/([^/]+)(?:\/(profile|target-job|match|path))?$/
  )
  if (!match) {
    return null
  }
  return { sessionId: decodeURIComponent(match[1]), step: match[2] ?? '' }
}

// Demo 模式下 /api/web/v1 的离线等价返回：数据只存在于浏览器，不进入正式用户数据域。
const demoWorkflowSummary = (
  sessionId: string,
  patch: UnknownRecord = {}
): UnknownRecord => ({
  session_id: sessionId,
  status: 'MATCH_COMPLETED',
  status_message: '人岗匹配已完成，可生成职业路径',
  job_id: DEMO_PRIMARY_JOB_ID,
  job_title: 'AI Agent开发工程师',
  overall_score: DEMO_MATCH_ANALYSIS.overall_score,
  has_student_profile: true,
  has_job_profile: true,
  has_match_result: true,
  has_career_roadmap: false,
  created_at: '2026-09-20T10:00:00+08:00',
  updated_at: '2026-09-20T10:00:00+08:00',
  ...patch
})

const handleWebRequest = (
  config: AxiosRequestConfig,
  url: string,
  method: string
): { handled: boolean; result: unknown } => {
  const workflow = readWorkflowPath(url)

  if (url === '/web/v1/jobs' && method === 'GET') {
    return {
      handled: true,
      result: {
        items: selectJobs(config),
        page: 1,
        page_size: 50,
        has_more: false,
        data_source: 'demo_json',
        fallback_used: false
      }
    }
  }

  const graphJobId = readWebJobId(url, '/graph')
  if (graphJobId !== null && method === 'GET') {
    return { handled: true, result: getDemoGraph(graphJobId) }
  }

  const jobId = readWebJobId(url)
  if (jobId !== null && method === 'GET') {
    return {
      handled: true,
      result: {
        context: getDemoJob(jobId),
        data_source: 'demo_json',
        fallback_used: false
      }
    }
  }

  if (url === '/web/v1/workflows' && method === 'POST') {
    const payload = isRecord(config.data) ? config.data : {}
    const requestedId =
      typeof payload.session_id === 'string' && payload.session_id.trim()
        ? payload.session_id.trim()
        : 'demo-session'
    return {
      handled: true,
      result: demoWorkflowSummary(requestedId, { created: true })
    }
  }

  if (url === '/web/v1/workflows' && method === 'GET') {
    const items = DEMO_HISTORY_REPORTS.map((report) =>
      demoWorkflowSummary(`demo-${report.history_id}`, {
        job_title: report.job_title,
        overall_score: report.overall_score,
        updated_at: report.created_at
      })
    )
    return {
      handled: true,
      result: { items, page: 1, page_size: 20, total: items.length, has_more: false }
    }
  }

  if (workflow && !workflow.step && method === 'GET') {
    return {
      handled: true,
      result: {
        ...demoWorkflowSummary(workflow.sessionId),
        student_profile: { basic_info: { target_job: 'AI Agent开发工程师' } },
        job_profile: { title: 'AI Agent开发工程师' },
        match_result: getDemoMatchAnalysis(DEMO_PRIMARY_JOB_ID),
        career_roadmap: null,
        agent_logs: []
      }
    }
  }

  if (workflow && workflow.step === 'profile' && method === 'PUT') {
    return {
      handled: true,
      result: demoWorkflowSummary(workflow.sessionId, {
        status: 'PROFILE_COMPLETED',
        has_student_profile: true
      })
    }
  }

  if (workflow && workflow.step === 'target-job' && method === 'PUT') {
    return {
      handled: true,
      result: demoWorkflowSummary(workflow.sessionId, {
        status: 'JOB_COMPLETED',
        has_job_profile: true
      })
    }
  }

  if (workflow && workflow.step === 'match' && method === 'POST') {
    const payload = isRecord(config.data) ? config.data : {}
    const targetJobId = numericValue(payload.job_id, DEMO_PRIMARY_JOB_ID)
    return {
      handled: true,
      result: {
        ...demoWorkflowSummary(workflow.sessionId, { status: 'MATCH_COMPLETED' }),
        match_result: getDemoMatchAnalysis(targetJobId || DEMO_PRIMARY_JOB_ID),
        idempotent_replay: false
      }
    }
  }

  if (workflow && workflow.step === 'path' && method === 'POST') {
    return {
      handled: true,
      result: {
        ...demoWorkflowSummary(workflow.sessionId, {
          status: 'PATH_COMPLETED',
          has_career_roadmap: true
        }),
        career_roadmap: { target_job: 'AI Agent开发工程师' },
        idempotent_replay: false
      }
    }
  }

  return { handled: false, result: undefined }
}

export const demoRequest = async <T>(config: AxiosRequestConfig): Promise<T> => {
  await waitForDemoResponse()

  const url = config.url ?? ''
  const method = (config.method ?? 'GET').toUpperCase()
  let result: unknown

  const webResult = handleWebRequest(config, url, method)
  if (webResult.handled) {
    result = webResult.result
  } else if (url === '/jobs' && method === 'GET') {
    result = { jobs: selectJobs(config) }
  } else if (url.endsWith('/profile') && readJobId(url)) {
    result = getDemoJob(readJobId(url) as number)
  } else if (url.endsWith('/graph') && readJobId(url)) {
    result = getDemoGraph(readJobId(url) as number)
  } else if ((url === '/student/upload/resume' || url === '/student/upload/profile') && method === 'POST') {
    result = DEMO_PROFILE_RESPONSE
  } else if (url === '/matching/analyze' && method === 'POST') {
    const payload = isRecord(config.data) ? config.data : {}
    const jobId = numericValue(payload.job_id, 0)
    result = jobId ? getDemoMatchAnalysis(jobId) : DEMO_MATCH_ANALYSIS
  } else if (url === '/reports/generate' && method === 'POST') {
    result = { report_id: DEMO_REPORT_ID, content: DEMO_REPORT_HTML, status: 'ready' }
  } else if (/^\/reports\/\d+\/polish$/.test(url) && method === 'POST') {
    const payload = isRecord(config.data) ? config.data : {}
    const sourceText = typeof payload.text === 'string' ? payload.text : DEMO_REPORT_HTML
    result = { polished_text: sourceText }
  } else if (/^\/reports\/\d+\/export$/.test(url) && method === 'GET') {
    result = new Blob(
      ['CareerPulse 成长报告\n\n技术匹配分：81.67\n目标岗位：AI Agent开发工程师'],
      { type: 'text/plain;charset=utf-8' }
    )
  } else if (readReportId(url) && method === 'GET') {
    result = { report_id: readReportId(url), content: DEMO_REPORT_HTML, status: 'ready' }
  } else if (/^\/users\/[^/]+\/histories$/.test(url) && method === 'GET') {
    result = { reports: DEMO_HISTORY_REPORTS }
  } else if (readHistoryId(url) && method === 'GET') {
    result = getDemoHistorySnapshot(readHistoryId(url) as number)
  } else if (url === '/recommendations' && method === 'GET') {
    result = DEMO_RESOURCES
  } else {
    throw new Error(`当前离线数据未覆盖请求：${method} ${url}`)
  }

  return result as T
}

