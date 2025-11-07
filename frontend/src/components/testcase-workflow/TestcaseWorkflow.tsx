import './TestcaseWorkflow.css'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { navigate } from '../../navigation'
import { useBackgroundTasks } from '../../app/background/BackgroundTaskContext'
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

interface ConversationMessage {
  role: 'user' | 'assistant'
  text: string
}

interface ScenarioGroupState {
  feature: FeatureRow
  scenarios: ScenarioEntry[]
  files: File[]
  scenarioCount: number
  status: 'idle' | 'loading' | 'success' | 'error'
  error: string | null
  rewriteMessages: ConversationMessage[]
  rewriteInput: string
  rewriteStatus: 'idle' | 'loading' | 'success' | 'error'
  rewriteError: string | null
  isCollapsed: boolean
}

interface TestcaseWorkflowProps {
  projectId: string
  backendUrl: string
  projectName?: string
}

interface TestcaseWorkflowDraft {
  version: 1
  savedAt: string
  step: Step
  projectOverview: string
  groups: Array<{
    feature: FeatureRow
    scenarioCount: number
    scenarios: ScenarioEntry[]
    rewriteMessages: ConversationMessage[]
    rewriteInput: string
    isCollapsed: boolean
  }>
  nextId: number
}

type Step = 'feature' | 'scenarios'

