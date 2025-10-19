import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'

import { FileUploader } from './FileUploader'
import type { FileType } from './fileUploaderTypes'

interface DefectEntry {
  index: number
  originalText: string
  polishedText: string
}

interface DefectReportWorkflowProps {
  backendUrl: string
  projectId: string
}

type AsyncStatus = 'idle' | 'loading' | 'success' | 'error'

type AttachmentMap = Record<number, File[]>

type ConversationRole = 'user' | 'assistant'

interface ConversationMessage {
  role: ConversationRole
  text: string
}

interface DefectReportColumn {
  key: string
  label: string
}

interface DefectReportTableRow {
  rowNumber: number
  cells: Record<string, string>
}

const TXT_ONLY: FileType[] = ['txt']
const ATTACHMENT_ACCEPT = new Set(['image/jpeg', 'image/png'])

const DEFECT_REPORT_START_ROW = 6

const DEFECT_REPORT_COLUMNS: DefectReportColumn[] = [
  { key: '순번', label: '순번' },
  { key: '시험환경(OS)', label: '시험환경(OS)' },
  { key: '결함요약', label: '결함요약' },
  { key: '결함정도', label: '결함정도' },
  { key: '발생빈도', label: '발생빈도' },
  { key: '품질특성', label: '품질특성' },
  { key: '결함 설명', label: '결함 설명' },
  { key: '업체 응답', label: '업체 응답' },
  { key: '수정여부', label: '수정여부' },
  { key: '비고', label: '비고' },
]

function sanitizeFileName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}

function buildAttachmentFileName(index: number, original: string): string {
  const safeOriginal = sanitizeFileName(original)
  const padded = index.toString().padStart(2, '0')
  return `defect-${padded}-${safeOriginal}`
}

function createFileKey(file: File): string {
  return `${file.name}-${file.size}-${file.lastModified}`
}

