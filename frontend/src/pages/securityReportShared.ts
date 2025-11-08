export interface SecurityRow {
  id: string
  order: string
  environment: string
  summary: string
  severity: string
  frequency: string
  quality: string
  description: string
  vendorResponse: string
  fixStatus: string
  note: string
  mappingType: string
}

export type SecurityRowKey = keyof Omit<SecurityRow, 'id'>

export interface SecurityColumn {
  key: SecurityRowKey
  label: string
  backendKey: string
  input: 'text' | 'textarea'
  readOnly?: boolean
  hidden?: boolean
}

export const SECURITY_COLUMNS: SecurityColumn[] = [
  { key: 'order', label: '순번', backendKey: '순번', input: 'text', readOnly: true, hidden: true },
  {
    key: 'environment',
    label: '시험환경(OS)',
    backendKey: '시험환경 OS',
    input: 'text',
    readOnly: true,
    hidden: true,
  },
  { key: 'summary', label: '결함요약', backendKey: '결함 요약', input: 'textarea' },
  { key: 'severity', label: '결함정도', backendKey: '결함 정도', input: 'text' },
  { key: 'frequency', label: '발생빈도', backendKey: '발생 빈도', input: 'text' },
  { key: 'quality', label: '품질특성', backendKey: '품질 특성', input: 'text', hidden: true },
  { key: 'description', label: '결함 설명', backendKey: '결함 설명', input: 'textarea' },
  {
    key: 'vendorResponse',
    label: '업체 응답',
    backendKey: '업체 응답',
    input: 'textarea',
    hidden: true,
  },
  { key: 'fixStatus', label: '수정여부', backendKey: '수정여부', input: 'text', hidden: true },
  { key: 'note', label: '비고', backendKey: '비고', input: 'textarea', hidden: true },
  {
    key: 'mappingType',
    label: '매핑 유형',
    backendKey: '매핑 유형',
    input: 'text',
    readOnly: true,
  },
]

export function normalizeSecurityPreviewRow(entry: unknown, index: number): SecurityRow | null {
  if (entry === null || typeof entry !== 'object') {
    return null
  }

  const record = entry as Record<string, unknown>

  const getString = (key: string, fallback: string = '') => {
    const value = record[key]
    if (value === undefined || value === null) {
      return fallback
    }
    return String(value)
  }

  const orderValue = getString('순번').trim()

  return {
    id: `security-row-${index + 1}`,
    order: orderValue || String(index + 1),
    environment: getString('시험환경 OS', '시험환경 모든 OS'),
    summary: getString('결함 요약'),
    severity: getString('결함 정도'),
    frequency: getString('발생 빈도'),
    quality: getString('품질 특성'),
    description: getString('결함 설명'),
    vendorResponse: getString('업체 응답'),
    fixStatus: getString('수정여부'),
    note: getString('비고', '보안성 시험 결과 참고'),
    mappingType: getString('매핑 유형'),
  }
}

export function buildSecurityPayloadRows(rows: SecurityRow[]): Array<Record<string, string>> {
  return rows.map((row) => {
    const payload: Record<string, string> = {}
    SECURITY_COLUMNS.forEach((column) => {
      payload[column.backendKey] = row[column.key] ?? ''
    })
    return payload
  })
}
