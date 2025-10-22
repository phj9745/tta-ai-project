import './FeatureListEditPage.css'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { getBackendUrl } from '../config'
import { navigate } from '../navigation'

interface FeatureListRow {
  majorCategory: string
  middleCategory: string
  minorCategory: string
  featureOverview: string
  featureDescription: string
}

interface FeatureListResponse {
  fileId?: string
  fileName?: string
  sheetName?: string
  startRow?: number
  headers?: string[]
  rows?: FeatureListRow[]
  modifiedTime?: string
}

type LoadState = 'idle' | 'loading' | 'error' | 'ready'

const DEFAULT_HEADERS = ['대분류', '중분류', '소분류', '기능 설명', '개요']

function createEmptyRow(): FeatureListRow {
  return {
    majorCategory: '',
    middleCategory: '',
    minorCategory: '',
    featureOverview: '',
    featureDescription: '',
  }
}

function normalizeRow(row: FeatureListRow | null | undefined): FeatureListRow {
  const description =
    typeof row?.featureDescription === 'string' ? row.featureDescription : ''
  const overview = typeof row?.featureOverview === 'string' ? row.featureOverview : ''
  const normalizedDescription = description || overview
  const normalizedOverview = overview || description
  return {
    majorCategory: typeof row?.majorCategory === 'string' ? row.majorCategory : '',
    middleCategory: typeof row?.middleCategory === 'string' ? row.middleCategory : '',
    minorCategory: typeof row?.minorCategory === 'string' ? row.minorCategory : '',
    featureOverview: normalizedOverview,
    featureDescription: normalizedDescription,
  }
}

function parseFileNameFromDisposition(disposition: string | null): string | null {
  if (!disposition) {
    return null
  }

  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }

  const quotedMatch = disposition.match(/filename="?([^";]+)"?/i)
  if (quotedMatch?.[1]) {
    return quotedMatch[1]
  }

  return null
}

function formatTimestamp(value: string | undefined): string | null {
  if (!value) {
    return null
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return null
  }
  try {
    return new Intl.DateTimeFormat('ko-KR', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date)
  } catch {
    return date.toLocaleString()
  }
}

interface FeatureListEditPageProps {
  projectId: string
}

