import './TestcaseWorkflow.css'

import { useCallback, useMemo, useRef, useState } from 'react'

interface FeatureRow {
  majorCategory: string
  middleCategory: string
  minorCategory: string
  featureDescription: string
}

interface ScenarioEntry {
  id: string
  scenario: string
  input: string
  expected: string
}

interface ScenarioGroupState {
  feature: FeatureRow
  scenarios: ScenarioEntry[]
  files: File[]
  scenarioCount: number
  status: 'idle' | 'loading' | 'success' | 'error'
  error: string | null
}

interface FinalRow extends ScenarioEntry {
  majorCategory: string
  middleCategory: string
  minorCategory: string
  testcaseId: string
  result: string
  detail: string
  note: string
}

interface TestcaseWorkflowProps {
  projectId: string
  backendUrl: string
}

type Step = 'feature' | 'scenarios' | 'review'

interface FinalizeResponseRow {
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

export function TestcaseWorkflow({ projectId, backendUrl }: TestcaseWorkflowProps) {
  const [step, setStep] = useState<Step>('feature')
  const [projectOverview, setProjectOverview] = useState<string>('')
  const [featureStatus, setFeatureStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [featureError, setFeatureError] = useState<string | null>(null)
  const [groups, setGroups] = useState<ScenarioGroupState[]>([])
  const [finalRows, setFinalRows] = useState<FinalRow[]>([])
  const [finalStatus, setFinalStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle')
  const [finalError, setFinalError] = useState<string | null>(null)
  const [finalFileName, setFinalFileName] = useState<string>('testcases.xlsx')
  const [finalCsv, setFinalCsv] = useState<string>('')
  const idRef = useRef(0)

  const handleUploadFeatureList = useCallback(
    async (file: File | null) => {
      if (!file) {
        return
      }

      setFeatureStatus('loading')
      setFeatureError(null)

      const formData = new FormData()
      formData.append('feature_list_file', file)

      try {
        const response = await fetch(
          `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/testcases/workflow/feature-list`,
          {
            method: 'POST',
            body: formData,
          },
        )

        if (!response.ok) {
          const payload = await response.json().catch(() => null)
          const detail = typeof payload?.detail === 'string' ? payload.detail : '기능리스트를 해석하지 못했습니다.'
          throw new Error(detail)
        }

        const payload = (await response.json()) as {
          rows?: FeatureRow[]
          projectOverview?: string
          fileName?: string
        }

        const rows = Array.isArray(payload.rows) ? payload.rows : []
        if (rows.length === 0) {
          throw new Error('기능리스트에서 항목을 찾을 수 없습니다.')
        }

        setProjectOverview(payload.projectOverview ?? '')
        setGroups(
          rows.map((feature) => ({
            feature,
            scenarios: [],
            files: [],
            scenarioCount: 3,
            status: 'idle',
            error: null,
          })),
        )
        setStep('scenarios')
        setFeatureStatus('idle')
      } catch (error) {
        const message = error instanceof Error ? error.message : '기능리스트 업로드 중 오류가 발생했습니다.'
        setFeatureStatus('error')
        setFeatureError(message)
      }
    },
    [backendUrl, projectId],
  )

  const handleUpdateGroupFiles = useCallback((index: number, files: FileList | null) => {
    setGroups((prev) => {
      if (index < 0 || index >= prev.length) {
        return prev
      }
      const nextFiles = files ? Array.from(files) : []
      const nextGroups = [...prev]
      nextGroups[index] = {
        ...prev[index],
        files: nextFiles,
      }
      return nextGroups
    })
  }, [])

  const handleChangeScenarioCount = useCallback((index: number, count: number) => {
    setGroups((prev) => {
      if (index < 0 || index >= prev.length) {
        return prev
      }
      const nextGroups = [...prev]
      nextGroups[index] = {
        ...prev[index],
        scenarioCount: count,
      }
      return nextGroups
    })
  }, [])

  const handleGenerateScenarios = useCallback(
    async (index: number) => {
      setGroups((prev) => {
        if (index < 0 || index >= prev.length) {
          return prev
        }
        const nextGroups = [...prev]
        nextGroups[index] = {
          ...prev[index],
          status: 'loading',
          error: null,
        }
        return nextGroups
      })

      const group = groups[index]
      if (!group) {
        return
      }

      const formData = new FormData()
      formData.append('major_category', group.feature.majorCategory)
      formData.append('middle_category', group.feature.middleCategory)
      formData.append('minor_category', group.feature.minorCategory)
      formData.append('feature_description', group.feature.featureDescription)
      formData.append('project_overview', projectOverview)
      formData.append('scenario_count', String(group.scenarioCount))
      group.files.forEach((file) => formData.append('attachments', file))

      try {
        const response = await fetch(
          `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/testcases/workflow/scenarios`,
          {
            method: 'POST',
            body: formData,
          },
        )

        if (!response.ok) {
          const payload = await response.json().catch(() => null)
          const detail = typeof payload?.detail === 'string' ? payload.detail : '테스트 시나리오를 생성하지 못했습니다.'
          throw new Error(detail)
        }

        const payload = (await response.json()) as { scenarios?: Array<{ scenario: string; input: string; expected: string }> }
        const scenarios = Array.isArray(payload.scenarios) ? payload.scenarios : []
        if (scenarios.length === 0) {
          throw new Error('생성된 테스트 시나리오가 없습니다.')
        }

        setGroups((prev) => {
          if (index < 0 || index >= prev.length) {
            return prev
          }
          const nextGroups = [...prev]
          const nextScenarios: ScenarioEntry[] = scenarios.map((entry) => {
            idRef.current += 1
            return {
              id: `scenario-${idRef.current}`,
              scenario: entry.scenario ?? '',
              input: entry.input ?? '',
              expected: entry.expected ?? '',
            }
          })

          nextGroups[index] = {
            ...prev[index],
            scenarios: nextScenarios,
            status: 'success',
            error: null,
          }
          return nextGroups
        })
      } catch (error) {
        const message = error instanceof Error ? error.message : '테스트 시나리오를 생성하지 못했습니다.'
        setGroups((prev) => {
          if (index < 0 || index >= prev.length) {
            return prev
          }
          const nextGroups = [...prev]
          nextGroups[index] = {
            ...prev[index],
            status: 'error',
            error: message,
          }
          return nextGroups
        })
      }
    },
    [backendUrl, groups, projectId, projectOverview],
  )

  const handleUpdateScenarioField = useCallback((groupIndex: number, scenarioId: string, key: 'scenario' | 'input' | 'expected', value: string) => {
    setGroups((prev) => {
      if (groupIndex < 0 || groupIndex >= prev.length) {
        return prev
      }
      const nextGroups = [...prev]
      const nextScenarios = prev[groupIndex].scenarios.map((scenario) =>
        scenario.id === scenarioId ? { ...scenario, [key]: value } : scenario,
      )
      nextGroups[groupIndex] = {
        ...prev[groupIndex],
        scenarios: nextScenarios,
      }
      return nextGroups
    })
  }, [])

  const handleRemoveScenario = useCallback((groupIndex: number, scenarioId: string) => {
    setGroups((prev) => {
      if (groupIndex < 0 || groupIndex >= prev.length) {
        return prev
      }
      const nextGroups = [...prev]
      nextGroups[groupIndex] = {
        ...prev[groupIndex],
        scenarios: prev[groupIndex].scenarios.filter((scenario) => scenario.id !== scenarioId),
      }
      return nextGroups
    })
  }, [])

  const handleAddScenario = useCallback((groupIndex: number) => {
    setGroups((prev) => {
      if (groupIndex < 0 || groupIndex >= prev.length) {
        return prev
      }
      idRef.current += 1
      const nextGroups = [...prev]
      nextGroups[groupIndex] = {
        ...prev[groupIndex],
        scenarios: [
          ...prev[groupIndex].scenarios,
          {
            id: `scenario-${idRef.current}`,
            scenario: '',
            input: '',
            expected: '',
          },
        ],
      }
      return nextGroups
    })
  }, [])

  const canProceedToReview = useMemo(
    () => groups.length > 0 && groups.every((group) => group.scenarios.length >= 3),
    [groups],
  )

  const handleFinalize = useCallback(async () => {
    setFinalStatus('loading')
    setFinalError(null)

    const payload = {
      projectOverview,
      groups: groups.map((group) => ({
        majorCategory: group.feature.majorCategory,
        middleCategory: group.feature.middleCategory,
        minorCategory: group.feature.minorCategory,
        featureDescription: group.feature.featureDescription,
        scenarios: group.scenarios.map((scenario) => ({
          scenario: scenario.scenario,
          input: scenario.input,
          expected: scenario.expected,
        })),
      })),
    }

    try {
      const response = await fetch(
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/testcases/workflow/finalize`,
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
        const detail = typeof body?.detail === 'string' ? body.detail : '테스트케이스를 완성하지 못했습니다.'
        throw new Error(detail)
      }

      const body = (await response.json()) as {
        rows?: FinalizeResponseRow[]
        fileName?: string
        csvText?: string
      }

      const rows = Array.isArray(body.rows) ? body.rows : []
      if (rows.length === 0) {
        throw new Error('생성된 테스트케이스가 없습니다.')
      }

      const mappedRows: FinalRow[] = rows.map((row) => {
        idRef.current += 1
        return {
          id: `final-${idRef.current}`,
          majorCategory: row.majorCategory ?? '',
          middleCategory: row.middleCategory ?? '',
          minorCategory: row.minorCategory ?? '',
          testcaseId: row.testcaseId ?? '',
          scenario: row.scenario ?? '',
          input: row.input ?? '',
          expected: row.expected ?? '',
          result: row.result ?? '미실행',
          detail: row.detail ?? '',
          note: row.note ?? '',
        }
      })

      setFinalRows(mappedRows)
      setFinalCsv(body.csvText ?? '')
      setFinalFileName(body.fileName ?? 'testcases.xlsx')
      setFinalStatus('success')
      setStep('review')
    } catch (error) {
      const message = error instanceof Error ? error.message : '테스트케이스를 완성하지 못했습니다.'
      setFinalStatus('error')
      setFinalError(message)
    }
  }, [backendUrl, groups, projectId, projectOverview])

  const handleUpdateFinalRow = useCallback(
    (rowId: string, key: keyof FinalRow, value: string) => {
      setFinalRows((prev) => prev.map((row) => (row.id === rowId ? { ...row, [key]: value } : row)))
    },
    [],
  )

  const handleDownloadXlsx = useCallback(async () => {
    if (finalRows.length === 0) {
      return
    }
    const payload = {
      rows: finalRows.map((row) => ({
        majorCategory: row.majorCategory,
        middleCategory: row.middleCategory,
        minorCategory: row.minorCategory,
        testcaseId: row.testcaseId,
        scenario: row.scenario,
        input: row.input,
        expected: row.expected,
        result: row.result,
        detail: row.detail,
        note: row.note,
      })),
    }

    try {
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
        const detail = typeof body?.detail === 'string' ? body.detail : '엑셀 파일을 다운로드하지 못했습니다.'
        throw new Error(detail)
      }

      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = finalFileName
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (error) {
      const message = error instanceof Error ? error.message : '엑셀 파일을 다운로드하지 못했습니다.'
      setFinalStatus('error')
      setFinalError(message)
    }
  }, [backendUrl, finalFileName, finalRows, projectId])

  const handleDownloadCsv = useCallback(() => {
    if (!finalCsv) {
      return
    }
    const blob = new Blob([finalCsv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = finalFileName.replace(/\.xlsx$/i, '.csv')
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }, [finalCsv, finalFileName])

  return (
    <div className="testcase-workflow">
      {step === 'feature' && (
        <section className="testcase-workflow__section" aria-labelledby="testcase-feature-step">
          <h2 id="testcase-feature-step" className="testcase-workflow__title">
            기능리스트 불러오기
          </h2>
          <p className="testcase-workflow__helper">
            테스트케이스를 작성할 기능리스트 파일을 업로드하세요. AI가 대분류/중분류/소분류 정보를 추출해 다음 단계에서 활용합니다.
          </p>
          <div className="testcase-workflow__uploader">
            <input
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={(event) => handleUploadFeatureList(event.target.files?.[0] ?? null)}
            />
            {featureStatus === 'loading' && (
              <div className="testcase-workflow__status testcase-workflow__status--loading">
                기능리스트를 분석하고 있습니다…
              </div>
            )}
            {featureStatus === 'error' && featureError && (
              <div className="testcase-workflow__status testcase-workflow__status--error">{featureError}</div>
            )}
          </div>
        </section>
      )}

      {step === 'scenarios' && (
        <section className="testcase-workflow__section" aria-labelledby="testcase-scenario-step">
          <h2 id="testcase-scenario-step" className="testcase-workflow__title">
            소분류별 테스트 시나리오 설계
          </h2>
          <p className="testcase-workflow__helper">
            각 소분류에 대한 참고 이미지를 첨부하고 테스트 시나리오를 생성하세요. AI는 기능 설명과 프로젝트 개요를 함께 참고합니다.
          </p>
          <div className="testcase-workflow__feature-list">
            {groups.map((group, index) => (
              <article key={`${group.feature.majorCategory}-${group.feature.minorCategory}-${index}`} className="testcase-workflow__card">
                <div className="testcase-workflow__card-header">
                  <span className="testcase-workflow__card-title">
                    {group.feature.majorCategory} / {group.feature.middleCategory} / {group.feature.minorCategory}
                  </span>
                  <span className="testcase-workflow__card-subtitle">프로젝트 개요: {projectOverview || '미제공'}</span>
                </div>
                <p className="testcase-workflow__card-description">{group.feature.featureDescription || '기능 설명이 제공되지 않았습니다.'}</p>

                <div className="testcase-workflow__controls">
                  <label>
                    <span>참고 이미지 첨부</span>
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={(event) => handleUpdateGroupFiles(index, event.target.files)}
                    />
                  </label>
                  <label>
                    <span>시나리오 수</span>
                    <select
                      className="testcase-workflow__select"
                      value={group.scenarioCount}
                      onChange={(event) => handleChangeScenarioCount(index, Number(event.target.value))}
                    >
                      {[3, 4, 5].map((count) => (
                        <option key={count} value={count}>
                          {count}개
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="testcase-workflow__button"
                    onClick={() => handleGenerateScenarios(index)}
                    disabled={group.status === 'loading'}
                  >
                    {group.status === 'loading' ? '생성 중…' : '시나리오 생성'}
                  </button>
                  <button
                    type="button"
                    className="testcase-workflow__secondary testcase-workflow__button"
                    onClick={() => handleAddScenario(index)}
                  >
                    시나리오 직접 추가
                  </button>
                </div>

                {group.files.length > 0 && (
                  <div className="testcase-workflow__helper">
                    첨부된 파일: {group.files.map((file) => file.name).join(', ')}
                  </div>
                )}

                {group.status === 'error' && group.error && (
                  <div className="testcase-workflow__status testcase-workflow__status--error">{group.error}</div>
                )}

                {group.scenarios.length > 0 && (
                  <div className="testcase-workflow__scenario-list">
                    {group.scenarios.map((scenario) => (
                      <div key={scenario.id} className="testcase-workflow__scenario">
                        <div className="testcase-workflow__scenario-fields">
                          <label>
                            <span>테스트 시나리오</span>
                            <textarea
                              className="testcase-workflow__textarea"
                              value={scenario.scenario}
                              onChange={(event) =>
                                handleUpdateScenarioField(index, scenario.id, 'scenario', event.target.value)
                              }
                            />
                          </label>
                          <label>
                            <span>입력(사전조건 포함)</span>
                            <textarea
                              className="testcase-workflow__textarea"
                              value={scenario.input}
                              onChange={(event) =>
                                handleUpdateScenarioField(index, scenario.id, 'input', event.target.value)
                              }
                            />
                          </label>
                          <label>
                            <span>기대 출력(사후조건 포함)</span>
                            <textarea
                              className="testcase-workflow__textarea"
                              value={scenario.expected}
                              onChange={(event) =>
                                handleUpdateScenarioField(index, scenario.id, 'expected', event.target.value)
                              }
                            />
                          </label>
                        </div>
                        <div className="testcase-workflow__scenario-actions">
                          <button
                            type="button"
                            className="testcase-workflow__secondary testcase-workflow__button"
                            onClick={() => handleRemoveScenario(index, scenario.id)}
                          >
                            시나리오 제거
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            ))}
          </div>

          <div className="testcase-workflow__step-actions">
            <button type="button" className="testcase-workflow__secondary testcase-workflow__button" onClick={() => setStep('feature')}>
              이전 단계
            </button>
            <button
              type="button"
              className="testcase-workflow__button"
              onClick={handleFinalize}
              disabled={!canProceedToReview || finalStatus === 'loading'}
            >
              {finalStatus === 'loading' ? '완료 중…' : '완료하고 테스트케이스 생성'}
            </button>
          </div>

          {finalStatus === 'error' && finalError && (
            <div className="testcase-workflow__status testcase-workflow__status--error">{finalError}</div>
          )}
        </section>
      )}

      {step === 'review' && (
        <section className="testcase-workflow__section" aria-labelledby="testcase-review-step">
          <h2 id="testcase-review-step" className="testcase-workflow__title">
            테스트케이스 검토 및 다운로드
          </h2>
          <p className="testcase-workflow__helper">
            생성된 테스트케이스를 검토하고 필요한 내용을 수정하세요. 수정된 내용은 즉시 다운로드할 수 있습니다.
          </p>

          {finalRows.length === 0 ? (
            <div className="testcase-workflow__empty">표시할 테스트케이스가 없습니다.</div>
          ) : (
            <div className="testcase-workflow__summary">
              <table className="testcase-workflow__table">
                <thead>
                  <tr>
                    <th>대분류</th>
                    <th>중분류</th>
                    <th>소분류</th>
                    <th>테스트 케이스 ID</th>
                    <th>테스트 시나리오</th>
                    <th>입력(사전조건 포함)</th>
                    <th>기대 출력(사후조건 포함)</th>
                    <th>테스트 결과</th>
                    <th>상세 테스트 결과</th>
                    <th>비고</th>
                  </tr>
                </thead>
                <tbody>
                  {finalRows.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <input
                          className="testcase-workflow__input"
                          value={row.majorCategory}
                          onChange={(event) => handleUpdateFinalRow(row.id, 'majorCategory', event.target.value)}
                        />
                      </td>
                      <td>
                        <input
                          className="testcase-workflow__input"
                          value={row.middleCategory}
                          onChange={(event) => handleUpdateFinalRow(row.id, 'middleCategory', event.target.value)}
                        />
                      </td>
                      <td>
                        <input
                          className="testcase-workflow__input"
                          value={row.minorCategory}
                          onChange={(event) => handleUpdateFinalRow(row.id, 'minorCategory', event.target.value)}
                        />
                      </td>
                      <td>
                        <input
                          className="testcase-workflow__input"
                          value={row.testcaseId}
                          onChange={(event) => handleUpdateFinalRow(row.id, 'testcaseId', event.target.value)}
                        />
                      </td>
                      <td>
                        <textarea
                          className="testcase-workflow__textarea"
                          value={row.scenario}
                          onChange={(event) => handleUpdateFinalRow(row.id, 'scenario', event.target.value)}
                        />
                      </td>
                      <td>
                        <textarea
                          className="testcase-workflow__textarea"
                          value={row.input}
                          onChange={(event) => handleUpdateFinalRow(row.id, 'input', event.target.value)}
                        />
                      </td>
                      <td>
                        <textarea
                          className="testcase-workflow__textarea"
                          value={row.expected}
                          onChange={(event) => handleUpdateFinalRow(row.id, 'expected', event.target.value)}
                        />
                      </td>
                      <td>
                        <input
                          className="testcase-workflow__input"
                          value={row.result}
                          onChange={(event) => handleUpdateFinalRow(row.id, 'result', event.target.value)}
                        />
                      </td>
                      <td>
                        <textarea
                          className="testcase-workflow__textarea"
                          value={row.detail}
                          onChange={(event) => handleUpdateFinalRow(row.id, 'detail', event.target.value)}
                        />
                      </td>
                      <td>
                        <textarea
                          className="testcase-workflow__textarea"
                          value={row.note}
                          onChange={(event) => handleUpdateFinalRow(row.id, 'note', event.target.value)}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="testcase-workflow__step-actions">
            <button
              type="button"
              className="testcase-workflow__secondary testcase-workflow__button"
              onClick={() => {
                setFinalStatus('idle')
                setFinalError(null)
                setStep('scenarios')
              }}
            >
              소분류 시나리오 단계로 돌아가기
            </button>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <button type="button" className="testcase-workflow__secondary testcase-workflow__button" onClick={handleDownloadCsv}>
                CSV 다운로드
              </button>
              <button type="button" className="testcase-workflow__button" onClick={handleDownloadXlsx}>
                엑셀 다운로드
              </button>
            </div>
          </div>

          {finalStatus === 'error' && finalError && (
            <div className="testcase-workflow__status testcase-workflow__status--error">{finalError}</div>
          )}
          {finalStatus === 'success' && (
            <div className="testcase-workflow__status testcase-workflow__status--success">
              테스트케이스가 생성되었습니다. 필요한 수정을 마치고 다운로드할 수 있습니다.
            </div>
          )}
        </section>
      )}
    </div>
  )
}
