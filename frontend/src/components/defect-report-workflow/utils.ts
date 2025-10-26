import { DEFECT_REPORT_COLUMNS, DEFECT_REPORT_START_ROW, type DefectReportTableRow } from './types'

const DEFECT_COLUMN_TO_FIELD: Record<string, string> = {
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

  const rowsArray = Array.isArray(rowsInput) ? rowsInput : []
  const tableRows: DefectReportTableRow[] = []

  rowsArray.forEach((rawRow) => {
    const rowCells: Record<string, string> = {}
    const rowObject = rawRow && typeof rawRow === 'object' && !Array.isArray(rawRow) ? rawRow : null
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

      if (!value) {
        const index = headerIndex.get(headerKey)
        if (index !== undefined && Array.isArray(rawRow)) {
          value = toCellText(rawRow[index])
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

