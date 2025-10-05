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

interface PromptSection {
  id: string
  label: string
  content: string
  enabled: boolean
}

interface PromptScaffolding {
  attachmentsHeading: string
  attachmentsIntro: string
  closingNote: string
  formatWarning: string
}

type BuiltinContextRenderMode = 'file' | 'image' | 'text'

interface BuiltinContext {
  id: string
  label: string
  description: string
  sourcePath: string
  renderMode: BuiltinContextRenderMode
  includeInPrompt: boolean
  showInAttachmentList: boolean
}

interface ModelParameters {
  temperature: number
  topP: number
  maxOutputTokens: number
  presencePenalty: number
  frequencyPenalty: number
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
  userPromptSections: PromptSection[]
  scaffolding: PromptScaffolding
  attachmentDescriptorTemplate: string
  builtinContexts: BuiltinContext[]
  modelParameters: ModelParameters
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
    userPromptSections: [
      {
        id: 'feature-overview',
        label: '분석 요청',
        content:
          '1. 첨부 자료에서 핵심 요구사항, 비즈니스 규칙, 화면 흐름을 추출한 뒤\n2. 기능을 대·중·소 분류 체계로 정리하고\n3. 근거가 된 원문이나 페이지 번호를 증빙 자료 열에 기재해 주세요.',
        enabled: true,
      },
      {
        id: 'feature-quality',
        label: '품질 기준',
        content:
          '- 중복된 기능은 병합하고, 이름은 한글 명사형으로 통일합니다.\n- 기능 설명에는 “무엇을/왜”를 한 문장씩 포함하고, 정량 기준이 있다면 추가합니다.',
        enabled: true,
      },
      {
        id: 'feature-followup',
        label: '후속 지시',
        content:
          'CSV에는 열 순서를 “대분류, 중분류, 소분류, 기능명, 기능설명, 근거자료”로 고정하고, 추가 제안은 별도 Markdown 섹션으로 출력하세요.',
        enabled: true,
      },
    ],
    scaffolding: {
      attachmentsHeading: '첨부 파일 목록',
      attachmentsIntro: '이번 요청에 포함된 참고 자료입니다. 파일별로 어떤 역할인지 명확히 이해하고 활용해 주세요.',
      closingNote:
        '위 자료는 신규 프로젝트 기능리스트 작성을 위한 참고 자료입니다. 누락된 영역이 보이면 추가 제안 섹션에 적어 주세요.',
      formatWarning: '⚠️ 결과물은 반드시 CSV 구조를 준수해야 하며, 다른 파일 형식이나 자연어 단락으로 대체하지 마세요.',
    },
    attachmentDescriptorTemplate:
      '{{index}}. {{label}} ({{extension}}) — {{description}}{{notesLine}}',
    builtinContexts: [
      {
        id: 'feature-template',
        label: '기능리스트 예제 양식',
        description: '내장된 기능리스트 예제 XLSX를 PDF로 변환한 자료. 열 구성 및 표기 예시 참고용.',
        sourcePath: 'template/가.계획/GS-B-XX-XXXX 기능리스트 v1.0.xlsx',
        renderMode: 'file',
        includeInPrompt: true,
        showInAttachmentList: true,
      },
    ],
    modelParameters: {
      temperature: 0.2,
      topP: 0.9,
      maxOutputTokens: 1600,
      presencePenalty: 0,
      frequencyPenalty: 0,
    },
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
    userPromptSections: [],
    scaffolding: {
      attachmentsHeading: '',
      attachmentsIntro: '',
      closingNote: '',
      formatWarning: '',
    },
    attachmentDescriptorTemplate: '{{index}}. {{label}}',
    builtinContexts: [],
    modelParameters: {
      temperature: 0.2,
      topP: 0.9,
      maxOutputTokens: 1200,
      presencePenalty: 0,
      frequencyPenalty: 0,
    },
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
    userPromptSections: [],
    scaffolding: {
      attachmentsHeading: '',
      attachmentsIntro: '',
      closingNote: '',
      formatWarning: '',
    },
    attachmentDescriptorTemplate: '{{index}}. {{label}}',
    builtinContexts: [],
    modelParameters: {
      temperature: 0.2,
      topP: 0.9,
      maxOutputTokens: 1200,
      presencePenalty: 0,
      frequencyPenalty: 0,
    },
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
    userPromptSections: [],
    scaffolding: {
      attachmentsHeading: '',
      attachmentsIntro: '',
      closingNote: '',
      formatWarning: '',
    },
    attachmentDescriptorTemplate: '{{index}}. {{label}}',
    builtinContexts: [],
    modelParameters: {
      temperature: 0.2,
      topP: 0.9,
      maxOutputTokens: 1200,
      presencePenalty: 0,
      frequencyPenalty: 0,
    },
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
    userPromptSections: [],
    scaffolding: {
      attachmentsHeading: '',
      attachmentsIntro: '',
      closingNote: '',
      formatWarning: '',
    },
    attachmentDescriptorTemplate: '{{index}}. {{label}}',
    builtinContexts: [],
    modelParameters: {
      temperature: 0.2,
      topP: 0.9,
      maxOutputTokens: 1200,
      presencePenalty: 0,
      frequencyPenalty: 0,
    },
  },
}

