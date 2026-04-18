import type { FetchJobsParams, JobItem } from '../api/modules/career'

const normalizeText = (value: string): string => value.trim().toLowerCase().replace(/\s+/g, '')

const normalizeJobName = (name: string): string =>
  normalizeText(name).replace(/[（(].*?[)）]/g, '')

const canonicalRoleName = (name: string): string => {
  const normalized = normalizeJobName(name)
  if (!normalized) {
    return ''
  }

  if (/(产品|product|pm)/i.test(normalized)) {
    return '产品经理'
  }
  if (/(测试|qa|test)/i.test(normalized)) {
    return '测试工程师'
  }
  if (/(java|后端|backend|服务端)/i.test(normalized)) {
    return '后端开发工程师'
  }
  if (/(前端|frontend|web|h5|vue|react)/i.test(normalized)) {
    return '前端开发工程师'
  }
  if (/(运维|devops|sre)/i.test(normalized)) {
    return '运维工程师'
  }
  if (/(数据|data|算法|ai|机器学习|ml)/i.test(normalized)) {
    return '数据/算法工程师'
  }
  if (/(全栈|fullstack)/i.test(normalized)) {
    return '全栈开发工程师'
  }
  return name.trim()
}

const buildKeywordQueue = (keyword: string): string[] => {
  const base = keyword.trim() || '产品经理'
  const normalized = normalizeText(base)
  const queue = new Set<string>([base])

  if (/(产品|product|pm)/i.test(normalized)) {
    ;['产品经理', '产品专员', '产品运营', '项目经理', '用户研究'].forEach((item) => queue.add(item))
  }
  if (/(测试|qa|test)/i.test(normalized)) {
    ;['测试工程师', '测试开发工程师', '自动化测试工程师', '质量工程师'].forEach((item) => queue.add(item))
  }
  if (/(java|后端|backend|服务端)/i.test(normalized)) {
    ;['Java开发工程师', '后端开发工程师', '全栈开发工程师', '运维开发工程师'].forEach((item) => queue.add(item))
  }
  if (/(前端|frontend|web|h5|vue|react)/i.test(normalized)) {
    ;['前端开发工程师', 'Web前端工程师', '全栈开发工程师', '客户端开发工程师', '小程序开发工程师'].forEach((item) => queue.add(item))
  }
  if (/(运维|devops|sre)/i.test(normalized)) {
    ;['运维工程师', 'DevOps工程师', 'SRE工程师'].forEach((item) => queue.add(item))
  }

  return [...queue]
}

const buildRelevanceTokens = (keyword: string): string[] => {
  const source = keyword.trim()
  if (!source) {
    return []
  }

  const tokens = new Set<string>([normalizeText(source)])
  if (/产品/.test(source)) {
    ;['产品', '产品经理', '产品专员', 'pm', 'product'].forEach((item) => tokens.add(normalizeText(item)))
  }
  if (/测试/.test(source) || /qa|test/i.test(source)) {
    ;['测试', 'qa', 'test', '测试工程师', '软件测试'].forEach((item) => tokens.add(normalizeText(item)))
  }
  if (/java|后端/i.test(source)) {
    ;['java', '后端', 'backend'].forEach((item) => tokens.add(normalizeText(item)))
  }
  if (/前端/i.test(source)) {
    ;['前端', 'frontend', 'web', 'react', 'vue'].forEach((item) => tokens.add(normalizeText(item)))
  }

  return [...tokens].filter(Boolean)
}

const isRelevantJob = (job: JobItem, keyword: string): boolean => {
  const tokens = buildRelevanceTokens(keyword)
  if (tokens.length === 0) {
    return true
  }
  const haystack = normalizeText(`${job.name} ${job.industry} ${job.company}`)
  return tokens.some((token) => token && haystack.includes(token))
}

export const pickDiverseTopJobs = async (
  keyword: string,
  fetcher: (params: FetchJobsParams) => Promise<JobItem[]>,
  topN = 10
): Promise<JobItem[]> => {
  const queue = buildKeywordQueue(keyword)
  const mergedRelevant: JobItem[] = []
  const mergedAll: JobItem[] = []
  const seenId = new Set<number>()

  for (const q of queue) {
    const jobs = await fetcher({ keyword: q, page: 1, size: 40 })
    const sorted = [...jobs].sort((a, b) => b.match - a.match)

    sorted.forEach((job) => {
      if (job.id <= 0 || seenId.has(job.id)) {
        return
      }
      seenId.add(job.id)
      mergedAll.push(job)
      if (isRelevantJob(job, keyword)) {
        mergedRelevant.push(job)
      }
    })

    if (mergedRelevant.length >= 50) {
      break
    }
  }

  const source = mergedRelevant.length > 0 ? mergedRelevant : mergedAll
  const targetCanonical = canonicalRoleName(keyword)
  const targetCanonicalKey = normalizeText(targetCanonical)

  // 优先返回与目标岗位同类（同 canonical）岗位，满足 TopN 后再回填相关岗位。
  const sameCategory = source.filter((job) => normalizeText(canonicalRoleName(job.name || '')) === targetCanonicalKey)
  const fallbackRelevant = source.filter((job) => normalizeText(canonicalRoleName(job.name || '')) !== targetCanonicalKey)

  return [...sameCategory, ...fallbackRelevant]
    .sort((a, b) => b.match - a.match)
    .slice(0, topN)
}
