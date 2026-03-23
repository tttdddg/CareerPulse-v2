import { request } from '../request'

type UnknownRecord = Record<string, unknown>

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === 'object' && value !== null

const asArray = (value: unknown): unknown[] => (Array.isArray(value) ? value : [])

const toNumber = (value: unknown, fallback = 0): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const normalized = value.replace(/%/g, '').trim()
    const parsed = Number(normalized)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return fallback
}

const toOptionalNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return undefined
}

const toStringSafe = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback

const pickRecordList = (source: unknown, keys: string[]): UnknownRecord[] => {
  if (Array.isArray(source)) {
    return source.filter(isRecord)
  }
  if (!isRecord(source)) {
    return []
  }
  for (const key of keys) {
    const value = source[key]
    if (Array.isArray(value)) {
      return value.filter(isRecord)
    }
  }
  return []
}

const getByKeys = (source: UnknownRecord, keys: string[]): unknown => {
  for (const key of keys) {
    if (key in source) {
      return source[key]
    }
  }
  return undefined
}

const pickPayloadRecord = (source: unknown): UnknownRecord => {
  if (!isRecord(source)) {
    return {}
  }

  const queue: unknown[] = [source]
  const visited = new Set<unknown>()
  const preferredKeys = ['data', 'result', 'analysis', 'payload']

  while (queue.length > 0) {
    const current = queue.shift()
    if (!isRecord(current) || visited.has(current)) {
      continue
    }
    visited.add(current)

    for (const key of preferredKeys) {
      const next = current[key]
      if (isRecord(next)) {
        return next
      }
      if (next !== undefined) {
        queue.push(next)
      }
    }
  }

  return source
}

const toStringArray = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map((item) => toStringSafe(item)).filter(Boolean)
  }
  if (typeof value === 'string') {
    return value
      .split(/[;,，；\n]/)
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return []
}

export interface JobItem {
  id: number
  name: string
  match: number
  company: string
  industry: string
  salaryRange: string
  requiredSkills: string[]
  requiredCerts: string[]
  softSkills: string[]
  abilityDimensions: {
    innovation: number
    learning: number
    stressTolerance: number
    communication: number
    internship: number
  }
  highlights: string[]
  description: string
}

export interface FetchJobsParams {
  keyword: string
  page?: number
  size?: number
}

export interface StudentUploadProfilePayload {
  name?: string
  skills: string
  certificates: string
  internships: string
  selfEvaluation: string
}

export interface StudentUploadProfileResult {
  studentId: number | null
  name: string
  skills: string
  certificates: string
  internships: string
  selfEvaluation: string
}

export interface MatchingAnalyzePayload {
  studentId: number
  jobId: number
  userId?: string
}

export interface RadarIndicator {
  name: string
  max: number
}

export interface RadarSeries {
  name: string
  values: number[]
}

export interface MatchingAnalyzeResult {
  matchScore: number
  radarIndicators: RadarIndicator[]
  radarSeries: RadarSeries[]
  strengths: string[]
  gaps: string[]
  reportId: number | null
}

export interface PathGraphNode {
  id: string
  label: string
  x?: number
  y?: number
  type?: 'vertical' | 'horizontal' | 'target'
  relation?: string
  jobDescription?: string
  coreSkills?: string[]
  salaryRange?: string
}

export interface PathGraphEdge {
  source: string
  target: string
  label?: string
  type?: 'vertical' | 'horizontal' | 'target'
}

export interface PathGraphResult {
  nodes: PathGraphNode[]
  edges: PathGraphEdge[]
}

const normalizeAbilityDimensions = (
  value: unknown
): {
  innovation: number
  learning: number
  stressTolerance: number
  communication: number
  internship: number
} => {
  const defaults = {
    innovation: 0,
    learning: 0,
    stressTolerance: 0,
    communication: 0,
    internship: 0
  }
  if (!isRecord(value)) {
    return defaults
  }

  return {
    innovation: toNumber(getByKeys(value, ['innovation', '创新能力']), 0),
    learning: toNumber(getByKeys(value, ['learning', '学习能力']), 0),
    stressTolerance: toNumber(getByKeys(value, ['stress_tolerance', 'stressTolerance', '抗压能力']), 0),
    communication: toNumber(getByKeys(value, ['communication', '沟通能力']), 0),
    internship: toNumber(getByKeys(value, ['internship', '实习能力']), 0)
  }
}

