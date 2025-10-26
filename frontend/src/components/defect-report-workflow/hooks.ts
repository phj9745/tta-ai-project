import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  ATTACHMENT_ACCEPT,
  DEFECT_REPORT_COLUMNS,
  type AttachmentMap,
  type AsyncStatus,
  type ConversationMessage,
  type DefectEntry,
  type DefectReportTableRow,
  type SelectedCell,
} from './types'
import {
  buildAttachmentFileName,
  buildRowsFromCsv,
  createFileKey,
  decodeBase64,
} from './utils'
import { createPromptAttachmentFiles } from './promptResources'

type FormalizeOptions = {
  backendUrl: string
  projectId: string
}

export function useFormalizeDefects({ backendUrl, projectId }: FormalizeOptions) {
  const [featureFiles, setFeatureFiles] = useState<File[]>([])
  const [sourceFiles, setSourceFiles] = useState<File[]>([])
  const [status, setStatus] = useState<AsyncStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [defects, setDefects] = useState<DefectEntry[]>([])

  const changeFeature = useCallback((files: File[]) => {
    setFeatureFiles(files.slice(0, 1))
    setStatus('idle')
    setError(null)
  }, [])

  const changeSource = useCallback((files: File[]) => {
    setSourceFiles(files.slice(0, 1))
    setStatus('idle')
    setError(null)
  }, [])

  const updatePolished = useCallback((index: number, value: string) => {
    setDefects((prev) => prev.map((item) => (item.index === index ? { ...item, polishedText: value } : item)))
  }, [])

  const formalize = useCallback(async () => {
    if (featureFiles.length === 0 && sourceFiles.length === 0) {
      setStatus('error')
      setError('기능리스트 파일과 TXT 파일을 모두 업로드해 주세요.')
      return false
    }

    if (featureFiles.length === 0) {
      setStatus('error')
      setError('기능리스트 파일을 업로드해 주세요.')
      return false
    }

    if (sourceFiles.length === 0) {
      setStatus('error')
      setError('TXT 파일을 업로드해 주세요.')
      return false
    }

    const formData = new FormData()
    formData.append('featureList', featureFiles[0])
    formData.append('defectNotes', sourceFiles[0])

    setStatus('loading')
    setError(null)

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
        setStatus('error')
        setError(detail)
        return false
      }

      const payload = (await response.json()) as {
        defects?: Array<{ index: number; originalText: string; polishedText: string }>
      }
      const items = Array.isArray(payload?.defects) ? payload.defects : []

      if (items.length === 0) {
        setStatus('error')
        setError('결함 문장을 찾을 수 없습니다. TXT 파일의 형식을 확인해 주세요.')
        return false
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
      setStatus('success')
      return true
    } catch (error) {
      console.error('Failed to formalize defects', error)
      setStatus('error')
      setError('결함 문장을 정제하는 중 예기치 않은 오류가 발생했습니다.')
      return false
    }
  }, [backendUrl, projectId, featureFiles, sourceFiles])

  const reset = useCallback(() => {
    setFeatureFiles([])
    setSourceFiles([])
    setStatus('idle')
    setError(null)
    setDefects([])
  }, [])

  return {
    featureFiles,
    sourceFiles,
    defects,
    formalizeStatus: status,
    formalizeError: error,
    changeFeature,
    changeSource,
    formalize,
    updatePolished,
    reset,
  }
}