function cloneAttachment(attachment: PromptAttachment): PromptAttachment {
  return { ...attachment }
}

function cloneMetadataEntry(entry: PromptMetadataEntry): PromptMetadataEntry {
  return { ...entry }
}

function cloneSection(section: PromptSection): PromptSection {
  return { ...section }
}

function cloneScaffolding(scaffolding: PromptScaffolding): PromptScaffolding {
  return { ...scaffolding }
}

function cloneBuiltinContext(context: BuiltinContext): BuiltinContext {
  return { ...context }
}

function cloneModelParameters(parameters: ModelParameters): ModelParameters {
  return { ...parameters }
}

function cloneConfig(config: PromptConfig): PromptConfig {
  return {
    ...config,
    attachments: config.attachments.map(cloneAttachment),
    metadata: config.metadata.map(cloneMetadataEntry),
    userPromptSections: config.userPromptSections.map(cloneSection),
    scaffolding: cloneScaffolding(config.scaffolding),
    builtinContexts: config.builtinContexts.map(cloneBuiltinContext),
    modelParameters: cloneModelParameters(config.modelParameters),
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

  const previewPrompt = useMemo(() => {
    const segments: string[] = []

    const base = activeConfig.userPrompt.trim()
    if (base) {
      segments.push(base)
    }

    activeConfig.userPromptSections
      .filter((section) => section.enabled)
      .forEach((section) => {
        const label = section.label.trim()
        const content = section.content.trim()
        if (!label && !content) {
          return
        }
        if (label && content) {
          segments.push(`${label}\n${content}`)
        } else {
          segments.push(label || content)
        }
      })

    const heading = activeConfig.scaffolding.attachmentsHeading.trim()
    if (heading) {
      segments.push(heading)
    }

    const intro = activeConfig.scaffolding.attachmentsIntro.trim()
    if (intro) {
      segments.push(intro)
    }

    const descriptorTemplate = activeConfig.attachmentDescriptorTemplate || '{{index}}. {{label}}'
    const descriptorLines = activeConfig.attachments.map((attachment, index) => {
      const extension = attachment.acceptedTypes.split(',')[0]?.trim() || '자료'
      const notesLine = attachment.notes ? `\n   비고: ${attachment.notes}` : ''
      return descriptorTemplate
        .replaceAll('{{index}}', String(index + 1))
        .replaceAll('{{label}}', attachment.label || '첨부 자료')
        .replaceAll('{{description}}', attachment.description || '')
        .replaceAll('{{extension}}', extension)
        .replaceAll('{{notes}}', attachment.notes ?? '')
        .replaceAll('{{notesLine}}', notesLine)
    })

    const builtinLines = activeConfig.builtinContexts
      .filter((context) => context.showInAttachmentList)
      .map((context, index) => {
        const templateIndex = descriptorLines.length + index + 1
        return descriptorTemplate
          .replaceAll('{{index}}', String(templateIndex))
          .replaceAll('{{label}}', context.label || '내장 컨텍스트')
          .replaceAll('{{description}}', context.description || '')
          .replaceAll('{{extension}}', context.renderMode === 'image' ? '이미지' : 'PDF')
          .replaceAll('{{notes}}', context.sourcePath)
          .replaceAll('{{notesLine}}', context.sourcePath ? `\n   경로: ${context.sourcePath}` : '')
      })

    const combinedDescriptorLines = [...descriptorLines, ...builtinLines]

    if (combinedDescriptorLines.length > 0) {
      segments.push(combinedDescriptorLines.join('\n'))
    }

    const closing = activeConfig.scaffolding.closingNote.trim()
    if (closing) {
      segments.push(closing)
    }

    const warning = activeConfig.scaffolding.formatWarning.trim()
    if (warning) {
      segments.push(warning)
    }

    return segments.join('\n\n').trim()
  }, [activeConfig])

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

  const handleUpdateSection = (
    sectionId: string,
    field: keyof Pick<PromptSection, 'label' | 'content'>,
    value: string,
  ) => {
    setConfigs((prev) => {
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
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleToggleSectionEnabled = (sectionId: string, enabled: boolean) => {
    setConfigs((prev) => {
      const current = prev[activeCategory]
      const nextSections = current.userPromptSections.map((section) =>
        section.id === sectionId ? { ...section, enabled } : section,
      )
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          userPromptSections: nextSections,
        },
      }
    })
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleRemoveSection = (sectionId: string) => {
    setConfigs((prev) => {
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
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleAddSection = () => {
    setConfigs((prev) => {
      const current = prev[activeCategory]
      const newSection: PromptSection = {
        id: createUniqueId(`${activeCategory}-section`),
        label: '새 지침 구간',
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
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleUpdateScaffolding = (
    field: keyof PromptScaffolding,
    value: string,
  ) => {
    setConfigs((prev) => ({
      ...prev,
      [activeCategory]: {
        ...prev[activeCategory],
        scaffolding: {
          ...prev[activeCategory].scaffolding,
          [field]: value,
        },
      },
    }))
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleUpdateDescriptorTemplate = (value: string) => {
    setConfigs((prev) => ({
      ...prev,
      [activeCategory]: {
        ...prev[activeCategory],
        attachmentDescriptorTemplate: value,
      },
    }))
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleUpdateBuiltinContext = <K extends keyof Pick<
    BuiltinContext,
    'label' | 'description' | 'sourcePath' | 'renderMode'
  >>(contextId: string, field: K, value: BuiltinContext[K]) => {
    setConfigs((prev) => {
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
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleToggleBuiltinContext = (
    contextId: string,
    field: keyof Pick<BuiltinContext, 'includeInPrompt' | 'showInAttachmentList'>,
    value: boolean,
  ) => {
    setConfigs((prev) => {
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
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleRemoveBuiltinContext = (contextId: string) => {
    setConfigs((prev) => {
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
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleAddBuiltinContext = () => {
    setConfigs((prev) => {
      const current = prev[activeCategory]
      const newContext: BuiltinContext = {
        id: createUniqueId(`${activeCategory}-builtin`),
        label: '새 내장 컨텍스트',
        description: '',
        sourcePath: '',
        renderMode: 'file',
        includeInPrompt: true,
        showInAttachmentList: false,
      }
      return {
        ...prev,
        [activeCategory]: {
          ...current,
          builtinContexts: [...current.builtinContexts, newContext],
        },
      }
    })
    setStatus({ category: null, type: 'idle', message: '' })
  }

  const handleUpdateModelParameters = <K extends keyof ModelParameters>(field: K, value: number) => {
    const nextValue = Number.isFinite(value) ? value : 0
    setConfigs((prev) => ({
      ...prev,
      [activeCategory]: {
        ...prev[activeCategory],
        modelParameters: {
          ...prev[activeCategory].modelParameters,
          [field]: nextValue,
        },
      },
    }))
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

            <section className="admin-prompts__group" aria-labelledby="sections-title">
              <div className="admin-prompts__group-header">
                <h3 id="sections-title" className="admin-prompts__group-title">
                  사용자 프롬프트 세부 지침
                </h3>
                <button type="button" className="admin-prompts__secondary" onClick={handleAddSection}>
                  지침 블록 추가
                </button>
              </div>
              {activeConfig.userPromptSections.length > 0 ? (
                <ul className="admin-prompts__list">
                  {activeConfig.userPromptSections.map((section) => (
                    <li key={section.id} className="admin-prompts__list-item">
                      <div className="admin-prompts__list-grid admin-prompts__list-grid--section">
                        <div className="admin-prompts__field">
                          <label className="admin-prompts__label" htmlFor={`${section.id}-label`}>
                            구간 제목
                          </label>
                          <input
                            id={`${section.id}-label`}
                            type="text"
                            className="admin-prompts__input"
                            value={section.label}
                            onChange={(event) => handleUpdateSection(section.id, 'label', event.target.value)}
                          />
                        </div>
                        <label className="admin-prompts__switch">
                          <input
                            type="checkbox"
                            checked={section.enabled}
                            onChange={(event) => handleToggleSectionEnabled(section.id, event.target.checked)}
                          />
                          사용
                        </label>
                      </div>
                      <div className="admin-prompts__field">
                        <label className="admin-prompts__label" htmlFor={`${section.id}-content`}>
                          지침 내용
                        </label>
                        <textarea
                          id={`${section.id}-content`}
                          className="admin-prompts__textarea"
                          rows={4}
                          value={section.content}
                          onChange={(event) => handleUpdateSection(section.id, 'content', event.target.value)}
                        />
                      </div>
                      <button
                        type="button"
                        className="admin-prompts__remove"
                        onClick={() => handleRemoveSection(section.id)}
                      >
                        삭제
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="admin-prompts__empty">아직 세부 지침이 없습니다. 필요한 지시를 추가해 주세요.</div>
              )}
            </section>

            <section className="admin-prompts__group" aria-labelledby="scaffolding-title">
              <h3 id="scaffolding-title" className="admin-prompts__group-title">
                프롬프트 스캐폴딩
              </h3>
              <div className="admin-prompts__grid">
                <div className="admin-prompts__field">
                  <label className="admin-prompts__label" htmlFor="scaffolding-heading">
                    첨부 목록 제목
                  </label>
                  <input
                    id="scaffolding-heading"
                    type="text"
                    className="admin-prompts__input"
                    value={activeConfig.scaffolding.attachmentsHeading}
                    onChange={(event) => handleUpdateScaffolding('attachmentsHeading', event.target.value)}
                  />
                </div>
                <div className="admin-prompts__field">
                  <label className="admin-prompts__label" htmlFor="scaffolding-intro">
                    첨부 안내 문구
                  </label>
                  <textarea
                    id="scaffolding-intro"
                    className="admin-prompts__textarea"
                    rows={3}
                    value={activeConfig.scaffolding.attachmentsIntro}
                    onChange={(event) => handleUpdateScaffolding('attachmentsIntro', event.target.value)}
                  />
                </div>
              </div>
              <div className="admin-prompts__grid">
                <div className="admin-prompts__field">
                  <label className="admin-prompts__label" htmlFor="scaffolding-closing">
                    마무리 안내 문장
                  </label>
                  <textarea
                    id="scaffolding-closing"
                    className="admin-prompts__textarea"
                    rows={3}
                    value={activeConfig.scaffolding.closingNote}
                    onChange={(event) => handleUpdateScaffolding('closingNote', event.target.value)}
                  />
                </div>
                <div className="admin-prompts__field">
                  <label className="admin-prompts__label" htmlFor="scaffolding-warning">
                    형식 제한 경고
                  </label>
                  <textarea
                    id="scaffolding-warning"
                    className="admin-prompts__textarea"
                    rows={3}
                    value={activeConfig.scaffolding.formatWarning}
                    onChange={(event) => handleUpdateScaffolding('formatWarning', event.target.value)}
                  />
                </div>
              </div>
            </section>

            <section className="admin-prompts__group" aria-labelledby="descriptor-title">
              <h3 id="descriptor-title" className="admin-prompts__group-title">
                첨부 설명 포맷
              </h3>
              <div className="admin-prompts__field">
                <label className="admin-prompts__label" htmlFor="descriptor-template">
                  템플릿 문자열
                </label>
                <input
                  id="descriptor-template"
                  type="text"
                  className="admin-prompts__input"
                  value={activeConfig.attachmentDescriptorTemplate}
                  onChange={(event) => handleUpdateDescriptorTemplate(event.target.value)}
                  placeholder="예: {{index}}. {{label}} ({{extension}}) — {{description}}"
                />
              </div>
              <p className="admin-prompts__help">
                {'사용 가능한 플레이스홀더: {{index}}, {{label}}, {{description}}, {{extension}}, {{notes}}, {{notesLine}}'}
              </p>
            </section>

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

            <section className="admin-prompts__group" aria-labelledby="builtin-title">
              <div className="admin-prompts__group-header">
                <h3 id="builtin-title" className="admin-prompts__group-title">
                  내장 컨텍스트
                </h3>
                <button type="button" className="admin-prompts__secondary" onClick={handleAddBuiltinContext}>
                  컨텍스트 추가
                </button>
              </div>
              {activeConfig.builtinContexts.length > 0 ? (
                <ul className="admin-prompts__list">
                  {activeConfig.builtinContexts.map((context) => (
                    <li key={context.id} className="admin-prompts__list-item">
                      <div className="admin-prompts__list-grid admin-prompts__list-grid--builtin">
                        <div className="admin-prompts__field">
                          <label className="admin-prompts__label" htmlFor={`${context.id}-label`}>
                            이름
                          </label>
                          <input
                            id={`${context.id}-label`}
                            type="text"
                            className="admin-prompts__input"
                            value={context.label}
                            onChange={(event) => handleUpdateBuiltinContext(context.id, 'label', event.target.value)}
                          />
                        </div>
                        <div className="admin-prompts__field">
                          <label className="admin-prompts__label" htmlFor={`${context.id}-source`}>
                            참조 경로 또는 설명
                          </label>
                          <input
                            id={`${context.id}-source`}
                            type="text"
                            className="admin-prompts__input"
                            value={context.sourcePath}
                            onChange={(event) => handleUpdateBuiltinContext(context.id, 'sourcePath', event.target.value)}
                            placeholder="예: template/... 또는 외부 링크"
                          />
                        </div>
                      </div>

                      <div className="admin-prompts__field">
                        <label className="admin-prompts__label" htmlFor={`${context.id}-description`}>
                          설명
                        </label>
                        <textarea
                          id={`${context.id}-description`}
                          className="admin-prompts__textarea"
                          rows={3}
                          value={context.description}
                          onChange={(event) => handleUpdateBuiltinContext(context.id, 'description', event.target.value)}
                        />
                      </div>

                      <div className="admin-prompts__list-footer admin-prompts__list-footer--wrap">
                        <div className="admin-prompts__field admin-prompts__field--inline">
                          <label className="admin-prompts__label" htmlFor={`${context.id}-render`}>
                            렌더링 방식
                          </label>
                          <select
                            id={`${context.id}-render`}
                            className="admin-prompts__select"
                            value={context.renderMode}
                            onChange={(event) =>
                              handleUpdateBuiltinContext(
                                context.id,
                                'renderMode',
                                event.target.value as BuiltinContextRenderMode,
                              )
                            }
                          >
                            <option value="file">파일</option>
                            <option value="image">이미지</option>
                            <option value="text">텍스트</option>
                          </select>
                        </div>

                        <label className="admin-prompts__switch">
                          <input
                            type="checkbox"
                            checked={context.includeInPrompt}
                            onChange={(event) =>
                              handleToggleBuiltinContext(context.id, 'includeInPrompt', event.target.checked)
                            }
                          />
                          모델에 전달
                        </label>

                        <label className="admin-prompts__switch">
                          <input
                            type="checkbox"
                            checked={context.showInAttachmentList}
                            onChange={(event) =>
                              handleToggleBuiltinContext(context.id, 'showInAttachmentList', event.target.checked)
                            }
                          />
                          첨부 목록에 노출
                        </label>

                        <button
                          type="button"
                          className="admin-prompts__remove"
                          onClick={() => handleRemoveBuiltinContext(context.id)}
                        >
                          삭제
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="admin-prompts__empty">등록된 내장 컨텍스트가 없습니다. 필요 시 추가하세요.</div>
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

            <section className="admin-prompts__group" aria-labelledby="model-params-title">
              <h3 id="model-params-title" className="admin-prompts__group-title">
                모델 파라미터
              </h3>
              <div className="admin-prompts__grid admin-prompts__grid--metrics">
                <div className="admin-prompts__field">
                  <label className="admin-prompts__label" htmlFor="param-temperature">
                    Temperature
                  </label>
                  <input
                    id="param-temperature"
                    type="number"
                    step={0.1}
                    min={0}
                    max={2}
                    className="admin-prompts__input"
                    value={activeConfig.modelParameters.temperature}
                    onChange={(event) =>
                      handleUpdateModelParameters('temperature', Number(event.target.value))
                    }
                  />
                </div>
                <div className="admin-prompts__field">
                  <label className="admin-prompts__label" htmlFor="param-top-p">
                    Top P
                  </label>
                  <input
                    id="param-top-p"
                    type="number"
                    step={0.05}
                    min={0}
                    max={1}
                    className="admin-prompts__input"
                    value={activeConfig.modelParameters.topP}
                    onChange={(event) => handleUpdateModelParameters('topP', Number(event.target.value))}
                  />
                </div>
                <div className="admin-prompts__field">
                  <label className="admin-prompts__label" htmlFor="param-max-tokens">
                    최대 출력 토큰
                  </label>
                  <input
                    id="param-max-tokens"
                    type="number"
                    step={50}
                    min={0}
                    className="admin-prompts__input"
                    value={activeConfig.modelParameters.maxOutputTokens}
                    onChange={(event) =>
                      handleUpdateModelParameters('maxOutputTokens', Number(event.target.value))
                    }
                  />
                </div>
                <div className="admin-prompts__field">
                  <label className="admin-prompts__label" htmlFor="param-presence">
                    Presence penalty
                  </label>
                  <input
                    id="param-presence"
                    type="number"
                    step={0.1}
                    min={-2}
                    max={2}
                    className="admin-prompts__input"
                    value={activeConfig.modelParameters.presencePenalty}
                    onChange={(event) =>
                      handleUpdateModelParameters('presencePenalty', Number(event.target.value))
                    }
                  />
                </div>
                <div className="admin-prompts__field">
                  <label className="admin-prompts__label" htmlFor="param-frequency">
                    Frequency penalty
                  </label>
                  <input
                    id="param-frequency"
                    type="number"
                    step={0.1}
                    min={-2}
                    max={2}
                    className="admin-prompts__input"
                    value={activeConfig.modelParameters.frequencyPenalty}
                    onChange={(event) =>
                      handleUpdateModelParameters('frequencyPenalty', Number(event.target.value))
                    }
                  />
                </div>
              </div>
            </section>

            <section className="admin-prompts__group" aria-labelledby="preview-title">
              <h3 id="preview-title" className="admin-prompts__group-title">
                사용자 프롬프트 미리보기
              </h3>
              <div className="admin-prompts__preview" role="presentation">
                <pre>{previewPrompt || '구성된 프롬프트가 여기에 표시됩니다.'}</pre>
              </div>
              <p className="admin-prompts__help">
                첨부 설명 미리보기는 현재 요구 첨부 항목과 내장 컨텍스트 설정을 기준으로 표시됩니다.
              </p>
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