export interface ReportItem {
  id: string
  title: string
  createdAt: string
  score: number
  tags: string[]
}

export interface GrowthPoint {
  date: string
  value: number
  label?: string
}

export interface UserHistoriesResult {
  reports: ReportItem[]
  growth: GrowthPoint[]
}

export interface ReportGeneratePayload {
  studentId: number
  jobId: number
  customInstructions?: string
  userId?: string
}

export interface ReportDocument {
  reportId: number | null
  content: string
  status?: string
}

const extractContent = (source: unknown): string => {
  if (typeof source === 'string') {
    return source
  }
  if (!isRecord(source)) {
    return ''
  }

  const sectionToHtml = (value: unknown): string => {
    if (!isRecord(value)) {
      return ''
    }
    const sectionTitle = toStringSafe(getByKeys(value, ['title', 'name']), '').trim()
    const sectionContent = toStringSafe(getByKeys(value, ['content', 'text', 'desc', 'description']), '').trim()
    if (!sectionTitle && !sectionContent) {
      return ''
    }
    if (sectionTitle && sectionContent) {
      return `<h3>${sectionTitle}</h3><p>${sectionContent}</p>`
    }
    if (sectionTitle) {
      return `<h3>${sectionTitle}</h3>`
    }
    return `<p>${sectionContent}</p>`
  }

  const renderStructuredContent = (value: UnknownRecord): string => {
    const title = toStringSafe(getByKeys(value, ['title', 'name']), '').trim()
    const intro = toStringSafe(getByKeys(value, ['content', 'text', 'summary']), '').trim()
    const sections = asArray(getByKeys(value, ['sections', 'items', 'chapters'])).map(sectionToHtml).filter(Boolean)

    const chunks: string[] = []
    if (title) {
      chunks.push(`<h2>${title}</h2>`)
    }
    if (intro) {
      chunks.push(`<p>${intro}</p>`)
    }
    if (sections.length) {
      chunks.push(sections.join(''))
    }
    return chunks.join('')
  }

  const direct = getByKeys(source, [
    'content',
    'text',
    'markdown',
    'plan',
    'report_content',
    'reportContent',
    'body',
    'detail',
    'html',
    'article'
  ])
  if (typeof direct === 'string' && direct.trim()) {
    return direct
  }
  if (isRecord(direct)) {
    const rendered = renderStructuredContent(direct)
    if (rendered) {
      return rendered
    }
  }

  const nestedKeys = ['report', 'data', 'result', 'payload']
  for (const key of nestedKeys) {
    const nested = source[key]
    const extracted = extractContent(nested)
    if (extracted) {
      return extracted
    }
  }

  return ''
}

const normalizeJob = (input: UnknownRecord): JobItem => {
  const id = toNumber(getByKeys(input, ['job_id', 'id']), 0)
  const name = toStringSafe(getByKeys(input, ['job_name', 'name', 'title', 'position']), `Job ${id || ''}`)
  const highlightsSource = getByKeys(input, ['highlights', 'advantages', 'strengths'])
  const highlights = asArray(highlightsSource).map((item) => toStringSafe(item)).filter(Boolean)
  const description = toStringSafe(getByKeys(input, ['job_description', 'description', 'desc', 'summary']), '')
  const match = toNumber(getByKeys(input, ['match_score', 'match', 'score']), 0)
  const abilityDimensions = normalizeAbilityDimensions(getByKeys(input, ['ability_dimensions', 'abilityDimensions']))

  return {
    id,
    name,
    match,
    company: toStringSafe(getByKeys(input, ['company', 'company_name']), ''),
    industry: toStringSafe(getByKeys(input, ['industry']), ''),
    salaryRange: toStringSafe(getByKeys(input, ['salary_range', 'salaryRange']), ''),
    requiredSkills: toStringArray(getByKeys(input, ['required_skills', 'skills'])),
    requiredCerts: toStringArray(getByKeys(input, ['required_certs', 'certificates'])),
    softSkills: toStringArray(getByKeys(input, ['soft_skills'])),
    abilityDimensions,
    highlights,
    description
  }
}