export function useDefectAttachments() {
  const [attachments, setAttachments] = useState<AttachmentMap>({})

  const addAttachments = useCallback((index: number, files: FileList | File[]) => {
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

  const removeAttachment = useCallback((index: number, target: File) => {
    setAttachments((prev) => {
      const existing = prev[index]
      if (!existing) {
        return prev
      }
      const next = existing.filter((file) => file !== target)
      if (next.length === 0) {
        const { [index]: _, ...rest } = prev
        return rest
      }
      return { ...prev, [index]: next }
    })
  }, [])

  const reset = useCallback(() => {
    setAttachments({})
  }, [])

  const hasAttachments = useMemo(() => Object.keys(attachments).length > 0, [attachments])

  return {
    attachments,
    addAttachments,
    removeAttachment,
    reset,
    hasAttachments,
  }
}

type DownloadOptions = {
  backendUrl: string
  projectId: string
}

export function useDefectDownload({ backendUrl, projectId }: DownloadOptions) {
  const [tableRows, setTableRows] = useState<DefectReportTableRow[]>([])
  const [isTableDirty, setIsTableDirty] = useState(false)
  const [generateStatus, setGenerateStatus] = useState<AsyncStatus>('idle')
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [downloadStatus, setDownloadStatus] = useState<AsyncStatus>('idle')
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [downloadName, setDownloadName] = useState<string | null>(null)
  const [selectedCell, setSelectedCell] = useState<SelectedCell | null>(null)
  const [rewriteMessages, setRewriteMessages] = useState<ConversationMessage[]>([])
  const [rewriteStatus, setRewriteStatus] = useState<AsyncStatus>('idle')
  const [rewriteError, setRewriteError] = useState<string | null>(null)
  const [rewriteInput, setRewriteInput] = useState('')

  useEffect(() => {
    return () => {
      if (downloadUrl) {
        URL.revokeObjectURL(downloadUrl)
      }
    }
  }, [downloadUrl])

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

  const selectCell = useCallback((rowIndex: number, columnKey: string) => {
    setSelectedCell({ rowIndex, columnKey })
    setRewriteMessages([])
    setRewriteStatus('idle')
    setRewriteError(null)
    setRewriteInput('')
  }, [])

  const updateRewriteInput = useCallback(
    (value: string) => {
      setRewriteInput(value)
      if (rewriteStatus !== 'idle') {
        setRewriteStatus('idle')
      }
      if (rewriteError) {
        setRewriteError(null)
      }
    },
    [rewriteError, rewriteStatus],
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

  const generateReport = useCallback(
    async (defects: DefectEntry[], attachments: AttachmentMap, canGenerate: boolean) => {
      if (!canGenerate) {
        setGenerateStatus('error')
        setGenerateError('먼저 결함 문장을 정제해 주세요.')
        return false
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
      setRewriteMessages([])
      setRewriteStatus('idle')
      setRewriteError(null)
      setRewriteInput('')

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

      createPromptAttachmentFiles([]).forEach((attachment) => {
        formData.append('files', attachment.file)
        metadataEntries.push(attachment.metadata)
      })

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
          return false
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

        if (downloadUrl) {
          URL.revokeObjectURL(downloadUrl)
        }

        const objectUrl = URL.createObjectURL(blob)
        setDownloadUrl(objectUrl)
        setDownloadName(filename)
        setIsTableDirty(false)
        setDownloadStatus('success')
        setGenerateStatus('success')
        return true
      } catch (error) {
        console.error('Failed to generate defect report', error)
        setGenerateStatus('error')
        setGenerateError('결함 리포트를 생성하는 중 예기치 않은 오류가 발생했습니다.')
        return false
      }
    },
    [backendUrl, downloadUrl, projectId],
  )

  const downloadReport = useCallback(
    async (attachments: AttachmentMap) => {
      if (downloadStatus === 'loading') {
        return false
      }

      if (!tableRows.length) {
        setDownloadError('다운로드할 리포트가 없습니다.')
        setDownloadStatus('error')
        return false
      }

      if (!isTableDirty && downloadUrl) {
        const link = document.createElement('a')
        link.href = downloadUrl
        link.download = downloadName ?? 'defect-report.xlsx'
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        setDownloadStatus('success')
        return true
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

        return true
      } catch (error) {
        const messageText =
          error instanceof Error
            ? error.message
            : '수정된 리포트를 다운로드하는 중 예기치 않은 오류가 발생했습니다.'
        setDownloadError(messageText)
        setDownloadStatus('error')
        return false
      }
    },
    [backendUrl, buildRowsPayload, downloadName, downloadStatus, downloadUrl, isTableDirty, projectId, selectedCell, tableRows.length],
  )

  const submitRewrite = useCallback(async () => {
    if (!selectedCell) {
      return false
    }

    const row = tableRows[selectedCell.rowIndex]
    const column = DEFECT_REPORT_COLUMNS.find((item) => item.key === selectedCell.columnKey)
    if (!row || !column) {
      return false
    }

    const message = rewriteInput.trim()
    if (!message) {
      setRewriteError('변경하고 싶은 내용을 입력해 주세요.')
      setRewriteStatus('error')
      return false
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
      return true
    } catch (error) {
      const messageText =
        error instanceof Error
          ? error.message
          : 'GPT 요청 중 예기치 않은 오류가 발생했습니다.'
      setRewriteError(messageText)
      setRewriteStatus('error')
      return false
    }
  }, [applyCellUpdate, backendUrl, projectId, rewriteInput, selectedCell, tableRows])

  const reset = useCallback(() => {
    if (downloadUrl) {
      URL.revokeObjectURL(downloadUrl)
    }
    setTableRows([])
    setIsTableDirty(false)
    setGenerateStatus('idle')
    setGenerateError(null)
    setDownloadStatus('idle')
    setDownloadError(null)
    setDownloadUrl(null)
    setDownloadName(null)
    setSelectedCell(null)
    setRewriteMessages([])
    setRewriteStatus('idle')
    setRewriteError(null)
    setRewriteInput('')
  }, [downloadUrl])

  const hasDownload = useMemo(() => Boolean(downloadUrl) || Boolean(downloadName), [downloadName, downloadUrl])
  const hasPreviewRows = useMemo(() => tableRows.length > 0, [tableRows.length])

  const selectedRow = useMemo(() => {
    if (!selectedCell) {
      return null
    }
    return tableRows[selectedCell.rowIndex] ?? null
  }, [selectedCell, tableRows])

  const selectedColumn = useMemo(() => {
    if (!selectedCell) {
      return null
    }
    return DEFECT_REPORT_COLUMNS.find((item) => item.key === selectedCell.columnKey) ?? null
  }, [selectedCell])

  const selectedValue = useMemo(() => {
    if (!selectedRow || !selectedColumn) {
      return ''
    }
    return selectedRow.cells[selectedColumn.key] ?? ''
  }, [selectedColumn, selectedRow])

  return {
    tableRows,
    isTableDirty,
    generateStatus,
    generateError,
    isGenerating: generateStatus === 'loading',
    downloadStatus,
    downloadError,
    hasDownload,
    hasPreviewRows,
    selectedCell,
    selectedRow,
    selectedColumn,
    selectedValue,
    rewriteMessages,
    rewriteStatus,
    rewriteError,
    rewriteInput,
    generateReport,
    downloadReport,
    selectCell,
    applyCellUpdate,
    updateRewriteInput,
    submitRewrite,
    reset,
  }
}
