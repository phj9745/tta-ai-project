import './TestcaseWorkflow.css'

import { useCallback, useMemo, useRef, useState } from 'react'

import { navigate } from '../../navigation'
import { FileUploader } from '../FileUploader'
import type { FileType } from '../fileUploaderTypes'

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
  projectName?: string
}

type Step = 'feature' | 'scenarios'

const FEATURE_FILE_TYPES: FileType[] = ['xlsx', 'xls', 'csv']
const ATTACHMENT_FILE_TYPES: FileType[] = ['jpg', 'png']
const SCENARIO_COUNT_OPTIONS = [3, 4, 5] as const

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
  fileId?: string
  fileName?: string
  modifiedTime?: string
}

export function TestcaseWorkflow({ projectId, backendUrl, projectName }: TestcaseWorkflowProps) {
  const [step, setStep] = useState<Step>('feature')
  const [projectOverview, setProjectOverview] = useState<string>('')
  const [featureStatus, setFeatureStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [featureError, setFeatureError] = useState<string | null>(null)
  const [featureFiles, setFeatureFiles] = useState<File[]>([])
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

  const handleSelectFeatureFiles = useCallback(
    (files: File[]) => {
      const [nextFile] = files
      setFeatureFiles(nextFile ? [nextFile] : [])
      void handleUploadFeatureList(nextFile ?? null)
    },
    [handleUploadFeatureList],
  )

  const handleSetGroupFiles = useCallback((index: number, files: File[]) => {
    setGroups((prev) => {
      if (index < 0 || index >= prev.length) {
        return prev
      }
      const nextGroups = [...prev]
      nextGroups[index] = {
        ...prev[index],
        files,
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

      const fileId = typeof body.fileId === 'string' ? body.fileId.trim() : ''
      if (!fileId) {
        throw new Error('테스트케이스 파일 정보를 확인하지 못했습니다.')
      }

      const nextParams = new URLSearchParams(window.location.search)
      if (projectName && projectName !== projectId && !nextParams.get('name')) {
        nextParams.set('name', projectName)
      }
      nextParams.set('fileId', fileId)
      if (typeof body.fileName === 'string' && body.fileName.trim().length > 0) {
        nextParams.set('fileName', body.fileName.trim())
      } else {
        nextParams.delete('fileName')
      }
      if (typeof body.modifiedTime === 'string' && body.modifiedTime.trim().length > 0) {
        nextParams.set('modifiedTime', body.modifiedTime.trim())
      } else {
        nextParams.delete('modifiedTime')
      }

      const query = nextParams.toString()
      navigate(
        `/projects/${encodeURIComponent(projectId)}/testcases/edit${query ? `?${query}` : ''}`,
      )
    } catch (error) {
      const message = error instanceof Error ? error.message : '테스트케이스를 완성하지 못했습니다.'
      setFinalStatus('error')
      setFinalError(message)
    }
  }, [backendUrl, groups, projectId, projectOverview, projectName])

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
          <div className="testcase-workflow__upload" aria-live="polite">
            <FileUploader
              allowedTypes={FEATURE_FILE_TYPES}
              files={featureFiles}
              onChange={handleSelectFeatureFiles}
              disabled={featureStatus === 'loading'}
              multiple={false}
              hideDropzoneWhenFilled
              maxFiles={1}
            />
            <p className="testcase-workflow__upload-helper">
              XLSX, XLS, CSV 형식의 기능리스트를 드래그 앤 드롭하거나 클릭해서 선택하세요. 업로드된 내용은 자동으로 소분류별로 분류됩니다.
            </p>
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
          {projectOverview && (
            <aside className="testcase-workflow__overview" aria-label="프로젝트 개요">
              <h3 className="testcase-workflow__overview-title">프로젝트 개요</h3>
              <p className="testcase-workflow__overview-description">{projectOverview}</p>
            </aside>
          )}
          <div className="testcase-workflow__feature-list">
            {groups.map((group, index) => (
              <article
                key={`${group.feature.majorCategory}-${group.feature.minorCategory}-${index}`}
                className="testcase-workflow__card"
              >
                <header className="testcase-workflow__card-header">
                  <div className="testcase-workflow__card-header-main">
                    <span className="testcase-workflow__card-badge">소분류 {index + 1}</span>
                    <h3 className="testcase-workflow__card-title">
                      {group.feature.majorCategory} | {group.feature.middleCategory} | {group.feature.minorCategory}
                    </h3>
                    <p className="testcase-workflow__card-subtitle">
                      {group.feature.featureDescription || '기능 설명이 제공되지 않았습니다.'}
                    </p>
                  </div>
                  <div className="testcase-workflow__card-meta" aria-live="polite">
                    <span className="testcase-workflow__card-meta-count">
                      생성된 시나리오 {group.scenarios.length}개
                    </span>
                  </div>
                </header>

                <div className="testcase-workflow__card-body">
                  <div className="testcase-workflow__card-grid">
                    <div className="testcase-workflow__attachments">
                      <h4 className="testcase-workflow__attachments-title">참고 이미지</h4>
                      <p className="testcase-workflow__attachments-helper">
                        테스트 화면, 설계서 캡처 등 시나리오 작성에 도움이 되는 이미지를 추가하세요.
                      </p>
                      <FileUploader
                        allowedTypes={ATTACHMENT_FILE_TYPES}
                        files={group.files}
                        onChange={(nextFiles) => handleSetGroupFiles(index, nextFiles)}
                        disabled={group.status === 'loading'}
                        variant="grid"
                      />
                    </div>
                    <div className="testcase-workflow__card-actions" aria-live="polite">
                      <label className="testcase-workflow__field">
                        <span>시나리오 수</span>
                        <select
                          className="testcase-workflow__select"
                          value={group.scenarioCount}
                          onChange={(event) => handleChangeScenarioCount(index, Number(event.target.value))}
                        >
                          {SCENARIO_COUNT_OPTIONS.map((count) => (
                            <option key={count} value={count}>
                              {count}개
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="testcase-workflow__action-buttons">
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
                      {group.status === 'loading' && (
                        <p className="testcase-workflow__status testcase-workflow__status--loading">
                          시나리오를 생성하고 있습니다…
                        </p>
                      )}
                      {group.status === 'success' && group.scenarios.length > 0 && (
                        <p className="testcase-workflow__status testcase-workflow__status--success">
                          시나리오 {group.scenarios.length}개가 생성되었습니다.
                        </p>
                      )}
                      {group.status === 'error' && group.error && (
                        <p className="testcase-workflow__status testcase-workflow__status--error">{group.error}</p>
                      )}
                    </div>
                  </div>

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
                              시나리오 삭제
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
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
