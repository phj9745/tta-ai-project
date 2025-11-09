import {
  DEFECT_REPORT_COLUMNS,
  DEFECT_REPORT_START_ROW,
  type DefectReportTableRow,
  type FinalizedDefectRow,
} from './types'

export const DEFECT_COLUMN_TO_FIELD: Record<string, string> = {
  순번: 'order',
  '시험환경(OS)': 'environment',
  결함요약: 'summary',
  결함정도: 'severity',
  발생빈도: 'frequency',
  품질특성: 'quality',
  '결함 설명': 'description',
  '업체 응답': 'vendorResponse',
  수정여부: 'fixStatus',
  비고: 'note',
}

const FINALIZE_FIELD_TO_COLUMN: Record<string, string> = {
  order: '순번',
  environment: '시험환경(OS)',
  summary: '결함요약',
  severity: '결함정도',
  frequency: '발생빈도',
  quality: '품질특성',
  description: '결함 설명',
  vendorResponse: '업체 응답',
  fixStatus: '수정여부',
  note: '비고',
}

function normalizeKey(key: unknown): string {
  return typeof key === 'string' ? key.replace(/\s+|[()]/g, '').toLowerCase() : ''
}

function toCellText(value: unknown): string {
  if (value == null) {
    return ''
  }
  return typeof value === 'string' ? value : String(value)
}

export function sanitizeFileName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}

export function buildAttachmentFileName(index: number, original: string): string {
  const safeOriginal = sanitizeFileName(original)
  const padded = index.toString().padStart(2, '0')
  return `defect-${padded}-${safeOriginal}`
}

export function createFileKey(file: File): string {
  return `${file.name}-${file.size}-${file.lastModified}`
}

function normalizeRowArray(row: unknown): string[] | null {
  if (Array.isArray(row)) {
    return row.map((value) => toCellText(value).trim())
  }

  if (typeof row === 'string') {
    const trimmed = row.trim()
    if (!trimmed) {
      return []
    }
    return trimmed.split('|').map((value) => value.trim())
  }

  return null
}

export function buildRowsFromJsonTable(
  headersInput: unknown,
  rowsInput: unknown,
): DefectReportTableRow[] {
  const headerValues = Array.isArray(headersInput)
    ? headersInput
        .map((value) => (typeof value === 'string' ? value.trim() : ''))
        .filter((value) => value.length > 0)
    : DEFECT_REPORT_COLUMNS.map((column) => column.key)

  const headerIndex = new Map<string, number>()
  headerValues.forEach((header, index) => {
    if (!headerIndex.has(header)) {
      headerIndex.set(header, index)
    }
  })

  const rowsArray: unknown[] = Array.isArray(rowsInput)
    ? rowsInput
    : typeof rowsInput === 'string'
      ? rowsInput
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter((line) => line.length > 0)
      : []
  const tableRows: DefectReportTableRow[] = []

  rowsArray.forEach((rawRow) => {
    const rowCells: Record<string, string> = {}
    const rowObject = rawRow && typeof rawRow === 'object' && !Array.isArray(rawRow) ? rawRow : null
    const rowArray = normalizeRowArray(rawRow)
    const normalizedObjectValues = new Map<string, string>()

    if (rowObject) {
      Object.entries(rowObject as Record<string, unknown>).forEach(([key, value]) => {
        const normalized = normalizeKey(key)
        if (normalized && !normalizedObjectValues.has(normalized)) {
          normalizedObjectValues.set(normalized, toCellText(value))
        }
      })
    }

    DEFECT_REPORT_COLUMNS.forEach((column) => {
      const headerKey = column.key
      let value = ''

      if (rowObject) {
        if (headerKey in (rowObject as Record<string, unknown>)) {
          value = toCellText((rowObject as Record<string, unknown>)[headerKey])
        } else {
          const fieldKey = DEFECT_COLUMN_TO_FIELD[headerKey]
          if (fieldKey && fieldKey in (rowObject as Record<string, unknown>)) {
            value = toCellText((rowObject as Record<string, unknown>)[fieldKey])
          } else {
            const normalized = normalizeKey(headerKey)
            const normalizedValue = normalizedObjectValues.get(normalized)
            if (normalizedValue !== undefined) {
              value = normalizedValue
            }
          }
        }
      }

      if (!value && rowArray) {
        const index = headerIndex.get(headerKey)
        if (index !== undefined && index < rowArray.length) {
          value = rowArray[index]
        }
      }

      if (!value && rowObject) {
        const fieldKey = DEFECT_COLUMN_TO_FIELD[headerKey]
        if (fieldKey) {
          const normalizedField = normalizeKey(fieldKey)
          const normalizedValue = normalizedObjectValues.get(normalizedField)
          if (normalizedValue !== undefined) {
            value = normalizedValue
          }
        }
      }

      rowCells[headerKey] = value
    })

    const hasValue = Object.values(rowCells).some((cell) => cell.trim().length > 0)
    if (hasValue) {
      tableRows.push({
        rowNumber: DEFECT_REPORT_START_ROW + tableRows.length,
        cells: rowCells,
      })
    }
  })

  return tableRows
}

function normalizeFinalizeValue(value: unknown): string {
  if (typeof value === 'string') {
    return value.trim()
  }
  if (value == null) {
    return ''
  }
  return String(value).trim()
}

export function buildFinalizeRowPayload(row: FinalizedDefectRow): Record<string, string> {
  const payload: Record<string, string> = {}
  Object.entries(FINALIZE_FIELD_TO_COLUMN).forEach(([field, column]) => {
    payload[field] = normalizeFinalizeValue(row.cells[column])
  })

  if (!payload.order) {
    payload.order = normalizeFinalizeValue(row.cells['순번']) || String(row.index)
  }

  return payload
}

