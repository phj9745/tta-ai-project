import { useCallback, useEffect, useMemo, useState } from 'react'

import { getBackendUrl } from '../config'
import { PageHeader } from '../components/layout/PageHeader'
import { PageLayout } from '../components/layout/PageLayout'
import { Modal } from '../components/Modal'

import './AdminPromptsPage.css'

type PromptCategory =
  | 'feature-list'
  | 'testcase-generation'
  | 'defect-report'
  | 'security-report'
  | 'performance-report'

type StatusType = 'idle' | 'success' | 'error'

type PromptScaffolding = {
  attachmentsHeading: string
  attachmentsIntro: string
  closingNote: string
  formatWarning: string
}

type PromptSection = {
  id: string
  label: string
  content: string
  enabled: boolean
}

type PromptBuiltinContext = {
  id: string
  label: string
  description: string
  sourcePath: string
  renderMode: 'file' | 'image' | 'xlsx-to-pdf' | 'text'
  includeInPrompt: boolean
  showInAttachmentList: boolean
}

type PromptModelParameters = {
  temperature: number
  topP: number
  maxOutputTokens: number
  presencePenalty: number
  frequencyPenalty: number
}

type PromptConfig = {
  label: string
  summary: string
  systemPrompt: string
  userPrompt: string
  userPromptSections: PromptSection[]
  scaffolding: PromptScaffolding
  attachmentDescriptorTemplate: string
  builtinContexts: PromptBuiltinContext[]
  modelParameters: PromptModelParameters
}

type PromptConfigResponse = Record<PromptCategory, PromptConfig>

type PromptResponsePayload = {
  current: Record<string, PromptConfig>
  defaults: Record<string, PromptConfig>
}

type PromptRequestLogApiEntry = {
  request_id: string
  timestamp: string
  project_id: string
  menu_id: string
  system_prompt: string
  user_prompt: string
  context_summary: string
}

type PromptRequestLogEntry = {
  requestId: string
  timestamp: string
  projectId: string
  menuId: string
  systemPrompt: string
  userPrompt: string
  contextSummary: string
}

type PromptRequestLogResponse = {
  logs: PromptRequestLogApiEntry[]
}

function isPromptCategory(value: string): value is PromptCategory {
  return (
    value === 'feature-list' ||
    value === 'testcase-generation' ||
    value === 'defect-report' ||
    value === 'security-report' ||
    value === 'performance-report'
  )
}

function cloneConfig(config: PromptConfig): PromptConfig {
  return {
    ...config,
    userPromptSections: config.userPromptSections.map((section) => ({ ...section })),
    scaffolding: { ...config.scaffolding },
    builtinContexts: config.builtinContexts.map((context) => ({ ...context })),
    modelParameters: { ...config.modelParameters },
  }
}

function cloneConfigMap(raw: Record<string, PromptConfig>): PromptConfigResponse {
  const entries = Object.entries(raw)
    .filter((entry): entry is [PromptCategory, PromptConfig] => isPromptCategory(entry[0]))
    .map(([key, value]) => [key, cloneConfig(value)])
  return Object.fromEntries(entries) as PromptConfigResponse
}

const PREVIEW_CONTEXT_SUMMARY = '사용자 매뉴얼 등 업로드 자료'

function buildPreview(config: PromptConfig): string {
  const parts: string[] = []
  const base = config.userPrompt.trim()
  if (base) {
    parts.push(base)
  }

  config.userPromptSections
    .filter((section) => section.enabled)
    .forEach((section) => {
      const label = section.label.trim()
      const content = section.content.trim()
      if (!label && !content) {
        return
      }
      if (label && content) {
        parts.push(`${label}\n${content}`)
      } else {
        parts.push(label || content)
      }
    })

  const heading = config.scaffolding.attachmentsHeading.trim()
  const intro = config.scaffolding.attachmentsIntro.trim()
  if (heading) {
    parts.push(heading)
  }
  if (intro) {
    parts.push(intro)
  }

  const descriptorTemplate = config.attachmentDescriptorTemplate || '{{index}}. {{descriptor}}'
  const descriptorExample = descriptorTemplate
    .replaceAll('{{index}}', '1')
    .replaceAll('{{descriptor}}', '사용자 매뉴얼 (PDF)')
    .replaceAll('{{label}}', '사용자 매뉴얼')
    .replaceAll('{{description}}', '첨부 자료 설명')
    .replaceAll('{{extension}}', 'PDF')
    .replaceAll('{{doc_id}}', 'sample-doc')
    .replaceAll('{{notes}}', '비고')
    .replaceAll('{{source_path}}', 'template/sample.pdf')
  if (descriptorExample.trim()) {
    parts.push(descriptorExample)
  }

  const closingTemplate = config.scaffolding.closingNote.trim()
  if (closingTemplate) {
    parts.push(closingTemplate.replaceAll('{{context_summary}}', PREVIEW_CONTEXT_SUMMARY))
  }

  const warning = config.scaffolding.formatWarning.trim()
  if (warning) {
    parts.push(warning)
  }

  return parts.join('\n\n').trim()
}