const normalizeAnalysis = (source: unknown): MatchingAnalyzeResult => {
  const record = pickPayloadRecord(source)
  const nested = pickPayloadRecord(record)
  const payload = Object.keys(nested).length > 0 ? nested : record

  const strengths = toStringArray(getByKeys(payload, ['strengths', 'advantages', 'highlights']))
  const gaps = toStringArray(getByKeys(payload, ['gaps', 'weaknesses', 'deficiencies']))

  const gapAnalysis = asArray(getByKeys(payload, ['gap_analysis', 'gapAnalysis']))
    .map((item) => {
      if (!isRecord(item)) {
        return ''
      }
      return toStringSafe(getByKeys(item, ['item', 'name', 'title']), '')
    })
    .filter(Boolean)
  const normalizedGaps = gaps.length > 0 ? gaps : gapAnalysis

  const radarIndicatorsSource = asArray(
    getByKeys(payload, ['radar_indicators', 'radarIndicators', 'indicators', 'dimensions'])
  )
  const radarIndicators = radarIndicatorsSource
    .map((item) => {
      if (!isRecord(item)) {
        return null
      }
      const name = toStringSafe(getByKeys(item, ['name', 'label']), '')
      if (!name) {
        return null
      }
      return {
        name,
        max: toNumber(getByKeys(item, ['max', 'maxValue']), 100)
      }
    })
    .filter((item): item is RadarIndicator => item !== null)

  const radarSeriesSource = asArray(getByKeys(payload, ['radar_series', 'radarSeries', 'series']))
  const radarSeries = radarSeriesSource
    .map((item) => {
      if (!isRecord(item)) {
        return null
      }
      const valuesSource = asArray(getByKeys(item, ['values', 'data']))
      const values = valuesSource.map((value) => toNumber(value, 0))
      if (!values.length) {
        return null
      }
      return {
        name: toStringSafe(getByKeys(item, ['name', 'label']), 'Capability'),
        values
      }
    })
    .filter((item): item is RadarSeries => item !== null)

  const dimensions = asArray(getByKeys(payload, ['dimensions']))
    .map((item) => {
      if (!isRecord(item)) {
        return null
      }
      const name = toStringSafe(getByKeys(item, ['name', 'label']), '')
      if (!name) {
        return null
      }
      return {
        name,
        candidate: toNumber(getByKeys(item, ['student_score', 'studentScore', 'score']), 0),
        target: toNumber(getByKeys(item, ['job_required', 'jobRequired', 'required']), 0)
      }
    })
    .filter((item): item is { name: string; candidate: number; target: number } => item !== null)

  const derivedIndicators =
    dimensions.length > 0
      ? dimensions.map((item) => ({
          name: item.name,
          max: 100
        }))
      : []
  const derivedSeries =
    dimensions.length > 0
      ? [
          {
            name: 'Candidate',
            values: dimensions.map((item) => item.candidate)
          },
          {
            name: 'Target Role',
            values: dimensions.map((item) => item.target)
          }
        ]
      : []

  const fallbackNames = normalizedGaps.length
    ? normalizedGaps
    : ['Business Understanding', 'Data Skill', 'Role Competency', 'Communication', 'Execution']
  const fallbackIndicators =
    radarIndicators.length > 0
      ? radarIndicators
      : derivedIndicators.length > 0
        ? derivedIndicators
      : fallbackNames.map((name) => ({
          name,
          max: 100
        }))
  const fallbackSeries =
    radarSeries.length > 0
      ? radarSeries
      : derivedSeries.length > 0
        ? derivedSeries
      : [
          {
            name: 'Candidate',
            values: fallbackIndicators.map(() => 65)
          },
          {
            name: 'Target Role',
            values: fallbackIndicators.map(() => 80)
          }
        ]

  return {
    matchScore: toNumber(getByKeys(payload, ['match_score', 'matchScore', 'score', 'overall_score', 'match']), 0),
    radarIndicators: fallbackIndicators,
    radarSeries: fallbackSeries,
    strengths,
    gaps: normalizedGaps,
    reportId: toOptionalNumber(getByKeys(payload, ['report_id', 'reportId'])) ?? null
  }
}

