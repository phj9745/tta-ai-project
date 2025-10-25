import './TestcaseWorkflow.css'

import { useCallback, useMemo, useRef, useState } from 'react'

import { navigate } from '../../navigation'

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

interface TestcaseWorkflowProps {
  projectId: string
  backendUrl: string
}

type Step = 'feature' | 'scenarios'

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

interface FinalizeResponsePayload {
  rows?: FinalizeResponseRow[]
  fileName?: string
  xlsxBase64?: string
}

export function TestcaseWorkflow({ projectId, backendUrl }: TestcaseWorkflowProps) {
  const [step, setStep] = useState<Step>('feature')
  const [projectOverview, setProjectOverview] = useState<string>('')
  const [featureStatus, setFeatureStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [featureError, setFeatureError] = useState<string | null>(null)
  const [groups, setGroups] = useState<ScenarioGroupState[]>([])
  const [finalStatus, setFinalStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [finalError, setFinalError] = useState<string | null>(null)
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

      const body = (await response.json()) as FinalizeResponsePayload

      const rows = Array.isArray(body.rows) ? body.rows : []
      if (rows.length === 0) {
        throw new Error('생성된 테스트케이스가 없습니다.')
      }

      const sessionData = {
        projectId,
        fileName:
          typeof body.fileName === 'string' && body.fileName.trim().length > 0
            ? body.fileName
            : 'testcases.xlsx',
        xlsxBase64: typeof body.xlsxBase64 === 'string' ? body.xlsxBase64 : '',
        rows,
        createdAt: Date.now(),
      }

      let sessionKey = ''
      try {
        sessionKey = `testcase-workflow-${projectId}-${Date.now()}`
        if (typeof window !== 'undefined' && window.sessionStorage) {
          window.sessionStorage.setItem(sessionKey, JSON.stringify(sessionData))
        }
      } catch (storageError) {
        console.warn('테스트케이스 세션 정보를 저장하지 못했습니다.', storageError)
        sessionKey = ''
      }

      if (!sessionKey) {
        throw new Error('브라우저 저장소에 접근하지 못했습니다. 새 창이나 다른 브라우저에서 다시 시도해 주세요.')
      }

      const params = new URLSearchParams()
      if (sessionKey) {
        params.set('sessionKey', sessionKey)
      }
      navigate(
        `/projects/${encodeURIComponent(projectId)}/testcases/edit${
          params.toString() ? `?${params.toString()}` : ''
        }`,
      )
    } catch (error) {
      const message = error instanceof Error ? error.message : '테스트케이스를 완성하지 못했습니다.'
      setFinalStatus('error')
      setFinalError(message)
    }
  }, [backendUrl, groups, projectId, projectOverview])

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
              기능리스트 단계로 돌아가기
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

    </div>
  )
}