const FEATURE_FILE_TYPES: FileType[] = ['xlsx', 'xls', 'csv']
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
  const { startTask } = useBackgroundTasks()
  const [step, setStep] = useState<Step>('feature')
  const [projectOverview, setProjectOverview] = useState<string>('')
  const [featureStatus, setFeatureStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [featureError, setFeatureError] = useState<string | null>(null)
  const [featureFiles, setFeatureFiles] = useState<File[]>([])
  const [groups, setGroups] = useState<ScenarioGroupState[]>([])
  const [finalStatus, setFinalStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [finalError, setFinalError] = useState<string | null>(null)
  const [draftFeedback, setDraftFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(
    null,
  )
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [isGeneratingAll, setIsGeneratingAll] = useState(false)
  const idRef = useRef(0)
  const storageKey = useMemo(() => `tta:testcase-workflow:${projectId}`, [projectId])

  const clearDraft = useCallback(() => {
    if (typeof window === 'undefined') {
      return
    }
    window.localStorage.removeItem(storageKey)
  }, [storageKey])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    const raw = window.localStorage.getItem(storageKey)
    if (!raw) {
      return
    }

    try {
      const draft = JSON.parse(raw) as TestcaseWorkflowDraft
      if (!draft || draft.version !== 1) {
        return
      }

      const shouldRestore = window.confirm('이전에 저장된 테스트케이스 작성 중간 내역이 있습니다. 불러올까요?')
      if (!shouldRestore) {
        return
      }

      setProjectOverview(draft.projectOverview ?? '')

      const normalizedGroups: ScenarioGroupState[] = []
      let nextIdCounter = typeof draft.nextId === 'number' && Number.isFinite(draft.nextId) ? draft.nextId : 0

      for (const group of draft.groups ?? []) {
        if (!group || !group.feature) {
          continue
        }

        const normalizedScenarios: ScenarioEntry[] = []
        for (const scenario of group.scenarios ?? []) {
          if (!scenario) {
            continue
          }
          let scenarioId = typeof scenario.id === 'string' && scenario.id.trim().length > 0 ? scenario.id : ''
          if (!scenarioId) {
            nextIdCounter += 1
            scenarioId = `scenario-${nextIdCounter}`
          } else {
            const match = scenarioId.match(/(\d+)$/)
            if (match) {
              const parsed = Number.parseInt(match[1] ?? '0', 10)
              if (!Number.isNaN(parsed)) {
                nextIdCounter = Math.max(nextIdCounter, parsed)
              }
            }
          }
          normalizedScenarios.push({
            id: scenarioId,
            scenario: scenario.scenario ?? '',
            input: scenario.input ?? '',
            expected: scenario.expected ?? '',
          })
        }

        normalizedGroups.push({
          feature: group.feature,
          scenarios: normalizedScenarios,
          files: [],
          scenarioCount: Math.max(3, Math.min(5, group.scenarioCount ?? 3)),
          status: 'idle',
          error: null,
          rewriteMessages: group.rewriteMessages ?? [],
          rewriteInput: group.rewriteInput ?? '',
          rewriteStatus: 'idle',
          rewriteError: null,
          isCollapsed: Boolean(group.isCollapsed),
        })
      }

      idRef.current = nextIdCounter
      setGroups(normalizedGroups)
      setFeatureStatus('idle')
      setFeatureError(null)
      setFeatureFiles([])
      setStep(normalizedGroups.length > 0 ? 'scenarios' : draft.step ?? 'feature')
      setDraftFeedback({ type: 'success', message: '중간 저장된 내용을 불러왔습니다.' })
    } catch (error) {
      console.error('Failed to restore testcase workflow draft', error)
      window.localStorage.removeItem(storageKey)
      setDraftFeedback({ type: 'error', message: '저장된 내용을 불러오지 못했습니다. 다시 저장해 주세요.' })
    }
  }, [storageKey])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    if (!draftFeedback) {
      return
    }
    const timer = window.setTimeout(() => {
      setDraftFeedback(null)
    }, 5000)
    return () => {
      window.clearTimeout(timer)
    }
  }, [draftFeedback])

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
        idRef.current = 0
        setGroups(
          rows.map((feature) => ({
            feature,
            scenarios: [],
            files: [],
            scenarioCount: 3,
            status: 'idle',
            error: null,
            rewriteMessages: [],
            rewriteInput: '',
            rewriteStatus: 'idle',
            rewriteError: null,
            isCollapsed: false,
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
        isCollapsed: false,
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
        isCollapsed: false,
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
          isCollapsed: false,
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
            scenarioCount: Math.max(3, nextScenarios.length),
            rewriteMessages: [],
            rewriteInput: '',
            rewriteStatus: 'idle',
            rewriteError: null,
            isCollapsed: false,
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
            isCollapsed: false,
          }
          return nextGroups
        })
      }
    },
    [backendUrl, groups, projectId, projectOverview],
  )

  const handleGenerateAllScenarios = useCallback(async () => {
    if (groups.length === 0) {
      return
    }

    setIsGeneratingAll(true)
    try {
      for (let index = 0; index < groups.length; index += 1) {
        // eslint-disable-next-line no-await-in-loop
        await handleGenerateScenarios(index)
      }
    } finally {
      setIsGeneratingAll(false)
    }
  }, [groups, handleGenerateScenarios])

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
        rewriteStatus:
          prev[groupIndex].rewriteStatus === 'loading'
            ? 'loading'
            : 'idle',
        rewriteError: null,
        isCollapsed: false,
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
        rewriteStatus:
          prev[groupIndex].rewriteStatus === 'loading'
            ? 'loading'
            : 'idle',
        rewriteError: null,
        isCollapsed: false,
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
        rewriteStatus:
          prev[groupIndex].rewriteStatus === 'loading'
            ? 'loading'
            : 'idle',
        rewriteError: null,
        isCollapsed: false,
      }
      return nextGroups
    })
  }, [])

  const handleChangeRewriteInput = useCallback((groupIndex: number, value: string) => {
    setGroups((prev) => {
      if (groupIndex < 0 || groupIndex >= prev.length) {
        return prev
      }
      const nextGroups = [...prev]
      const nextStatus = prev[groupIndex].rewriteStatus
      nextGroups[groupIndex] = {
        ...prev[groupIndex],
        rewriteInput: value,
        rewriteStatus:
          nextStatus === 'success' || nextStatus === 'error' ? 'idle' : nextStatus,
        rewriteError: null,
        isCollapsed: false,
      }
      return nextGroups
    })
  }, [])

  const handleSubmitRewrite = useCallback(
    async (groupIndex: number) => {
      const group = groups[groupIndex]
      if (!group) {
        return
      }

      const message = group.rewriteInput.trim()
      if (!message) {
        setGroups((prev) => {
          if (groupIndex < 0 || groupIndex >= prev.length) {
            return prev
          }
          const nextGroups = [...prev]
          nextGroups[groupIndex] = {
            ...prev[groupIndex],
            rewriteError: 'GPT에게 전달할 내용을 입력해 주세요.',
            rewriteStatus: 'error',
            isCollapsed: false,
          }
          return nextGroups
        })
        return
      }

      const nextMessages: ConversationMessage[] = [
        ...group.rewriteMessages,
        { role: 'user', text: message },
      ]

      setGroups((prev) => {
        if (groupIndex < 0 || groupIndex >= prev.length) {
          return prev
        }
        const nextGroups = [...prev]
        nextGroups[groupIndex] = {
          ...prev[groupIndex],
          rewriteMessages: nextMessages,
          rewriteInput: '',
          rewriteStatus: 'loading',
          rewriteError: null,
          isCollapsed: false,
        }
        return nextGroups
      })

      const payload = {
        projectOverview,
        majorCategory: group.feature.majorCategory,
        middleCategory: group.feature.middleCategory,
        minorCategory: group.feature.minorCategory,
        featureDescription: group.feature.featureDescription,
        scenarios: group.scenarios.map((scenario) => ({
          scenario: scenario.scenario,
          input: scenario.input,
          expected: scenario.expected,
        })),
        instructions: message,
        conversation: nextMessages.map((entry) => ({ role: entry.role, text: entry.text })),
      }

      try {
        const response = await fetch(
          `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/testcases/workflow/rewrite`,
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
          const detail = typeof body?.detail === 'string' ? body.detail : 'GPT 응답을 가져오지 못했습니다.'
          throw new Error(detail)
        }

        const body = (await response.json()) as {
          reply?: string
          scenarios?: Array<{ scenario?: string; input?: string; expected?: string }>
        }

        const scenarios = Array.isArray(body.scenarios) ? body.scenarios : []
        if (scenarios.length === 0) {
          throw new Error('GPT 응답에서 테스트케이스를 찾을 수 없습니다.')
        }

        const assistantMessage = typeof body.reply === 'string' && body.reply.trim().length > 0
          ? body.reply.trim()
          : 'GPT 응답이 도착했습니다.'

        setGroups((prev) => {
          if (groupIndex < 0 || groupIndex >= prev.length) {
            return prev
          }

          const nextGroups = [...prev]
          const nextScenarios: ScenarioEntry[] = scenarios.map((entry) => {
            idRef.current += 1
            return {
              id: `scenario-${idRef.current}`,
              scenario: entry?.scenario?.trim() ?? '',
              input: entry?.input?.trim() ?? '',
              expected: entry?.expected?.trim() ?? '',
            }
          })

          nextGroups[groupIndex] = {
            ...prev[groupIndex],
            scenarios: nextScenarios,
            scenarioCount: Math.max(3, nextScenarios.length),
            rewriteMessages: [...nextMessages, { role: 'assistant', text: assistantMessage }],
            rewriteStatus: 'success',
            rewriteError: null,
            isCollapsed: false,
          }

          return nextGroups
        })
      } catch (error) {
        const detail = error instanceof Error ? error.message : 'GPT 응답을 가져오지 못했습니다.'
        setGroups((prev) => {
          if (groupIndex < 0 || groupIndex >= prev.length) {
            return prev
          }
          const nextGroups = [...prev]
          nextGroups[groupIndex] = {
            ...prev[groupIndex],
            rewriteMessages: nextMessages,
            rewriteStatus: 'error',
            rewriteError: detail,
            isCollapsed: false,
          }
          return nextGroups
        })
      }
    },
    [backendUrl, groups, projectId, projectOverview],
  )

  const handleCompleteGroup = useCallback((groupIndex: number) => {
    setGroups((prev) => {
      if (groupIndex < 0 || groupIndex >= prev.length) {
        return prev
      }
      const nextGroups = [...prev]
      nextGroups[groupIndex] = {
        ...prev[groupIndex],
        isCollapsed: true,
      }
      return nextGroups
    })
  }, [])

  const handleResumeGroup = useCallback((groupIndex: number) => {
    setGroups((prev) => {
      if (groupIndex < 0 || groupIndex >= prev.length) {
        return prev
      }
      const nextGroups = [...prev]
      nextGroups[groupIndex] = {
        ...prev[groupIndex],
        isCollapsed: false,
      }
      return nextGroups
    })
  }, [])

  const handleRemoveGroup = useCallback((groupIndex: number) => {
    if (groupIndex < 0) {
      return
    }

    if (typeof window !== 'undefined' && typeof window.confirm === 'function') {
      const confirmed = window.confirm(
        '이 소분류를 삭제할까요? 생성된 시나리오와 첨부한 파일이 모두 사라집니다.',
      )
      if (!confirmed) {
        return
      }
    }

    setGroups((prev) => {
      if (groupIndex < 0 || groupIndex >= prev.length) {
        return prev
      }

      return prev.filter((_, index) => index !== groupIndex)
    })
  }, [])

  const canProceedToReview = useMemo(
    () => groups.length > 0 && groups.every((group) => group.scenarios.length >= 1),
    [groups],
  )

  const handleFinalize = useCallback(async () => {
    setFinalStatus('loading')
    setFinalError(null)
    const taskHandle = startTask('testcase-generation', '테스트케이스 생성')
    taskHandle.onCancel(() => {
      setFinalStatus('idle')
      setFinalError(null)
    })

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
          signal: taskHandle.signal,
        },
      )

      if (taskHandle.signal.aborted) {
        return
      }

      if (!response.ok) {
        const body = await response.json().catch(() => null)
        if (taskHandle.signal.aborted) {
          return
        }
        const detail = typeof body?.detail === 'string' ? body.detail : '테스트케이스를 완성하지 못했습니다.'
        throw new Error(detail)
      }

      const body = (await response.json()) as FinalizeResponsePayload

      if (taskHandle.signal.aborted) {
        return
      }

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
      const targetUrl = `/projects/${encodeURIComponent(projectId)}/testcases/edit${
        query ? `?${query}` : ''
      }`
      if (!taskHandle.signal.aborted) {
        clearDraft()
        taskHandle.complete({ type: 'navigate', url: targetUrl, label: '열기' }, '테스트케이스 생성 완료')
        navigate(targetUrl)
      }
    } catch (error) {
      if (taskHandle.signal.aborted) {
        return
      }
      const message = error instanceof Error ? error.message : '테스트케이스를 완성하지 못했습니다.'
      setFinalStatus('error')
      setFinalError(message)
      taskHandle.fail(message)
    }
  }, [backendUrl, clearDraft, groups, projectId, projectOverview, projectName, startTask])

  const handleSaveDraft = useCallback(() => {
    if (typeof window === 'undefined') {
      return
    }

    try {
      const draft: TestcaseWorkflowDraft = {
        version: 1,
        savedAt: new Date().toISOString(),
        step,
        projectOverview,
        groups: groups.map((group) => ({
          feature: group.feature,
          scenarioCount: group.scenarioCount,
          scenarios: group.scenarios.map((scenario) => ({ ...scenario })),
          rewriteMessages: group.rewriteMessages.map((message) => ({ ...message })),
          rewriteInput: group.rewriteInput,
          isCollapsed: group.isCollapsed,
        })),
        nextId: idRef.current,
      }

      window.localStorage.setItem(storageKey, JSON.stringify(draft))
      setDraftFeedback({
        type: 'success',
        message: '중간 저장했습니다. 같은 브라우저에서 다시 열면 이어서 작업할 수 있습니다.',
      })
    } catch (error) {
      console.error('Failed to save testcase workflow draft', error)
      setDraftFeedback({ type: 'error', message: '중간 저장에 실패했습니다. 다시 시도해 주세요.' })
    }
  }, [groups, idRef, projectOverview, step, storageKey])

  const canSaveDraft = useMemo(
    () => projectOverview.trim().length > 0 || groups.some((group) => group.scenarios.length > 0),
    [groups, projectOverview],
  )

  const handleRequestReset = useCallback(() => {
    setShowResetConfirm(true)
  }, [])

  const handleCancelReset = useCallback(() => {
    setShowResetConfirm(false)
  }, [])

  const handleConfirmReset = useCallback(() => {
    setShowResetConfirm(false)
    setStep('feature')
    setProjectOverview('')
    setFeatureStatus('idle')
    setFeatureError(null)
    setFeatureFiles([])
    setGroups([])
    setFinalStatus('idle')
    setFinalError(null)
    setDraftFeedback(null)
    idRef.current = 0
    clearDraft()
  }, [clearDraft])

  return (
    <div className="testcase-workflow">
      {step === 'feature' && (
        <section className="testcase-workflow__section" aria-labelledby="testcase-feature-step">
          <h2 id="testcase-feature-step" className="testcase-workflow__title">
            기능리스트 불러오기
          </h2>
          <p className="testcase-workflow__helper">
            테스트케이스를 작성할 기능리스트 파일을 업로드하세요. 대/중/소분류 정보를 활용합니다.
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
          <div className="testcase-workflow__bulk-actions">
            <button
              type="button"
              className="testcase-workflow__button"
              onClick={handleGenerateAllScenarios}
              disabled={isGeneratingAll || groups.length === 0}
            >
              {isGeneratingAll ? '전체 생성 중…' : '전체 시나리오 생성'}
            </button>
          </div>
          <div className="testcase-workflow__feature-list">
            {groups.map((group, index) => (
              <article
                key={`${group.feature.majorCategory}-${group.feature.minorCategory}-${index}`}
                className={`testcase-workflow__card${group.isCollapsed ? ' testcase-workflow__card--collapsed' : ''}`}
                aria-expanded={!group.isCollapsed}
              >
                <header className="testcase-workflow__card-header">
                  <div className="testcase-workflow__card-header-main">
                    <span className="testcase-workflow__card-badge">소분류 {index + 1}</span>
                    {group.isCollapsed ? (
                      <p className="testcase-workflow__card-name">
                        {group.feature.majorCategory} | {group.feature.middleCategory} | {group.feature.minorCategory}
                        <span className="testcase-workflow__card-name-value">
                          {group.feature.featureDescription || '기능 설명이 제공되지 않았습니다.'}
                        </span>
                      </p>
                    ) : (
                      <>
                        <h3 className="testcase-workflow__card-title">
                          {group.feature.majorCategory} | {group.feature.middleCategory} | {group.feature.minorCategory}
                        </h3>
                        <p className="testcase-workflow__card-subtitle">
                          {group.feature.featureDescription || '기능 설명이 제공되지 않았습니다.'}
                        </p>
                      </>
                    )}
                  </div>
                  <div className="testcase-workflow__card-meta" aria-live="polite">
                    <span className="testcase-workflow__card-meta-count">
                      생성된 시나리오 {group.scenarios.length}개
                    </span>
                    {group.isCollapsed && (
                      <button
                        type="button"
                        className="testcase-workflow__secondary testcase-workflow__button"
                        onClick={() => handleResumeGroup(index)}
                      >
                        수정
                      </button>
                    )}
                    <button
                      type="button"
                      className="testcase-workflow__danger testcase-workflow__button"
                      onClick={() => handleRemoveGroup(index)}
                    >
                      소분류 삭제
                    </button>
                  </div>
                </header>

                {!group.isCollapsed && (
                  <>
                    <div className="testcase-workflow__card-body">
                      <div className="testcase-workflow__card-grid">
                        <div className="testcase-workflow__attachments">
                          <h4 className="testcase-workflow__attachments-title">참고 이미지 첨부</h4>
                          <p className="testcase-workflow__attachments-helper">
                            기능 이해를 위한 이미지을 선택하세요.
                          </p>          
                          <input
                            type="file"
                            accept="image/*"
                            multiple
                            className="testcase-workflow__attachments-input"
                            onChange={(event) => handleSetGroupFiles(index, Array.from(event.target.files ?? []))}
                            disabled={group.status === 'loading'}
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
                              disabled={group.status === 'loading' || isGeneratingAll}
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
                    </div>

                    {group.scenarios.length > 0 && (
                      <div className="testcase-workflow__scenario-list">
                        {group.scenarios.map((scenario) => (
                          <div key={scenario.id} className="testcase-workflow__scenario">
                            <div className="testcase-workflow__scenario-fields">
                              <label className="testcase-workflow__scenario-field">
                                <span>테스트 시나리오</span>
                                <textarea
                                  className="testcase-workflow__textarea"
                                  value={scenario.scenario}
                                  onChange={(event) =>
                                    handleUpdateScenarioField(index, scenario.id, 'scenario', event.target.value)
                                  }
                                />
                              </label>
                              <label className="testcase-workflow__scenario-field">
                                <span>입력(사전조건 포함)</span>
                                <textarea
                                  className="testcase-workflow__textarea"
                                  value={scenario.input}
                                  onChange={(event) =>
                                    handleUpdateScenarioField(index, scenario.id, 'input', event.target.value)
                                  }
                                />
                              </label>
                              <label className="testcase-workflow__scenario-field">
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
                    {group.scenarios.length > 0 && (
                      <div className="testcase-workflow__chat">
                        <h4 className="testcase-workflow__chat-title">GPT와 테스트케이스 다듬기</h4>
                        <p className="testcase-workflow__chat-helper">
                          수정이 필요한 방향을 설명하면 현재 테스트케이스를 참고해 GPT가 새로운 안을 제안합니다.
                        </p>
                        <div className="testcase-workflow__chat-log" role="log" aria-live="polite">
                          {group.rewriteMessages.length === 0 && (
                            <p className="testcase-workflow__chat-helper">아직 대화가 없습니다.</p>
                          )}
                          {group.rewriteMessages.map((message, messageIndex) => (
                            <div
                              key={`${message.role}-${messageIndex}`}
                              className={`testcase-workflow__chat-message testcase-workflow__chat-message--${message.role}`}
                            >
                              <span>{message.role === 'user' ? '요청' : 'GPT 응답'}</span>
                              <p>{message.text}</p>
                            </div>
                          ))}
                        </div>
                        {group.rewriteError && (
                          <p className="testcase-workflow__status testcase-workflow__status--error" role="alert">
                            {group.rewriteError}
                          </p>
                        )}
                        {group.rewriteStatus === 'success' && !group.rewriteError && (
                          <p className="testcase-workflow__status testcase-workflow__status--success">
                            GPT 응답을 테스트케이스에 반영했습니다.
                          </p>
                        )}
                        <form
                          className="testcase-workflow__chat-form"
                          onSubmit={(event) => {
                            event.preventDefault()
                            void handleSubmitRewrite(index)
                          }}
                        >
                          <textarea
                            className="testcase-workflow__textarea"
                            value={group.rewriteInput}
                            onChange={(event) => handleChangeRewriteInput(index, event.target.value)}
                            placeholder="예: 2번 테스트를 로그인 실패 케이스로 바꿔줘"
                            disabled={group.rewriteStatus === 'loading'}
                          />
                          <div className="testcase-workflow__chat-actions">
                            <button
                              type="submit"
                              className="testcase-workflow__button"
                              disabled={group.rewriteStatus === 'loading' || group.scenarios.length === 0}
                            >
                              {group.rewriteStatus === 'loading' ? '요청 중…' : 'GPT에게 수정 요청'}
                            </button>
                            <button
                              type="button"
                              className="testcase-workflow__secondary testcase-workflow__button"
                              onClick={() => handleCompleteGroup(index)}
                            >
                              완료
                            </button>
                          </div>
                        </form>
                      </div>
                    )}
                  </>
                )}
              </article>
            ))}
          </div>

          <div className="testcase-workflow__step-actions">
            <button
              type="button"
              className="testcase-workflow__secondary testcase-workflow__button"
              onClick={handleRequestReset}
            >
              처음 단계로 돌아가기
            </button>
            <div className="testcase-workflow__step-actions-group">
              <button
                type="button"
                className="testcase-workflow__secondary testcase-workflow__button"
                onClick={handleSaveDraft}
                disabled={!canSaveDraft}
              >
                중간 저장
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
          </div>

          {draftFeedback && (
            <div
              className={`testcase-workflow__status testcase-workflow__status--${
                draftFeedback.type === 'success' ? 'success' : 'error'
              }`}
              role={draftFeedback.type === 'error' ? 'alert' : 'status'}
            >
              {draftFeedback.message}
            </div>
          )}

          {finalStatus === 'error' && finalError && (
            <div className="testcase-workflow__status testcase-workflow__status--error">{finalError}</div>
          )}
        </section>
      )}


      {showResetConfirm && (
        <div className="testcase-workflow__modal-overlay" role="presentation">
          <div className="testcase-workflow__modal-backdrop" onClick={handleCancelReset} />
          <div
            className="testcase-workflow__modal"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="testcase-workflow-reset-title"
            aria-describedby="testcase-workflow-reset-description"
          >
            <h3 id="testcase-workflow-reset-title" className="testcase-workflow__modal-title">
              저장한 내용을 삭제하고 처음 단계로 돌아갈까요?
            </h3>
            <p id="testcase-workflow-reset-description" className="testcase-workflow__modal-description">
              돌아가기를 선택하면 중간 저장된 내용과 현재 작성 중인 정보가 모두 삭제됩니다. 계속하시겠어요?
            </p>
            <div className="testcase-workflow__modal-actions">
              <button
                type="button"
                className="testcase-workflow__secondary testcase-workflow__button"
                onClick={handleCancelReset}
              >
                취소
              </button>
              <button type="button" className="testcase-workflow__button" onClick={handleConfirmReset}>
                저장 안 하고 돌아가기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