const normalizeGraph = (source: unknown): PathGraphResult => {
  const record = pickPayloadRecord(source)

  const centerRaw = getByKeys(record, ['center'])
  const verticalRaw = asArray(getByKeys(record, ['vertical']))
  const lateralRaw = asArray(getByKeys(record, ['lateral']))
  const hasCenterStylePayload = isRecord(centerRaw) || verticalRaw.length > 0 || lateralRaw.length > 0

  if (hasCenterStylePayload) {
    const center = isRecord(centerRaw) ? centerRaw : {}
    const centerId = toStringSafe(getByKeys(center, ['id', 'job_id']), 'center')
    const centerLabel = toStringSafe(getByKeys(center, ['name', 'label', 'title']), '目标岗位')

    const centerNode: PathGraphNode = {
      id: centerId,
      label: centerLabel,
      x: 80,
      y: 280,
      type: 'target',
      relation: toStringSafe(getByKeys(center, ['relation']), ''),
      jobDescription: toStringSafe(getByKeys(center, ['job_description', 'description', 'desc']), ''),
      coreSkills: toStringArray(getByKeys(center, ['core_skills', 'required_skills', 'skills'])),
      salaryRange: toStringSafe(getByKeys(center, ['salary_range', 'salaryRange']), '')
    }

    const verticalNodes = verticalRaw
      .filter(isRecord)
      .map((item, index) => ({
        id: toStringSafe(getByKeys(item, ['id', 'job_id']), `vertical-${index}`),
        label: toStringSafe(getByKeys(item, ['name', 'label', 'title']), `纵向岗位 ${index + 1}`),
        x: 80,
        y: 80 + index * 100,
        type: 'vertical' as const,
        relation: toStringSafe(getByKeys(item, ['relation']), ''),
        jobDescription: toStringSafe(getByKeys(item, ['job_description', 'description', 'desc']), ''),
        coreSkills: toStringArray(getByKeys(item, ['core_skills', 'required_skills', 'skills'])),
        salaryRange: toStringSafe(getByKeys(item, ['salary_range', 'salaryRange']), '')
      }))

    const lateralNodes = lateralRaw
      .filter(isRecord)
      .map((item, index) => ({
        id: toStringSafe(getByKeys(item, ['id', 'job_id']), `lateral-${index}`),
        label: toStringSafe(getByKeys(item, ['name', 'label', 'title']), `横向岗位 ${index + 1}`),
        x: 320,
        y: 180 + index * 100,
        type: 'horizontal' as const,
        relation: toStringSafe(getByKeys(item, ['relation']), ''),
        jobDescription: toStringSafe(getByKeys(item, ['job_description', 'description', 'desc']), ''),
        coreSkills: toStringArray(getByKeys(item, ['core_skills', 'required_skills', 'skills'])),
        salaryRange: toStringSafe(getByKeys(item, ['salary_range', 'salaryRange']), '')
      }))

    const relationEdges = pickRecordList(record, ['relations']).map((edge) => ({
      source: toStringSafe(getByKeys(edge, ['source', 'from', 'start']), ''),
      target: toStringSafe(getByKeys(edge, ['target', 'to', 'end']), ''),
      label: toStringSafe(getByKeys(edge, ['label', 'name', 'relation']), '') || undefined,
      type: toStringSafe(getByKeys(edge, ['type']), '') as PathGraphEdge['type']
    }))

    const allNodes = [centerNode, ...verticalNodes, ...lateralNodes]
    const fallbackEdges: PathGraphEdge[] = [
      ...verticalNodes.map((node) => ({
        source: node.id,
        target: centerNode.id,
        label: node.relation || '晋升',
        type: 'vertical' as const
      })),
      ...lateralNodes.map((node) => ({
        source: centerNode.id,
        target: node.id,
        label: node.relation || '换岗',
        type: 'horizontal' as const
      }))
    ]
    const edges =
      relationEdges.length > 0
        ? relationEdges.filter((item) => item.source && item.target)
        : fallbackEdges

    return {
      nodes: allNodes.filter((item) => item.id && item.label),
      edges
    }
  }

  const nodeCandidates = pickRecordList(record, ['nodes', 'vertexes', 'vertices', 'data', 'positions', 'jobs'])
  const edgeCandidates = pickRecordList(record, ['edges', 'links', 'relations', 'connections', 'paths'])

  const nodes = nodeCandidates.map((node, index) => ({
    id: toStringSafe(getByKeys(node, ['id', 'node_id']), `node-${index}`),
    label: toStringSafe(getByKeys(node, ['label', 'name', 'title']), `Node ${index + 1}`),
    x: toOptionalNumber(getByKeys(node, ['x', 'posX'])),
    y: toOptionalNumber(getByKeys(node, ['y', 'posY'])),
    type: toStringSafe(getByKeys(node, ['type']), '') as PathGraphNode['type'],
    relation: toStringSafe(getByKeys(node, ['relation']), ''),
    jobDescription: toStringSafe(getByKeys(node, ['job_description', 'description', 'desc']), ''),
    coreSkills: toStringArray(getByKeys(node, ['core_skills', 'required_skills', 'skills'])),
    salaryRange: toStringSafe(getByKeys(node, ['salary_range', 'salaryRange']), '')
  }))

  const edges = edgeCandidates.map((edge) => ({
    source: toStringSafe(getByKeys(edge, ['source', 'from', 'start', 'from_id', 'source_id']), ''),
    target: toStringSafe(getByKeys(edge, ['target', 'to', 'end', 'to_id', 'target_id']), ''),
    label: toStringSafe(getByKeys(edge, ['label', 'name']), '') || undefined,
    type: toStringSafe(getByKeys(edge, ['type']), '') as PathGraphEdge['type']
  }))

  if (nodes.length === 0 && edges.length > 0) {
    const uniqueIds = [...new Set(edges.flatMap((edge) => [edge.source, edge.target]).filter(Boolean))]
    const derivedNodes = uniqueIds.map((id, index) => ({
      id,
      label: id,
      x: index % 2 === 0 ? 60 : 260,
      y: 60 + Math.floor(index / 2) * 100,
      type: (index === uniqueIds.length - 1 ? 'target' : 'vertical') as PathGraphNode['type']
    }))

    return {
      nodes: derivedNodes,
      edges: edges.filter((item) => item.source && item.target)
    }
  }

  return {
    nodes: nodes.filter((item) => item.id && item.label),
    edges: edges.filter((item) => item.source && item.target)
  }
}

