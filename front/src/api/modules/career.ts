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

const toDisplayText = (value: unknown): string => {
  if (typeof value === 'string') {
    return value.trim()
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  if (Array.isArray(value)) {
    return value.map(toDisplayText).filter(Boolean).join('；')
  }
  if (!isRecord(value)) {
    return ''
  }

  return [...new Set(Object.values(value).map(toDisplayText).filter(Boolean))].join('；')
}

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
  education: string
  major: string
  skills: string
  certificates: string
  projects: string
  internships: string
  workExperience: string
  targetJob: string
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
  gapDetails: MatchingGap[]
  historyId: number | null
  reportId: number | null
}

export interface MatchingGap {
  name: string
  status?: string
  suggestion?: string
  priority?: string
}

export interface PathGraphNode {
  id: string
  label: string
  x?: number
  y?: number
  type?: 'vertical' | 'horizontal' | 'target'
  relation?: string
  relationStrength?: number
  jobDescription?: string
  coreSkills?: string[]
  salaryRange?: string
}

export interface PathGraphEdge {
  source: string
  target: string
  label?: string
  type?: 'vertical' | 'horizontal' | 'target'
  weight?: number
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
  score: number | null
  tags: string[]
  content?: string
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

export interface LearningResource {
  title: string
  type: string
  targetAbility?: string
  reason?: string
  url?: string
  source?: string
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

const normalizeStudentUploadResponse = (
  source: unknown,
  submittedProfile?: StudentUploadProfilePayload
): StudentUploadProfileResult => {
  const envelope = isRecord(source) ? source : {}
  const profileValue = getByKeys(envelope, ['profile'])
  const profile = isRecord(profileValue) ? profileValue : {}
  const educationValue = getByKeys(profile, ['education', 'education_background', 'educationBackground'])
  const educationRecords = (Array.isArray(educationValue) ? educationValue : [educationValue]).filter(isRecord)
  const nestedMajor = educationRecords
    .map((item) => getByKeys(item, ['major', 'specialty', 'field_of_study', 'fieldOfStudy', 'program']))
    .map(toDisplayText)
    .find(Boolean)

  const studentId = toOptionalNumber(getByKeys(envelope, ['student_id', 'studentId'])) ?? null
  if (!studentId) {
    throw new Error('学生画像接口未返回有效 student_id')
  }

  return {
    studentId,
    name:
      toDisplayText(getByKeys(profile, ['name', 'student_name', 'studentName'])) ||
      toDisplayText(getByKeys(envelope, ['student_name', 'studentName'])) ||
      submittedProfile?.name?.trim() ||
      '',
    education: toDisplayText(educationValue),
    major:
      toDisplayText(getByKeys(profile, ['major', 'major_name', 'majorName', 'profession'])) || nestedMajor || '',
    skills: toDisplayText(getByKeys(profile, ['skills', 'professional_skills', 'professionalSkills'])),
    certificates: toDisplayText(getByKeys(profile, ['certificates', 'certs', 'qualifications'])),
    projects: toDisplayText(getByKeys(profile, ['projects', 'project_experience', 'projectExperience'])),
    internships: toDisplayText(getByKeys(profile, ['internships', 'internship_experience', 'internshipExperience'])),
    workExperience: toDisplayText(
      getByKeys(profile, ['work_experience', 'workExperience', 'employment', 'employment_history'])
    ),
    targetJob: toDisplayText(
      getByKeys(profile, ['target_job', 'targetJob', 'target_role', 'targetRole', 'desired_position'])
    ),
    selfEvaluation: toDisplayText(
      getByKeys(profile, ['self_evaluation', 'selfEvaluation', 'summary', 'objective'])
    )
  }
}

const normalizeAnalysis = (source: unknown): MatchingAnalyzeResult => {
  const record = pickPayloadRecord(source)
  const nested = pickPayloadRecord(record)
  const payload = Object.keys(nested).length > 0 ? nested : record

  const strengths = toStringArray(getByKeys(payload, ['strengths', 'advantages', 'highlights']))
  const gaps = toStringArray(getByKeys(payload, ['gaps', 'weaknesses', 'deficiencies']))

  const gapDetails: MatchingGap[] = asArray(getByKeys(payload, ['gap_analysis', 'gapAnalysis']))
    .map((item) => {
      if (!isRecord(item)) {
        return null
      }
      const name = toStringSafe(getByKeys(item, ['item', 'name', 'title']), '').trim()
      if (!name) {
        return null
      }
      const gap: MatchingGap = {
        name,
        status: toStringSafe(getByKeys(item, ['status']), '') || undefined,
        suggestion: toStringSafe(getByKeys(item, ['suggestion', 'description', 'desc']), '') || undefined,
        priority: toStringSafe(getByKeys(item, ['priority', 'priority_label', 'priorityLabel']), '') || undefined
      }
      return gap
    })
    .filter((item): item is MatchingGap => item !== null)
  const normalizedGaps = gaps.length > 0 ? gaps : gapDetails.map((item) => item.name)
  const normalizedGapDetails: MatchingGap[] =
    gapDetails.length > 0 ? gapDetails : normalizedGaps.map((name) => ({ name }))

  const radarIndicatorsSource = asArray(getByKeys(payload, ['radar_indicators', 'radarIndicators', 'indicators']))
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
      const values = asArray(getByKeys(item, ['values', 'data'])).map(toOptionalNumber)
      if (!values.length || values.some((value) => value === undefined)) {
        return null
      }
      return {
        name: toStringSafe(getByKeys(item, ['name', 'label']), 'Capability'),
        values: values.filter((value): value is number => value !== undefined)
      }
    })
    .filter((item): item is RadarSeries => item !== null)

