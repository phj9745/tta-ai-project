import './TestcaseEditPage.css'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { getBackendUrl } from '../config'
import { navigate } from '../navigation'

interface TestcaseRow {
  majorCategory: string
  middleCategory: string
  minorCategory: string
  testcaseId: string
  scenario: string
  input: string
  expected: string
  result: string
  detail: string
  note: string
}

interface EditableTestcaseRow extends TestcaseRow {
  id: string
}

interface TestcaseResponse {
  fileId?: string
  fileName?: string
  sheetName?: string
  startRow?: number
  headers?: string[]
  rows?: TestcaseRow[]
  modifiedTime?: string
}

type LoadState = 'loading' | 'ready' | 'error'

type SaveState = 'idle' | 'success' | 'error'

const DEFAULT_HEADERS = [
  '대분류',
  '중분류',
  '소분류',
  '테스트 케이스 ID',
  '테스트 시나리오',
  '입력(사전조건 포함)',
  '기대 출력(사후조건 포함)',
  '테스트 결과',
  '상세 테스트 결과',
  '비고',
]

function normalizeRow(row: Partial<TestcaseRow> | null | undefined): TestcaseRow {
  return {
    majorCategory: typeof row?.majorCategory === 'string' ? row.majorCategory : '',
    middleCategory: typeof row?.middleCategory === 'string' ? row.middleCategory : '',
    minorCategory: typeof row?.minorCategory === 'string' ? row.minorCategory : '',
    testcaseId: typeof row?.testcaseId === 'string' ? row.testcaseId : '',
    scenario: typeof row?.scenario === 'string' ? row.scenario : '',
    input: typeof row?.input === 'string' ? row.input : '',
    expected: typeof row?.expected === 'string' ? row.expected : '',
    result: typeof row?.result === 'string' ? row.result : '',
    detail: typeof row?.detail === 'string' ? row.detail : '',
    note: typeof row?.note === 'string' ? row.note : '',
  }
}