function decodeBase64(value: string | null): string {
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

function parseCsv(text: string): string[][] {
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

function buildRowsFromCsv(csvText: string): DefectReportTableRow[] {
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
export function DefectReportWorkflow({ backendUrl, projectId }: DefectReportWorkflowProps) {
  const [sourceFiles, setSourceFiles] = useState<File[]>([])
  const [formalizeStatus, setFormalizeStatus] = useState<AsyncStatus>('idle')
  const [formalizeError, setFormalizeError] = useState<string | null>(null)
  const [defects, setDefects] = useState<DefectEntry[]>([])
  const [attachments, setAttachments] = useState<AttachmentMap>({})
  const [generateStatus, setGenerateStatus] = useState<AsyncStatus>('idle')
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [downloadName, setDownloadName] = useState<string | null>(null)
  const [tableRows, setTableRows] = useState<DefectReportTableRow[]>([])
  const [isTableDirty, setIsTableDirty] = useState(false)
  const [downloadStatus, setDownloadStatus] = useState<AsyncStatus>('idle')
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [selectedCell, setSelectedCell] = useState<{ rowIndex: number; columnKey: string } | null>(null)
  const [rewriteMessages, setRewriteMessages] = useState<ConversationMessage[]>([])
  const [rewriteStatus, setRewriteStatus] = useState<AsyncStatus>('idle')
  const [rewriteError, setRewriteError] = useState<string | null>(null)
  const [rewriteInput, setRewriteInput] = useState('')
  const previewSectionRef = useRef<HTMLElement | null>(null)
  const previousRowCountRef = useRef(0)

  useEffect(() => {
    return () => {
      if (downloadUrl) {
        URL.revokeObjectURL(downloadUrl)
      }
    }
  }, [downloadUrl])

  useEffect(() => {
    const previousCount = previousRowCountRef.current
    if (tableRows.length > 0 && previousCount === 0) {
      if (!selectedCell) {
        setSelectedCell({ rowIndex: 0, columnKey: DEFECT_REPORT_COLUMNS[0].key })
      }
      if (previewSectionRef.current) {
        previewSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }
    previousRowCountRef.current = tableRows.length
  }, [selectedCell, tableRows])

  const handleChangeSource = useCallback((files: File[]) => {
    setSourceFiles(files.slice(0, 1))
    setFormalizeStatus('idle')
    setFormalizeError(null)
  }, [])

  const handleFormalize = useCallback(async () => {
    if (sourceFiles.length === 0) {
      setFormalizeStatus('error')
      setFormalizeError('TXT 파일을 업로드해 주세요.')
      return
    }

    const formData = new FormData()
    formData.append('file', sourceFiles[0])

    setFormalizeStatus('loading')
    setFormalizeError(null)
    setGenerateStatus('idle')
    setGenerateError(null)
    setDownloadName(null)
    if (downloadUrl) {
      URL.revokeObjectURL(downloadUrl)
      setDownloadUrl(null)
    }
    setTableRows([])
    setIsTableDirty(false)
    setSelectedCell(null)

    try {
      const response = await fetch(
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/defect-report/formalize`,
        {
          method: 'POST',
          body: formData,
        },
      )

      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        const detail =
          payload && typeof payload.detail === 'string'
            ? payload.detail
            : '결함 문장을 정제하는 중 오류가 발생했습니다.'
        setFormalizeStatus('error')
        setFormalizeError(detail)
        return
      }

      const payload = (await response.json()) as {
        defects?: Array<{ index: number; originalText: string; polishedText: string }>
      }
      const items = Array.isArray(payload?.defects) ? payload.defects : []
      if (items.length === 0) {
        setFormalizeStatus('error')
        setFormalizeError('결함 문장을 찾을 수 없습니다. TXT 파일의 형식을 확인해 주세요.')
        return
      }

      const sorted = [...items]
        .filter((item) => typeof item.index === 'number' && typeof item.polishedText === 'string')
        .sort((a, b) => a.index - b.index)
        .map((item) => ({
          index: item.index,
          originalText: item.originalText ?? '',
          polishedText: item.polishedText,
        }))

      setDefects(sorted)
      setAttachments({})
      setFormalizeStatus('success')
    } catch (error) {
      console.error('Failed to formalize defects', error)
      setFormalizeStatus('error')
      setFormalizeError('결함 문장을 정제하는 중 예기치 않은 오류가 발생했습니다.')
    }
  }, [backendUrl, downloadUrl, projectId, sourceFiles])

  const handleUpdatePolished = useCallback((index: number, value: string) => {
    setDefects((prev) => prev.map((item) => (item.index === index ? { ...item, polishedText: value } : item)))
  }, [])

  const handleAddAttachments = useCallback((index: number, files: FileList | File[]) => {
    const list = Array.from(files)
    if (list.length === 0) {
      return
    }

    const filtered = list.filter((file) => {
      if (file.type && ATTACHMENT_ACCEPT.has(file.type.toLowerCase())) {
        return true
      }
      const ext = file.name.split('.').pop()?.toLowerCase()
      return ext === 'png' || ext === 'jpg' || ext === 'jpeg'
    })

    if (filtered.length === 0) {
      return
    }

    setAttachments((prev) => {
      const existing = prev[index] ?? []
      const existingKeys = new Set(existing.map(createFileKey))
      const next = [...existing]
      filtered.forEach((file) => {
        const key = createFileKey(file)
        if (!existingKeys.has(key)) {
          next.push(file)
          existingKeys.add(key)
        }
      })
      return { ...prev, [index]: next }
    })
  }, [])

  const handleRemoveAttachment = useCallback((index: number, target: File) => {
    setAttachments((prev) => {
      const existing = prev[index]
      if (!existing) {
        return prev
      }
      const next = existing.filter((file) => file !== target)
      const nextMap: AttachmentMap = { ...prev }
      if (next.length === 0) {
        delete nextMap[index]
      } else {
        nextMap[index] = next
      }
      return nextMap
    })
  }, [])
  const handleReset = useCallback(() => {
    setSourceFiles([])
    setFormalizeStatus('idle')
    setFormalizeError(null)
    setDefects([])
    setAttachments({})
    setGenerateStatus('idle')
    setGenerateError(null)
    setDownloadName(null)
    if (downloadUrl) {
      URL.revokeObjectURL(downloadUrl)
      setDownloadUrl(null)
    }
    setTableRows([])
    setIsTableDirty(false)
    setDownloadStatus('idle')
    setDownloadError(null)
    setSelectedCell(null)
    setRewriteMessages([])
    setRewriteStatus('idle')
    setRewriteError(null)
    setRewriteInput('')
  }, [downloadUrl])

  const canGenerate = defects.length > 0 && formalizeStatus === 'success'

  const applyCellUpdate = useCallback(
    (rowIndex: number, columnKey: string, value: string) => {
      setTableRows((prev) => {
        const target = prev[rowIndex]
        if (!target) {
          return prev
        }
        const next = [...prev]
        next[rowIndex] = {
          ...target,
          cells: {
            ...target.cells,
            [columnKey]: value,
          },
        }
        return next
      })
      setIsTableDirty(true)
      setDownloadStatus('idle')
      setDownloadError(null)
      if (downloadUrl) {
        URL.revokeObjectURL(downloadUrl)
        setDownloadUrl(null)
      }
    },
    [downloadUrl],
  )

  const buildRowsPayload = useCallback(() => {
    return tableRows.map((row) => {
      const entry: Record<string, string> = {}
      DEFECT_REPORT_COLUMNS.forEach((column) => {
        entry[column.key] = row.cells[column.key] ?? ''
      })
      return entry
    })
  }, [tableRows])

  const handleGenerate = useCallback(async () => {
    if (!canGenerate) {
      setGenerateStatus('error')
      setGenerateError('먼저 결함 문장을 정제해 주세요.')
      return
    }

    setGenerateStatus('loading')
    setGenerateError(null)
    if (downloadUrl) {
      URL.revokeObjectURL(downloadUrl)
      setDownloadUrl(null)
    }

    setTableRows([])
    setIsTableDirty(false)
    setSelectedCell(null)
    setDownloadStatus('idle')
    setDownloadError(null)

    const summary = {
      defects: defects.map((item) => ({
        index: item.index,
        originalText: item.originalText,
        polishedText: item.polishedText,
        attachments: (attachments[item.index] ?? []).map((file) => ({
          fileName: buildAttachmentFileName(item.index, file.name),
          originalFileName: file.name,
        })),
      })),
    }

    const formData = new FormData()
    formData.append('menu_id', 'defect-report')

    const summaryFile = new File([JSON.stringify(summary, null, 2)], '정제된-결함-목록.json', {
      type: 'application/json',
    })
    const metadataEntries: Array<Record<string, unknown>> = [
      {
        role: 'additional',
        description: '정제된 결함 목록',
        label: '정제된 결함 목록',
        notes: '결함 문장 정제 결과(JSON)',
      },
    ]
    formData.append('files', summaryFile)

    defects.forEach((item) => {
      const files = attachments[item.index] ?? []
      files.forEach((file) => {
        const normalizedName = buildAttachmentFileName(item.index, file.name)
        const renamed =
          file.name === normalizedName ? file : new File([file], normalizedName, { type: file.type })
        formData.append('files', renamed)
        metadataEntries.push({
          role: 'additional',
          description: `결함 ${item.index} 이미지`,
          label: `결함 ${item.index} 이미지`,
          notes: `원본 파일명: ${file.name}`,
          defect_index: item.index,
        })
      })
    })

    formData.append('file_metadata', JSON.stringify(metadataEntries))

    try {
      const response = await fetch(
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/generate`,
        {
          method: 'POST',
          body: formData,
        },
      )

      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        const detail =
          payload && typeof payload.detail === 'string'
            ? payload.detail
            : '결함 리포트를 생성하는 중 오류가 발생했습니다.'
        setGenerateStatus('error')
        setGenerateError(detail)
        return
      }

      const blob = await response.blob()
      const disposition = response.headers.get('content-disposition')
      let filename = 'defect-report.xlsx'
      if (disposition) {
        const match = disposition.match(/filename\*?=([^;]+)/i)
        if (match) {
          const value = match[1].replace(/^UTF-8''/i, '')
          try {
            filename = decodeURIComponent(value.replace(/"/g, ''))
          } catch {
            filename = value.replace(/"/g, '')
          }
        }
      }

      const encodedTable = decodeBase64(response.headers.get('x-defect-table'))
      if (encodedTable) {
        const rows = buildRowsFromCsv(encodedTable)
        setTableRows(rows)
        if (rows.length > 0) {
          setSelectedCell({ rowIndex: 0, columnKey: DEFECT_REPORT_COLUMNS[0].key })
        }
      }

      const objectUrl = URL.createObjectURL(blob)
      setDownloadUrl(objectUrl)
      setDownloadName(filename)
      setIsTableDirty(false)
      setDownloadStatus('success')
      setGenerateStatus('success')
    } catch (error) {
      console.error('Failed to generate defect report', error)
      setGenerateStatus('error')
      setGenerateError('결함 리포트를 생성하는 중 예기치 않은 오류가 발생했습니다.')
    }
  }, [attachments, backendUrl, canGenerate, defects, downloadUrl, projectId])
  const handleSelectCell = useCallback((rowIndex: number, columnKey: string) => {
    setSelectedCell({ rowIndex, columnKey })
    setRewriteMessages([])
    setRewriteStatus('idle')
    setRewriteError(null)
    setRewriteInput('')
  }, [])

  const handleRewriteInputChange = useCallback(
    (event: ChangeEvent<HTMLTextAreaElement>) => {
      setRewriteInput(event.target.value)
      if (rewriteStatus !== 'idle') {
        setRewriteStatus('idle')
      }
      if (rewriteError) {
        setRewriteError(null)
      }
    },
    [rewriteError, rewriteStatus],
  )

  const handleRewriteSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      if (!selectedCell) {
        return
      }

      const row = tableRows[selectedCell.rowIndex]
      const column = DEFECT_REPORT_COLUMNS.find((item) => item.key === selectedCell.columnKey)
      if (!row || !column) {
        return
      }

      const message = rewriteInput.trim()
      if (!message) {
        setRewriteError('변경하고 싶은 내용을 입력해 주세요.')
        setRewriteStatus('error')
        return
      }

      const originalValue = row.cells[column.key] ?? ''
      setRewriteMessages((prev) => [...prev, { role: 'user', text: message }])
      setRewriteStatus('loading')
      setRewriteError(null)
      setRewriteInput('')

      try {
        const response = await fetch(
          `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/defect-report/rewrite`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              columnKey: column.key,
              columnLabel: column.label,
              originalValue,
              instructions: message,
              rowValues: { ...row.cells },
            }),
          },
        )

        if (!response.ok) {
          const payload = await response.json().catch(() => null)
          const detail =
            payload && typeof payload.detail === 'string'
              ? payload.detail
              : 'GPT에게 수정 요청을 전달하는 중 오류가 발생했습니다.'
          throw new Error(detail)
        }

        const payload = (await response.json()) as { updatedText?: string }
        const updatedText = typeof payload?.updatedText === 'string' ? payload.updatedText : ''
        if (!updatedText.trim()) {
          throw new Error('GPT 응답에서 수정된 내용을 찾을 수 없습니다.')
        }

        setRewriteMessages((prev) => [...prev, { role: 'assistant', text: updatedText }])
        applyCellUpdate(selectedCell.rowIndex, column.key, updatedText)
        setRewriteStatus('success')
      } catch (error) {
        const messageText =
          error instanceof Error
            ? error.message
            : 'GPT 요청 중 예기치 않은 오류가 발생했습니다.'
        setRewriteError(messageText)
        setRewriteStatus('error')
      }
    },
    [applyCellUpdate, backendUrl, projectId, rewriteInput, selectedCell, tableRows],
  )

  const handleDownload = useCallback(async () => {
    if (downloadStatus === 'loading') {
      return
    }

    if (!tableRows.length) {
      setDownloadError('다운로드할 리포트가 없습니다.')
      setDownloadStatus('error')
      return
    }

    if (!isTableDirty && downloadUrl) {
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = downloadName ?? 'defect-report.xlsx'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      setDownloadStatus('success')
      return
    }

    setDownloadStatus('loading')
    setDownloadError(null)

    const formData = new FormData()
    formData.append('rows', JSON.stringify(buildRowsPayload()))

    const metadataEntries: Array<Record<string, unknown>> = []
    const attachmentFiles: File[] = []
    Object.entries(attachments).forEach(([indexKey, files]) => {
      const defectIndex = Number(indexKey)
      if (!Number.isFinite(defectIndex)) {
        return
      }
      files.forEach((file) => {
        const normalizedName = buildAttachmentFileName(defectIndex, file.name)
        const renamed =
          file.name === normalizedName ? file : new File([file], normalizedName, { type: file.type })
        attachmentFiles.push(renamed)
        metadataEntries.push({
          defect_index: defectIndex,
          originalFileName: file.name,
        })
      })
    })

    attachmentFiles.forEach((file) => {
      formData.append('attachments', file)
    })

    if (metadataEntries.length > 0) {
      formData.append('attachment_metadata', JSON.stringify(metadataEntries))
    }

    try {
      const response = await fetch(
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/defect-report/compile`,
        {
          method: 'POST',
          body: formData,
        },
      )

      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        const detail =
          payload && typeof payload.detail === 'string'
            ? payload.detail
            : '수정된 리포트를 생성하는 중 오류가 발생했습니다.'
        throw new Error(detail)
      }

      const blob = await response.blob()
      const disposition = response.headers.get('content-disposition')
      let filename = downloadName ?? 'defect-report-edited.xlsx'
      if (disposition) {
        const match = disposition.match(/filename\*?=([^;]+)/i)
        if (match) {
          const value = match[1].replace(/^UTF-8''/i, '')
          try {
            filename = decodeURIComponent(value.replace(/"/g, ''))
          } catch {
            filename = value.replace(/"/g, '')
          }
        }
      }

      const encodedTable = decodeBase64(response.headers.get('x-defect-table'))
      if (encodedTable) {
        const rows = buildRowsFromCsv(encodedTable)
        setTableRows(rows)
        if (!selectedCell && rows.length > 0) {
          setSelectedCell({ rowIndex: 0, columnKey: DEFECT_REPORT_COLUMNS[0].key })
        }
      }

      if (downloadUrl) {
        URL.revokeObjectURL(downloadUrl)
      }

      const objectUrl = URL.createObjectURL(blob)
      setDownloadUrl(objectUrl)
      setDownloadName(filename)
      setIsTableDirty(false)
      setDownloadStatus('success')

      const link = document.createElement('a')
      link.href = objectUrl
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } catch (error) {
      const messageText =
        error instanceof Error
          ? error.message
          : '수정된 리포트를 다운로드하는 중 예기치 않은 오류가 발생했습니다.'
      setDownloadError(messageText)
      setDownloadStatus('error')
    }
  }, [attachments, backendUrl, buildRowsPayload, downloadName, downloadStatus, downloadUrl, isTableDirty, projectId, selectedCell, tableRows])

  const selectedRowIndex = selectedCell?.rowIndex ?? -1
  const selectedRow = selectedRowIndex >= 0 ? tableRows[selectedRowIndex] : null
  const selectedColumn = selectedCell
    ? DEFECT_REPORT_COLUMNS.find((item) => item.key === selectedCell.columnKey)
    : null
  const selectedValue = selectedRow && selectedColumn ? selectedRow.cells[selectedColumn.key] ?? '' : ''

  return (
    <div className="defect-workflow">
      {formalizeStatus !== 'success' ? (
        <section className="defect-workflow__section" aria-labelledby="defect-upload">
          <h2 id="defect-upload" className="defect-workflow__title">
            1. 결함 메모 업로드
          </h2>
          <p className="defect-workflow__helper">숫자 목록(1. 2. …) 형태의 TXT 파일을 업로드한 뒤 결함 문장을 정제하세요.</p>
          <FileUploader
            allowedTypes={TXT_ONLY}
            files={sourceFiles}
            onChange={handleChangeSource}
            multiple={false}
            maxFiles={1}
            hideDropzoneWhenFilled={false}
          />
          <div className="defect-workflow__actions">
            <button
              type="button"
              className="defect-workflow__primary"
              onClick={handleFormalize}
              disabled={formalizeStatus === 'loading'}
            >
              {formalizeStatus === 'loading' ? '정제 중…' : '결함 문장 다듬기'}
            </button>
            {formalizeStatus === 'error' && formalizeError && (
              <p className="defect-workflow__status defect-workflow__status--error" role="alert">
                {formalizeError}
              </p>
            )}
          </div>
        </section>
      ) : (
        <section className="defect-workflow__section" aria-labelledby="defect-upload">
          <h2 id="defect-upload" className="defect-workflow__title">
            1. 결함 메모 업로드
          </h2>
          <p className="defect-workflow__status defect-workflow__status--success" role="status">
            결함 문장이 정제되었습니다. 아래 단계에서 검토를 계속하세요. 새 TXT 파일을 업로드하려면 초기화 버튼을 눌러주세요.
          </p>
        </section>
      )}
      {defects.length > 0 && (
        <section className="defect-workflow__section" aria-labelledby="defect-review">
          <h2 id="defect-review" className="defect-workflow__title">
            2. 결함 검토 및 증적 첨부
          </h2>
          <p className="defect-workflow__helper">필요 시 문장을 수정하고 결함별 증빙 이미지를 첨부한 뒤 리포트를 생성하세요.</p>
          <ol className="defect-workflow__list">
            {defects.map((item) => {
              const files = attachments[item.index] ?? []
              return (
                <li key={item.index} className="defect-workflow__item">
                  <header className="defect-workflow__item-header">
                    <span className="defect-workflow__badge">#{item.index}</span>
                    <span className="defect-workflow__label">원문</span>
                    <p className="defect-workflow__original">{item.originalText || '원문 정보 없음'}</p>
                  </header>
                  <label className="defect-workflow__label" htmlFor={`polished-${item.index}`}>
                    정제된 문장
                  </label>
                  <textarea
                    id={`polished-${item.index}`}
                    value={item.polishedText}
                    onChange={(event) => handleUpdatePolished(item.index, event.target.value)}
                  />
                  <div className="defect-workflow__attachments">
                    <div className="defect-workflow__attachment-header">
                      <span>증빙 이미지 (선택)</span>
                      <input
                        type="file"
                        accept="image/png,image/jpeg"
                        multiple
                        onChange={(event) => {
                          if (event.currentTarget.files) {
                            handleAddAttachments(item.index, event.currentTarget.files)
                            event.currentTarget.value = ''
                          }
                        }}
                      />
                    </div>
                    {files.length > 0 && (
                      <ul className="defect-workflow__attachment-list">
                        {files.map((file) => (
                          <li key={createFileKey(file)} className="defect-workflow__attachment-item">
                            <span>{file.name}</span>
                            <button
                              type="button"
                              onClick={() => handleRemoveAttachment(item.index, file)}
                              className="defect-workflow__remove"
                            >
                              제거
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </li>
              )
            })}
          </ol>
        </section>
      )}

      {tableRows.length > 0 && (
        <section
          className="defect-workflow__section"
          aria-labelledby="defect-preview"
          ref={previewSectionRef}
        >
          <h2 id="defect-preview" className="defect-workflow__title">
            3. 결함 리포트 미리보기 및 편집
          </h2>
          <p className="defect-workflow__helper">
            생성된 표를 확인하고 수정할 칸을 선택하세요. 오른쪽 패널에서 직접 편집하거나 GPT에게 수정 요청을 보낼 수 있습니다.
          </p>
          <div className="defect-workflow__preview">
            <div className="defect-workflow__table-wrapper" role="region" aria-live="polite">
              <table className="defect-workflow__table">
                <thead>
                  <tr>
                    {DEFECT_REPORT_COLUMNS.map((column) => (
                      <th key={column.key} scope="col">
                        {column.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map((row, rowIndex) => (
                    <tr key={row.rowNumber}>
                      {DEFECT_REPORT_COLUMNS.map((column) => {
                        const value = row.cells[column.key]
                        const isSelected =
                          selectedCell?.rowIndex === rowIndex && selectedCell.columnKey === column.key
                        return (
                          <td key={column.key}>
                            <button
                              type="button"
                              className={`defect-workflow__cell-button${
                                isSelected ? ' defect-workflow__cell-button--selected' : ''
                              }`}
                              onClick={() => handleSelectCell(rowIndex, column.key)}
                            >
                              {value ? (
                                <span>{value}</span>
                              ) : (
                                <span className="defect-workflow__cell-placeholder">내용 없음</span>
                              )}
                            </button>
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {selectedRow && selectedColumn ? (
              <aside className="defect-workflow__editor" aria-live="polite">
                <div className="defect-workflow__editor-header">
                  <h3 className="defect-workflow__editor-title">셀 편집</h3>
                  <p className="defect-workflow__editor-subtitle">
                    {selectedColumn.label} · #{selectedRow.cells['순번'] || selectedRow.rowNumber}
                  </p>
                </div>
                <label
                  className="defect-workflow__label"
                  htmlFor={`cell-editor-${selectedRow.rowNumber}-${selectedColumn.key}`}
                >
                  직접 수정
                </label>
                <textarea
                  id={`cell-editor-${selectedRow.rowNumber}-${selectedColumn.key}`}
                  value={selectedValue}
                  onChange={(event) => {
                    if (selectedRowIndex >= 0) {
                      applyCellUpdate(selectedRowIndex, selectedColumn.key, event.target.value)
                    }
                  }}
                />
                <div className="defect-workflow__chat">
                  <h4 className="defect-workflow__chat-title">GPT에게 수정 요청</h4>
                  <p className="defect-workflow__chat-helper">
                    바꾸고 싶은 방향을 입력하면 GPT 응답이 셀에 바로 반영됩니다.
                  </p>
                  <div className="defect-workflow__chat-log" role="log" aria-live="polite">
                    {rewriteMessages.length === 0 && (
                      <p className="defect-workflow__chat-helper">아직 대화가 없습니다.</p>
                    )}
                    {rewriteMessages.map((message, index) => (
                      <div
                        key={`${message.role}-${index}`}
                        className={`defect-workflow__chat-message defect-workflow__chat-message--${message.role}`}
                      >
                        <span>{message.role === 'user' ? '요청' : 'GPT 응답'}</span>
                        <p>{message.text}</p>
                      </div>
                    ))}
                  </div>
                  {rewriteError && (
                    <p className="defect-workflow__status defect-workflow__status--error" role="alert">
                      {rewriteError}
                    </p>
                  )}
                  {rewriteStatus === 'success' && !rewriteError && (
                    <p className="defect-workflow__status defect-workflow__status--success">
                      GPT 응답이 셀에 반영되었습니다.
                    </p>
                  )}
                  <form className="defect-workflow__chat-form" onSubmit={handleRewriteSubmit}>
                    <textarea
                      value={rewriteInput}
                      onChange={handleRewriteInputChange}
                      placeholder="예: 문장을 더 간결하고 정중하게 바꿔줘"
                    />
                    <button
                      type="submit"
                      className="defect-workflow__primary"
                      disabled={rewriteStatus === 'loading'}
                    >
                      {rewriteStatus === 'loading' ? '요청 중…' : 'GPT에게 수정 요청'}
                    </button>
                  </form>
                </div>
              </aside>
            ) : (
              <aside className="defect-workflow__editor defect-workflow__editor--empty">
                <p>편집할 셀을 선택하면 내용과 GPT 대화창이 표시됩니다.</p>
              </aside>
            )}
          </div>
        </section>
      )}

      <div className="defect-workflow__footer">
        <div className="defect-workflow__buttons">
          <button
            type="button"
            className="defect-workflow__primary"
            onClick={handleGenerate}
            disabled={!canGenerate || generateStatus === 'loading'}
          >
            {generateStatus === 'loading' ? '리포트 생성 중…' : '결함 리포트 생성'}
          </button>
          <button type="button" className="defect-workflow__secondary" onClick={handleReset}>
            초기화
          </button>
        </div>

        {generateStatus === 'error' && generateError && (
          <p className="defect-workflow__status defect-workflow__status--error" role="alert">
            {generateError}
          </p>
        )}

        {tableRows.length > 0 && (
          <div className="defect-workflow__result">
            <button
              type="button"
              className="defect-workflow__primary"
              onClick={handleDownload}
              disabled={downloadStatus === 'loading'}
            >
              {downloadStatus === 'loading' ? '다운로드 준비 중…' : '엑셀 다운로드'}
            </button>
            {isTableDirty && (
              <p className="defect-workflow__status defect-workflow__status--success">
                화면에서 수정한 내용이 반영된 새 파일을 생성합니다.
              </p>
            )}
            {downloadError && (
              <p className="defect-workflow__status defect-workflow__status--error" role="alert">
                {downloadError}
              </p>
            )}
            <p className="defect-workflow__helper defect-workflow__helper--small">
              생성된 리포트는 프로젝트 드라이브의 결함 리포트 템플릿에도 반영되었습니다.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