const normalizeReport = (source: unknown): ReportItem | null => {
  const record = isRecord(source) ? source : {}
  const reportId = toStringSafe(getByKeys(record, ['report_id', 'reportId', 'id']), '').trim()
  const title = toStringSafe(getByKeys(record, ['title', 'report_title', 'job_name']), '').trim()
  const createdAt = toStringSafe(
    getByKeys(record, ['created_at', 'createdAt', 'date']),
    new Date().toISOString().slice(0, 10)
  )
  const score = toNumber(getByKeys(record, ['score', 'match_score', 'matchScore']), 0)
  const tags = asArray(getByKeys(record, ['tags', 'labels'])).map((item) => toStringSafe(item)).filter(Boolean)

  // 后端返回空对象/占位对象时，不生成默认假报告，避免登录后重复出现 "Career Report"。
  if (!reportId || !title) {
    return null
  }

  return {
    id: reportId,
    title,
    createdAt: createdAt.slice(0, 10),
    score,
    tags
  }
}

const normalizeGrowth = (source: unknown): GrowthPoint[] => {
  const list = pickRecordList(source, ['growth', 'growth_series', 'series', 'points'])
  return list.map((item) => ({
    date: toStringSafe(getByKeys(item, ['date', 'x', 'month']), ''),
    value: toNumber(getByKeys(item, ['value', 'score', 'y']), 0),
    label: toStringSafe(getByKeys(item, ['label']), '') || undefined
  }))
}

