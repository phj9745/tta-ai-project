import { useCallback, useEffect, useMemo, useState } from 'react'

import { FileUploader } from './FileUploader'
import type { FileType } from './fileUploaderTypes'
import { navigate } from '../navigation'
import { useBackgroundTasks } from '../app/background/BackgroundTaskContext'
import {
  SECURITY_COLUMNS,
  type SecurityColumn,
  type SecurityRow,
  type SecurityRowKey,
  buildSecurityPayloadRows,
  normalizeSecurityPreviewRow,
} from '../pages/securityReportShared'

type AsyncStatus = 'idle' | 'loading' | 'success' | 'error'

interface SecurityReportWorkflowProps {
  backendUrl: string
  projectId: string
  projectName: string
}

const HTML_TYPES = ['html'] as unknown as FileType[]

export function SecurityReportWorkflow({
  backendUrl,
  projectId,
  projectName,
}: SecurityReportWorkflowProps) {
  const { startTask } = useBackgroundTasks()
  const [sourceFiles, setSourceFiles] = useState<File[]>([])
  const [previewStatus, setPreviewStatus] = useState<AsyncStatus>('idle')
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [rows, setRows] = useState<SecurityRow[]>([])
  const [saveStatus, setSaveStatus] = useState<AsyncStatus>('idle')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isFullscreenPreview, setIsFullscreenPreview] = useState(false)

  const handleFileChange = useCallback((nextFiles: File[]) => {
    setSourceFiles(nextFiles.slice(0, 1))
    setPreviewStatus('idle')
    setPreviewError(null)
    setRows([])
    setSaveStatus('idle')
    setSaveError(null)
  }, [])

  const handleReset = useCallback(() => {
    setSourceFiles([])
    setPreviewStatus('idle')
    setPreviewError(null)
    setRows([])
    setSaveStatus('idle')
    setSaveError(null)
    setIsFullscreenPreview(false)
  }, [])

  const handlePreview = useCallback(async () => {
    if (sourceFiles.length === 0) {
      setPreviewStatus('error')
      setPreviewError('Invicti HTML 보고서를 업로드해 주세요.')
      return
    }

    const formData = new FormData()
    formData.append('invictiReport', sourceFiles[0])

    setPreviewStatus('loading')
    setPreviewError(null)
    const taskHandle = startTask('security-report', '보안성 리포트 미리보기')
    taskHandle.onCancel(() => {
      setPreviewStatus('idle')
      setPreviewError(null)
    })

    try {
      const response = await fetch(
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/security-report/preview`,
        {
          method: 'POST',
          body: formData,
          signal: taskHandle.signal,
        },
      )

      if (taskHandle.signal.aborted) {
        return
      }

      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        if (taskHandle.signal.aborted) {
          return
        }
        const detail =
          payload && typeof payload.detail === 'string'
            ? payload.detail
            : '보안성 리포트 초안을 생성하는 중 오류가 발생했습니다.'
        setPreviewStatus('error')
        setPreviewError(detail)
        taskHandle.fail(detail)
        return
      }

      const payload = (await response.json().catch(() => ({}))) as {
        headers?: unknown
        rows?: unknown
      }

      if (taskHandle.signal.aborted) {
        return
      }

      const rawRows = Array.isArray(payload.rows) ? payload.rows : []
      const normalizedRows = rawRows
        .map((entry, index) => normalizeSecurityPreviewRow(entry, index))
        .filter((item): item is SecurityRow => item !== null)

      if (normalizedRows.length === 0) {
        setPreviewStatus('error')
        setPreviewError('생성된 보안성 결함 데이터를 찾지 못했습니다.')
        setRows([])
        taskHandle.fail('생성된 보안성 결함 데이터를 찾지 못했습니다.')
        return
      }

      if (taskHandle.signal.aborted) {
        return
      }

      setRows(normalizedRows)
      setPreviewStatus('success')
      setPreviewError(null)
      setSaveStatus('idle')
      setSaveError(null)
      if (!taskHandle.signal.aborted) {
        taskHandle.complete({ type: 'data', payload: normalizedRows }, '미리보기 준비 완료')
      }
    } catch (error) {
      if (taskHandle.signal.aborted) {
        return
      }
      console.error('Failed to preview security report', error)
      setPreviewStatus('error')
      setPreviewError('보안성 리포트 초안을 생성하는 중 예기치 않은 오류가 발생했습니다.')
      taskHandle.fail('미리보기 중 오류가 발생했습니다.')
    }
  }, [backendUrl, projectId, sourceFiles, startTask])

  const handleCellChange = useCallback((rowId: string, key: SecurityRowKey, value: string) => {
    setRows((prev) =>
      prev.map((row) =>
        row.id === rowId
          ? {
              ...row,
              [key]: value,
            }
          : row,
      ),
    )
  }, [])

  const handleSave = useCallback(async () => {
    if (rows.length === 0) {
      setSaveStatus('error')
      setSaveError('저장할 보안성 결함 데이터가 없습니다.')
      return
    }

    const payloadRows = buildSecurityPayloadRows(rows)

    const formData = new FormData()
    formData.append('menu_id', 'security-report')
    formData.append('rows_json', JSON.stringify(payloadRows))

    setSaveStatus('loading')
    setSaveError(null)
    const taskHandle = startTask('security-report', '보안성 리포트 저장')
    taskHandle.onCancel(() => {
      setSaveStatus('idle')
      setSaveError(null)
    })

    try {
      const response = await fetch(
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/generate`,
        {
          method: 'POST',
          body: formData,
          signal: taskHandle.signal,
        },
      )

      if (taskHandle.signal.aborted) {
        return
      }

      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        if (taskHandle.signal.aborted) {
          return
        }
        const detail =
          payload && typeof payload.detail === 'string'
            ? payload.detail
            : '보안성 리포트를 저장하는 중 오류가 발생했습니다.'
        setSaveStatus('error')
        setSaveError(detail)
        taskHandle.fail(detail)
        return
      }

      const payload = (await response.json().catch(() => ({}))) as {
        fileId?: unknown
        fileName?: unknown
        modifiedTime?: unknown
      }

      if (taskHandle.signal.aborted) {
        return
      }

      setSaveStatus('success')
      if (!taskHandle.signal.aborted) {
        taskHandle.complete({ type: 'data', payload }, '보안성 리포트 저장 완료')
      }

      if (typeof window !== 'undefined' && !taskHandle.signal.aborted) {
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

        const modifiedTime =
          typeof payload.modifiedTime === 'string' ? payload.modifiedTime.trim() : ''
        if (modifiedTime) {
          nextParams.set('modifiedTime', modifiedTime)
        } else {
          nextParams.delete('modifiedTime')
        }

        const query = nextParams.toString()
        navigate(
          `/projects/${encodeURIComponent(projectId)}/defect-report/edit${query ? `?${query}` : ''}`,
        )
      }
    } catch (error) {
      if (taskHandle.signal.aborted) {
        return
      }
      console.error('Failed to save security report', error)
      setSaveStatus('error')
      setSaveError('보안성 리포트를 저장하는 중 예기치 않은 오류가 발생했습니다.')
      taskHandle.fail('저장 중 오류가 발생했습니다.')
    }
  }, [backendUrl, projectId, projectName, rows, startTask])

  const openFullscreen = useCallback(() => {
    setIsFullscreenPreview(true)
  }, [])

  const closeFullscreen = useCallback(() => {
    setIsFullscreenPreview(false)
  }, [])

  const columns: SecurityColumn[] = useMemo(() => SECURITY_COLUMNS, [])
  const showResetButton = sourceFiles.length > 0 || rows.length > 0
  const isPreviewLoading = previewStatus === 'loading'
  const isSaving = saveStatus === 'loading'

  useEffect(() => {
    if (!isFullscreenPreview) {
      return
    }
    if (typeof document === 'undefined') {
      return
    }
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [isFullscreenPreview])

  const renderTable = useCallback(
    (readOnly: boolean) => (
      <table className="defect-workflow__table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              {columns.map((column) => {
                const value = row[column.key] ?? ''
                const isReadOnly = readOnly || Boolean(column.readOnly)
                return (
                  <td key={column.key}>
                    {column.input === 'textarea' ? (
                      <textarea
                        className="defect-workflow__editor"
                        value={value}
                        onChange={(event) => {
                          if (!isReadOnly) {
                            handleCellChange(row.id, column.key, event.target.value)
                          }
                        }}
                        readOnly={isReadOnly}
                      />
                    ) : (
                      <input
                        type="text"
                        className="defect-workflow__editor"
                        value={value}
                        onChange={(event) => {
                          if (!isReadOnly) {
                            handleCellChange(row.id, column.key, event.target.value)
                          }
                        }}
                        readOnly={isReadOnly}
                      />
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    ),
    [columns, handleCellChange, rows],
  )

  return (
    <div className={`defect-workflow${isFullscreenPreview ? ' defect-workflow--fullscreen-open' : ''}`}>
      <section className="defect-workflow__section" aria-labelledby="security-upload">
        <div className="defect-workflow__section-heading">
          <h2 id="security-upload" className="defect-workflow__title">
            1. Invicti HTML 업로드
          </h2>
          {showResetButton && (
            <div className="defect-workflow__section-actions">
              <button
                type="button"
                className="defect-workflow__secondary"
                onClick={handleReset}
                disabled={isPreviewLoading || isSaving}
              >
                초기화
              </button>
            </div>
          )}
        </div>
        <p className="defect-workflow__helper">
          Invicti에서 추출한 HTML 보고서를 업로드하면 보안성 결함 표를 생성합니다. 표는 아래에서 바로 확인하고 수정할
          수 있습니다.
        </p>
        <FileUploader
          allowedTypes={HTML_TYPES}
          files={sourceFiles}
          onChange={handleFileChange}
          multiple={false}
          maxFiles={1}
          hideDropzoneWhenFilled
          disabled={isPreviewLoading || isSaving}
        />
        <div className="defect-workflow__actions">
          <button
            type="button"
            className="defect-workflow__primary"
            onClick={() => {
              void handlePreview()
            }}
            disabled={isPreviewLoading || isSaving}
          >
            {isPreviewLoading ? '초안 생성 중…' : '보안성 결함 불러오기'}
          </button>
          {previewStatus === 'error' && previewError && (
            <p className="defect-workflow__status defect-workflow__status--error" role="alert">
              {previewError}
            </p>
          )}
          {previewStatus === 'success' && rows.length > 0 && (
            <p className="defect-workflow__status defect-workflow__status--success">
              생성된 보안성 결함이 아래 표에 표시되었습니다. 내용을 확인하고 수정한 뒤 저장해 주세요.
            </p>
          )}
        </div>
      </section>

      {rows.length > 0 && (
        <section className="defect-workflow__section" aria-labelledby="security-review">
          <div className="defect-workflow__section-heading">
            <h2 id="security-review" className="defect-workflow__title">
              2. 보안성 결함 검토 및 편집
            </h2>
            <div className="defect-workflow__section-actions">
              <button
                type="button"
                className="defect-workflow__secondary"
                onClick={openFullscreen}
              >
                전체 화면 보기
              </button>
            </div>
          </div>
          <p className="defect-workflow__helper">
            각 열을 자유롭게 수정할 수 있습니다. 매핑 유형 등 회색으로 표시된 값은 참조용 입니다.
          </p>
          <div className="defect-workflow__preview">
            <div className="defect-workflow__table-wrapper" role="region" aria-live="polite">
              {renderTable(false)}
            </div>
          </div>
        </section>
      )}

      <div className="defect-workflow__footer">
        <div className="defect-workflow__buttons">
          <button
            type="button"
            className="defect-workflow__primary"
            onClick={() => {
              void handleSave()
            }}
            disabled={rows.length === 0 || isSaving}
          >
            {isSaving ? '저장 중…' : '보안성 결함 저장'}
          </button>
        </div>
        {saveStatus === 'error' && saveError && (
          <p className="defect-workflow__status defect-workflow__status--error" role="alert">
            {saveError}
          </p>
        )}
        {saveStatus === 'success' && (
          <p className="defect-workflow__status defect-workflow__status--success">
            보안성 결함을 결함 리포트에 추가했습니다. 편집 화면으로 이동합니다.
          </p>
        )}
      </div>

      {isFullscreenPreview && (
        <div className="security-preview-overlay" role="dialog" aria-modal="true">
          <div className="security-preview-overlay__content">
            <header className="security-preview-overlay__header">
              <div>
                <span className="security-preview-overlay__eyebrow">보안성 결함 전체 보기</span>
                <h2 className="security-preview-overlay__title">{projectName}</h2>
              </div>
              <button
                type="button"
                className="security-preview-overlay__close"
                onClick={closeFullscreen}
              >
                닫기
              </button>
            </header>
            <div className="security-preview-overlay__body">
              <div className="security-preview-overlay__table-wrapper">{renderTable(false)}</div>
            </div>
            <footer className="security-preview-overlay__footer">
              <button
                type="button"
                className="security-preview-overlay__primary"
                onClick={() => {
                  closeFullscreen()
                  void handleSave()
                }}
                disabled={isSaving}
              >
                {isSaving ? '저장 중…' : '보안성 결함 저장'}
              </button>
              <button
                type="button"
                className="security-preview-overlay__secondary"
                onClick={closeFullscreen}
              >
                닫기
              </button>
            </footer>
          </div>
        </div>
      )}
    </div>
  )
}
