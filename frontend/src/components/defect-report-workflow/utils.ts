import { DEFECT_REPORT_COLUMNS, DEFECT_REPORT_START_ROW, type DefectReportTableRow } from './types'

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

export function decodeBase64(value: string | null): string {
  if (!value) {
    return ''
  }

  try {
    if (typeof atob === 'function') {
      const binary = atob(value)
      const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0))
      return new TextDecoder().decode(bytes)
    }
  } catch (error) {
    console.error('Failed to decode base64 value', error)
  }

  return ''
}

export function parseCsv(text: string): string[][] {
  const rows: string[][] = []
  let currentField = ''
  let currentRow: string[] = []
  let inQuotes = false

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index]

    if (inQuotes) {
      if (char === '"') {
        if (index + 1 < text.length && text[index + 1] === '"') {
          currentField += '"'
          index += 1
        } else {
          inQuotes = false
        }
      } else {
        currentField += char
      }
      continue
    }

    if (char === '"') {
      inQuotes = true
      continue
    }

    if (char === ',') {
      currentRow.push(currentField)
      currentField = ''
      continue
    }

    if (char === '\n') {
      currentRow.push(currentField)
      if (currentRow.some((cell) => cell.trim().length > 0)) {
        rows.push(currentRow)
      }
      currentRow = []
      currentField = ''
      continue
    }

    if (char === '\r') {
      continue
    }

    currentField += char
  }

  if (currentField.length > 0 || currentRow.length > 0) {
    currentRow.push(currentField)
  }
  if (currentRow.length > 0 && currentRow.some((cell) => cell.trim().length > 0)) {
    rows.push(currentRow)
  }

  return rows
}

export function buildRowsFromCsv(csvText: string): DefectReportTableRow[] {
  const parsed = parseCsv(csvText)
  if (parsed.length === 0) {
    return []
  }

  const headerRow = parsed[0].map((cell) => cell.trim())
  const headerIndex = new Map<string, number>()
  headerRow.forEach((header, index) => {
    if (!headerIndex.has(header)) {
      headerIndex.set(header, index)
    }
  })

  const rows: DefectReportTableRow[] = []
  const dataRows = parsed.slice(1)

  dataRows.forEach((cells) => {
    const rowCells: Record<string, string> = {}
    let hasValue = false

    DEFECT_REPORT_COLUMNS.forEach((column) => {
      const columnIndex = headerIndex.get(column.key) ?? headerIndex.get(column.label)
      const value =
        columnIndex !== undefined && columnIndex < cells.length ? cells[columnIndex] ?? '' : ''
      rowCells[column.key] = value
      if (!hasValue && value.trim()) {
        hasValue = true
      }
    })

    if (hasValue) {
      const rowNumber = DEFECT_REPORT_START_ROW + rows.length
      rows.push({ rowNumber, cells: rowCells })
    }
  })

  return rows
}