let uniqueId = 0
function createUniqueId(prefix: string): string {
  uniqueId += 1
  return `${prefix}-${Date.now()}-${uniqueId}`
}

function formatDateTime(value: string): string {
  if (!value) {
    return '-'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  try {
    return new Intl.DateTimeFormat('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  } catch (error) {
    console.error(error)
    return date.toLocaleString()
  }
}

export function AdminPromptsPage() {
  const backendUrl = useMemo(() => getBackendUrl(), [])
  const [configs, setConfigs] = useState<PromptConfigResponse | null>(null)
  const [serverConfigs, setServerConfigs] = useState<PromptConfigResponse | null>(null)
  const [defaults, setDefaults] = useState<PromptConfigResponse | null>(null)
  const [activeCategory, setActiveCategory] = useState<PromptCategory>('feature-list')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState<{ type: StatusType; message: string }>({ type: 'idle', message: '' })
  const [previewOpen, setPreviewOpen] = useState(false)
  const [requestLogs, setRequestLogs] = useState<PromptRequestLogEntry[]>([])
  const [logsLoading, setLogsLoading] = useState(true)
  const [logsRefreshing, setLogsRefreshing] = useState(false)
  const [logsError, setLogsError] = useState<string | null>(null)

  const fetchLogs = useCallback(
    async (signal?: AbortSignal, silent = false) => {
      if (silent) {
        setLogsRefreshing(true)
      } else {
        setLogsLoading(true)
        setLogsError(null)
      }
      try {
        const response = await fetch(`${backendUrl}/admin/prompts/logs?limit=50`, {
          method: 'GET',
          signal,
        })
        if (!response.ok) {
          throw new Error('failed to fetch logs')
        }
        const payload = (await response.json()) as PromptRequestLogResponse
        const normalized = (payload.logs ?? []).map((entry) => ({
          requestId: entry.request_id,
          timestamp: entry.timestamp,
          projectId: entry.project_id,
          menuId: entry.menu_id,
          systemPrompt: entry.system_prompt,
          userPrompt: entry.user_prompt,
          contextSummary: entry.context_summary,
        }))
        setRequestLogs(normalized)
        if (!silent) {
          setLogsError(null)
        }
      } catch (caughtError) {
        if (signal?.aborted) {
          return
        }
        console.error(caughtError)
        setLogsError('요청 기록을 불러오지 못했습니다. 나중에 다시 시도해 주세요.')
      } finally {
        if (silent) {
          setLogsRefreshing(false)
        } else {
          setLogsLoading(false)
        }
      }
    },
    [backendUrl],
  )

  const resolveMenuLabel = useCallback(
    (menuId: string) => {
      if (configs && isPromptCategory(menuId)) {
        const label = configs[menuId]?.label
        if (label) {
          return label
        }
      }
      if (defaults && isPromptCategory(menuId)) {
        const label = defaults[menuId]?.label
        if (label) {
          return label
        }
      }
      return menuId
    },
    [configs, defaults],
  )

  useEffect(() => {
    const controller = new AbortController()
    async function loadConfigs() {
      setLoading(true)
      setError(null)
      try {
        const response = await fetch(`${backendUrl}/admin/prompts`, {
          method: 'GET',
          signal: controller.signal,
        })
        if (!response.ok) {
          throw new Error('서버에서 프롬프트 구성을 불러오지 못했습니다.')
        }
        const payload = (await response.json()) as PromptResponsePayload
        const current = cloneConfigMap(payload.current)
        const fallback = cloneConfigMap(payload.defaults)
        setConfigs(current)
        setServerConfigs(cloneConfigMap(payload.current))
        setDefaults(fallback)
      } catch (caughtError) {
        if (controller.signal.aborted) {
          return
        }
        console.error(caughtError)
        setError('프롬프트 구성을 불러오는 중 오류가 발생했습니다.')
      } finally {
        setLoading(false)
      }
    }

    loadConfigs()
    return () => controller.abort()
  }, [backendUrl])

  useEffect(() => {
    const controller = new AbortController()
    void fetchLogs(controller.signal)
    return () => controller.abort()
  }, [fetchLogs])

  const activeConfig = configs ? configs[activeCategory] : null
  const preview = activeConfig ? buildPreview(activeConfig) : ''

  const navItems = useMemo(() => {
    if (!configs) {
      return []
    }
    return (Object.entries(configs) as [PromptCategory, PromptConfig][]).map(([key, value]) => ({
      id: key,
      label: value.label,
      summary: value.summary,
    }))
  }, [configs])

  const handleUpdateConfigField = (field: keyof Pick<PromptConfig, 'label' | 'summary' | 'systemPrompt' | 'userPrompt'>, value: string) => {
    if (!configs) {
      return
    }
    setConfigs((prev) => {
      if (!prev) {
        return prev
      }
      return {
        ...prev,
        [activeCategory]: {
          ...prev[activeCategory],
          [field]: value,
        },
      }
    })
    setStatus({ type: 'idle', message: '' })
  }

  const handleUpdateSection = (sectionId: string, field: keyof PromptSection, value: string | boolean) => {
    setConfigs((prev) => {
      if (!prev) {
        return prev
      }
      const current = prev[activeCategory]
      const nextSections = current.userPromptSections.map((section) =>
        section.id === sectionId ? { ...section, [field]: value } : section,
      )
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          userPromptSections: nextSections,
        },
      }
    })
    setStatus({ type: 'idle', message: '' })
  }

  const handleAddSection = () => {
    setConfigs((prev) => {
      if (!prev) {
        return prev
      }
      const current = prev[activeCategory]
      const newSection: PromptSection = {
        id: createUniqueId(`${activeCategory}-section`),
        label: '새 지침',
        content: '',
        enabled: true,
      }
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          userPromptSections: [...current.userPromptSections, newSection],
        },
      }
    })
    setStatus({ type: 'idle', message: '' })
  }

  const handleRemoveSection = (sectionId: string) => {
    setConfigs((prev) => {
      if (!prev) {
        return prev
      }
      const current = prev[activeCategory]
      const nextSections = current.userPromptSections.filter((section) => section.id !== sectionId)
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          userPromptSections: nextSections,
        },
      }
    })
    setStatus({ type: 'idle', message: '' })
  }

  const handleScaffoldingChange = (field: keyof PromptScaffolding, value: string) => {
    setConfigs((prev) => {
      if (!prev) {
        return prev
      }
      return {
        ...prev,
        [activeCategory]: {
          ...prev[activeCategory],
          scaffolding: {
            ...prev[activeCategory].scaffolding,
            [field]: value,
          },
        },
      }
    })
    setStatus({ type: 'idle', message: '' })
  }

  const handleDescriptorTemplateChange = (value: string) => {
    setConfigs((prev) => {
      if (!prev) {
        return prev
      }
      return {
        ...prev,
        [activeCategory]: {
          ...prev[activeCategory],
          attachmentDescriptorTemplate: value,
        },
      }
    })
    setStatus({ type: 'idle', message: '' })
  }

  const handleBuiltinContextChange = <K extends keyof PromptBuiltinContext>(contextId: string, field: K, value: PromptBuiltinContext[K]) => {
    setConfigs((prev) => {
      if (!prev) {
        return prev
      }
      const current = prev[activeCategory]
      const nextContexts = current.builtinContexts.map((context) =>
        context.id === contextId ? { ...context, [field]: value } : context,
      )
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          builtinContexts: nextContexts,
        },
      }
    })
    setStatus({ type: 'idle', message: '' })
  }

  const handleToggleBuiltinContext = (contextId: string, field: keyof Pick<PromptBuiltinContext, 'includeInPrompt' | 'showInAttachmentList'>, checked: boolean) => {
    handleBuiltinContextChange(contextId, field, checked)
  }

  const handleAddBuiltinContext = () => {
    setConfigs((prev) => {
      if (!prev) {
        return prev
      }
      const current = prev[activeCategory]
      const newContext: PromptBuiltinContext = {
        id: createUniqueId(`${activeCategory}-builtin`),
        label: '새 내장 컨텍스트',
        description: '',
        sourcePath: '',
        renderMode: 'file',
        includeInPrompt: true,
        showInAttachmentList: true,
      }
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          builtinContexts: [...current.builtinContexts, newContext],
        },
      }
    })
    setStatus({ type: 'idle', message: '' })
  }

  const handleRemoveBuiltinContext = (contextId: string) => {
    setConfigs((prev) => {
      if (!prev) {
        return prev
      }
      const current = prev[activeCategory]
      const nextContexts = current.builtinContexts.filter((context) => context.id !== contextId)
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          builtinContexts: nextContexts,
        },
      }
    })
    setStatus({ type: 'idle', message: '' })
  }

  const handleModelParameterChange = <K extends keyof PromptModelParameters>(field: K, value: number) => {
    if (!Number.isFinite(value)) {
      return
    }
    setConfigs((prev) => {
      if (!prev) {
        return prev
      }
      return {
        ...prev,
        [activeCategory]: {
          ...prev[activeCategory],
          modelParameters: {
            ...prev[activeCategory].modelParameters,
            [field]: value,
          },
        },
      }
    })
    setStatus({ type: 'idle', message: '' })
  }

  const handleSave = async () => {
    if (!configs || !activeConfig) {
      return
    }
    setSaving(true)
    setStatus({ type: 'idle', message: '' })
    try {
      const response = await fetch(`${backendUrl}/admin/prompts/${activeCategory}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(activeConfig),
      })
      if (!response.ok) {
        throw new Error('save failed')
      }
      const payload = (await response.json()) as { config: PromptConfig }
      const updated = cloneConfig(payload.config)
      setConfigs((prev) => {
        if (!prev) {
          return prev
        }
        return {
          ...prev,
          [activeCategory]: updated,
        }
      })
      setServerConfigs((prev) => {
        const base = prev ? { ...prev } : ({} as PromptConfigResponse)
        base[activeCategory] = cloneConfig(updated)
        return base
      })
      setStatus({ type: 'success', message: '변경 사항을 저장했습니다.' })
    } catch (caughtError) {
      console.error(caughtError)
      setStatus({ type: 'error', message: '저장 중 오류가 발생했습니다. 다시 시도해 주세요.' })
    } finally {
      setSaving(false)
    }
  }

  const handleRevert = () => {
    if (!serverConfigs) {
      return
    }
    const baseline = serverConfigs[activeCategory]
    if (!baseline) {
      return
    }
    setConfigs((prev) => {
      if (!prev) {
        return prev
      }
      return {
        ...prev,
        [activeCategory]: cloneConfig(baseline),
      }
    })
    setStatus({ type: 'success', message: '서버에 저장된 값으로 되돌렸습니다.' })
  }

  const handleRestoreDefault = () => {
    if (!defaults) {
      return
    }
    const fallback = defaults[activeCategory]
    if (!fallback) {
      return
    }
    setConfigs((prev) => {
      if (!prev) {
        return prev
      }
      return {
        ...prev,
        [activeCategory]: cloneConfig(fallback),
      }
    })
    setStatus({ type: 'success', message: '기본 템플릿을 불러왔습니다.' })
  }

  if (loading) {
    return (
      <PageLayout>
        <div className="admin-prompts admin-prompts--loading">
          <PageHeader
            eyebrow="프롬프트 자산 관리"
            title="요청 템플릿 & 첨부 자료 설정"
            subtitle="기능리스트, 테스트케이스, 결함 리포트 등 생성 작업에 필요한 프롬프트를 관리합니다."
          />
          <div className="admin-prompts__placeholder">프롬프트 구성을 불러오는 중입니다...</div>
        </div>
      </PageLayout>
    )
  }

  if (error || !configs || !activeConfig) {
    return (
      <PageLayout>
        <div className="admin-prompts admin-prompts--error">
          <PageHeader
            eyebrow="프롬프트 자산 관리"
            title="요청 템플릿 & 첨부 자료 설정"
            subtitle="프롬프트 구성을 불러오는 중 문제가 발생했습니다."
          />
          <div className="admin-prompts__placeholder admin-prompts__placeholder--error">{error ?? '구성 데이터를 찾을 수 없습니다.'}</div>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout>
      <div className="admin-prompts">
        <PageHeader
          eyebrow="프롬프트 자산 관리"
          title="요청 템플릿 & 첨부 자료 설정"
          subtitle="생성 작업에 사용되는 시스템/사용자 프롬프트와 부가 정보를 실시간으로 조정하세요."
        />

        <div className="admin-prompts__layout">
          <nav className="admin-prompts__nav" aria-label="프롬프트 카테고리">
            {navItems.map((item) => {
              const isActive = item.id === activeCategory
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`admin-prompts__nav-item${isActive ? ' admin-prompts__nav-item--active' : ''}`}
                  onClick={() => {
                    setActiveCategory(item.id)
                    setStatus({ type: 'idle', message: '' })
                  }}
                >
                  <span className="admin-prompts__nav-label">{item.label}</span>
                  <span className="admin-prompts__nav-summary">{item.summary || '설명 없음'}</span>
                </button>
              )
            })}
          </nav>

          <section className="admin-prompts__content" aria-live="polite">
            <header className="admin-prompts__content-header">
              <h2 className="admin-prompts__title">{activeConfig.label}</h2>
              <p className="admin-prompts__summary">{activeConfig.summary || '설명이 비어 있습니다.'}</p>
            </header>

            <div className="admin-prompts__content-body">
              <div className="admin-prompts__main">
                <div className="admin-prompts__field">
                  <label className="admin-prompts__label" htmlFor="systemPrompt">시스템 프롬프트</label>
                  <textarea
                    id="systemPrompt"
                    className="admin-prompts__textarea"
                    value={activeConfig.systemPrompt}
                    onChange={(event) => handleUpdateConfigField('systemPrompt', event.target.value)}
                  />
                </div>

                <div className="admin-prompts__field">
                  <label className="admin-prompts__label" htmlFor="userPrompt">기본 사용자 지시</label>
                  <textarea
                    id="userPrompt"
                    className="admin-prompts__textarea"
                    value={activeConfig.userPrompt}
                    onChange={(event) => handleUpdateConfigField('userPrompt', event.target.value)}
                  />
                </div>

                <section className="admin-prompts__group">
                  <header className="admin-prompts__group-header">
                    <h3 className="admin-prompts__group-title">추가 지침 블록</h3>
                    <button type="button" className="admin-prompts__secondary" onClick={handleAddSection}>
                      + 지침 추가
                    </button>
                  </header>
                  {activeConfig.userPromptSections.length === 0 ? (
                    <p className="admin-prompts__empty">등록된 지침이 없습니다. 필요한 내용을 추가하세요.</p>
                  ) : (
                    <ul className="admin-prompts__list">
                      {activeConfig.userPromptSections.map((section) => (
                        <li key={section.id} className="admin-prompts__list-item">
                          <div className="admin-prompts__list-row">
                            <div className="admin-prompts__field admin-prompts__field--half">
                              <label className="admin-prompts__label" htmlFor={`${section.id}-label`}>
                                제목
                              </label>
                              <input
                                id={`${section.id}-label`}
                                className="admin-prompts__input"
                                value={section.label}
                                onChange={(event) => handleUpdateSection(section.id, 'label', event.target.value)}
                              />
                            </div>
                            <label className="admin-prompts__switch">
                              <input
                                type="checkbox"
                                checked={section.enabled}
                                onChange={(event) => handleUpdateSection(section.id, 'enabled', event.target.checked)}
                              />
                              <span>활성화</span>
                            </label>
                          </div>
                          <div className="admin-prompts__field">
                            <label className="admin-prompts__label" htmlFor={`${section.id}-content`}>
                              내용
                            </label>
                            <textarea
                              id={`${section.id}-content`}
                              className="admin-prompts__textarea"
                              value={section.content}
                              onChange={(event) => handleUpdateSection(section.id, 'content', event.target.value)}
                            />
                          </div>
                          <button
                            type="button"
                            className="admin-prompts__remove"
                            onClick={() => handleRemoveSection(section.id)}
                            aria-label="지침 삭제"
                          >
                            삭제
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>

                <section className="admin-prompts__group">
                  <h3 className="admin-prompts__group-title">첨부 안내 문구</h3>
                  <div className="admin-prompts__field-grid">
                    <div className="admin-prompts__field">
                      <label className="admin-prompts__label" htmlFor="attachmentsHeading">섹션 제목</label>
                      <input
                        id="attachmentsHeading"
                        className="admin-prompts__input"
                        value={activeConfig.scaffolding.attachmentsHeading}
                        onChange={(event) => handleScaffoldingChange('attachmentsHeading', event.target.value)}
                      />
                    </div>
                    <div className="admin-prompts__field">
                      <label className="admin-prompts__label" htmlFor="attachmentsIntro">소개 문구</label>
                      <textarea
                        id="attachmentsIntro"
                        className="admin-prompts__textarea"
                        value={activeConfig.scaffolding.attachmentsIntro}
                        onChange={(event) => handleScaffoldingChange('attachmentsIntro', event.target.value)}
                      />
                    </div>
                  </div>
                  <div className="admin-prompts__field-grid">
                    <div className="admin-prompts__field">
                      <label className="admin-prompts__label" htmlFor="closingNote">
                        마무리 문장 ({'{'}context_summary{'}'} 사용 가능)
                      </label>
                      <textarea
                        id="closingNote"
                        className="admin-prompts__textarea"
                        value={activeConfig.scaffolding.closingNote}
                        onChange={(event) => handleScaffoldingChange('closingNote', event.target.value)}
                      />
                    </div>
                    <div className="admin-prompts__field">
                      <label className="admin-prompts__label" htmlFor="formatWarning">형식 경고</label>
                      <textarea
                        id="formatWarning"
                        className="admin-prompts__textarea"
                        value={activeConfig.scaffolding.formatWarning}
                        onChange={(event) => handleScaffoldingChange('formatWarning', event.target.value)}
                      />
                    </div>
                  </div>
                </section>

                <div className="admin-prompts__field">
                  <label className="admin-prompts__label" htmlFor="descriptorTemplate">
                    첨부 설명 템플릿 (사용 가능 키: index, descriptor, label, description, extension, doc_id, notes, source_path)
                  </label>
                  <input
                    id="descriptorTemplate"
                    className="admin-prompts__input"
                    value={activeConfig.attachmentDescriptorTemplate}
                    onChange={(event) => handleDescriptorTemplateChange(event.target.value)}
                  />
                </div>

                <section className="admin-prompts__group">
                  <header className="admin-prompts__group-header">
                    <h3 className="admin-prompts__group-title">내장 컨텍스트</h3>
                    <button type="button" className="admin-prompts__secondary" onClick={handleAddBuiltinContext}>
                      + 컨텍스트 추가
                    </button>
                  </header>
                  {activeConfig.builtinContexts.length === 0 ? (
                    <p className="admin-prompts__empty">등록된 내장 컨텍스트가 없습니다.</p>
                  ) : (
                    <ul className="admin-prompts__list">
                      {activeConfig.builtinContexts.map((context) => (
                        <li key={context.id} className="admin-prompts__list-item">
                          <div className="admin-prompts__field">
                            <label className="admin-prompts__label" htmlFor={`${context.id}-label`}>
                              이름
                            </label>
                            <input
                              id={`${context.id}-label`}
                              className="admin-prompts__input"
                              value={context.label}
                              onChange={(event) => handleBuiltinContextChange(context.id, 'label', event.target.value)}
                            />
                          </div>
                          <div className="admin-prompts__field">
                            <label className="admin-prompts__label" htmlFor={`${context.id}-description`}>
                              설명
                            </label>
                            <textarea
                              id={`${context.id}-description`}
                              className="admin-prompts__textarea"
                              value={context.description}
                              onChange={(event) => handleBuiltinContextChange(context.id, 'description', event.target.value)}
                            />
                          </div>
                          <div className="admin-prompts__field">
                            <label className="admin-prompts__label" htmlFor={`${context.id}-source`}>
                              파일 경로
                            </label>
                            <input
                              id={`${context.id}-source`}
                              className="admin-prompts__input"
                              value={context.sourcePath}
                              onChange={(event) => handleBuiltinContextChange(context.id, 'sourcePath', event.target.value)}
                            />
                          </div>
                          <div className="admin-prompts__field">
                            <label className="admin-prompts__label" htmlFor={`${context.id}-render`}>
                              렌더링 방식
                            </label>
                            <select
                              id={`${context.id}-render`}
                              className="admin-prompts__select"
                              value={context.renderMode}
                              onChange={(event) =>
                                handleBuiltinContextChange(context.id, 'renderMode', event.target.value as PromptBuiltinContext['renderMode'])
                              }
                            >
                              <option value="file">파일 그대로</option>
                              <option value="image">이미지</option>
                              <option value="xlsx-to-pdf">XLSX → PDF</option>
                              <option value="text">텍스트</option>
                            </select>
                          </div>
                          <div className="admin-prompts__toggles">
                            <label className="admin-prompts__switch">
                              <input
                                type="checkbox"
                                checked={context.includeInPrompt}
                                onChange={(event) => handleToggleBuiltinContext(context.id, 'includeInPrompt', event.target.checked)}
                              />
                              <span>첨부에 포함</span>
                            </label>
                            <label className="admin-prompts__switch">
                              <input
                                type="checkbox"
                                checked={context.showInAttachmentList}
                                onChange={(event) =>
                                  handleToggleBuiltinContext(context.id, 'showInAttachmentList', event.target.checked)
                                }
                              />
                              <span>목록에 표시</span>
                            </label>
                          </div>
                          <button
                            type="button"
                            className="admin-prompts__remove"
                            onClick={() => handleRemoveBuiltinContext(context.id)}
                            aria-label="내장 컨텍스트 삭제"
                          >
                            삭제
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>

                <section className="admin-prompts__group">
                  <h3 className="admin-prompts__group-title">모델 파라미터</h3>
                  <div className="admin-prompts__model-grid">
                    <label className="admin-prompts__model-field">
                      <span>Temperature</span>
                      <input
                        type="number"
                        step="0.05"
                        value={activeConfig.modelParameters.temperature}
                        onChange={(event) => handleModelParameterChange('temperature', Number(event.target.value))}
                      />
                    </label>
                    <label className="admin-prompts__model-field">
                      <span>Top-p</span>
                      <input
                        type="number"
                        step="0.05"
                        value={activeConfig.modelParameters.topP}
                        onChange={(event) => handleModelParameterChange('topP', Number(event.target.value))}
                      />
                    </label>
                    <label className="admin-prompts__model-field">
                      <span>Max Output Tokens</span>
                      <input
                        type="number"
                        value={activeConfig.modelParameters.maxOutputTokens}
                        onChange={(event) => handleModelParameterChange('maxOutputTokens', Number(event.target.value))}
                      />
                    </label>
                    <label className="admin-prompts__model-field">
                      <span>Presence Penalty</span>
                      <input
                        type="number"
                        step="0.1"
                        value={activeConfig.modelParameters.presencePenalty}
                        onChange={(event) => handleModelParameterChange('presencePenalty', Number(event.target.value))}
                      />
                    </label>
                    <label className="admin-prompts__model-field">
                      <span>Frequency Penalty</span>
                      <input
                        type="number"
                        step="0.1"
                        value={activeConfig.modelParameters.frequencyPenalty}
                        onChange={(event) => handleModelParameterChange('frequencyPenalty', Number(event.target.value))}
                      />
                    </label>
                  </div>
                </section>

                {status.message && (
                  <div className={`admin-prompts__status admin-prompts__status--${status.type}`}>
                    {status.message}
                  </div>
                )}

                <div className="admin-prompts__actions">
                  <button
                    type="button"
                    className="admin-prompts__secondary"
                    onClick={() => setPreviewOpen(true)}
                    disabled={!activeConfig}
                  >
                    미리보기
                  </button>
                  <button type="button" className="admin-prompts__primary" onClick={handleSave} disabled={saving}>
                    {saving ? '저장 중...' : '저장'}
                  </button>
                  <button type="button" className="admin-prompts__secondary" onClick={handleRevert} disabled={saving}>
                    되돌리기
                  </button>
                  <button type="button" className="admin-prompts__secondary" onClick={handleRestoreDefault} disabled={saving}>
                    기본값 적용
                  </button>
                </div>
              </div>

              <aside className="admin-prompts__sidebar">
                <section className="admin-prompts__group admin-prompts__logs">
                  <header className="admin-prompts__group-header">
                    <h3 className="admin-prompts__group-title">최근 요청 기록</h3>
                    <button
                      type="button"
                      className="admin-prompts__secondary"
                      onClick={() => {
                        void fetchLogs(undefined, true)
                      }}
                      disabled={logsLoading || logsRefreshing}
                    >
                      {logsRefreshing ? '갱신 중...' : '새로고침'}
                    </button>
                  </header>
                  <p className="admin-prompts__logs-caption">
                    실제 생성 요청이 실행되면 해당 프롬프트 내용을 확인할 수 있습니다. 최근 50건이 표시됩니다.
                  </p>
                  {logsLoading ? (
                    <p className="admin-prompts__empty">요청 기록을 불러오는 중입니다...</p>
                  ) : logsError ? (
                    <p className="admin-prompts__empty admin-prompts__empty--error">{logsError}</p>
                  ) : requestLogs.length === 0 ? (
                    <p className="admin-prompts__empty">아직 기록된 요청이 없습니다.</p>
                  ) : (
                    <ul className="admin-prompts__log-list">
                      {requestLogs.map((entry) => {
                        const menuLabel = resolveMenuLabel(entry.menuId)
                        return (
                          <li key={entry.requestId} className="admin-prompts__log-item">
                            <div className="admin-prompts__log-meta">
                              <span className="admin-prompts__log-menu">{menuLabel}</span>
                              <span className="admin-prompts__log-time">{formatDateTime(entry.timestamp)}</span>
                            </div>
                            {entry.projectId ? (
                              <p className="admin-prompts__log-project">프로젝트 ID: {entry.projectId}</p>
                            ) : null}
                            {entry.contextSummary ? (
                              <p className="admin-prompts__log-summary">{entry.contextSummary}</p>
                            ) : null}
                            <details className="admin-prompts__log-details">
                              <summary>프롬프트 전문 보기</summary>
                              <div className="admin-prompts__log-details-content">
                                <div>
                                  <h4 className="admin-prompts__log-heading">시스템 프롬프트</h4>
                                  <pre className="admin-prompts__log-block">{entry.systemPrompt || '내용이 없습니다.'}</pre>
                                </div>
                                <div>
                                  <h4 className="admin-prompts__log-heading">사용자 프롬프트</h4>
                                  <pre className="admin-prompts__log-block">{entry.userPrompt || '내용이 없습니다.'}</pre>
                                </div>
                              </div>
                            </details>
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </section>
                <section className="admin-prompts__hint">
                  <h4 className="admin-prompts__hint-title">템플릿 팁</h4>
                  <p className="admin-prompts__hint-text">
                    첨부 설명 템플릿에는 {'{'}index{'}'}, {'{'}descriptor{'}'}, {'{'}label{'}'}, {'{'}description{'}'}, {'{'}extension{'}'}, {'{'}doc_id{'}'}, {'{'}notes{'}'},
                    {'{'}source_path{'}'} 키를 사용할 수 있습니다.
                  </p>
                </section>
              </aside>
            </div>
          </section>
        </div>
      </div>
      <Modal
        open={previewOpen}
        title="프롬프트 미리보기"
        description="현재 입력된 내용으로 생성된 프롬프트입니다."
        onClose={() => setPreviewOpen(false)}
      >
        <div className="admin-prompts__preview-modal" role="presentation">
          <pre>{preview || '지침을 입력하면 미리보기가 표시됩니다.'}</pre>
        </div>
        <footer className="modal__footer">
          <button type="button" className="modal__button" onClick={() => setPreviewOpen(false)}>
            닫기
          </button>
        </footer>
      </Modal>
    </PageLayout>
  )
}
