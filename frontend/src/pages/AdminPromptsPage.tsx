import { useMemo, useState } from 'react'

import { PageHeader } from '../components/layout/PageHeader'
import { PageLayout } from '../components/layout/PageLayout'

import './AdminPromptsPage.css'

type PromptCategory =
  | 'feature-list'
  | 'testcase-generation'
  | 'defect-report'
  | 'security-report'
  | 'performance-report'

type StatusType = 'idle' | 'success' | 'info'

interface PromptAttachment {
  id: string
  label: string
  description: string
  required: boolean
  acceptedTypes: string
  notes?: string
}

interface PromptMetadataEntry {
  id: string
  key: string
  value: string
}

interface PromptConfig {
  label: string
  summary: string
  requestDescription: string
  systemPrompt: string
  userPrompt: string
  evaluationNotes: string
  attachments: PromptAttachment[]
  metadata: PromptMetadataEntry[]
}

const INITIAL_PROMPTS: Record<PromptCategory, PromptConfig> = {
  'feature-list': {
    label: '기능리스트 생성',
    summary:
      '요구사항, 사용 매뉴얼, 기존 기능 정의서를 바탕으로 새로운 프로젝트의 기능 정의서를 생성하는 기본 템플릿입니다.',
    requestDescription:
      '업로드된 요구사항을 검토하여 기능 목록, 기능 설명, 관련 근거 자료를 정리한 결과물을 생성합니다. 입력 문서를 정제하고 핵심 내용을 추출할 수 있도록 안내해 주세요.',
    systemPrompt:
      'You are an assistant that specialises in extracting structured feature definitions from Korean software requirement documents. Use polite and concise Korean, preserve numbering, and reference uploaded evidence where helpful.',
    userPrompt:
      '아래 첨부된 자료들을 검토하여 기능리스트 초안을 작성해 주세요.\n- 각 기능은 식별자, 이름, 설명, 근거 자료 링크를 포함합니다.\n- 사용자 매뉴얼과 기존 기능리스트가 있으면 우선적으로 반영하고, 누락된 요구사항이 있으면 “추가 제안” 섹션에 정리해 주세요.',
    evaluationNotes:
      '출력은 Markdown 테이블과 추가 제안 요약으로 구성합니다. 첨부 파일이 부족할 경우 필요한 자료를 명시적으로 요청하도록 안내하세요.',
    attachments: [
      {
        id: 'feature-manual',
        label: '사용자 매뉴얼',
        description: '최신 버전의 사용자 매뉴얼. 기능 흐름과 화면 정의가 포함되어야 합니다.',
        required: true,
        acceptedTypes: 'PDF, DOCX, HWP',
        notes: '없으면 요구사항 명세서 또는 제안요청서를 대신 업로드하도록 안내',
      },
      {
        id: 'feature-config',
        label: '형상 이미지',
        description: 'UI 흐름, 메뉴 구조, 아키텍처를 설명하는 다이어그램.',
        required: false,
        acceptedTypes: 'PNG, JPG, SVG',
        notes: '가능하다면 최신 형상 버전을 첨부',
      },
      {
        id: 'feature-existing',
        label: '기존 기능리스트',
        description: '벤더 또는 이전 프로젝트에서 제공한 기능 정의 자료.',
        required: false,
        acceptedTypes: 'XLSX, CSV, PDF',
      },
    ],
    metadata: [
      {
        id: 'feature-tone',
        key: 'tone',
        value: 'formal-korean',
      },
      {
        id: 'feature-output',
        key: 'output_format',
        value: 'markdown-table+summary',
      },
    ],
  },
  'testcase-generation': {
    label: '테스트케이스 생성',
    summary:
      '테스트 케이스 설계 자동화를 위한 프롬프트 영역입니다. 요구사항과 기능리스트를 기반으로 테스트 항목을 도출합니다.',
    requestDescription: '',
    systemPrompt: '',
    userPrompt: '',
    evaluationNotes: '',
    attachments: [],
    metadata: [],
  },
  'defect-report': {
    label: '결함 리포트',
    summary:
      '결함 재현 단계, 영향도, 스크린샷을 정리하여 리포트 형태로 변환하는 프롬프트 설정 공간입니다.',
    requestDescription: '',
    systemPrompt: '',
    userPrompt: '',
    evaluationNotes: '',
    attachments: [],
    metadata: [],
  },
  'security-report': {
    label: '보안성 리포트',
    summary:
      '보안 점검 결과와 취약점 목록을 요약하는 데 사용할 프롬프트를 등록하는 공간입니다.',
    requestDescription: '',
    systemPrompt: '',
    userPrompt: '',
    evaluationNotes: '',
    attachments: [],
    metadata: [],
  },
  'performance-report': {
    label: '성능 평가 리포트',
    summary:
      '성능 측정 데이터와 분석 결과를 구조화된 보고서로 전환하는 프롬프트 초안을 준비할 수 있습니다.',
    requestDescription: '',
    systemPrompt: '',
    userPrompt: '',
    evaluationNotes: '',
    attachments: [],
    metadata: [],
  },
}

