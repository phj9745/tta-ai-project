import { useMemo, useState } from 'react'
import { getBackendUrl } from '../config'

type Row = {
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

const API_CANDIDATES = ['/api/testcases', '/testcases', '']

async function fetchWithFallback(path: '/generate' | '/export', init: RequestInit) {
  const base = getBackendUrl()
  let lastError: Error | null = null
  const tried: string[] = []

  for (const prefix of API_CANDIDATES) {
    const target = `${base}${prefix}${path}`
    tried.push(target)
    try {
      const response = await fetch(target, init)
      if (response.status === 404) {
        continue
      }
      return response
    } catch (error) {
      lastError = error instanceof Error ? error : new Error('요청 실패')
    }
  }

  if (lastError) {
    throw lastError
  }
  throw new Error(`API 경로를 찾을 수 없습니다. 시도한 경로: ${tried.join(', ')}. 서버 재시작 후 다시 시도해 주세요.`)
}


async function tryLegacyGenerate(base: string, files: File[], projectOverview: string): Promise<boolean> {
  const form = new FormData()
  form.append('menu_id', 'testcase-generation')
  files.forEach((file) => form.append('files', file))

  const fileMetadata = files.map((file, index) =>
    index === 0
      ? { role: 'required', id: 'user-manual', label: '사용자 매뉴얼' }
      : { role: 'additional', description: '추가 문서' },
  )
  form.append('file_metadata', JSON.stringify(fileMetadata))

  if (projectOverview.trim()) {
    form.append('project_overview', projectOverview.trim())
  }

  const response = await fetch(`${base}/api/drive/projects/quick-testcase/generate`, {
    method: 'POST',
    body: form,
  })

  if (!response.ok) {
    return false
  }

  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('spreadsheetml')) {
    return false
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'testcases.xlsx'
  a.click()
  URL.revokeObjectURL(url)
  return true
}

export function TestcaseQuickPage() {
  const [files, setFiles] = useState<File[]>([])
  const [overview, setOverview] = useState('')
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const canGenerate = useMemo(() => files.length > 0 && !loading, [files.length, loading])

  const handleGenerate = async () => {
    if (!canGenerate) return
    setLoading(true)
    setError(null)
    setNotice(null)

    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    form.append('project_overview', overview)

    try {
      const response = await fetchWithFallback('/generate', {
        method: 'POST',
        body: form,
      })

      if (!response.ok) {
        if (response.status === 413) {
          throw new Error('업로드 용량이 너무 큽니다. 파일 크기를 줄이거나 문서를 나눠서 업로드해 주세요.')
        }
        const payload = await response.json().catch(() => ({}))
        throw new Error(payload?.detail ?? '테스트케이스 생성에 실패했습니다.')
      }

      const payload = (await response.json()) as { rows: Row[] }
      setRows(payload.rows ?? [])
    } catch (e) {
      const message = e instanceof Error ? e.message : '오류가 발생했습니다.'
      if (message.includes('API 경로를 찾을 수 없습니다')) {
        const legacyOk = await tryLegacyGenerate(getBackendUrl(), files, overview)
        if (legacyOk) {
          setNotice('구버전 서버 경로로 테스트케이스를 생성해 다운로드했습니다. 서버 업데이트 후 표 미리보기도 사용할 수 있습니다.')
          setRows([])
          return
        }
      }
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async () => {
    if (!rows.length) return

    const response = await fetchWithFallback('/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rows }),
    })

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}))
      setError(payload?.detail ?? '엑셀 다운로드에 실패했습니다.')
      return
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'testcases.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="quick-page">
      <section className="hero">
        <p className="hero__eyebrow">TESTCASE ONLY</p>
        <h1>문서 업로드 한 번으로 테스트케이스 생성</h1>
        <p className="hero__subtitle">
          사용자 매뉴얼/기능정의서 같은 문서를 올리면, 기능 분석부터 테스트케이스 표 작성까지 한 번에 수행합니다.
        </p>
      </section>

      <section className="card guide-card">
        <h2>어떤 문서를 올리면 되나요?</h2>
        <ul>
          <li>
            <strong>필수(최소 1개):</strong> 사용자 매뉴얼, 기능정의서, 요구사항 명세서
          </li>
          <li>
            <strong>추가(선택):</strong> 기존 기능리스트, 화면 정의서, 정책 문서
          </li>
          <li>
            <strong>지원 형식:</strong> PDF, DOCX, XLSX, CSV
          </li>
        </ul>
      </section>

      <section className="card form-card">
        <label className="field-label" htmlFor="overview">프로젝트 개요 (선택)</label>
        <textarea
          id="overview"
          placeholder="예) 전자결재 웹서비스, 결재 상신/승인/반려/이력조회 기능 중심"
          value={overview}
          onChange={(event) => setOverview(event.target.value)}
        />

        <label className="field-label" htmlFor="docs">참고 문서 업로드</label>
        <input
          id="docs"
          type="file"
          multiple
          accept=".pdf,.docx,.xlsx,.csv"
          onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
        />

        <p className="file-count">선택된 파일: {files.length}개</p>

        <div className="actions">
          <button className="btn btn--primary" onClick={handleGenerate} disabled={!canGenerate}>
            {loading ? '생성 중...' : '테스트케이스 생성'}
          </button>
          <button className="btn btn--ghost" onClick={handleExport} disabled={!rows.length || loading}>
            엑셀 다운로드
          </button>
        </div>

        {notice ? <p className="notice">{notice}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </section>

      <section className="card result-card">
        <div className="result-header">
          <h2>생성 결과</h2>
          <span>{rows.length}건</span>
        </div>

        {rows.length > 0 ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>대분류</th>
                  <th>중분류</th>
                  <th>소분류</th>
                  <th>ID</th>
                  <th>시나리오</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={`${row.testcaseId}-${index}`}>
                    <td>{row.majorCategory || '-'}</td>
                    <td>{row.middleCategory || '-'}</td>
                    <td>{row.minorCategory || '-'}</td>
                    <td>{row.testcaseId || '-'}</td>
                    <td>{row.scenario || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty">문서를 업로드하고 [테스트케이스 생성]을 눌러주세요.</p>
        )}
      </section>
    </div>
  )
}
