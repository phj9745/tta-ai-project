import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { navigate } from '../navigation'
import { DefectTable } from './defect-report-workflow/DefectTable'
import { SourceUploadPanel } from './defect-report-workflow/SourceUploadPanel'
import {
  ATTACHMENT_ACCEPT,
  type AttachmentMap,
  type ConversationMessage,
  type DefectReportWorkflowProps,
  type DefectWorkItem,
} from './defect-report-workflow/types'
import {
  useDefectFinalize,
  useFormalizeDefects,
  type DefectFinalizeRow,
} from './defect-report-workflow/hooks'
import {
  buildAttachmentFileName,
  buildRowsFromJsonTable,
  createFileKey,
} from './defect-report-workflow/utils'
import {
  buildPromptResourcesPayload,
  type PromptResourcesConfig,
} from './defect-report-workflow/promptResources'
import { normalizeDefectResultCells } from './defect-report-workflow/normalizers'

const RESULT_COLUMN_KEYS = ['결함요약', '결함정도', '발생빈도', '품질특성', '결함 설명'] as const

export function DefectReportWorkflow({
  backendUrl,
  projectId,
  projectName,
}: DefectReportWorkflowProps) {
  
  const {
    featureFiles,
    sourceFiles,
    defects,
    formalizeStatus,
    formalizeError,
    changeFeature,
    changeSource,
    formalize,
    updatePolished,
    reset: resetFormalize,
  } = useFormalizeDefects({ backendUrl, projectId })

  const [defectItems, setDefectItems] = useState<DefectWorkItem[]>([])
  const defectItemsRef = useRef<DefectWorkItem[]>([])

  useEffect(() => {
    defectItemsRef.current = defectItems
  }, [defectItems])

  useEffect(() => {
    if (formalizeStatus !== 'success') {
      setDefectItems([])
      return
    }

    setDefectItems((prev) => {
      const map = new Map(prev.map((item) => [item.entry.index, item]))
      return defects.map((defect) => {
        const existing = map.get(defect.index)
        if (existing) {
          return {
            ...existing,
            entry: defect,
          }
        }
        return {
          entry: defect,
          attachments: [],
          status: 'idle',
          error: null,
          result: {},
          messages: [],
          input: '',
          inputError: null,
          isCollapsed: false,
        }
      })
    })
  }, [defects, formalizeStatus])

  const attachmentMap = useMemo<AttachmentMap>(() => {
    const map: AttachmentMap = {}
    defectItems.forEach((item) => {
      if (item.attachments.length > 0) {
        map[item.entry.index] = item.attachments
      }
    })
    return map
  }, [defectItems])

  const hasAttachments = useMemo(
    () => defectItems.some((item) => item.attachments.length > 0),
    [defectItems],
  )

  const [promptResources, setPromptResources] = useState<PromptResourcesConfig | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    async function loadPromptResources() {
      try {
        const response = await fetch(`${backendUrl}/admin/prompts/defect-report`, {
          method: 'GET',
          signal: controller.signal,
        })
        if (!response.ok) {
          return
        }
        const payload = (await response.json()) as {
          config?: { promptResources?: PromptResourcesConfig | null }
        }
        const raw = payload?.config?.promptResources
        if (raw && typeof raw.judgementCriteria === 'string' && typeof raw.outputExample === 'string') {
          setPromptResources({
            judgementCriteria: raw.judgementCriteria,
            outputExample: raw.outputExample,
          })
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          console.error(error)
        }
      }
    }

    loadPromptResources()
    return () => controller.abort()
  }, [backendUrl])

  const {
    status: finalizeStatus,
    error: finalizeError,
    finalize: finalizeReport,
    reset: resetFinalize,
  } = useDefectFinalize({ backendUrl, projectId })

  const handleFormalize = useCallback(async () => {
    resetFinalize()
    setDefectItems([])
    const success = await formalize()
    if (!success) {
      setDefectItems([])
    }
  }, [formalize, resetFinalize])

  const handleAddAttachments = useCallback((defectIndex: number, files: FileList | File[]) => {
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

    setDefectItems((prev) =>
      prev.map((item) => {
        if (item.entry.index !== defectIndex) {
          return item
        }
        const existingKeys = new Set(item.attachments.map(createFileKey))
        const nextAttachments = [...item.attachments]
        filtered.forEach((file) => {
          const key = createFileKey(file)
          if (!existingKeys.has(key)) {
            nextAttachments.push(file)
            existingKeys.add(key)
          }
        })
        return { ...item, attachments: nextAttachments, isCollapsed: false }
      }),
    )
  }, [])

  const handleRemoveAttachment = useCallback((defectIndex: number, target: File) => {
    setDefectItems((prev) =>
      prev.map((item) => {
        if (item.entry.index !== defectIndex) {
          return item
        }
        const nextAttachments = item.attachments.filter((file) => file !== target)
        return { ...item, attachments: nextAttachments, isCollapsed: false }
      }),
    )
  }, [])

  const handlePolishedChange = useCallback(
    (defectIndex: number, value: string) => {
      updatePolished(defectIndex, value)
      setDefectItems((prev) =>
        prev.map((item) =>
          item.entry.index === defectIndex ? { ...item, isCollapsed: false } : item,
        ),
      )
    },
    [updatePolished],
  )

  const handleResultChange = useCallback(
    (defectIndex: number, columnKey: string, value: string) => {
      setDefectItems((prev) =>
        prev.map((item) => {
          if (item.entry.index !== defectIndex) {
            return item
          }
          return {
            ...item,
            result: {
              ...item.result,
              [columnKey]: value,
            },
            isCollapsed: false,
          }
        }),
      )
    },
    [],
  )

  const handleComplete = useCallback((defectIndex: number) => {
    setDefectItems((prev) =>
      prev.map((item) => {
        if (item.entry.index !== defectIndex) {
          return item
        }
        const hasValue = RESULT_COLUMN_KEYS.some(
          (key) => (item.result[key] ?? '').trim().length > 0,
        )
        if (!hasValue) {
          return item
        }
        return { ...item, isCollapsed: true }
      }),
    )
  }, [])

  const handleResume = useCallback((defectIndex: number) => {
    setDefectItems((prev) =>
      prev.map((item) =>
        item.entry.index === defectIndex ? { ...item, isCollapsed: false } : item,
      ),
    )
  }, [])

  const handleChatInputChange = useCallback((defectIndex: number, value: string) => {
    setDefectItems((prev) =>
      prev.map((item) =>
        item.entry.index === defectIndex
          ? { ...item, input: value, inputError: null, isCollapsed: false }
          : item,
      ),
    )
  }, [])

  const handleGenerateDefectRow = useCallback(
    async (defectIndex: number, overrideMessages?: ConversationMessage[]) => {
      const card = defectItemsRef.current.find((item) => item.entry.index === defectIndex)
      if (!card) {
        return
      }

      const messages = overrideMessages ?? card.messages

      setDefectItems((prev) =>
        prev.map((item) =>
          item.entry.index === defectIndex
            ? { ...item, status: 'loading', error: null, inputError: null, isCollapsed: false }
            : item,
        ),
      )

      const summary = {
        defects: [
          {
            index: card.entry.index,
            originalText: card.entry.originalText,
            polishedText: card.entry.polishedText,
            attachments: card.attachments.map((file) => ({
              fileName: buildAttachmentFileName(card.entry.index, file.name),
              originalFileName: file.name,
            })),
          },
        ],
        promptResources: buildPromptResourcesPayload(messages, promptResources ?? undefined),
      }

      const formData = new FormData()
      formData.append('menu_id', 'defect-report')

      const summaryFile = new File(
        [JSON.stringify(summary, null, 2)],
        `정제된-결함-${card.entry.index}.json`,
        { type: 'application/json' },
      )

      const metadataEntries: Array<Record<string, unknown>> = [
        {
          role: 'additional',
          description: '정제된 결함 목록',
          label: '정제된 결함 목록',
          notes: '결함 문장 정제 결과(JSON)',
        },
      ]

      formData.append('files', summaryFile)

      card.attachments.forEach((file) => {
        const normalizedName = buildAttachmentFileName(card.entry.index, file.name)
        const renamed =
          file.name === normalizedName ? file : new File([file], normalizedName, { type: file.type })
        formData.append('files', renamed)
        metadataEntries.push({
          role: 'additional',
          description: `결함 ${card.entry.index} 이미지`,
          label: `결함 ${card.entry.index} 이미지`,
          notes: `원본 파일명: ${file.name}`,
          defect_index: card.entry.index,
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
              : '결함 요약을 생성하지 못했습니다.'
          throw new Error(detail)
        }

        const payload = (await response.json().catch(() => ({}))) as {
          rows?: unknown
          headers?: unknown
        }

        const rows = buildRowsFromJsonTable(payload.headers, payload.rows)
        const row = rows[0]
        if (!row) {
          throw new Error('생성된 결함 요약을 찾을 수 없습니다.')
        }

        const result = normalizeDefectResultCells({ ...row.cells })
        const assistantText = RESULT_COLUMN_KEYS.map((key) => {
          const value = result[key]?.trim()
          return `${key}: ${value || '-'}`
        }).join('\n')

        setDefectItems((prev) =>
          prev.map((item) =>
            item.entry.index === defectIndex
              ? {
                  ...item,
                  status: 'success',
                  error: null,
                  result,
                  messages: [...messages, { role: 'assistant', text: assistantText }],
                }
              : item,
          ),
        )
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : '결함 요약을 생성하는 중 예기치 않은 오류가 발생했습니다.'
        setDefectItems((prev) =>
          prev.map((item) =>
            item.entry.index === defectIndex
              ? { ...item, status: 'error', error: message }
              : item,
          ),
        )
      }
    },
    [backendUrl, projectId],
  )

  const handleGenerateDefect = useCallback(
    (defectIndex: number) => {
      void handleGenerateDefectRow(defectIndex)
    },
    [handleGenerateDefectRow],
  )

  const handleChatSubmit = useCallback(
    (defectIndex: number) => {
      const card = defectItemsRef.current.find((item) => item.entry.index === defectIndex)
      if (!card) {
        return
      }

      const message = card.input.trim()
      if (!message) {
        setDefectItems((prev) =>
          prev.map((item) =>
            item.entry.index === defectIndex
              ? { ...item, inputError: 'GPT에게 전달할 내용을 입력해 주세요.' }
              : item,
          ),
        )
        return
      }

      const nextMessages: ConversationMessage[] = [
        ...card.messages,
        { role: 'user', text: message },
      ]

      setDefectItems((prev) =>
        prev.map((item) =>
          item.entry.index === defectIndex
            ? { ...item, messages: nextMessages, input: '', inputError: null, isCollapsed: false }
            : item,
        ),
      )

      void handleGenerateDefectRow(defectIndex, nextMessages)
    },
    [handleGenerateDefectRow],
  )

  const handleGenerate = useCallback(async () => {
    if (finalizeStatus === 'loading') {
      return
    }

    const finalizeRows: DefectFinalizeRow[] = defectItems
      .map((item) => {
        const cells = item.result || {}
        const attachments = attachmentMap[item.entry.index] ?? []

        const getCellValue = (key: string) => {
          const value = (cells as Record<string, unknown>)[key]
          if (typeof value === 'string') {
            return value.trim()
          }
          if (value == null) {
            return ''
          }
          return String(value).trim()
        }

        const summary = getCellValue('결함요약')
        const severity = getCellValue('결함정도')
        const frequency = getCellValue('발생빈도')
        const quality = getCellValue('품질특성')
        const description = getCellValue('결함 설명')
        const vendorResponse = getCellValue('업체 응답')
        const fixStatus = getCellValue('수정여부')
        const note = getCellValue('비고')
        const environment = getCellValue('시험환경(OS)')

        const hasContent =
          summary.length > 0 ||
          severity.length > 0 ||
          frequency.length > 0 ||
          quality.length > 0 ||
          description.length > 0 ||
          vendorResponse.length > 0 ||
          fixStatus.length > 0 ||
          note.length > 0

        if (!hasContent && attachments.length === 0) {
          return null
        }

        return {
          order: item.entry.index,
          environment,
          summary,
          severity,
          frequency,
          quality,
          description,
          vendorResponse,
          fixStatus,
          note,
        }
      })
      .filter((row): row is DefectFinalizeRow => row !== null)

    const payload = await finalizeReport(finalizeRows, attachmentMap)
    if (!payload || typeof payload !== 'object') {
      return
    }

    if (typeof window === 'undefined') {
      return
    }

    const nextParams = new URLSearchParams(window.location.search)
    if (projectName && projectName !== projectId && !nextParams.get('name')) {
      nextParams.set('name', projectName)
    }

    const fileId = typeof payload.fileId === 'string' ? payload.fileId.trim() : ''
    if (fileId) {
      nextParams.set('fileId', fileId)
    } else {
      nextParams.delete('fileId')
    }

    const fileName = typeof payload.fileName === 'string' ? payload.fileName.trim() : ''
    if (fileName) {
      nextParams.set('fileName', fileName)
    } else {
      nextParams.delete('fileName')
    }

    const modified = typeof payload.modifiedTime === 'string' ? payload.modifiedTime.trim() : ''
    if (modified) {
      nextParams.set('modifiedTime', modified)
    } else {
      nextParams.delete('modifiedTime')
    }

    const query = nextParams.toString()
    navigate(
      `/projects/${encodeURIComponent(projectId)}/defect-report/edit${query ? `?${query}` : ''}`,
    )
  }, [attachmentMap, defectItems, finalizeReport, finalizeStatus, projectId, projectName])

  const handleReset = useCallback(() => {
    resetFormalize()
    resetFinalize()
    setDefectItems([])
  }, [resetFinalize, resetFormalize])

  const canGenerate = defectItems.length > 0 && formalizeStatus === 'success'
  const hasSource = featureFiles.length > 0 || sourceFiles.length > 0

  const hasDefectWork = useMemo(
    () =>
      defectItems.some(
        (item) =>
          item.attachments.length > 0 ||
          item.messages.length > 0 ||
          RESULT_COLUMN_KEYS.some((key) => (item.result[key] ?? '').trim().length > 0) ||
          item.status === 'loading' ||
          item.status === 'success',
      ),
    [defectItems],
  )

  const hasProgress = useMemo(
    () => hasSource || defectItems.length > 0 || hasAttachments || hasDefectWork,
    [defectItems.length, hasAttachments, hasDefectWork, hasSource],
  )

  const isResetDisabled = formalizeStatus === 'loading' || finalizeStatus === 'loading'

  const showResetInUpload = hasProgress && formalizeStatus !== 'success'

  const rootClassName = 'defect-workflow'

  return (
    <div className={rootClassName}>
      {formalizeStatus !== 'success' && (
        <SourceUploadPanel
          featureFiles={featureFiles}
          sourceFiles={sourceFiles}
          status={formalizeStatus}
          error={formalizeError}
          onChangeFeature={changeFeature}
          onChangeSource={changeSource}
          onFormalize={handleFormalize}
          showReset={showResetInUpload}
          onReset={handleReset}
          isResetDisabled={isResetDisabled}
        />
      )}

      {defectItems.length > 0 && (
        <DefectTable
          items={defectItems}
          onPolishedChange={handlePolishedChange}
          onAddAttachments={handleAddAttachments}
          onRemoveAttachment={handleRemoveAttachment}
          onGenerate={handleGenerateDefect}
          onChatInputChange={handleChatInputChange}
          onChatSubmit={handleChatSubmit}
          onResultChange={handleResultChange}
          onComplete={handleComplete}
          onResume={handleResume}
        />
      )}

      <div className="defect-workflow__footer">
        <div className="defect-workflow__buttons">
          <button
            type="button"
            className="defect-workflow__primary"
            onClick={handleGenerate}
            disabled={!canGenerate || finalizeStatus === 'loading'}
          >
            {finalizeStatus === 'loading' ? '리포트 생성 중…' : '결함 리포트 생성'}
          </button>
        </div>

        {finalizeStatus === 'error' && finalizeError && (
          <p className="defect-workflow__status defect-workflow__status--error" role="alert">
            {finalizeError}
          </p>
        )}
        {finalizeStatus === 'success' && (
          <p className="defect-workflow__status defect-workflow__status--success">
            결함 리포트 파일로 이동합니다. 잠시만 기다려 주세요.
          </p>
        )}
      </div>
    </div>
  )
}