function cloneAttachment(attachment: PromptAttachment): PromptAttachment {
  return { ...attachment }
}

function cloneMetadataEntry(entry: PromptMetadataEntry): PromptMetadataEntry {
  return { ...entry }
}

function cloneConfig(config: PromptConfig): PromptConfig {
  return {
    ...config,
    attachments: config.attachments.map(cloneAttachment),
    metadata: config.metadata.map(cloneMetadataEntry),
  }
}

function cloneConfigMap(map: Record<PromptCategory, PromptConfig>): Record<PromptCategory, PromptConfig> {
  return Object.fromEntries(
    Object.entries(map).map(([key, value]) => [key as PromptCategory, cloneConfig(value)]),
  ) as Record<PromptCategory, PromptConfig>
}

let uniqueId = 0
function createUniqueId(prefix: string): string {
  uniqueId += 1
  return `${prefix}-${Date.now()}-${uniqueId}`
}

export function AdminPromptsPage() {
  const [configs, setConfigs] = useState<Record<PromptCategory, PromptConfig>>(() => cloneConfigMap(INITIAL_PROMPTS))
  const [activeCategory, setActiveCategory] = useState<PromptCategory>('feature-list')
  const [status, setStatus] = useState<{ category: PromptCategory | null; type: StatusType; message: string }>(
    { category: null, type: 'idle', message: '' },
  )

  const activeConfig = configs[activeCategory]

  const navItems = useMemo(
    () =>
      (Object.entries(configs) as [PromptCategory, PromptConfig][]).map(([key, value]) => ({
        id: key,
        label: value.label,
        summary: value.summary,
      })),
    [configs],
  )

  const handleUpdateField = (field: keyof Pick<PromptConfig, 'requestDescription' | 'systemPrompt' | 'userPrompt' | 'evaluationNotes'>, value: string) => {
    setConfigs((prev) => ({
      ...prev,
      [activeCategory]: {
        ...prev[activeCategory],
        [field]: value,
      },
    }))
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleUpdateAttachment = (
    attachmentId: string,
    field: keyof Pick<PromptAttachment, 'label' | 'description' | 'acceptedTypes' | 'notes'>,
    value: string,
  ) => {
    setConfigs((prev) => {
      const current = prev[activeCategory]
      const nextAttachments = current.attachments.map((attachment) =>
        attachment.id === attachmentId ? { ...attachment, [field]: value } : attachment,
      )
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          attachments: nextAttachments,
        },
      }
    })
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleToggleAttachmentRequired = (attachmentId: string, required: boolean) => {
    setConfigs((prev) => {
      const current = prev[activeCategory]
      const nextAttachments = current.attachments.map((attachment) =>
        attachment.id === attachmentId ? { ...attachment, required } : attachment,
      )
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          attachments: nextAttachments,
        },
      }
    })
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleRemoveAttachment = (attachmentId: string) => {
    setConfigs((prev) => {
      const current = prev[activeCategory]
      const nextAttachments = current.attachments.filter((attachment) => attachment.id !== attachmentId)
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          attachments: nextAttachments,
        },
      }
    })
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleAddAttachment = () => {
    setConfigs((prev) => {
      const current = prev[activeCategory]
      const newAttachment: PromptAttachment = {
        id: createUniqueId(`${activeCategory}-attachment`),
        label: '새 첨부 자료',
        description: '',
        required: false,
        acceptedTypes: '',
      }
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          attachments: [...current.attachments, newAttachment],
        },
      }
    })
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleUpdateMetadata = (entryId: string, field: 'key' | 'value', value: string) => {
    setConfigs((prev) => {
      const current = prev[activeCategory]
      const nextMetadata = current.metadata.map((entry) =>
        entry.id === entryId ? { ...entry, [field]: value } : entry,
      )
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          metadata: nextMetadata,
        },
      }
    })
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleRemoveMetadata = (entryId: string) => {
    setConfigs((prev) => {
      const current = prev[activeCategory]
      const nextMetadata = current.metadata.filter((entry) => entry.id !== entryId)
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          metadata: nextMetadata,
        },
      }
    })
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleAddMetadata = () => {
    setConfigs((prev) => {
      const current = prev[activeCategory]
      const newEntry: PromptMetadataEntry = {
        id: createUniqueId(`${activeCategory}-metadata`),
        key: '',
        value: '',
      }
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          metadata: [...current.metadata, newEntry],
        },
      }
    })
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleSave = () => {
    setStatus({
      category: activeCategory,
      type: 'success',
      message: '현재 입력값을 임시로 저장했습니다. 백엔드 연동 시 이 로직을 API 호출로 교체하세요.',
    })
  }

  const handleReset = () => {
    setConfigs((prev) => ({
      ...prev,
      [activeCategory]: cloneConfig(INITIAL_PROMPTS[activeCategory]),
    }))
    setStatus({
      category: activeCategory,
      type: 'info',
      message: '초기 템플릿으로 되돌렸습니다.',
    })
  }

  return (
    <PageLayout>
      <div className="admin-prompts">
        <PageHeader
          eyebrow="프롬프트 자산 관리"
          title="요청 템플릿 & 첨부 자료 설정"
          subtitle="기능리스트, 테스트케이스, 결함 리포트 등 각 생성 작업에 필요한 프롬프트와 첨부 요구사항을 한 곳에서 관리하세요."
        />

        <div className="admin-prompts__layout">
          <nav className="admin-prompts__nav" aria-label="프롬프트 카테고리">
            {navItems.map((item) => {
              const isActive = item.id === activeCategory
              return (
                <button
                  type="button"
                  key={item.id}
                  className={`admin-prompts__nav-button${isActive ? ' admin-prompts__nav-button--active' : ''}`}
                  onClick={() => setActiveCategory(item.id)}
                >
                  <span className="admin-prompts__nav-label">{item.label}</span>
                  <span className="admin-prompts__nav-summary">{item.summary}</span>
                </button>
              )
            })}
          </nav>

          <section className="admin-prompts__content" aria-live="polite">
            <header className="admin-prompts__content-header">
              <h2 className="admin-prompts__content-title">{activeConfig.label}</h2>
              <p className="admin-prompts__content-description">{activeConfig.summary}</p>
            </header>

            <div className="admin-prompts__field">
              <label className="admin-prompts__label" htmlFor="request-description">
                요청 설명
              </label>
              <textarea
                id="request-description"
                className="admin-prompts__textarea"
                placeholder="요청 의도, 출력물 구성, 톤앤매너 등을 설명해 주세요."
                value={activeConfig.requestDescription}
                onChange={(event) => handleUpdateField('requestDescription', event.target.value)}
                rows={4}
              />
            </div>

            <div className="admin-prompts__grid">
              <div className="admin-prompts__field">
                <label className="admin-prompts__label" htmlFor="system-prompt">
                  시스템 프롬프트
                </label>
                <textarea
                  id="system-prompt"
                  className="admin-prompts__textarea"
                  placeholder="모델에게 줄 역할 및 행동 지침을 입력하세요."
                  value={activeConfig.systemPrompt}
                  onChange={(event) => handleUpdateField('systemPrompt', event.target.value)}
                  rows={6}
                />
              </div>

              <div className="admin-prompts__field">
                <label className="admin-prompts__label" htmlFor="user-prompt">
                  사용자 프롬프트 템플릿
                </label>
                <textarea
                  id="user-prompt"
                  className="admin-prompts__textarea"
                  placeholder="사용자에게서 전달받는 입력 서식을 정의하세요."
                  value={activeConfig.userPrompt}
                  onChange={(event) => handleUpdateField('userPrompt', event.target.value)}
                  rows={6}
                />
              </div>
            </div>

            <div className="admin-prompts__field">
              <label className="admin-prompts__label" htmlFor="evaluation-notes">
                출력 검증 & 후처리 메모
              </label>
              <textarea
                id="evaluation-notes"
                className="admin-prompts__textarea"
                placeholder="출력 검증 체크리스트, 후처리 규칙, 품질 기준 등을 기록하세요."
                value={activeConfig.evaluationNotes}
                onChange={(event) => handleUpdateField('evaluationNotes', event.target.value)}
                rows={4}
              />
            </div>

            <section className="admin-prompts__group" aria-labelledby="attachments-title">
              <div className="admin-prompts__group-header">
                <h3 id="attachments-title" className="admin-prompts__group-title">
                  첨부 자료 요구사항
                </h3>
                <button type="button" className="admin-prompts__secondary" onClick={handleAddAttachment}>
                  첨부 항목 추가
                </button>
              </div>
              {activeConfig.attachments.length > 0 ? (
                <ul className="admin-prompts__list">
                  {activeConfig.attachments.map((attachment) => (
                    <li key={attachment.id} className="admin-prompts__list-item">
                      <div className="admin-prompts__list-grid">
                        <div className="admin-prompts__field">
                          <label className="admin-prompts__label" htmlFor={`${attachment.id}-label`}>
                            자료 이름
                          </label>
                          <input
                            id={`${attachment.id}-label`}
                            type="text"
                            className="admin-prompts__input"
                            value={attachment.label}
                            onChange={(event) =>
                              handleUpdateAttachment(attachment.id, 'label', event.target.value)
                            }
                          />
                        </div>

                        <div className="admin-prompts__field">
                          <label className="admin-prompts__label" htmlFor={`${attachment.id}-types`}>
                            허용 확장자 또는 소스
                          </label>
                          <input
                            id={`${attachment.id}-types`}
                            type="text"
                            className="admin-prompts__input"
                            placeholder="예: PDF, XLSX / 또는 Google Drive 폴더 경로"
                            value={attachment.acceptedTypes}
                            onChange={(event) =>
                              handleUpdateAttachment(attachment.id, 'acceptedTypes', event.target.value)
                            }
                          />
                        </div>
                      </div>

                      <div className="admin-prompts__field">
                        <label className="admin-prompts__label" htmlFor={`${attachment.id}-description`}>
                          설명
                        </label>
                        <textarea
                          id={`${attachment.id}-description`}
                          className="admin-prompts__textarea"
                          rows={3}
                          value={attachment.description}
                          onChange={(event) =>
                            handleUpdateAttachment(attachment.id, 'description', event.target.value)
                          }
                        />
                      </div>

                      <div className="admin-prompts__list-footer">
                        <label className="admin-prompts__checkbox">
                          <input
                            type="checkbox"
                            checked={attachment.required}
                            onChange={(event) =>
                              handleToggleAttachmentRequired(attachment.id, event.target.checked)
                            }
                          />
                          필수 첨부
                        </label>

                        <div className="admin-prompts__notes">
                          <label className="admin-prompts__label" htmlFor={`${attachment.id}-notes`}>
                            가이드 메모 (선택)
                          </label>
                          <textarea
                            id={`${attachment.id}-notes`}
                            className="admin-prompts__textarea"
                            rows={2}
                            value={attachment.notes ?? ''}
                            placeholder="업로드 시 추가 안내가 필요하다면 작성하세요."
                            onChange={(event) =>
                              handleUpdateAttachment(attachment.id, 'notes', event.target.value)
                            }
                          />
                        </div>

                        <button
                          type="button"
                          className="admin-prompts__remove"
                          onClick={() => handleRemoveAttachment(attachment.id)}
                        >
                          삭제
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="admin-prompts__empty">등록된 첨부 자료 요구사항이 없습니다. 항목을 추가해 주세요.</div>
              )}
            </section>

            <section className="admin-prompts__group" aria-labelledby="metadata-title">
              <div className="admin-prompts__group-header">
                <h3 id="metadata-title" className="admin-prompts__group-title">
                  추가 메타데이터
                </h3>
                <button type="button" className="admin-prompts__secondary" onClick={handleAddMetadata}>
                  메타데이터 추가
                </button>
              </div>
              {activeConfig.metadata.length > 0 ? (
                <ul className="admin-prompts__list admin-prompts__list--compact">
                  {activeConfig.metadata.map((entry) => (
                    <li key={entry.id} className="admin-prompts__list-item">
                      <div className="admin-prompts__list-grid admin-prompts__list-grid--metadata">
                        <div className="admin-prompts__field">
                          <label className="admin-prompts__label" htmlFor={`${entry.id}-key`}>
                            키
                          </label>
                          <input
                            id={`${entry.id}-key`}
                            type="text"
                            className="admin-prompts__input"
                            value={entry.key}
                            onChange={(event) =>
                              handleUpdateMetadata(entry.id, 'key', event.target.value)
                            }
                          />
                        </div>
                        <div className="admin-prompts__field">
                          <label className="admin-prompts__label" htmlFor={`${entry.id}-value`}>
                            값
                          </label>
                          <input
                            id={`${entry.id}-value`}
                            type="text"
                            className="admin-prompts__input"
                            value={entry.value}
                            onChange={(event) =>
                              handleUpdateMetadata(entry.id, 'value', event.target.value)
                            }
                          />
                        </div>
                      </div>
                      <button
                        type="button"
                        className="admin-prompts__remove"
                        onClick={() => handleRemoveMetadata(entry.id)}
                      >
                        삭제
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="admin-prompts__empty">추가 메타데이터가 없습니다. 필요 시 항목을 추가하세요.</div>
              )}
            </section>

            {status.category === activeCategory && status.message && (
              <div
                className={`admin-prompts__status admin-prompts__status--${status.type}`}
                role={status.type === 'success' ? 'status' : 'note'}
              >
                {status.message}
              </div>
            )}

            <div className="admin-prompts__actions">
              <button type="button" className="admin-prompts__primary" onClick={handleSave}>
                임시 저장
              </button>
              <button type="button" className="admin-prompts__secondary" onClick={handleReset}>
                초기값으로 복원
              </button>
            </div>
          </section>
        </div>
      </div>
    </PageLayout>
  )
}
