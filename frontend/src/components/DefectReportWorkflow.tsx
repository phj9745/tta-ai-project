import { useCallback, useEffect, useMemo, useRef } from 'react'

import { DefectTable } from './defect-report-workflow/DefectTable'
import { PreviewSection } from './defect-report-workflow/PreviewSection'
import { SourceUploadPanel } from './defect-report-workflow/SourceUploadPanel'
import {
  DEFECT_REPORT_COLUMNS,
  type DefectReportWorkflowProps,
} from './defect-report-workflow/types'
import {
  useDefectAttachments,
  useDefectDownload,
  useFormalizeDefects,
} from './defect-report-workflow/hooks'

export function DefectReportWorkflow({
  backendUrl,
  projectId,
  onPreviewModeChange,
}: DefectReportWorkflowProps) {
  const previewSectionRef = useRef<HTMLElement | null>(null)
  const previousRowCountRef = useRef(0)

  const {
    sourceFiles,
    defects,
    formalizeStatus,
    formalizeError,
    changeSource,
    formalize,
    updatePolished,
    reset: resetFormalize,
  } = useFormalizeDefects({ backendUrl, projectId })

  const {
    attachments,
    addAttachments,
    removeAttachment,
    reset: resetAttachments,
    hasAttachments,
  } = useDefectAttachments()

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
    const success = await formalize()
    if (success) {
      resetAttachments()
    }
  }, [formalize, resetAttachments, resetDownload])

  const handleGenerate = useCallback(() => {
    void generateReport(defects, attachments, defects.length > 0 && formalizeStatus === 'success')
  }, [attachments, defects, formalizeStatus, generateReport])

  const handleDownload = useCallback(() => {
    void downloadReport(attachments)
  }, [attachments, downloadReport])

  const handleReset = useCallback(() => {
    previousRowCountRef.current = 0
    resetFormalize()
    resetAttachments()
    resetDownload()
  }, [resetAttachments, resetDownload, resetFormalize])

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

  const canGenerate = defects.length > 0 && formalizeStatus === 'success'
  const isGenerated = generateStatus === 'success'
  const shouldHideReviewStep = isGenerating || isGenerated || hasPreviewRows
  const shouldShowPreviewSection = hasPreviewRows || isGenerating || isGenerated
  const hasSource = sourceFiles.length > 0

  const hasProgress = useMemo(
    () =>
      hasSource ||
      defects.length > 0 ||
      hasAttachments ||
      hasPreviewRows ||
      isGenerating ||
      isGenerated ||
      isTableDirty ||
      rewriteMessages.length > 0 ||
      hasDownload,
    [
      defects.length,
      hasAttachments,
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
  const showResetInReview = hasProgress && formalizeStatus === 'success' && !shouldHideReviewStep
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
          sourceFiles={sourceFiles}
          status={formalizeStatus}
          error={formalizeError}
          onChangeSource={changeSource}
          onFormalize={handleFormalize}
          showReset={showResetInUpload}
          onReset={handleReset}
          isResetDisabled={isResetDisabled}
        />
      )}

      {defects.length > 0 && !shouldHideReviewStep && (
        <DefectTable
          defects={defects}
          attachments={attachments}
          onUpdatePolished={updatePolished}
          onAddAttachments={addAttachments}
          onRemoveAttachment={removeAttachment}
          showReset={showResetInReview}
          onReset={handleReset}
          isResetDisabled={isResetDisabled}
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
