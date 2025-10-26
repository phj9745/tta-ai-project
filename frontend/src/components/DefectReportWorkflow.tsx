import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { DefectTable } from './defect-report-workflow/DefectTable'
import { PreviewSection } from './defect-report-workflow/PreviewSection'
import { SourceUploadPanel } from './defect-report-workflow/SourceUploadPanel'
import {
  DEFECT_REPORT_COLUMNS,
  ATTACHMENT_ACCEPT,
  type AttachmentMap,
  type ConversationMessage,
  type DefectReportWorkflowProps,
  type DefectWorkItem,
} from './defect-report-workflow/types'
import {
  useDefectDownload,
  useFormalizeDefects,
} from './defect-report-workflow/hooks'
import {
  buildAttachmentFileName,
  buildRowsFromCsv,
  createFileKey,
  decodeBase64,
} from './defect-report-workflow/utils'
import { buildPromptResourcesPayload } from './defect-report-workflow/promptResources'

const RESULT_COLUMN_KEYS = ['결함요약', '결함정도', '발생빈도', '품질특성', '결함 설명'] as const

export function DefectReportWorkflow({
  backendUrl,
  projectId,
  onPreviewModeChange,
}: DefectReportWorkflowProps) {
  const previewSectionRef = useRef<HTMLElement | null>(null)
  const previousRowCountRef = useRef(0)

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

  const {
    tableRows,
    isTableDirty,
    generateStatus,
    generateError,
    isGenerating,
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
    reset: resetDownload,
  } = useDefectDownload({ backendUrl, projectId })


  const handleFormalize = useCallback(async () => {
    previousRowCountRef.current = 0
    resetDownload()
    setDefectItems([])
    const success = await formalize()
    if (!success) {
      setDefectItems([])
    }
  }, [formalize, resetDownload])

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
        promptResources: buildPromptResourcesPayload(messages),
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

        await response.blob()

        const encodedTable = decodeBase64(response.headers.get('x-defect-table'))
        if (!encodedTable) {
          throw new Error('생성된 결함 요약을 찾을 수 없습니다.')
        }

        const rows = buildRowsFromCsv(encodedTable)
        const row = rows[0]
        if (!row) {
          throw new Error('생성된 결함 요약을 찾을 수 없습니다.')
        }

        const result = { ...row.cells }
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

  const handleGenerate = useCallback(() => {
    void generateReport(
      defects,
      attachmentMap,
      defects.length > 0 && formalizeStatus === 'success',
    )
  }, [attachmentMap, defects, formalizeStatus, generateReport])

  const handleDownload = useCallback(() => {
    void downloadReport(attachmentMap)
  }, [attachmentMap, downloadReport])

  const handleReset = useCallback(() => {
    previousRowCountRef.current = 0
    resetFormalize()
    resetDownload()
    setDefectItems([])
  }, [resetDownload, resetFormalize])

  const handleSelectCell = useCallback(
    (rowIndex: number, columnKey: string) => {
      selectCell(rowIndex, columnKey)
    },
    [selectCell],
  )

  const handleUpdateSelectedValue = useCallback(
    (value: string) => {
      if (!selectedCell) {
        return
      }
      applyCellUpdate(selectedCell.rowIndex, selectedCell.columnKey, value)
    },
    [applyCellUpdate, selectedCell],
  )

  const handleRewriteSubmit = useCallback(() => {
    void submitRewrite()
  }, [submitRewrite])

  const canGenerate = defectItems.length > 0 && formalizeStatus === 'success'
  const isGenerated = generateStatus === 'success'
  const shouldHideReviewStep = isGenerating || isGenerated || hasPreviewRows
  const shouldShowPreviewSection = hasPreviewRows || isGenerating || isGenerated
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
    () =>
      hasSource ||
      defectItems.length > 0 ||
      hasAttachments ||
      hasDefectWork ||
      hasPreviewRows ||
      isGenerating ||
      isGenerated ||
      isTableDirty ||
      rewriteMessages.length > 0 ||
      hasDownload,
    [
      defectItems.length,
      hasAttachments,
      hasDefectWork,
      hasDownload,
      hasPreviewRows,
      hasSource,
      isGenerating,
      isGenerated,
      isTableDirty,
      rewriteMessages.length,
    ],
  )

  const isResetDisabled =
    formalizeStatus === 'loading' || isGenerating || downloadStatus === 'loading'

  const showResetInUpload = hasProgress && formalizeStatus !== 'success'
  const showResetInPreview = hasProgress && shouldShowPreviewSection

  useEffect(() => {
    const previousCount = previousRowCountRef.current
    if (tableRows.length > 0 && previousCount === 0 && previewSectionRef.current) {
      previewSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    previousRowCountRef.current = tableRows.length
  }, [tableRows.length])

  useEffect(() => {
    if (generateStatus === 'loading' || generateStatus === 'success') {
      if (previewSectionRef.current) {
        previewSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }
  }, [generateStatus])

  useEffect(() => {
    if (!onPreviewModeChange) {
      return
    }

    onPreviewModeChange(shouldShowPreviewSection)

    return () => {
      onPreviewModeChange(false)
    }
  }, [onPreviewModeChange, shouldShowPreviewSection])

  const rootClassName = `defect-workflow${shouldShowPreviewSection ? ' defect-workflow--preview-visible' : ''}`

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

      {defectItems.length > 0 && !shouldHideReviewStep && (
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

      {shouldShowPreviewSection && (
        <PreviewSection
          columns={DEFECT_REPORT_COLUMNS}
          tableRows={tableRows}
          selectedCell={selectedCell}
          onSelectCell={handleSelectCell}
          selectedRow={selectedRow}
          selectedColumn={selectedColumn}
          selectedValue={selectedValue}
          onUpdateSelectedValue={handleUpdateSelectedValue}
          rewriteMessages={rewriteMessages}
          rewriteStatus={rewriteStatus}
          rewriteError={rewriteError}
          rewriteInput={rewriteInput}
          onRewriteInputChange={updateRewriteInput}
          onRewriteSubmit={handleRewriteSubmit}
          isGenerating={isGenerating}
          showReset={showResetInPreview}
          onReset={handleReset}
          isResetDisabled={isResetDisabled}
          sectionRef={previewSectionRef}
        />
      )}

      <div className="defect-workflow__footer">
        <div className="defect-workflow__buttons">
          {!shouldHideReviewStep && (
            <button
              type="button"
              className="defect-workflow__primary"
              onClick={handleGenerate}
              disabled={!canGenerate || isGenerating}
            >
              {isGenerating ? '리포트 생성 중…' : '결함 리포트 생성'}
            </button>
          )}
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