export const fetchJobs = async (params: FetchJobsParams): Promise<JobItem[]> => {
  const response = await request<unknown>({
    url: '/jobs',
    method: 'GET',
    params: {
      keyword: params.keyword,
      page: params.page ?? 1,
      size: params.size ?? 20
    }
  })

  const items = pickRecordList(response, ['jobs', 'items', 'list', 'data'])
  if (items.length > 0) {
    return items.map(normalizeJob).filter((job) => job.id > 0)
  }

  if (Array.isArray(response)) {
    return response.filter(isRecord).map(normalizeJob).filter((job) => job.id > 0)
  }

  return []
}

export const fetchJobProfile = async (jobId: number): Promise<JobItem> => {
  const response = await request<unknown>({
    url: `/jobs/${jobId}/profile`,
    method: 'GET'
  })
  return normalizeJob(isRecord(response) ? response : {})
}

export const fetchJobGraph = async (jobId: number): Promise<PathGraphResult> => {
  const response = await request<unknown>({
    url: `/jobs/${jobId}/graph`,
    method: 'GET'
  })
  return normalizeGraph(response)
}

export const uploadStudentResume = async (formData: FormData): Promise<StudentUploadProfileResult> => {
  const response = await request<unknown>({
    url: '/student/upload/resume',
    method: 'POST',
    data: formData,
    timeout: 90000,
    skipAuth: true
  })

  const record = pickPayloadRecord(response)
  return {
    studentId: toOptionalNumber(getByKeys(record, ['student_id', 'studentId'])) ?? null,
    name: toStringSafe(getByKeys(record, ['name']), ''),
    skills: toStringSafe(getByKeys(record, ['skills']), ''),
    certificates: toStringSafe(getByKeys(record, ['certificates']), ''),
    internships: toStringSafe(getByKeys(record, ['internships', 'experience']), ''),
    selfEvaluation: toStringSafe(getByKeys(record, ['self_evaluation', 'selfEvaluation']), '')
  }
}

export const uploadStudentProfile = async (
  payload: StudentUploadProfilePayload
): Promise<StudentUploadProfileResult> => {
  const response = await request<unknown>({
    url: '/student/upload/profile',
    method: 'POST',
    skipAuth: true,
    data: {
      name: payload.name,
      skills: payload.skills,
      certificates: payload.certificates,
      internships: payload.internships,
      self_evaluation: payload.selfEvaluation
    }
  })

  const record = pickPayloadRecord(response)
  return {
    studentId: toOptionalNumber(getByKeys(record, ['student_id', 'studentId'])) ?? null,
    name: toStringSafe(getByKeys(record, ['name']), payload.name ?? ''),
    skills: toStringSafe(getByKeys(record, ['skills']), payload.skills),
    certificates: toStringSafe(getByKeys(record, ['certificates']), payload.certificates),
    internships: toStringSafe(getByKeys(record, ['internships']), payload.internships),
    selfEvaluation: toStringSafe(
      getByKeys(record, ['self_evaluation', 'selfEvaluation']),
      payload.selfEvaluation
    )
  }
}

export const matchingAnalyze = async (payload: MatchingAnalyzePayload): Promise<MatchingAnalyzeResult> => {
  const response = await request<unknown>({
    url: '/matching/analyze',
    method: 'POST',
    skipAuth: true,
    timeout: 120000,
    data: {
      student_id: payload.studentId,
      job_id: payload.jobId,
      user_id: payload.userId ?? 'default'
    }
  })

  return normalizeAnalysis(response)
}

export const generateReport = async (payload: ReportGeneratePayload): Promise<ReportDocument> => {
  const response = await request<unknown>({
    url: '/reports/generate',
    method: 'POST',
    skipAuth: true,
    timeout: 45000,
    data: {
      student_id: payload.studentId,
      job_id: payload.jobId,
      custom_instructions: payload.customInstructions,
      user_id: payload.userId ?? 'default'
    }
  })

  const record = pickPayloadRecord(response)
  return {
    reportId: toOptionalNumber(getByKeys(record, ['report_id', 'reportId'])) ?? null,
    content: extractContent(record),
    status: toStringSafe(getByKeys(record, ['status']), '') || undefined
  }
}