export function FeatureListEditPage({ projectId }: FeatureListEditPageProps) {
  const backendUrl = useMemo(() => getBackendUrl(), [])
  const [rows, setRows] = useState<FeatureListRow[]>([createEmptyRow()])
  const [headers, setHeaders] = useState<string[]>(() => [...DEFAULT_HEADERS])
  const [sheetName, setSheetName] = useState<string>('기능리스트')
  const [fileName, setFileName] = useState<string>(() => {
    if (typeof window === 'undefined') {
      return ''
    }
    const params = new URLSearchParams(window.location.search)
    return params.get('fileName') ?? ''
  })
  const [modifiedTime, setModifiedTime] = useState<string | undefined>(() => {
    if (typeof window === 'undefined') {
      return undefined
    }
    const params = new URLSearchParams(window.location.search)
    const value = params.get('modifiedTime')
    return value ?? undefined
  })
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [isDirty, setIsDirty] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)
  const [fileId, setFileId] = useState<string | null>(() => {
    if (typeof window === 'undefined') {
      return null
    }
    const params = new URLSearchParams(window.location.search)
    const value = params.get('fileId')
    return value && value.trim().length > 0 ? value : null
  })
  const fileIdRef = useRef<string | null>(fileId)

  useEffect(() => {
    fileIdRef.current = fileId
  }, [fileId])

  const projectName = useMemo(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('name') ?? projectId
  }, [projectId])

  const formattedModified = useMemo(() => formatTimestamp(modifiedTime), [modifiedTime])

  const columnLabels = useMemo(
    () => ({
      majorCategory: headers[0]?.trim() || '대분류',
      middleCategory: headers[1]?.trim() || '중분류',
      minorCategory: headers[2]?.trim() || '소분류',
      featureDescription: headers[3]?.trim() || '기능 설명',
      featureOverview: headers[4]?.trim() || '개요',
    }),
    [headers],
  )

  const tableColumns = useMemo<
    Array<{
      key: keyof FeatureListRow
      label: string
      multiline?: boolean
      placeholder: string
    }>
  >(
    () => {
      const overviewLabel = columnLabels.featureOverview
      const descriptionLabel =
        columnLabels.featureDescription === '기능 설명'
          ? '상세 내용'
          : columnLabels.featureDescription || '상세 내용'

      return [
        {
          key: 'majorCategory',
          label: columnLabels.majorCategory,
          placeholder: `${columnLabels.majorCategory}을(를) 입력하세요`,
        },
        {
          key: 'middleCategory',
          label: columnLabels.middleCategory,
          placeholder: `${columnLabels.middleCategory}을(를) 입력하세요`,
        },
        {
          key: 'minorCategory',
          label: columnLabels.minorCategory,
          placeholder: `${columnLabels.minorCategory}을(를) 입력하세요`,
        },
        {
          key: 'featureOverview',
          label: overviewLabel,
          multiline: true,
          placeholder: `${overviewLabel}을(를) 입력하세요`,
        },
        {
          key: 'featureDescription',
          label: descriptionLabel,
          multiline: true,
          placeholder: `${descriptionLabel}을(를) 입력하세요`,
        },
      ]
    },
    [columnLabels],
  )

  useEffect(() => {
    const controller = new AbortController()
    setLoadState('loading')
    setErrorMessage(null)

    const fetchData = async () => {
      try {
        const searchParams = new URLSearchParams()
        let requestedFileId: string | null = null
        let requestedFileName: string | null = null
        let requestedModified: string | undefined
        if (typeof window !== 'undefined') {
          const params = new URLSearchParams(window.location.search)
          requestedFileId = params.get('fileId')
          requestedFileName = params.get('fileName')
          const modifiedParam = params.get('modifiedTime')
          requestedModified = modifiedParam ?? undefined
        }
        const normalizedRequestedId =
          requestedFileId && requestedFileId.trim().length > 0 ? requestedFileId.trim() : null
        const currentFileId = fileIdRef.current
        const effectiveRequestId =
          normalizedRequestedId ??
          (currentFileId && currentFileId.trim().length > 0 ? currentFileId.trim() : null)
        if (effectiveRequestId) {
          searchParams.set('fileId', effectiveRequestId)
        }

        const response = await fetch(
          `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/feature-list${
            searchParams.toString() ? `?${searchParams.toString()}` : ''
          }`,
          { signal: controller.signal },
        )

        if (!response.ok) {
          const payload = await response.json().catch(() => null)
          const detail =
            payload && typeof payload.detail === 'string'
              ? payload.detail
              : '기능리스트를 불러오는 중 오류가 발생했습니다.'
          throw new Error(detail)
        }

        const payload = (await response.json()) as FeatureListResponse
        if (controller.signal.aborted) {
          return
        }

        const nextHeaders = Array.isArray(payload.headers)
          ? payload.headers.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
          : undefined
        if (nextHeaders && nextHeaders.length >= 3) {
          const merged = [...DEFAULT_HEADERS]
          nextHeaders.forEach((name, index) => {
            if (index < merged.length) {
              merged[index] = name
            }
          })
          setHeaders(merged)
        } else {
          setHeaders([...DEFAULT_HEADERS])
        }

        setSheetName(payload.sheetName?.trim() || '기능리스트')
        const nextFileName =
          typeof payload.fileName === 'string' && payload.fileName.trim().length > 0
            ? payload.fileName.trim()
            : requestedFileName ?? ''
        setFileName(nextFileName)
        setModifiedTime(payload.modifiedTime ?? requestedModified)

        const effectiveFileId =
          typeof payload.fileId === 'string' && payload.fileId.trim().length > 0
            ? payload.fileId.trim()
            : effectiveRequestId
        setFileId((current) => {
          const nextId = effectiveFileId && effectiveFileId.trim().length > 0 ? effectiveFileId : null
          return current === nextId ? current : nextId
        })

        const fetchedRows = Array.isArray(payload.rows)
          ? payload.rows.map((row) => normalizeRow(row))
          : []
        setRows(fetchedRows.length > 0 ? fetchedRows : [createEmptyRow()])
        setIsDirty(false)
        setSuccessMessage(null)
        setLoadState('ready')
      } catch (error) {
        if (controller.signal.aborted) {
          return
        }
        const message =
          error instanceof Error && error.message
            ? error.message
            : '기능리스트를 불러오는 중 예기치 않은 오류가 발생했습니다.'
        setErrorMessage(message)
        setLoadState('error')
      }
    }

    fetchData()

    return () => {
      controller.abort()
    }
  }, [backendUrl, projectId, reloadToken])

  const handleRetry = useCallback(() => {
    setReloadToken((token) => token + 1)
  }, [])

  const handleBack = useCallback(() => {
    const params = new URLSearchParams(window.location.search)
    params.delete('fileId')
    params.delete('fileName')
    params.delete('modifiedTime')
    const query = params.toString()
    navigate(`/projects/${encodeURIComponent(projectId)}${query ? `?${query}` : ''}`)
  }, [projectId])

  const handleChange = useCallback((index: number, key: keyof FeatureListRow, value: string) => {
    setRows((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], [key]: value }
      return next
    })
    setIsDirty(true)
    setSuccessMessage(null)
  }, [])

  const handleAddRow = useCallback(() => {
    setRows((prev) => [...prev, createEmptyRow()])
    setIsDirty(true)
    setSuccessMessage(null)
  }, [])

  const handleRemoveRow = useCallback((index: number) => {
    setRows((prev) => {
      if (prev.length === 1) {
        return [createEmptyRow()]
      }
      return prev.filter((_, rowIndex) => rowIndex !== index)
    })
    setIsDirty(true)
    setSuccessMessage(null)
  }, [])

  const handleSave = useCallback(async () => {
    setIsSaving(true)
    setSaveError(null)
    setSuccessMessage(null)
    try {
      const payload = {
        rows: rows.map((row) => ({
          majorCategory: row.majorCategory,
          middleCategory: row.middleCategory,
          minorCategory: row.minorCategory,
          featureOverview: row.featureOverview,
          featureDescription: row.featureDescription,
        })),
      }

      const searchParams = new URLSearchParams()
      if (fileId && fileId.trim().length > 0) {
        searchParams.set('fileId', fileId)
      }

      const response = await fetch(
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/feature-list${
          searchParams.toString() ? `?${searchParams.toString()}` : ''
        }`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
      )

      if (!response.ok) {
        const data = await response.json().catch(() => null)
        const detail =
          data && typeof data.detail === 'string'
            ? data.detail
            : '기능리스트를 저장하는 중 오류가 발생했습니다.'
        throw new Error(detail)
      }

      const result = (await response.json().catch(() => ({}))) as FeatureListResponse
      setIsDirty(false)
      setSuccessMessage('기능리스트를 저장했습니다.')
      if (typeof result.modifiedTime === 'string' && result.modifiedTime.trim().length > 0) {
        setModifiedTime(result.modifiedTime)
      }
      if (typeof result.fileName === 'string') {
        setFileName(result.fileName)
      }
      if (typeof result.fileId === 'string' && result.fileId.trim().length > 0) {
        setFileId(result.fileId.trim())
      }
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : '기능리스트를 저장하는 중 예기치 않은 오류가 발생했습니다.'
      setSaveError(message)
    } finally {
      setIsSaving(false)
    }
  }, [backendUrl, fileId, projectId, rows])

  const handleDownload = useCallback(async () => {
    setIsDownloading(true)
    setDownloadError(null)
    try {
      const searchParams = new URLSearchParams()
      if (fileId && fileId.trim().length > 0) {
        searchParams.set('fileId', fileId)
      }

      const response = await fetch(
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/feature-list/download${
          searchParams.toString() ? `?${searchParams.toString()}` : ''
        }`,
      )

      if (!response.ok) {
        const data = await response.json().catch(() => null)
        const detail =
          data && typeof data.detail === 'string'
            ? data.detail
            : '기능리스트 파일을 다운로드하지 못했습니다.'
        throw new Error(detail)
      }

      const blob = await response.blob()
      const disposition = response.headers.get('content-disposition')
      let downloadName = parseFileNameFromDisposition(disposition) || fileName || 'feature-list.xlsx'
      if (!downloadName.toLowerCase().endsWith('.xlsx')) {
        downloadName = `${downloadName.replace(/\.[^./\\]+$/, '')}.xlsx`
      }

      const objectUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = downloadName
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(objectUrl)
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : '기능리스트 파일을 다운로드하지 못했습니다.'
      setDownloadError(message)
    } finally {
      setIsDownloading(false)
    }
  }, [backendUrl, fileId, fileName, projectId])

  const isSaveDisabled = loadState !== 'ready' || isSaving || (!isDirty && rows.length > 0)

  return (
    <div className="feature-list-editor defect-workflow">
      <section className="defect-workflow__section" aria-labelledby="feature-summary">
        <div className="defect-workflow__section-heading">
          <h2 id="feature-summary" className="defect-workflow__title">
            기능리스트 정보
          </h2>
          <div className="defect-workflow__section-actions">
            <button type="button" className="defect-workflow__secondary" onClick={handleBack}>
              프로젝트로 돌아가기
            </button>
          </div>
        </div>
        <p className="defect-workflow__helper">
          {projectName} 프로젝트의 기능리스트 템플릿을 내려받아 수정한 뒤 저장할 수 있습니다.
        </p>
        <dl className="feature-list-editor__meta">
          <div className="feature-list-editor__meta-item">
            <dt>스프레드시트</dt>
            <dd>{fileName || '기능리스트 파일'}</dd>
          </div>
          <div className="feature-list-editor__meta-item">
            <dt>시트 이름</dt>
            <dd>{sheetName}</dd>
          </div>
          {formattedModified && (
            <div className="feature-list-editor__meta-item">
              <dt>마지막 수정</dt>
              <dd>{formattedModified}</dd>
            </div>
          )}
        </dl>
      </section>

      <section className="defect-workflow__section" aria-labelledby="feature-edit">
        <div className="defect-workflow__section-heading">
          <h2 id="feature-edit" className="defect-workflow__title">
            기능리스트 편집
          </h2>
          <div className="defect-workflow__section-actions">
            <button
              type="button"
              className="defect-workflow__secondary"
              onClick={handleDownload}
              disabled={loadState !== 'ready' || isDownloading}
            >
              {isDownloading ? '다운로드 중…' : '다운로드'}
            </button>
            <button
              type="button"
              className="defect-workflow__primary"
              onClick={handleSave}
              disabled={isSaveDisabled}
            >
              {isSaving ? '저장 중…' : '수정 완료'}
            </button>
          </div>
        </div>
        <p className="defect-workflow__helper">
          대·중·소 분류와 기능 개요, 상세 내용을 편집한 뒤 저장하세요. 저장된 내용은 드라이브의 기능리스트 파일에 반영됩니다.
        </p>

        {loadState === 'loading' && (
          <div className="defect-workflow__loading">기능리스트를 불러오는 중…</div>
        )}

        {loadState === 'error' && (
          <div className="feature-list-editor__error-panel">
            <p className="defect-workflow__status defect-workflow__status--error" role="alert">
              {errorMessage}
            </p>
            <button type="button" className="defect-workflow__secondary" onClick={handleRetry}>
              다시 시도
            </button>
          </div>
        )}

        {loadState === 'ready' && (
          <div className="feature-list-editor__workspace">
            <div className="defect-workflow__table-wrapper">
              <table className="defect-workflow__table">
                <thead>
                  <tr>
                    {tableColumns.map((column) => (
                      <th key={column.key}>{column.label}</th>
                    ))}
                    <th className="feature-list-editor__table-actions">작업</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, index) => (
                    <tr key={`feature-row-${index}`}>
                      {tableColumns.map((column) => (
                        <td key={`${column.key}-${index}`}>
                          {column.multiline ? (
                            <textarea
                              value={row[column.key]}
                              onChange={(event) => handleChange(index, column.key, event.target.value)}
                              className="feature-list-editor__textarea"
                              placeholder={column.placeholder}
                              rows={3}
                            />
                          ) : (
                            <input
                              type="text"
                              value={row[column.key]}
                              onChange={(event) => handleChange(index, column.key, event.target.value)}
                              className="feature-list-editor__table-input"
                              placeholder={column.placeholder}
                            />
                          )}
                        </td>
                      ))}
                      <td className="feature-list-editor__table-actions">
                        <button
                          type="button"
                          className="feature-list-editor__remove"
                          onClick={() => handleRemoveRow(index)}
                          aria-label="행 삭제"
                        >
                          삭제
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="feature-list-editor__footer">
              <button
                type="button"
                className="defect-workflow__secondary feature-list-editor__add"
                onClick={handleAddRow}
              >
                행 추가
              </button>
              {isDirty && (
                <span className="feature-list-editor__status-note" role="status">
                  저장되지 않은 변경 사항이 있습니다.
                </span>
              )}
              {successMessage && !isDirty && (
                <span className="defect-workflow__status defect-workflow__status--success" role="status">
                  {successMessage}
                </span>
              )}
            </div>

            {saveError && (
              <p className="defect-workflow__status defect-workflow__status--error" role="alert">
                {saveError}
              </p>
            )}
            {downloadError && (
              <p className="defect-workflow__status defect-workflow__status--error" role="alert">
                {downloadError}
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  )
}
