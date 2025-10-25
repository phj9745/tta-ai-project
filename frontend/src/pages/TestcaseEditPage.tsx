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

interface TestcaseSessionData {
  projectId: string
  fileName: string
  rows: TestcaseRow[]
  xlsxBase64?: string
  createdAt?: number
}

interface EditableTestcaseRow extends TestcaseRow {
  id: string
}

interface TestcaseEditPageProps {
  projectId: string
}

type LoadState = 'loading' | 'ready' | 'error'
type DownloadState = 'idle' | 'loading' | 'success' | 'error'

type EditableFieldKey =
  | 'majorCategory'
  | 'middleCategory'
  | 'minorCategory'
  | 'testcaseId'
  | 'scenario'
  | 'input'
  | 'expected'
  | 'result'
  | 'detail'
  | 'note'

function ensureXlsxFileName(rawName: string): string {
  const trimmed = rawName.trim()
  if (!trimmed) {
    return 'testcases.xlsx'
  }
  if (trimmed.toLowerCase().endsWith('.xlsx')) {
    return trimmed
  }
  const withoutExtension = trimmed.replace(/\.[^./\\]+$/, '')
  return `${withoutExtension}.xlsx`
}

function blobFromBase64(base64: string, mimeType: string): Blob {
  const normalized = base64.trim()
  const binary = atob(normalized)
  const buffer = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    buffer[index] = binary.charCodeAt(index)
  }
  return new Blob([buffer], { type: mimeType })
}

function toBase64FromArrayBuffer(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte)
  })
  return btoa(binary)
}

