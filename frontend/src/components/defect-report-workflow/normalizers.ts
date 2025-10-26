import type { DefectReportTableRow } from './types'

const SEVERITY_CODES = new Set(['H', 'M', 'L'])
const FREQUENCY_CODES = new Set(['A', 'R'])

const QUALITY_LABEL_MAP: Record<string, string> = {
  기능성: '기능성',
  기능적합성: '기능적합성',
  기능: '기능성',
  기능품질: '기능성',
  성능효율성: '성능효율성',
  성능효율: '성능효율성',
  성능: '성능효율성',
  호환성: '호환성',
  사용성: '사용성',
  신뢰성: '신뢰성',
  보안성: '보안성',
  유지보수성: '유지보수성',
  유지관리성: '유지보수성',
  이식성: '이식성',
  일반적요구사항: '일반적 요구사항',
  일반적요구: '일반적 요구사항',
  일반적 요구사항: '일반적 요구사항',
}

const QUALITY_KEYS = new Set(Object.keys(QUALITY_LABEL_MAP))

const SENTENCE_PUNCTUATION = /[.!?]|[\.\?!]$|[\.\?!]/

function normalizeWhitespace(value: string): string {
  return value.replace(/\s+/g, '')
}

function detectSeverity(raw: string): 'H' | 'M' | 'L' | null {
  const trimmed = raw.trim()
  if (!trimmed) {
    return null
  }

  const upper = trimmed.toUpperCase()
  if (SEVERITY_CODES.has(upper)) {
    return upper as 'H' | 'M' | 'L'
  }

  const normalized = normalizeWhitespace(trimmed).toLowerCase()
  if (
    upper.includes('HIGH') ||
    upper.includes('CRITICAL') ||
    normalized.includes('치명') ||
    normalized.includes('중대') ||
    normalized.includes('심각') ||
    normalized.includes('높음')
  ) {
    return 'H'
  }

  if (
    upper.includes('MEDIUM') ||
    normalized.includes('중간') ||
    normalized.includes('보통') ||
    normalized.includes('보통수준') ||
    normalized.includes('보통급')
  ) {
    return 'M'
  }

  if (
    upper.includes('LOW') ||
    normalized.includes('경미') ||
    normalized.includes('경미함') ||
    normalized.includes('낮음') ||
    normalized.includes('미미') ||
    normalized.includes('사소') ||
    normalized.includes('경한')
  ) {
    return 'L'
  }

  return null
}

function detectFrequency(raw: string): 'A' | 'R' | null {
  const trimmed = raw.trim()
  if (!trimmed) {
    return null
  }

  const upper = trimmed.toUpperCase()
  if (FREQUENCY_CODES.has(upper)) {
    return upper as 'A' | 'R'
  }

  const normalized = normalizeWhitespace(trimmed).toLowerCase()
  if (
    upper.includes('ALWAYS') ||
    normalized.includes('항상') ||
    normalized.includes('항시') ||
    normalized.includes('상시') ||
    normalized.includes('지속') ||
    normalized.includes('매번') ||
    normalized.includes('항구')
  ) {
    return 'A'
  }

  if (
    upper.includes('INTERMITTENT') ||
    upper.includes('SOMETIMES') ||
    upper.includes('OCCASIONAL') ||
    upper.includes('RARE') ||
    normalized.includes('간헐') ||
    normalized.includes('가끔') ||
    normalized.includes('드물') ||
    normalized.includes('재현') ||
    normalized.includes('비정기') ||
    normalized.includes('때때로') ||
    normalized.includes('조건부')
  ) {
    return 'R'
  }

  return null
}

function detectQuality(raw: string): string | null {
  const trimmed = raw.trim()
  if (!trimmed) {
    return null
  }

  const normalized = normalizeWhitespace(trimmed)
  if (QUALITY_KEYS.has(normalized)) {
    return QUALITY_LABEL_MAP[normalized]
  }

  const lower = normalized.toLowerCase()
  if (QUALITY_KEYS.has(lower)) {
    return QUALITY_LABEL_MAP[lower]
  }

  return null
}

function isLikelyDescription(value: string): boolean {
  const trimmed = value.trim()
  if (!trimmed) {
    return false
  }

  if (trimmed.length >= 25) {
    return true
  }

  if (trimmed.length >= 12 && /\s/.test(trimmed)) {
    return true
  }

  if (SENTENCE_PUNCTUATION.test(trimmed)) {
    return true
  }

  if (/[,，]/.test(trimmed)) {
    return true
  }

  return false
}

export function normalizeDefectResultCells(
  cells: Record<string, string>,
): Record<string, string> {
  const normalized: Record<string, string> = { ...cells }

  const severitySources: Array<{ key: string; value: string }> = [
    { key: '결함정도', value: cells['결함정도'] ?? '' },
    { key: '발생빈도', value: cells['발생빈도'] ?? '' },
    { key: '품질특성', value: cells['품질특성'] ?? '' },
    { key: '결함 설명', value: cells['결함 설명'] ?? '' },
  ]

  let severity: 'H' | 'M' | 'L' | null = null
  let severitySource: string | null = null
  for (const candidate of severitySources) {
    const detected = detectSeverity(candidate.value)
    if (detected) {
      severity = detected
      severitySource = candidate.key
      break
    }
  }

  if (severity) {
    normalized['결함정도'] = severity
  } else if (cells['결함정도']) {
    normalized['결함정도'] = cells['결함정도'].trim()
  }

  const frequencySources: Array<{ key: string; value: string }> = severitySource
    ? severitySources.filter((candidate) => candidate.key !== severitySource)
    : severitySources

  let frequency: 'A' | 'R' | null = null
  let frequencySource: string | null = null
  for (const candidate of frequencySources) {
    const detected = detectFrequency(candidate.value)
    if (detected) {
      frequency = detected
      frequencySource = candidate.key
      break
    }
  }

  if (frequency) {
    normalized['발생빈도'] = frequency
  } else if (cells['발생빈도']) {
    normalized['발생빈도'] = cells['발생빈도'].trim()
  }

  const qualitySources: Array<{ key: string; value: string }> = []
  severitySources.forEach((candidate) => {
    if (candidate.key === severitySource || candidate.key === frequencySource) {
      return
    }
    qualitySources.push(candidate)
  })

  let quality: string | null = null
  let qualitySource: string | null = null
  for (const candidate of qualitySources) {
    const detected = detectQuality(candidate.value)
    if (detected) {
      quality = detected
      qualitySource = candidate.key
      break
    }
  }

  if (quality) {
    normalized['품질특성'] = quality
  } else if (cells['품질특성']) {
    normalized['품질특성'] = cells['품질특성'].trim()
  }

  const descriptionCandidates: Array<{ key: string; value: string }> = []
  severitySources.forEach((candidate) => {
    if (
      candidate.key === severitySource ||
      candidate.key === frequencySource ||
      candidate.key === qualitySource
    ) {
      return
    }
    descriptionCandidates.push(candidate)
  })

  let description = (cells['결함 설명'] ?? '').trim()
  if (!isLikelyDescription(description)) {
    for (const candidate of descriptionCandidates) {
      if (isLikelyDescription(candidate.value)) {
        description = candidate.value.trim()
        break
      }
    }
  }

  if (description) {
    normalized['결함 설명'] = description
  }

  return normalized
}

export function normalizeDefectRows(rows: DefectReportTableRow[]): DefectReportTableRow[] {
  return rows.map((row) => ({
    ...row,
    cells: normalizeDefectResultCells(row.cells),
  }))
}