  const dimensions = asArray(getByKeys(payload, ['dimensions']))
    .map((item) => {
      if (!isRecord(item)) {
        return null
      }
      const name = toStringSafe(getByKeys(item, ['name', 'label']), '')
      const candidate = toOptionalNumber(getByKeys(item, ['student_score', 'studentScore', 'score']))
      const target = toOptionalNumber(getByKeys(item, ['job_required', 'jobRequired', 'required']))
      if (!name || candidate === undefined || target === undefined) {
        return null
      }
      return {
        name,
        candidate,
        target
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

  const matchScore = toOptionalNumber(
    getByKeys(payload, ['match_score', 'matchScore', 'score', 'overall_score', 'match'])
  )
  if (matchScore === undefined) {
    throw new Error('匹配分析接口未返回有效总分')
  }

  const normalizedIndicators = radarIndicators.length > 0 ? radarIndicators : derivedIndicators
  const normalizedSeries = radarSeries.length > 0 ? radarSeries : derivedSeries
  const hasCompleteRadar =
    normalizedIndicators.length > 0 &&
    normalizedSeries.length > 0 &&
    normalizedSeries.every((series) => series.values.length === normalizedIndicators.length)

  return {
    matchScore,
    radarIndicators: hasCompleteRadar ? normalizedIndicators : [],
    radarSeries: hasCompleteRadar ? normalizedSeries : [],
    strengths,
    gaps: normalizedGaps,
    gapDetails: normalizedGapDetails,
    historyId: toOptionalNumber(getByKeys(payload, ['history_id', 'historyId'])) ?? null,
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
    const centerId = toDisplayText(getByKeys(center, ['id', 'job_id']))
    const centerLabel = toStringSafe(getByKeys(center, ['name', 'label', 'title']), '').trim()

    const centerNode: PathGraphNode = {
      id: centerId,
      label: centerLabel,
      x: 80,
      y: 280,
      type: 'target',
      relation: toStringSafe(getByKeys(center, ['relation']), ''),
      relationStrength: toOptionalNumber(getByKeys(center, ['relation_strength', 'relationStrength', 'strength', 'score'])),
      jobDescription: toStringSafe(getByKeys(center, ['job_description', 'description', 'desc']), ''),
      coreSkills: toStringArray(getByKeys(center, ['core_skills', 'required_skills', 'skills'])),
      salaryRange: toStringSafe(getByKeys(center, ['salary_range', 'salaryRange']), '')
    }

    const verticalNodes = verticalRaw
      .filter(isRecord)
      .map((item, index) => ({
        id: toDisplayText(getByKeys(item, ['id', 'job_id'])),
        label: toStringSafe(getByKeys(item, ['name', 'label', 'title']), '').trim(),
        x: 80,
        y: 80 + index * 100,
        type: 'vertical' as const,
        relation: toStringSafe(getByKeys(item, ['relation']), ''),
        relationStrength: toOptionalNumber(getByKeys(item, ['relation_strength', 'relationStrength', 'strength', 'score'])),
        jobDescription: toStringSafe(getByKeys(item, ['job_description', 'description', 'desc']), ''),
        coreSkills: toStringArray(getByKeys(item, ['core_skills', 'required_skills', 'skills'])),
        salaryRange: toStringSafe(getByKeys(item, ['salary_range', 'salaryRange']), '')
      }))

    const lateralNodes = lateralRaw
      .filter(isRecord)
      .map((item, index) => ({
        id: toDisplayText(getByKeys(item, ['id', 'job_id'])),
        label: toStringSafe(getByKeys(item, ['name', 'label', 'title']), '').trim(),
        x: 320,
        y: 180 + index * 100,
        type: 'horizontal' as const,
        relation: toStringSafe(getByKeys(item, ['relation']), ''),
        relationStrength: toOptionalNumber(getByKeys(item, ['relation_strength', 'relationStrength', 'strength', 'score'])),
        jobDescription: toStringSafe(getByKeys(item, ['job_description', 'description', 'desc']), ''),
        coreSkills: toStringArray(getByKeys(item, ['core_skills', 'required_skills', 'skills'])),
        salaryRange: toStringSafe(getByKeys(item, ['salary_range', 'salaryRange']), '')
      }))

    const relationEdges = pickRecordList(record, ['relations']).map((edge) => ({
      source: toStringSafe(getByKeys(edge, ['source', 'from', 'start']), ''),
      target: toStringSafe(getByKeys(edge, ['target', 'to', 'end']), ''),
      label: toStringSafe(getByKeys(edge, ['label', 'name', 'relation']), '') || undefined,
      type: toStringSafe(getByKeys(edge, ['type']), '') as PathGraphEdge['type'],
      weight: toOptionalNumber(getByKeys(edge, ['weight', 'strength', 'relation_strength', 'score']))
    }))

    const allNodes = [centerNode, ...verticalNodes, ...lateralNodes]
    const edges = relationEdges.filter((item) => item.source && item.target)

    return {
      nodes: allNodes.filter((item) => item.id && item.label),
      edges
    }
  }

  const nodeCandidates = pickRecordList(record, ['nodes', 'vertexes', 'vertices', 'data', 'positions', 'jobs'])
  const edgeCandidates = pickRecordList(record, ['edges', 'links', 'relations', 'connections', 'paths'])

  const nodes = nodeCandidates.map((node) => ({
    id: toDisplayText(getByKeys(node, ['id', 'node_id'])),
    label: toStringSafe(getByKeys(node, ['label', 'name', 'title']), '').trim(),
    x: toOptionalNumber(getByKeys(node, ['x', 'posX'])),
    y: toOptionalNumber(getByKeys(node, ['y', 'posY'])),
    type: toStringSafe(getByKeys(node, ['type']), '') as PathGraphNode['type'],
    relation: toStringSafe(getByKeys(node, ['relation']), ''),
    relationStrength: toOptionalNumber(getByKeys(node, ['relation_strength', 'relationStrength', 'strength', 'score'])),
    jobDescription: toStringSafe(getByKeys(node, ['job_description', 'description', 'desc']), ''),
    coreSkills: toStringArray(getByKeys(node, ['core_skills', 'required_skills', 'skills'])),
    salaryRange: toStringSafe(getByKeys(node, ['salary_range', 'salaryRange']), '')
  }))

  const edges = edgeCandidates.map((edge) => ({
    source: toStringSafe(getByKeys(edge, ['source', 'from', 'start', 'from_id', 'source_id']), ''),
    target: toStringSafe(getByKeys(edge, ['target', 'to', 'end', 'to_id', 'target_id']), ''),
    label: toStringSafe(getByKeys(edge, ['label', 'name']), '') || undefined,
    type: toStringSafe(getByKeys(edge, ['type']), '') as PathGraphEdge['type'],
    weight: toOptionalNumber(getByKeys(edge, ['weight', 'strength', 'relation_strength', 'score']))
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
  const reportId = toDisplayText(getByKeys(record, ['history_id', 'historyId', 'report_id', 'reportId', 'id']))
  const rawTitle = toStringSafe(
    getByKeys(record, ['title', 'report_title', 'job_title', 'job_name']),
    ''
  ).trim()
  const title = rawTitle && !/匹配(报告|记录)$/.test(rawTitle) ? `${rawTitle} 匹配报告` : rawTitle
  const createdAt = toStringSafe(getByKeys(record, ['created_at', 'createdAt', 'date']), '').trim()
  const score = toOptionalNumber(getByKeys(record, ['score', 'overall_score', 'match_score', 'matchScore'])) ?? null
  const tags = asArray(getByKeys(record, ['tags', 'labels'])).map((item) => toStringSafe(item)).filter(Boolean)

  // 后端返回空对象/占位对象时，不生成默认假报告，避免登录后重复出现 "Career Report"。
  if (!reportId || !title || !createdAt) {
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

const buildGrowthFromReports = (reports: ReportItem[]): GrowthPoint[] => {
  return reports
    .filter((report): report is ReportItem & { score: number } => report.score !== null)
    .map((report) => ({
      date: report.createdAt,
      value: report.score,
      label: report.title
    }))
    .sort((a, b) => a.date.localeCompare(b.date))
}

const normalizeHistorySnapshot = (source: unknown): ReportItem => {
  const record = isRecord(source) ? source : {}
  const jobProfileValue = getByKeys(record, ['job_profile', 'jobProfile'])
  const jobProfile = isRecord(jobProfileValue) ? jobProfileValue : {}
  const historyId = toDisplayText(getByKeys(record, ['history_id', 'historyId', 'id']))
  const jobTitle = toStringSafe(getByKeys(jobProfile, ['title', 'job_title', 'name']), '').trim()
  const createdAt = toStringSafe(getByKeys(record, ['created_at', 'createdAt']), '').trim()
  const score = toOptionalNumber(getByKeys(record, ['overall_score', 'match_score', 'matchScore'])) ?? null

  if (!historyId || !jobTitle || !createdAt) {
    throw new Error('历史快照接口返回结构不完整')
  }

  return {
    id: historyId,
    title: `${jobTitle} 匹配报告`,
    createdAt: createdAt.slice(0, 10),
    score,
    tags: [],
    content: extractContent(getByKeys(record, ['report']))
  }
}

export const fetchJobs = async (params: FetchJobsParams): Promise<JobItem[]> => {
  const query = {
    keyword: params.keyword,
    page: params.page ?? 1,
    size: params.size ?? 20
  }

  const response = await request<unknown>({
    url: '/jobs',
    method: 'GET',
    params: query
  })

  const items = pickRecordList(response, ['jobs'])
  if (items.length > 0) {
    return items.map(normalizeJob).filter((job) => job.id > 0)
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

  return normalizeStudentUploadResponse(response)
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

  return normalizeStudentUploadResponse(response, payload)
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
    const polished = toStringSafe(getByKeys(response, ['polished_text', 'polishedText']), '').trim()
    if (polished) {
      return polished
    }
  }
  throw new Error('报告润色接口未返回 polished_text')
}

export const exportReport = async (reportId: number, format: 'pdf' | 'word' = 'pdf'): Promise<Blob> => {
  return request<Blob>({
    url: `/reports/${reportId}/export`,
    method: 'GET',
    params: { format: format === 'word' ? 'docx' : 'pdf' },
    responseType: 'blob'
  })
}

export const fetchUserHistories = async (userId: string): Promise<UserHistoriesResult> => {
  const response = await request<unknown>({
    url: `/users/${userId}/histories`,
    method: 'GET'
  })

  const reports = pickRecordList(response, ['reports', 'histories', 'items', 'list'])
    .map(normalizeReport)
    .filter((item): item is ReportItem => item !== null)
  const growth = buildGrowthFromReports(reports)

  return { reports, growth }
}

export const fetchHistorySnapshot = async (historyId: number): Promise<ReportItem> => {
  const response = await request<unknown>({
    url: `/histories/${historyId}/snapshot`,
    method: 'GET'
  })
  return normalizeHistorySnapshot(response)
}

const normalizeLearningResource = (value: unknown): LearningResource | null => {
  if (typeof value === 'string') {
    const title = value.trim()
    return title ? { title, type: '' } : null
  }
  if (!isRecord(value)) {
    return null
  }

  const title = toStringSafe(getByKeys(value, ['title', 'name', 'item']), '').trim()
  if (!title) {
    return null
  }

  return {
    title,
    type: toStringSafe(getByKeys(value, ['type', 'resource_type', 'resourceType']), '').trim(),
    targetAbility:
      toStringSafe(getByKeys(value, ['target_ability', 'targetAbility', 'ability', 'skill']), '').trim() || undefined,
    reason:
      toStringSafe(
        getByKeys(value, ['recommendation_reason', 'recommendationReason', 'reason', 'suggestion', 'desc', 'description']),
        ''
      ).trim() || undefined,
    url: toStringSafe(getByKeys(value, ['url', 'link']), '').trim() || undefined,
    source: toStringSafe(getByKeys(value, ['source', 'provider', 'platform']), '').trim() || undefined
  }
}

export const fetchRecommendations = async (gap = ''): Promise<LearningResource[]> => {
  const response = await request<unknown>({
    url: '/recommendations',
    method: 'GET',
    params: { gap }
  })

  if (Array.isArray(response)) {
    return response
      .map(normalizeLearningResource)
      .filter((item): item is LearningResource => item !== null)
  }

  if (isRecord(response)) {
    return asArray(getByKeys(response, ['recommendations', 'items', 'tips']))
      .map(normalizeLearningResource)
      .filter((item): item is LearningResource => item !== null)
  }

  return []
}