export function TestcaseEditPage({ projectId }: TestcaseEditPageProps) {
  const backendUrl = getBackendUrl()
  const idRef = useRef(0)
  const createdAtRef = useRef<number | null>(null)

  const [sessionKey, setSessionKey] = useState<string | null>(null)
  const [rows, setRows] = useState<EditableTestcaseRow[]>([])
  const [fileName, setFileName] = useState<string>('testcases.xlsx')
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [infoMessage, setInfoMessage] = useState<string | null>(null)
  const [downloadState, setDownloadState] = useState<DownloadState>('idle')
  const [downloadMessage, setDownloadMessage] = useState<string | null>(null)
  const [isDirty, setIsDirty] = useState<boolean>(false)
  const [initialBase64, setInitialBase64] = useState<string | null>(null)

  useEffect(() => {
    setLoadState('loading')
    setErrorMessage(null)
    setInfoMessage(null)

    if (typeof window === 'undefined') {
      setErrorMessage('브라우저 환경에서만 테스트케이스를 수정할 수 있습니다.')
      setLoadState('error')
      return
    }

    const params = new URLSearchParams(window.location.search)
    const key = params.get('sessionKey')?.trim()

    if (!key) {
      setErrorMessage('테스트케이스 생성 결과를 찾을 수 없습니다. 워크플로를 다시 진행해 주세요.')
      setLoadState('error')
      return
    }

    let stored: string | null = null
    try {
      stored = window.sessionStorage.getItem(key)
    } catch (error) {
      console.warn('테스트케이스 세션 정보를 불러오지 못했습니다.', error)
      setErrorMessage('세션 정보를 불러오지 못했습니다. 다시 생성해 주세요.')
      setLoadState('error')
      return
    }

    if (!stored) {
      setErrorMessage('세션이 만료되었거나 삭제되었습니다. 테스트케이스 생성을 다시 진행해 주세요.')
      setLoadState('error')
      return
    }

    let parsed: TestcaseSessionData | null = null
    try {
      parsed = JSON.parse(stored) as TestcaseSessionData
    } catch (error) {
      console.warn('테스트케이스 세션 데이터를 해석하지 못했습니다.', error)
      setErrorMessage('저장된 테스트케이스 정보를 해석하지 못했습니다. 다시 생성해 주세요.')
      setLoadState('error')
      return
    }

    if (!parsed || parsed.projectId !== projectId) {
      setErrorMessage('다른 프로젝트의 세션 정보입니다. 해당 프로젝트에서 워크플로를 다시 실행해 주세요.')
      setLoadState('error')
      return
    }

    const normalizedRows = Array.isArray(parsed.rows) ? parsed.rows : []
    if (normalizedRows.length === 0) {
      setErrorMessage('테스트케이스 데이터가 비어 있습니다. 워크플로를 다시 실행해 주세요.')
      setLoadState('error')
      return
    }

    idRef.current = 0
    const editableRows = normalizedRows.map((row) => {
      idRef.current += 1
      return {
        id: `row-${idRef.current}`,
        majorCategory: row.majorCategory ?? '',
        middleCategory: row.middleCategory ?? '',
        minorCategory: row.minorCategory ?? '',
        testcaseId: row.testcaseId ?? '',
        scenario: row.scenario ?? '',
        input: row.input ?? '',
        expected: row.expected ?? '',
        result: row.result ?? 'P',
        detail: row.detail ?? '',
        note: row.note ?? '',
      }
    })

    setRows(editableRows)
    setFileName(parsed.fileName && parsed.fileName.trim().length > 0 ? parsed.fileName : 'testcases.xlsx')
    setInitialBase64(parsed.xlsxBase64 && parsed.xlsxBase64.trim().length > 0 ? parsed.xlsxBase64 : null)
    createdAtRef.current = typeof parsed.createdAt === 'number' ? parsed.createdAt : Date.now()
    setSessionKey(key)
    setIsDirty(false)
    setInfoMessage('생성된 테스트케이스를 수정한 뒤 엑셀로 다운로드할 수 있습니다.')
    setLoadState('ready')
  }, [projectId])

  useEffect(() => {
    if (!sessionKey) {
      return
    }
    if (typeof window === 'undefined') {
      return
    }

    try {
      const payload: TestcaseSessionData = {
        projectId,
        fileName,
        rows: rows.map(({ id, ...rest }) => ({ ...rest })),
        xlsxBase64: initialBase64 ?? undefined,
        createdAt: createdAtRef.current ?? Date.now(),
      }
      window.sessionStorage.setItem(sessionKey, JSON.stringify(payload))
    } catch (error) {
      console.warn('테스트케이스 세션 정보를 업데이트하지 못했습니다.', error)
    }
  }, [sessionKey, rows, fileName, initialBase64, projectId])

  const handleBack = useCallback(() => {
    if (typeof window === 'undefined') {
      return
    }
    const params = new URLSearchParams(window.location.search)
    params.delete('sessionKey')
    const query = params.toString()
    navigate(`/projects/${encodeURIComponent(projectId)}${query ? `?${query}` : ''}`)
  }, [projectId])

  const handleChangeField = useCallback((rowId: string, key: EditableFieldKey, value: string) => {
    setRows((prev) => prev.map((row) => (row.id === rowId ? { ...row, [key]: value } : row)))
    setIsDirty(true)
    setDownloadState('idle')
    setDownloadMessage(null)
  }, [])

  const handleFileNameChange = useCallback((value: string) => {
    setFileName(value)
  }, [])

  const hasRows = rows.length > 0

  const handleDownload = useCallback(async () => {
    if (!hasRows) {
      setDownloadState('error')
      setDownloadMessage('다운로드할 테스트케이스가 없습니다.')
      return
    }

    setDownloadState('loading')
    setDownloadMessage(null)

    const effectiveName = ensureXlsxFileName(fileName)

    try {
      if (!isDirty && initialBase64) {
        const blob = blobFromBase64(
          initialBase64,
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = effectiveName
        document.body.appendChild(link)
        link.click()
        link.remove()
        URL.revokeObjectURL(url)
        setDownloadState('success')
        setDownloadMessage('초기 생성된 엑셀 파일을 다운로드했습니다.')
        return
      }

      const payload = {
        rows: rows.map(({ id, ...rest }) => ({ ...rest })),
      }

      const response = await fetch(
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/testcases/workflow/export`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        },
      )

      if (!response.ok) {
        const body = await response.json().catch(() => null)
        const detail =
          body && typeof body.detail === 'string'
            ? body.detail
            : '엑셀 파일을 생성하지 못했습니다.'
        throw new Error(detail)
      }

      const blob = await response.blob()
      const arrayBuffer = await blob.arrayBuffer()
      setInitialBase64(toBase64FromArrayBuffer(arrayBuffer))
      createdAtRef.current = Date.now()
      setIsDirty(false)

      const downloadUrl = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = downloadUrl
      anchor.download = effectiveName
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(downloadUrl)

      setDownloadState('success')
      setDownloadMessage('수정된 내용을 반영한 엑셀 파일을 다운로드했습니다.')
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : '엑셀 파일 다운로드 중 오류가 발생했습니다.'
      setDownloadState('error')
      setDownloadMessage(message)
    }
  }, [backendUrl, fileName, hasRows, initialBase64, isDirty, projectId, rows])

  const statusContent = useMemo(() => {
    if (downloadState === 'error' && downloadMessage) {
      return (
        <div className="testcase-edit__status testcase-edit__status--error" role="alert">
          {downloadMessage}
        </div>
      )
    }
    if (downloadState === 'success' && downloadMessage) {
      return <div className="testcase-edit__status testcase-edit__status--success">{downloadMessage}</div>
    }
    if (infoMessage) {
      return <div className="testcase-edit__status testcase-edit__status--info">{infoMessage}</div>
    }
    return null
  }, [downloadState, downloadMessage, infoMessage])

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
        <button type="button" className="testcase-edit__button" onClick={handleBack}>
          테스트케이스 워크플로로 돌아가기
        </button>
      </div>
    )
  }

  return (
    <div className="testcase-edit">
      <header className="testcase-edit__header">
        <button type="button" className="testcase-edit__back" onClick={handleBack}>
          ← 테스트케이스 워크플로로 돌아가기
        </button>
        <h1 className="testcase-edit__title">테스트케이스 수정 및 다운로드</h1>
        <p className="testcase-edit__description">
          각 테스트케이스의 내용을 검토하고 필요한 수정을 반영한 뒤 엑셀 파일로 저장하세요.
        </p>
      </header>

      {statusContent}

      <div className="testcase-edit__controls" role="group" aria-label="다운로드 옵션">
        <label className="testcase-edit__file-label">
          <span>다운로드 파일명</span>
          <input
            className="testcase-edit__input"
            value={fileName}
            onChange={(event) => handleFileNameChange(event.target.value)}
            placeholder="예: project-testcases.xlsx"
          />
        </label>
        <button
          type="button"
          className="testcase-edit__button"
          onClick={handleDownload}
          disabled={downloadState === 'loading' || !hasRows}
        >
          {downloadState === 'loading' ? '엑셀 생성 중…' : '엑셀 다운로드'}
        </button>
      </div>

      <div className="testcase-edit__table-wrapper">
        {hasRows ? (
          <table className="testcase-edit__table">
            <thead>
              <tr>
                <th>대분류</th>
                <th>중분류</th>
                <th>소분류</th>
                <th>TC_ID</th>
                <th>테스트 시나리오</th>
                <th>입력(사전조건 포함)</th>
                <th>기대 출력(사후조건 포함)</th>
                <th>테스트 결과</th>
                <th>상세 테스트 결과</th>
                <th>비고</th>
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
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="testcase-edit__status testcase-edit__status--info">
            표시할 테스트케이스가 없습니다.
          </div>
        )}
      </div>
    </div>
  )
}
