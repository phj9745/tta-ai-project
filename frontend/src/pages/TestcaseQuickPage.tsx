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

export function TestcaseQuickPage() {
  const [files, setFiles] = useState<File[]>([])
  const [overview, setOverview] = useState('')
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canGenerate = useMemo(() => files.length > 0 && !loading, [files.length, loading])

  const handleGenerate = async () => {
    if (!canGenerate) return
    setLoading(true)
    setError(null)

    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    form.append('project_overview', overview)

    try {
      const response = await fetch(`${getBackendUrl()}/api/testcases/generate`, {
        method: 'POST',
        body: form,
      })
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        throw new Error(payload?.detail ?? '테스트케이스 생성에 실패했습니다.')
      }
      const payload = (await response.json()) as { rows: Row[] }
      setRows(payload.rows ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : '오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async () => {
    if (!rows.length) return

    const response = await fetch(`${getBackendUrl()}/api/testcases/export`, {
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
      <h1>테스트케이스 빠른 생성</h1>
      <p>문서를 업로드하면 기능 분석부터 테스트케이스 문서 생성까지 한 번에 처리합니다.</p>
      <textarea
        placeholder="프로젝트 개요(선택)"
        value={overview}
        onChange={(event) => setOverview(event.target.value)}
      />
      <input
        type="file"
        multiple
        accept=".pdf,.docx,.xlsx,.csv"
        onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
      />
      <button onClick={handleGenerate} disabled={!canGenerate}>
        {loading ? '생성 중...' : '테스트케이스 생성'}
      </button>
      <button onClick={handleExport} disabled={!rows.length || loading}>
        엑셀 다운로드
      </button>
      {error ? <p className="error">{error}</p> : null}

      {rows.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>대분류</th><th>중분류</th><th>소분류</th><th>ID</th><th>시나리오</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.testcaseId}-${index}`}>
                <td>{row.majorCategory}</td>
                <td>{row.middleCategory}</td>
                <td>{row.minorCategory}</td>
                <td>{row.testcaseId}</td>
                <td>{row.scenario}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  )
}