export const fetchReport = async (reportId: number): Promise<ReportDocument> => {
  const response = await request<unknown>({
    url: `/reports/${reportId}`,
    method: 'GET',
    skipAuth: true,
    timeout: 30000
  })
  const record = pickPayloadRecord(response)
  return {
    reportId: toOptionalNumber(getByKeys(record, ['report_id', 'reportId'])) ?? reportId,
    content: extractContent(record),
    status: toStringSafe(getByKeys(record, ['status']), '') || undefined
  }
}

export const polishReport = async (
  reportId: number,
  payload: { text: string; paragraphIndex?: number }
): Promise<string> => {
  const response = await request<unknown>({
    url: `/reports/${reportId}/polish`,
    method: 'POST',
    data: {
      paragraph_index: payload.paragraphIndex ?? 0,
      text: payload.text
    }
  })

  if (typeof response === 'string') {
    return response
  }
  if (isRecord(response)) {
    return toStringSafe(getByKeys(response, ['content', 'text', 'result']), payload.text)
  }
  return payload.text
}

export const exportReport = async (reportId: number, format: 'pdf' | 'word' = 'pdf'): Promise<Blob> => {
  try {
    return await request<Blob>({
      url: `/reports/${reportId}/export`,
      method: 'GET',
      params: { format },
      responseType: 'blob'
    })
  } catch (error) {
    const status = (error as { status?: number })?.status
    if (status !== 404 && status !== 405) {
      throw error
    }

    const fallbackRequests = [
      () =>
        request<Blob>({
          url: `/history/reports/${reportId}/export`,
          method: 'GET',
          params: { format },
          responseType: 'blob'
        }),
      () =>
        request<Blob>({
          url: `/reports/${reportId}/export`,
          method: 'POST',
          data: { format },
          responseType: 'blob'
        }),
      () =>
        request<Blob>({
          url: `/history/reports/${reportId}/export`,
          method: 'POST',
          data: { format },
          responseType: 'blob'
        })
    ]

    let lastError: unknown = error
    for (const run of fallbackRequests) {
      try {
        return await run()
      } catch (fallbackError) {
        lastError = fallbackError
      }
    }

    throw lastError
  }
}

export const fetchUserHistories = async (userId: string): Promise<UserHistoriesResult> => {
  const response = await request<unknown>({
    url: `/users/${userId}/histories`,
    method: 'GET'
  })

  const reports = pickRecordList(response, ['reports', 'histories', 'items', 'list'])
    .map(normalizeReport)
    .filter((item): item is ReportItem => item !== null)
  const growth = normalizeGrowth(response)

  return { reports, growth }
}

export const fetchHistorySnapshot = async (historyId: number): Promise<GrowthPoint[]> => {
  const response = await request<unknown>({
    url: `/histories/${historyId}/snapshot`,
    method: 'GET'
  })
  return normalizeGrowth(response)
}

export const fetchRecommendations = async (gap = ''): Promise<string[]> => {
  const response = await request<unknown>({
    url: '/recommendations',
    method: 'GET',
    params: { gap }
  })

  if (Array.isArray(response)) {
    return response
      .map((item) => {
        if (typeof item === 'string') {
          return item
        }
        if (!isRecord(item)) {
          return ''
        }
        const title = toStringSafe(getByKeys(item, ['title', 'name', 'item']), '')
        const url = toStringSafe(getByKeys(item, ['url', 'link']), '')
        const suggestion = toStringSafe(getByKeys(item, ['suggestion', 'desc', 'description']), '')
        if (title && url) {
          return `${title}：${url}`
        }
        return title || suggestion
      })
      .filter(Boolean)
  }

  if (isRecord(response)) {
    return asArray(getByKeys(response, ['recommendations', 'items', 'tips']))
      .map((item) => toStringSafe(item))
      .filter(Boolean)
  }

  return []
}