function createEmptyRow(): TestcaseRow {
  return {
    majorCategory: '',
    middleCategory: '',
    minorCategory: '',
    testcaseId: '',
    scenario: '',
    input: '',
    expected: '',
    result: 'P',
    detail: '',
    note: '',
  }
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

interface TestcaseEditPageProps {
  projectId: string
}

export function TestcaseEditPage({ projectId }: TestcaseEditPageProps) {
  const backendUrl = useMemo(() => getBackendUrl(), [])
  const idRef = useRef(0)

  const [fileId, setFileId] = useState<string | null>(() => {
    if (typeof window === 'undefined') {
      return null
    }
    const params = new URLSearchParams(window.location.search)
    const value = params.get('fileId')
    return value && value.trim().length > 0 ? value.trim() : null
  })
  const [fileName, setFileName] = useState<string>(() => {
    if (typeof window === 'undefined') {
      return 'testcases.xlsx'
    }
    const params = new URLSearchParams(window.location.search)
    const value = params.get('fileName')
    return value && value.trim().length > 0 ? value.trim() : 'testcases.xlsx'
  })
  const [sheetName, setSheetName] = useState<string>('테스트케이스')
  const [headers, setHeaders] = useState<string[]>(() => [...DEFAULT_HEADERS])
  const [modifiedTime, setModifiedTime] = useState<string | undefined>(() => {
    if (typeof window === 'undefined') {
      return undefined
    }
    const params = new URLSearchParams(window.location.search)
    const value = params.get('modifiedTime')
    return value ?? undefined
  })
  const [rows, setRows] = useState<EditableTestcaseRow[]>([])
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isDirty, setIsDirty] = useState<boolean>(false)
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState<boolean>(false)
  const [isDownloading, setIsDownloading] = useState<boolean>(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  const projectName = useMemo(() => {
    if (typeof window === 'undefined') {
      return projectId
    }
    const params = new URLSearchParams(window.location.search)
    return params.get('name') ?? projectId
  }, [projectId])

  const formattedModified = useMemo(() => formatTimestamp(modifiedTime), [modifiedTime])

  useEffect(() => {
    if (typeof window === 'undefined') {
      setErrorMessage('브라우저 환경에서만 테스트케이스를 수정할 수 있습니다.')
      setLoadState('error')
      return
    }

    const controller = new AbortController()
    setLoadState('loading')
    setErrorMessage(null)

    const params = new URLSearchParams(window.location.search)
    const requestedFileId = params.get('fileId')?.trim() ?? ''
    const requestedFileName = params.get('fileName')?.trim() ?? ''
    const requestedModified = params.get('modifiedTime')?.trim() ?? ''

    const searchParams = new URLSearchParams()
    if (requestedFileId) {
      searchParams.set('fileId', requestedFileId)
    }

    async function fetchData() {
      try {
        const response = await fetch(
          `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/testcases${
            searchParams.toString() ? `?${searchParams.toString()}` : ''
          }`,
          { signal: controller.signal },
        )

        if (!response.ok) {
          const payload = await response.json().catch(() => null)
          const detail =
            payload && typeof payload.detail === 'string'
              ? payload.detail
              : '테스트케이스를 불러오는 중 오류가 발생했습니다.'
          throw new Error(detail)
        }

        const payload = (await response.json()) as TestcaseResponse
        if (controller.signal.aborted) {
          return
        }

        const nextHeaders = Array.isArray(payload.headers)
          ? payload.headers.filter((item): item is string => typeof item === 'string')
          : undefined
        if (nextHeaders && nextHeaders.length >= DEFAULT_HEADERS.length) {
          const merged = DEFAULT_HEADERS.map((fallback, index) => {
            const candidate = nextHeaders[index]
            if (!candidate || candidate.trim().length === 0) {
              return fallback
            }
            return candidate.trim()
          })
          setHeaders(merged)
        } else {
          setHeaders([...DEFAULT_HEADERS])
        }

        setSheetName(payload.sheetName?.trim() || '테스트케이스')

        const effectiveFileName =
          typeof payload.fileName === 'string' && payload.fileName.trim().length > 0
            ? payload.fileName.trim()
            : requestedFileName || 'testcases.xlsx'
        setFileName(effectiveFileName)

        const effectiveModified = payload.modifiedTime ?? (requestedModified || undefined)
        setModifiedTime(effectiveModified || undefined)

        const effectiveFileId =
          typeof payload.fileId === 'string' && payload.fileId.trim().length > 0
            ? payload.fileId.trim()
            : requestedFileId || ''
        setFileId(effectiveFileId ? effectiveFileId : null)

        const fetchedRows = Array.isArray(payload.rows)
          ? payload.rows.map((row) => normalizeRow(row))
          : []

        idRef.current = 0
        const editableRows: EditableTestcaseRow[] =
          fetchedRows.length > 0
            ? fetchedRows.map((row) => {
                idRef.current += 1
                return { id: `row-${idRef.current}`, ...row }
              })
            : (() => {
                idRef.current += 1
                return [{ id: `row-${idRef.current}`, ...createEmptyRow() }]
              })()

        setRows(editableRows)
        setIsDirty(false)
        setSaveState('idle')
        setSaveError(null)
        setDownloadError(null)
        setLoadState('ready')
      } catch (error) {
        if (controller.signal.aborted) {
          return
        }
        const message =
          error instanceof Error && error.message
            ? error.message
            : '테스트케이스를 불러오는 중 예기치 않은 오류가 발생했습니다.'
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
    if (typeof window === 'undefined') {
      return
    }
    const params = new URLSearchParams(window.location.search)
    params.delete('fileId')
    params.delete('fileName')
    params.delete('modifiedTime')
    const query = params.toString()
    navigate(`/projects/${encodeURIComponent(projectId)}${query ? `?${query}` : ''}`)
  }, [projectId])

  const handleChangeField = useCallback((rowId: string, key: keyof TestcaseRow, value: string) => {
    setRows((prev) =>
      prev.map((row) => (row.id === rowId ? { ...row, [key]: value } : row)),
    )
    setIsDirty(true)
    setSaveState('idle')
    setSaveError(null)
  }, [])

  const handleAddRow = useCallback(() => {
    idRef.current += 1
    setRows((prev) => [...prev, { id: `row-${idRef.current}`, ...createEmptyRow() }])
    setIsDirty(true)
    setSaveState('idle')
    setSaveError(null)
  }, [])

  const handleRemoveRow = useCallback((rowId: string) => {
    setRows((prev) => {
      if (prev.length <= 1) {
        return prev
      }
      const next = prev.filter((row) => row.id !== rowId)
      if (next.length === 0) {
        idRef.current += 1
        return [{ id: `row-${idRef.current}`, ...createEmptyRow() }]
      }
      return next
    })
    setIsDirty(true)
    setSaveState('idle')
    setSaveError(null)
  }, [])

  const handleSave = useCallback(async () => {
    setIsSaving(true)
    setSaveError(null)
    setSaveState('idle')
    try {
      const payload = {
        rows: rows.map(({ id, ...rest }) => ({ ...rest })),
      }
      const searchParams = new URLSearchParams()
      if (fileId && fileId.trim().length > 0) {
        searchParams.set('fileId', fileId)
      }

      const response = await fetch(
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/testcases${
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
            : '테스트케이스를 저장하는 중 오류가 발생했습니다.'
        throw new Error(detail)
      }

      const result = (await response.json().catch(() => ({}))) as TestcaseResponse
      setIsDirty(false)
      setSaveState('success')
      if (typeof result.modifiedTime === 'string' && result.modifiedTime.trim().length > 0) {
        setModifiedTime(result.modifiedTime.trim())
      }
      if (typeof result.fileName === 'string' && result.fileName.trim().length > 0) {
        setFileName(result.fileName.trim())
      }
      if (typeof result.fileId === 'string' && result.fileId.trim().length > 0) {
        setFileId(result.fileId.trim())
      }
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : '테스트케이스를 저장하는 중 예기치 않은 오류가 발생했습니다.'
      setSaveError(message)
      setSaveState('error')
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
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/testcases/download${
          searchParams.toString() ? `?${searchParams.toString()}` : ''
        }`,
      )

      if (!response.ok) {
        const data = await response.json().catch(() => null)
        const detail =
          data && typeof data.detail === 'string'
            ? data.detail
            : '테스트케이스 파일을 다운로드하지 못했습니다.'
        throw new Error(detail)
      }

      const blob = await response.blob()
      const disposition = response.headers.get('content-disposition')
      let downloadName = parseFileNameFromDisposition(disposition) || fileName || 'testcases.xlsx'
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
          : '테스트케이스 파일을 다운로드하지 못했습니다.'
      setDownloadError(message)
    } finally {
      setIsDownloading(false)
    }
  }, [backendUrl, fileId, fileName, projectId])

  const hasRows = rows.length > 0

  const statusMessage = useMemo(() => {
    if (saveState === 'success') {
      return '테스트케이스를 저장했습니다.'
    }
    if (saveState === 'error' && saveError) {
      return saveError
    }
    if (downloadError) {
      return downloadError
    }
    return null
  }, [downloadError, saveError, saveState])

  const statusVariant = useMemo(() => {
    if (saveState === 'success') {
      return 'success'
    }
    if ((saveState === 'error' && saveError) || downloadError) {
      return 'error'
    }
    return null
  }, [downloadError, saveError, saveState])

  if (loadState === 'loading') {
    return (
      <div className="testcase-edit">
        <div className="testcase-edit__loading" role="status">
          테스트케이스 정보를 불러오고 있습니다…
        </div>
      </div>
    )
  }

  if (loadState === 'error') {
    return (
      <div className="testcase-edit">
        <div className="testcase-edit__status testcase-edit__status--error" role="alert">
          {errorMessage || '테스트케이스 정보를 불러올 수 없습니다.'}
        </div>
        <div className="testcase-edit__actions">
          <button type="button" className="testcase-edit__button" onClick={handleRetry}>
            다시 시도
          </button>
          <button type="button" className="testcase-edit__secondary" onClick={handleBack}>
            프로젝트로 돌아가기
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="testcase-edit">
      <header className="testcase-edit__header">
        <button type="button" className="testcase-edit__back" onClick={handleBack}>
          ← 프로젝트로 돌아가기
        </button>
        <h1 className="testcase-edit__title">테스트케이스 수정 및 다운로드</h1>
        <p className="testcase-edit__description">
          {projectName} 프로젝트의 테스트케이스 파일을 검토하고 필요한 변경 사항을 저장한 뒤 엑셀로 다운로드하세요.
        </p>
        <dl className="testcase-edit__meta">
          <div>
            <dt>스프레드시트</dt>
            <dd>{fileName}</dd>
          </div>
          <div>
            <dt>시트 이름</dt>
            <dd>{sheetName}</dd>
          </div>
          {formattedModified && (
            <div>
              <dt>마지막 수정</dt>
              <dd>{formattedModified}</dd>
            </div>
          )}
        </dl>
      </header>

      {statusMessage && statusVariant === 'success' && (
        <div className="testcase-edit__status testcase-edit__status--success">{statusMessage}</div>
      )}
      {statusMessage && statusVariant === 'error' && (
        <div className="testcase-edit__status testcase-edit__status--error" role="alert">
          {statusMessage}
        </div>
      )}

      <div className="testcase-edit__toolbar" role="group" aria-label="테스트케이스 작업">
        <button type="button" className="testcase-edit__secondary" onClick={handleAddRow}>
          행 추가
        </button>
        <button
          type="button"
          className="testcase-edit__button"
          onClick={handleSave}
          disabled={isSaving || !hasRows || !isDirty}
        >
          {isSaving ? '저장 중…' : '변경 사항 저장'}
        </button>
        <button
          type="button"
          className="testcase-edit__button"
          onClick={handleDownload}
          disabled={isDownloading || !hasRows}
        >
          {isDownloading ? '다운로드 준비 중…' : '엑셀 다운로드'}
        </button>
      </div>

      <div className="testcase-edit__table-wrapper">
        {hasRows ? (
          <table className="testcase-edit__table">
            <thead>
              <tr>
                <th>{headers[0]}</th>
                <th>{headers[1]}</th>
                <th>{headers[2]}</th>
                <th>{headers[3]}</th>
                <th>{headers[4]}</th>
                <th>{headers[5]}</th>
                <th>{headers[6]}</th>
                <th>{headers[7]}</th>
                <th>{headers[8]}</th>
                <th>{headers[9]}</th>
                <th className="testcase-edit__actions-cell">작업</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <input
                      className="testcase-edit__input"
                      value={row.majorCategory}
                      onChange={(event) => handleChangeField(row.id, 'majorCategory', event.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      className="testcase-edit__input"
                      value={row.middleCategory}
                      onChange={(event) => handleChangeField(row.id, 'middleCategory', event.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      className="testcase-edit__input"
                      value={row.minorCategory}
                      onChange={(event) => handleChangeField(row.id, 'minorCategory', event.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      className="testcase-edit__input"
                      value={row.testcaseId}
                      onChange={(event) => handleChangeField(row.id, 'testcaseId', event.target.value)}
                    />
                  </td>
                  <td>
                    <textarea
                      className="testcase-edit__textarea"
                      value={row.scenario}
                      onChange={(event) => handleChangeField(row.id, 'scenario', event.target.value)}
                    />
                  </td>
                  <td>
                    <textarea
                      className="testcase-edit__textarea"
                      value={row.input}
                      onChange={(event) => handleChangeField(row.id, 'input', event.target.value)}
                    />
                  </td>
                  <td>
                    <textarea
                      className="testcase-edit__textarea"
                      value={row.expected}
                      onChange={(event) => handleChangeField(row.id, 'expected', event.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      className="testcase-edit__input"
                      value={row.result}
                      onChange={(event) => handleChangeField(row.id, 'result', event.target.value)}
                    />
                  </td>
                  <td>
                    <textarea
                      className="testcase-edit__textarea"
                      value={row.detail}
                      onChange={(event) => handleChangeField(row.id, 'detail', event.target.value)}
                    />
                  </td>
                  <td>
                    <textarea
                      className="testcase-edit__textarea"
                      value={row.note}
                      onChange={(event) => handleChangeField(row.id, 'note', event.target.value)}
                    />
                  </td>
                  <td className="testcase-edit__actions-cell">
                    <button
                      type="button"
                      className="testcase-edit__remove"
                      onClick={() => handleRemoveRow(row.id)}
                      disabled={rows.length <= 1}
                    >
                      삭제
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="testcase-edit__status testcase-edit__status--info">표시할 테스트케이스가 없습니다.</div>
        )}
      </div>
    </div>
  )
}
