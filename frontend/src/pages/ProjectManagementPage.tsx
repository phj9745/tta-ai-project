import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ActivityIcon,
  BugIcon,
  ImageIcon,
  ListIcon,
  ShieldCheckIcon,
  ScrollTextIcon,
  type LucideIcon,
} from 'lucide-react'

import { FileUploader } from '../components/FileUploader'
import { ALL_FILE_TYPES, type FileType } from '../components/fileUploaderTypes'
import { DefectReportWorkflow } from '../components/DefectReportWorkflow'
import { SecurityReportWorkflow } from '../components/SecurityReportWorkflow'
import { TestcaseWorkflow } from '../components/testcase-workflow/TestcaseWorkflow'
import { Modal } from '../components/Modal'
import { useBackgroundTasks } from '../app/background/BackgroundTaskContext'
import { getBackendUrl } from '../config'
import { navigate } from '../navigation'

type MenuItemId =
  | 'configuration-images'
  | 'feature-list'
  | 'testcase-generation'
  | 'defect-report'
  | 'security-report'
  | 'performance-report'

interface RequiredDocument {
  id: string
  label: string
  allowedTypes?: FileType[]
  required?: boolean
}

interface AdditionalFileEntry {
  id: string
  file: File
  description: string
}

type FileMetadataEntry =
  | { role: 'required'; id: string; label: string }
  | { role: 'additional'; description: string }

interface MenuItemContent {
  id: MenuItemId
  label: string
  icon: LucideIcon
  eyebrow: string
  title: string
  description: string
  helper: string
  buttonLabel: string
  allowedTypes: FileType[]
  requiredDocuments?: RequiredDocument[]
  uploaderVariant?: 'default' | 'grid'
  maxFiles?: number
  hideDropzoneWhenFilled?: boolean
}

type GenerationStatus = 'idle' | 'loading' | 'success' | 'error'

interface FeatureListGenerateResponse {
  status?: string
  projectId?: string
  fileId?: string
  fileName?: string
  modifiedTime?: string
  generatedFilename?: string
}

interface ConfigurationCaptureResponse {
  status?: string
  projectId?: string
  folderId?: string
  files?: Array<{
    id?: string
    name?: string
    mimeType?: string
    timeSec?: number
    isStart?: boolean
  }>
  eventsFile?: {
    id?: string
    name?: string
    mimeType?: string
  } | null
}

type ConfigurationCaptureFile = NonNullable<ConfigurationCaptureResponse['files']>[number]

const IMAGE_FILE_TYPES = new Set<FileType>(['jpg', 'png'])
const PERFORMANCE_OS_OPTIONS = [
  { value: 'windows', label: 'Windows' },
  { value: 'linux', label: 'Linux' },
]

interface PerformanceInputState {
  memoryGb: string
  deviceName: string
}

interface PerformanceOSModalState {
  menuId: MenuItemId
  files: Array<{ name: string; index: number }>
  selections: Record<number, string>
  error: string | null
}

const getPerformanceFileKey = (file: File): string =>
  `${file.name}::${file.size}::${file.lastModified}`

interface ItemState {
  files: File[]
  requiredFiles: Record<string, File[]>
  additionalFiles: AdditionalFileEntry[]
  status: GenerationStatus
  errorMessage: string | null
  downloadUrl: string | null
  downloadName: string | null
  warnings: string[]
  performanceInputs: Record<string, PerformanceInputState>
}

function createItemState(item?: MenuItemContent): ItemState {
  const requiredFiles: Record<string, File[]> = {}
  if (item?.requiredDocuments) {
    item.requiredDocuments.forEach((doc) => {
      requiredFiles[doc.id] = []
    })
  }

  return {
    files: [],
    requiredFiles,
    additionalFiles: [],
    status: 'idle',
    errorMessage: null,
    downloadUrl: null,
    downloadName: null,
    warnings: [],
    performanceInputs: {},
  }
}

function createInitialItemStates(): Record<MenuItemId, ItemState> {
  return MENU_ITEMS.reduce((acc, item) => {
    acc[item.id] = createItemState(item)
    return acc
  }, {} as Record<MenuItemId, ItemState>)
}

function parseFileNameFromDisposition(disposition: string | null): string | null {
  if (!disposition) {
    return null
  }

  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }

  const quotedMatch = disposition.match(/filename="?([^";]+)"?/i)
  if (quotedMatch?.[1]) {
    return quotedMatch[1]
  }

  return null
}

function sanitizeFileName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}

const XLSX_RESULT_MENUS: Set<MenuItemId> = new Set([
  'testcase-generation',
  'defect-report',
])

const MENU_ITEMS: MenuItemContent[] = [
  {
    id: 'configuration-images',
    label: '형상 이미지 추출',
    icon: ImageIcon,
    eyebrow: '형상 관리',
    title: '형상 이미지 추출',
    description:
      '프로그램 기능 시연 동영상을 업로드하면 장면 전환을 감지하여 주요 화면 이미지를 자동으로 추출합니다.',
    helper: 'MP4 또는 MOV 형식의 동영상 1개만 업로드하면 됩니다.',
    buttonLabel: '형상 이미지 추출하기',
    allowedTypes: ['mp4', 'mov'],
    requiredDocuments: [
      {
        id: 'capture-video',
        label: '시연 동영상',
        allowedTypes: ['mp4', 'mov'],
      },
    ],
    maxFiles: 1,
    hideDropzoneWhenFilled: true,
  },
  {
    id: 'feature-list',
    label: '기능리스트',
    icon: ListIcon,
    eyebrow: '계획',
    title: '기능리스트 생성',
    description:
      '사용자 매뉴얼 및 요구사항 명세 문서를 업로드하면 AI가 주요 기능을 정리한 기능 리스트를 생성합니다.',
    helper: 'PDF, TXT, CSV 등 요구사항 관련 문서를 업로드해 주세요. 필요한 자료를 하나만 올리면 됩니다.',
    buttonLabel: '기능리스트 생성하기',
    allowedTypes: ALL_FILE_TYPES,
    requiredDocuments: [
      {
        id: 'user-manual',
        label: '사용자 매뉴얼',
        allowedTypes: ['pdf', 'docx', 'xlsx'],
      },
      {
        id: 'configuration',
        label: '형상 이미지',
        allowedTypes: ['png', 'jpg'],
        required: false,
      },
      {
        id: 'vendor-feature-list',
        label: '기능리스트',
        allowedTypes: ['pdf', 'docx', 'xlsx'],
        required: false,
      },
    ],
  },
  {
    id: 'testcase-generation',
    label: '테스트케이스',
    icon: ScrollTextIcon,
    eyebrow: '설계',
    title: '테스트케이스 생성',
    description:
      '기능리스트를 바탕으로 테스트 시나리오와 기대 결과를 정리한 테스트케이스 초안을 생성합니다.',
    helper: '기능리스트를 업로드해 주세요. 필요한 자료를 하나만 올리면 됩니다.',
    buttonLabel: '테스트케이스 생성하기',
    allowedTypes: ALL_FILE_TYPES,
    requiredDocuments: [
      {
        id: 'user-manual',
        label: '사용자 매뉴얼',
        allowedTypes: ['pdf', 'docx', 'xlsx'],
      },
      {
        id: 'configuration',
        label: '형상 이미지',
        allowedTypes: ['png', 'jpg'],
        required: false,
      },
      {
        id: 'vendor-feature-list',
        label: '기능리스트',
        allowedTypes: ['pdf', 'docx', 'xlsx'],
        required: false,
      },
    ],
  },
  {
    id: 'defect-report',
    label: '결함리포트',
    icon: BugIcon,
    eyebrow: '수행',
    title: '결함리포트 생성',
    description:
      '기능리스트와 결함 메모를 바탕으로 결함 리포트 초안을 생성합니다.',
    helper: '테스트 로그, 정리된 표, 스크린샷 등 결함 관련 증적 자료를 첨부해 주세요.',
    buttonLabel: '결함리포트 생성하기',
    allowedTypes: ['pdf', 'txt', 'csv', 'jpg'],
    uploaderVariant: 'grid',
    maxFiles: 12,
    hideDropzoneWhenFilled: true,
  },
  {
    id: 'security-report',
    label: '보안성 결함리포트',
    icon: ShieldCheckIcon,
    eyebrow: '수행',
    title: '보안성 결함리포트 생성',
    description:
      'Invicti 상세 스캔 보고서를 바탕으로 결함리포트를 생성합니다.',
    helper:
      'Invicti 상세 스캔 보고서(.html)를 업로드하세요. 보고서에 포함된 Medium 이상 취약점만 분석됩니다.',
    buttonLabel: 'Invicti 보고서 분석하기',
    allowedTypes: ['html'],
    maxFiles: 1,
    hideDropzoneWhenFilled: true,
  },
  {
    id: 'performance-report',
    label: '성능시험 리포트',
    icon: ActivityIcon,
    eyebrow: '수행',
    title: '성능시험 리포트 생성',
    description:
      '성능 모니터링 데이터를 바탕으로 성능시험 리포트를 생성합니다.',
    helper:
      'Windows 성능 모니터 및 Linux vmstat 성능 측정 rawdata를 여러 개 업로드할 수 있습니다.',
    buttonLabel: '성능시험 리포트 생성하기',
    allowedTypes: ['csv', 'txt'],
    maxFiles: 12,
    hideDropzoneWhenFilled: false,
  },
]

const MENU_ITEM_IDS = MENU_ITEMS.map((item) => item.id)

const FIRST_MENU_ITEM = MENU_ITEMS[0]?.id ?? 'feature-list'

interface ProjectManagementPageProps {
  projectId: string
}

export function ProjectManagementPage({ projectId }: ProjectManagementPageProps) {
  const projectName = useMemo(() => {
    const searchParams = new URLSearchParams(window.location.search)
    const name = searchParams.get('name')
    return name ?? projectId
  }, [projectId])

  const backendUrl = useMemo(() => getBackendUrl(), [])
  const [activeItem, setActiveItem] = useState<MenuItemId>(FIRST_MENU_ITEM)
  const [itemStates, setItemStates] = useState<Record<MenuItemId, ItemState>>(() => createInitialItemStates())
  const downloadUrlsRef = useRef<Record<MenuItemId, string | null>>(
    Object.fromEntries(MENU_ITEM_IDS.map((id) => [id, null])) as Record<MenuItemId, string | null>,
  )
  const performanceOverridesRef = useRef<Record<string, string> | null>(null)
  const [performanceModalState, setPerformanceModalState] = useState<PerformanceOSModalState | null>(null)
  const { startTask } = useBackgroundTasks()
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const isMountedRef = useRef(true)
  const menuById = useMemo(() => {
    return MENU_ITEMS.reduce((acc, item) => {
      acc[item.id] = item
      return acc
    }, {} as Record<MenuItemId, MenuItemContent>)
  }, [])
  const additionalIdRef = useRef(0)

  const releaseDownloadUrl = useCallback((id: MenuItemId, url: string | null) => {
    if (url) {
      URL.revokeObjectURL(url)
    }
    downloadUrlsRef.current[id] = null
  }, [])

  const activeContent = MENU_ITEMS.find((item) => item.id === activeItem) ?? MENU_ITEMS[0]
  const isDefectReport = activeContent.id === 'defect-report'
  const isSecurityReport = activeContent.id === 'security-report'
  const isTestcaseWorkflow = activeContent.id === 'testcase-generation'

  const activeState = itemStates[activeContent.id] ?? createItemState(activeContent)
  const activeRequiredDocuments = activeContent.requiredDocuments ?? []
  const hasRequiredDocuments = activeRequiredDocuments.length > 0
  const hasMandatoryDocuments = activeRequiredDocuments.some((doc) => doc.required !== false)
  const requiredSectionTitle = hasMandatoryDocuments ? '필수 문서 업로드' : '문서 업로드 (선택)'

  const handleSelectAnotherProject = useCallback(() => {
    navigate('/projects')
  }, [])

  const handleToggleSidebar = useCallback(() => {
    setIsSidebarOpen((prev) => !prev)
  }, [])

  const handleCloseSidebar = useCallback(() => {
    setIsSidebarOpen(false)
  }, [])

  const handleSelectMenuItem = useCallback(
    (itemId: MenuItemId) => {
      setActiveItem(itemId)
      if (typeof window !== 'undefined' && window.innerWidth < 1024) {
        setIsSidebarOpen(false)
      }
    },
    [setActiveItem, setIsSidebarOpen],
  )

  useEffect(() => {
    return () => {
      isMountedRef.current = false
    }
  }, [])

  const handleChangeFiles = useCallback(
    (id: MenuItemId, nextFiles: File[]) => {
      setItemStates((prev) => {
        const current = prev[id]
        if (!current || current.status === 'loading') {
          return prev
        }

        if (current.downloadUrl) {
          releaseDownloadUrl(id, current.downloadUrl)
        }

        return {
          ...prev,
          [id]: {
            ...current,
            files: nextFiles,
            status: 'idle',
            errorMessage: null,
            downloadUrl: null,
            downloadName: null,
            warnings: [],
            performanceInputs:
              id === 'performance-report'
                ? nextFiles.reduce<Record<string, PerformanceInputState>>((acc, file) => {
                  const key = getPerformanceFileKey(file)
                  acc[key] = current.performanceInputs[key] ?? { memoryGb: '', deviceName: '' }
                  return acc
                }, {})
                : current.performanceInputs,
          },
        }
      })
    },
    [releaseDownloadUrl],
  )

  const handleSetRequiredFiles = useCallback(
    (id: MenuItemId, docId: string, nextFiles: File[]) => {
      setItemStates((prev) => {
        const current = prev[id]
        if (!current || current.status === 'loading') {
          return prev
        }

        if (!(docId in current.requiredFiles)) {
          return prev
        }

        if (current.downloadUrl) {
          releaseDownloadUrl(id, current.downloadUrl)
        }

        return {
          ...prev,
          [id]: {
            ...current,
            requiredFiles: {
              ...current.requiredFiles,
              [docId]: nextFiles,
            },
            status: 'idle',
            errorMessage: null,
            downloadUrl: null,
            downloadName: null,
          },
        }
      })
    },
    [releaseDownloadUrl],
  )

  const handleAddAdditionalFiles = useCallback(
    (id: MenuItemId, selectedFiles: File[]) => {
      if (selectedFiles.length === 0) {
        return
      }

      setItemStates((prev) => {
        const current = prev[id]
        if (!current || current.status === 'loading') {
          return prev
        }

        if (current.downloadUrl) {
          releaseDownloadUrl(id, current.downloadUrl)
        }

        const entries = selectedFiles.map((file) => {
          additionalIdRef.current += 1
          return {
            id: `${id}-extra-${additionalIdRef.current}`,
            file,
            description: '',
          }
        })

        return {
          ...prev,
          [id]: {
            ...current,
            additionalFiles: [...current.additionalFiles, ...entries],
            status: 'idle',
            errorMessage: null,
            downloadUrl: null,
            downloadName: null,
            warnings: [],
          },
        }
      })
    },
    [releaseDownloadUrl],
  )

  const handleUpdateAdditionalDescription = useCallback(
    (id: MenuItemId, entryId: string, description: string) => {
      setItemStates((prev) => {
        const current = prev[id]
        if (!current || current.status === 'loading') {
          return prev
        }

        const nextEntries = current.additionalFiles.map((entry) =>
          entry.id === entryId ? { ...entry, description } : entry,
        )

        return {
          ...prev,
          [id]: {
            ...current,
            additionalFiles: nextEntries,
          },
        }
      })
    },
    [],
  )

  const handleRemoveAdditionalFile = useCallback(
    (id: MenuItemId, entryId: string) => {
      setItemStates((prev) => {
        const current = prev[id]
        if (!current || current.status === 'loading') {
          return prev
        }

        const nextEntries = current.additionalFiles.filter((entry) => entry.id !== entryId)
        if (nextEntries.length === current.additionalFiles.length) {
          return prev
        }

        if (current.downloadUrl) {
          releaseDownloadUrl(id, current.downloadUrl)
        }

        return {
          ...prev,
          [id]: {
            ...current,
            additionalFiles: nextEntries,
            status: 'idle',
            errorMessage: null,
            downloadUrl: null,
            downloadName: null,
            warnings: [],
          },
        }
      })
    },
    [releaseDownloadUrl],
  )

  const handleUpdatePerformanceInput = useCallback(
    (itemId: MenuItemId, file: File, field: keyof PerformanceInputState, value: string) => {
      if (itemId !== 'performance-report') {
        return
      }
      const key = getPerformanceFileKey(file)
      setItemStates((prev) => {
        const current = prev[itemId]
        if (!current || current.status === 'loading') {
          return prev
        }

        const nextInputs: Record<string, PerformanceInputState> = {
          ...current.performanceInputs,
          [key]: {
            ...(current.performanceInputs[key] ?? { memoryGb: '', deviceName: '' }),
            [field]: value,
          },
        }

        return {
          ...prev,
          [itemId]: {
            ...current,
            performanceInputs: nextInputs,
            status: current.status === 'success' ? 'idle' : current.status,
            errorMessage: null,
            warnings: current.status === 'success' ? [] : current.warnings,
          },
        }
      })
    },
    [],
  )

  const handlePerformanceSelectionChange = useCallback((index: number, value: string) => {
    setPerformanceModalState((prev) => {
      if (!prev) {
        return prev
      }
      return {
        ...prev,
        selections: {
          ...prev.selections,
          [index]: value,
        },
        error: null,
      }
    })
  }, [])

  const handleGenerate = useCallback(
    async (id: MenuItemId) => {
      const current = itemStates[id]
      const menu = menuById[id] ?? MENU_ITEMS[0]
      if (!current || current.status === 'loading') {
        return
      }

      const requiredDocs = menu?.requiredDocuments ?? []
      let uploads: File[] = []
      const metadataEntries: FileMetadataEntry[] = []

      if (requiredDocs.length > 0) {
        const missingDocs = requiredDocs.filter(
          (doc) => doc.required !== false && (current.requiredFiles[doc.id]?.length ?? 0) === 0,
        )
        if (missingDocs.length > 0) {
          setItemStates((prev) => ({
            ...prev,
            [id]: {
              ...prev[id],
              status: 'error',
              errorMessage: `다음 필수 문서를 업로드해 주세요: ${missingDocs
                .map((doc) => doc.label)
                .join(', ')}`,
              warnings: [],
              downloadUrl: null,
              downloadName: null,
            },
          }))
          return
        }

        const incompleteDescriptions = current.additionalFiles.filter(
          (entry) => entry.description.trim().length === 0,
        )
        if (incompleteDescriptions.length > 0) {
          setItemStates((prev) => ({
            ...prev,
            [id]: {
              ...prev[id],
              status: 'error',
              errorMessage: '추가로 업로드한 문서의 종류를 입력해 주세요.',
              warnings: [],
              downloadUrl: null,
              downloadName: null,
            },
          }))
          return
        }

        requiredDocs.forEach((doc) => {
          const files = current.requiredFiles[doc.id] ?? []
          files.forEach((file) => {
            uploads.push(file)
            metadataEntries.push({ role: 'required', id: doc.id, label: doc.label })
          })
        })

        current.additionalFiles.forEach((entry) => {
          uploads.push(entry.file)
          metadataEntries.push({ role: 'additional', description: entry.description })
        })
      } else {
        uploads = current.files
      }

      if (uploads.length === 0) {
        setItemStates((prev) => ({
          ...prev,
          [id]: {
            ...prev[id],
            status: 'error',
            errorMessage: '업로드된 파일이 없습니다. 파일을 추가해 주세요.',
            warnings: [],
            downloadUrl: null,
            downloadName: null,
          },
        }))
        return
      }

      let performanceMetadataPayload: Array<{ fileName: string; memoryGb: number; deviceName: string }> = []
      if (id === 'performance-report') {
        const missingInfo = uploads.some((file) => {
          const key = getPerformanceFileKey(file)
          const meta = current.performanceInputs[key]
          if (!meta) {
            return true
          }
          if (!meta.deviceName.trim()) {
            return true
          }
          const value = Number(meta.memoryGb)
          if (!Number.isFinite(value) || value <= 0) {
            return true
          }
          return false
        })

        if (missingInfo) {
          setItemStates((prev) => ({
            ...prev,
            [id]: {
              ...prev[id],
              status: 'error',
              errorMessage: '각 rawdata의 메모리(GB)와 장비명을 모두 입력해 주세요.',
              warnings: [],
              downloadUrl: null,
              downloadName: null,
            },
          }))
          return
        }

        performanceMetadataPayload = uploads.map((file) => {
          const key = getPerformanceFileKey(file)
          const meta = current.performanceInputs[key]
          const value = Number(meta?.memoryGb ?? 0)
          return {
            fileName: file.name,
            memoryGb: Number.isFinite(value) ? Number(value.toFixed(4)) : 0,
            deviceName: meta?.deviceName.trim() ?? '',
          }
        })
      }

      setItemStates((prev) => ({
        ...prev,
        [id]: {
          ...prev[id],
          status: 'loading',
          errorMessage: null,
          warnings: [],
          downloadUrl: null,
          downloadName: null,
        },
      }))

      if (current.downloadUrl) {
        releaseDownloadUrl(id, current.downloadUrl)
      }

      const taskHandle = startTask(id, menu.label)
      taskHandle.onCancel(() => {
        setItemStates((prev) => ({
          ...prev,
          [id]: {
            ...prev[id],
            status: 'idle',
            errorMessage: null,
            warnings: [],
            downloadUrl: null,
            downloadName: null,
          },
        }))
      })

      const formData = new FormData()
      formData.append('menu_id', id)
      uploads.forEach((file) => {
        formData.append('files', file)
      })
      if (metadataEntries.length > 0) {
        formData.append('file_metadata', JSON.stringify(metadataEntries))
      }
      if (id === 'performance-report' && performanceOverridesRef.current) {
        const overrides = performanceOverridesRef.current
        performanceOverridesRef.current = null
        if (overrides && Object.keys(overrides).length > 0) {
          formData.append('performance_os_overrides', JSON.stringify(overrides))
        }
      }
      if (id === 'performance-report' && performanceMetadataPayload.length > 0) {
        formData.append('performance_metadata', JSON.stringify(performanceMetadataPayload))
      }

      try {
        const response = await fetch(
          `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/generate`,
          {
            method: 'POST',
            body: formData,
            signal: taskHandle.signal,
          },
        )

        if (taskHandle.signal.aborted) {
          return
        }

        if (!response.ok) {
          if (response.status === 409 && id === 'performance-report') {
            let detailPayload: unknown = null
            try {
              detailPayload = await response.json()
            } catch {
              detailPayload = null
            }

            let modalFiles: Array<{ name: string; index: number }> = []
            if (
              detailPayload &&
              typeof detailPayload === 'object' &&
              detailPayload !== null &&
              'detail' in detailPayload
            ) {
              const detail = (detailPayload as { detail?: unknown }).detail
              if (
                detail &&
                typeof detail === 'object' &&
                detail !== null &&
                (detail as { code?: string }).code === 'performance.os_required'
              ) {
                const files = (detail as { files?: unknown }).files
                if (Array.isArray(files)) {
                  modalFiles = files
                    .map((file) => {
                      if (
                        file &&
                        typeof file === 'object' &&
                        'index' in file &&
                        typeof (file as { index: unknown }).index === 'number'
                      ) {
                        return {
                          name:
                            typeof (file as { name?: unknown }).name === 'string'
                              ? ((file as { name?: unknown }).name as string)
                              : `파일 ${((file as { index: number }).index ?? 0) + 1}`,
                          index: (file as { index: number }).index,
                        }
                      }
                      return null
                    })
                    .filter((entry): entry is { name: string; index: number } => entry !== null)
                }
              }
            }

            if (taskHandle.signal.aborted) {
              return
            }

            setItemStates((prev) => ({
              ...prev,
              [id]: {
                ...prev[id],
                status: 'idle',
                errorMessage: null,
                warnings: [],
                downloadUrl: null,
                downloadName: null,
              },
            }))

            if (modalFiles.length > 0) {
              setPerformanceModalState({
                menuId: id,
                files: modalFiles,
                selections: Object.fromEntries(modalFiles.map((file) => [file.index, ''])),
                error: null,
              })
              taskHandle.fail('OS 종류 선택이 필요합니다.')
            } else {
              if (taskHandle.signal.aborted) {
                return
              }

              setItemStates((prev) => ({
                ...prev,
                [id]: {
                  ...prev[id],
                  status: 'error',
                  errorMessage: '업로드된 파일의 OS 유형을 판별하지 못했습니다. 다시 시도해 주세요.',
                  warnings: [],
                  downloadUrl: null,
                  downloadName: null,
                },
              }))
              taskHandle.fail('OS 정보를 확인하지 못했습니다.')
            }
            return
          }

          let detail = '자료를 생성하는 중 오류가 발생했습니다.'
          try {
            const text = await response.text()
            try {
              const payload = JSON.parse(text) as { detail?: unknown }
              if (payload && typeof payload.detail === 'string') {
                detail = payload.detail
              }
            } catch {
              if (text) {
                detail = text
              }
            }
          } catch {
            // body unreadable – keep default detail
          }

          if (taskHandle.signal.aborted) {
            return
          }

          setItemStates((prev) => ({
            ...prev,
            [id]: {
              ...prev[id],
              status: 'error',
              errorMessage: detail,
              warnings: [],
              downloadUrl: null,
              downloadName: null,
            },
          }))
          taskHandle.fail(detail)
          return
        }

        if (taskHandle.signal.aborted) {
          return
        }

        if (id === 'configuration-images') {
          let payload: ConfigurationCaptureResponse | null = null
          try {
            payload = (await response.json()) as ConfigurationCaptureResponse
          } catch {
            payload = null
          }

          if (taskHandle.signal.aborted) {
            return
          }

          const captureFiles: ConfigurationCaptureFile[] = Array.isArray(payload?.files)
            ? (payload?.files as ConfigurationCaptureFile[])
            : []
          const files: Array<ConfigurationCaptureFile & { id: string }> = captureFiles.filter(
            (file): file is ConfigurationCaptureFile & { id: string } => typeof file?.id === 'string',
          )

          if (!payload || files.length === 0) {
            if (taskHandle.signal.aborted) {
              return
            }
            setItemStates((prev) => ({
              ...prev,
              [id]: {
                ...prev[id],
                status: 'error',
                errorMessage: '추출된 형상 이미지 정보를 확인하지 못했습니다.',
              },
            }))
            taskHandle.fail('형상 이미지 정보를 확인하지 못했습니다.')
            return
          }

          if (taskHandle.signal.aborted) {
            return
          }

          setItemStates((prev) => ({
            ...prev,
            [id]: createItemState(menu),
          }))

          const nextParams = new URLSearchParams(window.location.search)
          if (!nextParams.get('name') && projectName && projectName !== projectId) {
            nextParams.set('name', projectName)
          }
          if (payload.folderId) {
            nextParams.set('folderId', payload.folderId)
          } else {
            nextParams.delete('folderId')
          }

          const recentIds = files
            .map((file) => (typeof file.id === 'string' ? file.id : null))
            .filter((value): value is string => Boolean(value))

          if (recentIds.length > 0) {
            nextParams.set('recent', recentIds.join(','))
          } else {
            nextParams.delete('recent')
          }

          const query = nextParams.toString()
          const targetUrl = `/projects/${encodeURIComponent(projectId)}/configuration-images/edit${query ? `?${query}` : ''
            }`

          if (!taskHandle.signal.aborted) {
            taskHandle.complete({ type: 'navigate', url: targetUrl, label: '열기' }, '형상 이미지 추출 완료')
            if (isMountedRef.current) {
              navigate(targetUrl)
            }
          }
          return
        }

        if (taskHandle.signal.aborted) {
          return
        }

        if (id === 'feature-list') {
          let payload: FeatureListGenerateResponse | null = null
          try {
            payload = (await response.json()) as FeatureListGenerateResponse
          } catch {
            payload = null
          }

          if (taskHandle.signal.aborted) {
            return
          }

          if (!payload || typeof payload.fileId !== 'string') {
            if (taskHandle.signal.aborted) {
              return
            }
            setItemStates((prev) => ({
              ...prev,
              [id]: {
                ...prev[id],
                status: 'error',
                errorMessage: '생성된 기능리스트 정보를 확인하지 못했습니다.',
              },
            }))
            taskHandle.fail('기능리스트 정보를 확인하지 못했습니다.')
            return
          }

          if (taskHandle.signal.aborted) {
            return
          }

          setItemStates((prev) => ({
            ...prev,
            [id]: createItemState(menu),
          }))

          const nextParams = new URLSearchParams(window.location.search)
          if (!nextParams.get('name') && projectName && projectName !== projectId) {
            nextParams.set('name', projectName)
          }
          nextParams.set('fileId', payload.fileId)
          if (payload.fileName) {
            nextParams.set('fileName', payload.fileName)
          } else {
            nextParams.delete('fileName')
          }
          if (payload.modifiedTime) {
            nextParams.set('modifiedTime', payload.modifiedTime)
          } else {
            nextParams.delete('modifiedTime')
          }

          const query = nextParams.toString()
          const targetUrl = `/projects/${encodeURIComponent(projectId)}/feature-list/edit${query ? `?${query}` : ''
            }`

          if (!taskHandle.signal.aborted) {
            taskHandle.complete({ type: 'navigate', url: targetUrl, label: '열기' }, '기능리스트 생성 완료')
            if (isMountedRef.current) {
              navigate(targetUrl)
            }
          }
          return
        }

        if (taskHandle.signal.aborted) {
          return
        }

        const blob = await response.blob()

        if (taskHandle.signal.aborted) {
          return
        }

        const disposition = response.headers.get('content-disposition')
        const parsedName = parseFileNameFromDisposition(disposition)
        const contentType = response.headers.get('content-type') ?? ''
        const expectsXlsx =
          XLSX_RESULT_MENUS.has(id) || contentType.includes('spreadsheetml')

        let effectiveName = parsedName?.trim() ?? ''
        if (!effectiveName) {
          effectiveName = `${id}-result`
        }

        if (expectsXlsx) {
          if (!effectiveName.toLowerCase().endsWith('.xlsx')) {
            const withoutExtension = effectiveName.replace(/\.[^./\\]+$/, '')
            effectiveName = `${withoutExtension}.xlsx`
          }
        } else if (!effectiveName.includes('.')) {
          effectiveName = `${effectiveName}.csv`
        }

        const safeName = sanitizeFileName(effectiveName)
        const objectUrl = URL.createObjectURL(blob)
        const warningsHeader = response.headers.get('x-performance-warnings')
        let warnings: string[] = []
        if (id === 'performance-report' && warningsHeader) {
          try {
            const parsed = JSON.parse(warningsHeader) as unknown
            if (Array.isArray(parsed)) {
              warnings = parsed.filter((entry): entry is string => typeof entry === 'string')
            }
          } catch {
            warnings = [warningsHeader]
          }
        }

        setItemStates((prev) => {
          if (taskHandle.signal.aborted) {
            return prev
          }
          const previous = prev[id]
          if (previous?.downloadUrl) {
            releaseDownloadUrl(id, previous.downloadUrl)
          }

          const baseState = createItemState(menu)

          return {
            ...prev,
            [id]: {
              ...baseState,
              status: 'success',
              downloadUrl: objectUrl,
              downloadName: safeName,
              warnings,
            },
          }
        })

        if (taskHandle.signal.aborted) {
          URL.revokeObjectURL(objectUrl)
          return
        }

        downloadUrlsRef.current[id] = objectUrl

        const successMessage = warnings.length > 0 ? '생성 완료 (주의 사항 있음)' : '생성 완료'
        if (!taskHandle.signal.aborted) {
          taskHandle.complete(
            { type: 'download', blob, filename: safeName, contentType, warnings },
            successMessage,
          )
        }
      } catch (error) {
        if (taskHandle.signal.aborted) {
          return
        }
        const fallback =
          error instanceof Error
            ? error.message
            : '자료를 생성하는 중 예기치 않은 오류가 발생했습니다.'

        setItemStates((prev) => ({
          ...prev,
          [id]: {
            ...prev[id],
            status: 'error',
            errorMessage: fallback,
            warnings: [],
            downloadUrl: null,
            downloadName: null,
          },
        }))
        taskHandle.fail(fallback)
      }
    },
    [
      backendUrl,
      itemStates,
      menuById,
      projectId,
      projectName,
      releaseDownloadUrl,
      startTask,
    ],
  )

  const handlePerformanceModalClose = useCallback(() => {
    setPerformanceModalState(null)
    performanceOverridesRef.current = null
  }, [])

  const handlePerformanceModalSubmit = useCallback(() => {
    if (!performanceModalState) {
      return
    }

    const missing = performanceModalState.files.filter(
      (file) => !performanceModalState.selections[file.index],
    )
    if (missing.length > 0) {
      setPerformanceModalState((prev) =>
        prev
          ? {
            ...prev,
            error: '모든 파일의 OS 종류를 선택해 주세요.',
          }
          : prev,
      )
      return
    }

    const overrides: Record<string, string> = {}
    performanceModalState.files.forEach((file) => {
      const choice = performanceModalState.selections[file.index]
      if (!choice) {
        return
      }
      if (file.name) {
        overrides[file.name] = choice
      }
      overrides[`index:${file.index}`] = choice
      overrides[`file:${file.index + 1}`] = choice
    })

    performanceOverridesRef.current = overrides
    setPerformanceModalState(null)
    void handleGenerate(performanceModalState.menuId)
  }, [handleGenerate, performanceModalState])

  const handleReset = useCallback(
    (id: MenuItemId) => {
      if (id === 'performance-report') {
        performanceOverridesRef.current = null
        setPerformanceModalState(null)
      }

      setItemStates((prev) => {
        const current = prev[id]
        if (current?.downloadUrl) {
          releaseDownloadUrl(id, current.downloadUrl)
        }

        return {
          ...prev,
          [id]: createItemState(menuById[id] ?? MENU_ITEMS[0]),
        }
      })
    },
    [menuById, releaseDownloadUrl],
  )

  useEffect(() => {
    return () => {
      MENU_ITEM_IDS.forEach((id) => {
        const downloadUrl = downloadUrlsRef.current[id as MenuItemId]
        if (downloadUrl) {
          URL.revokeObjectURL(downloadUrl)
          downloadUrlsRef.current[id as MenuItemId] = null
        }
      })
    }
  }, [])

  const sidebarToggleLabel = isSidebarOpen ? '사이드바 접기' : '사이드바 펼치기'
  const pageClassName = [
    'project-management-page',
    isSidebarOpen ? 'project-management-page--sidebar-open' : 'project-management-page--sidebar-collapsed',
    isTestcaseWorkflow ? 'project-management-page--preview' : '',
  ]
    .filter(Boolean)
    .join(' ')
  const contentClassName = [
    'project-management-content',
    isTestcaseWorkflow ? 'project-management-content--preview' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={pageClassName}>
      <button
        type="button"
        className="project-management-sidebar-toggle"
        onClick={handleToggleSidebar}
        aria-expanded={isSidebarOpen}
        aria-controls="project-management-sidebar"
        title={sidebarToggleLabel}
      >
        <span className="project-management-sidebar-toggle__icon" aria-hidden="true" style={
          !isSidebarOpen
            ? { position: "absolute", left: "17px" }
            : undefined
        }>
          {isSidebarOpen ? (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M15 8L11 12L15 16" />
            </svg>
          ) : (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"

            >
              <path d="M10 8L14 12L10 16" />
            </svg>
          )}
        </span>
        <span className="project-management-sr-only">{sidebarToggleLabel}</span>
      </button>
      <aside
        id="project-management-sidebar"
        className="project-management-sidebar"
        aria-hidden={!isSidebarOpen}
      >
        <div className="project-management-overview">
          <span className="project-management-overview__label">프로젝트</span>
          <strong className="project-management-overview__name">{projectName}</strong>
        </div>

        <nav aria-label="프로젝트 관리 메뉴" className="project-management-menu">
          <ul className="project-management-menu__list">
            {MENU_ITEMS.map((item) => {
              const isActive = activeItem === item.id
              const Icon = item.icon

              return (
                <li
                  key={item.id}
                  className={`project-management-menu__item${isActive ? ' project-management-menu__item--active' : ''
                    }`}
                >
                  <button
                    type="button"
                    className="project-management-menu__button"
                    onClick={() => handleSelectMenuItem(item.id)}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <span className="project-management-menu__icon" aria-hidden="true">
                      <Icon size={20} strokeWidth={2} />
                    </span>
                    <span className="project-management-menu__text">
                      <span className="project-management-menu__label">{item.label}</span>
                      <span className="project-management-menu__eyebrow">{item.eyebrow}</span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>
      </aside>

      <button
        type="button"
        className="project-management-sidebar-backdrop"
        aria-hidden="true"
        tabIndex={-1}
        onClick={handleCloseSidebar}
      />

      <main className={contentClassName} aria-label="프로젝트 관리 컨텐츠">
        <div className="project-management-content__inner">
          <div className="project-management-content__toolbar" role="navigation" aria-label="프로젝트 작업 메뉴">
            <button
              type="button"
              className="project-management-content__secondary project-management-content__toolbar-button"
              onClick={handleSelectAnotherProject}
            >
              다른 프로젝트 선택
            </button>
          </div>
          <div className="project-management-content__header">
            <span className="project-management-content__eyebrow">{activeContent.eyebrow}</span>
            <h1 className="project-management-content__title">{activeContent.title}</h1>
            <p className="project-management-content__description">{activeContent.description}</p>
          </div>

          {isTestcaseWorkflow ? (
            <TestcaseWorkflow
              backendUrl={backendUrl}
              projectId={projectId}
              projectName={projectName}
            />
          ) : (
            <>
              {activeState.status !== 'success' && (
                isDefectReport ? (
                  <DefectReportWorkflow
                    backendUrl={backendUrl}
                    projectId={projectId}
                    projectName={projectName}
                  />
                ) : isSecurityReport ? (
                  <SecurityReportWorkflow
                    backendUrl={backendUrl}
                    projectId={projectId}
                    projectName={projectName}
                  />
                ) : hasRequiredDocuments ? (
                  <>
                    <section
                      aria-labelledby="required-upload-section"
                      className="project-management-content__section"
                    >
                      <h2
                        id="required-upload-section"
                        className="project-management-content__section-title"
                      >
                        {requiredSectionTitle}
                      </h2>
                      <div className="project-management-required__list">
                        {(activeContent.requiredDocuments ?? []).map((doc) => {
                          const fileList = activeState.requiredFiles[doc.id] ?? []
                          const resolvedTypes = doc.allowedTypes ?? activeContent.allowedTypes
                          const allowMultiple = resolvedTypes.every((type) => IMAGE_FILE_TYPES.has(type))
                          const label = doc.required === false ? `${doc.label} (선택)` : doc.label

                          return (
                            <div key={doc.id} className="project-management-required__item">
                              <span className="project-management-required__label">{label}</span>
                              <FileUploader
                                allowedTypes={doc.allowedTypes ?? activeContent.allowedTypes}
                                files={fileList}
                                onChange={(nextFiles) =>
                                  handleSetRequiredFiles(activeContent.id, doc.id, nextFiles)
                                }
                                disabled={activeState.status === 'loading'}
                                multiple={allowMultiple}
                                hideDropzoneWhenFilled
                              />
                            </div>
                          )
                        })}
                      </div>

                      <div className="project-management-additional project-management-additional--inline">
                        <h3 className="project-management-additional__title">추가 파일 업로드 (선택)</h3>
                        <FileUploader
                          allowedTypes={activeContent.allowedTypes}
                          files={[]}
                          onChange={(nextFiles) => handleAddAdditionalFiles(activeContent.id, nextFiles)}
                          disabled={activeState.status === 'loading'}
                        />
                        {activeState.additionalFiles.length > 0 && (
                          <ul className="project-management-additional__list">
                            {activeState.additionalFiles.map((entry) => (
                              <li key={entry.id} className="project-management-additional__item">
                                <div className="project-management-additional__file">{entry.file.name}</div>
                                <label className="project-management-additional__description">
                                  <span>문서 종류</span>
                                  <input
                                    type="text"
                                    value={entry.description}
                                    onChange={(event) =>
                                      handleUpdateAdditionalDescription(
                                        activeContent.id,
                                        entry.id,
                                        event.target.value,
                                      )
                                    }
                                    placeholder="예: 테스트 보고서"
                                    disabled={activeState.status === 'loading'}
                                  />
                                </label>
                                <button
                                  type="button"
                                  className="project-management-additional__remove"
                                  onClick={() => handleRemoveAdditionalFile(activeContent.id, entry.id)}
                                  disabled={activeState.status === 'loading'}
                                >
                                  제거
                                </button>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </section>
                  </>
                ) : (
                  <section aria-labelledby="upload-section" className="project-management-content__section">
                    <h2 id="upload-section" className="project-management-content__section-title">
                      자료 업로드
                    </h2>
                    <p className="project-management-content__helper">{activeContent.helper}</p>
                    <FileUploader
                      allowedTypes={activeContent.allowedTypes}
                      files={activeState.files}
                      onChange={(nextFiles) => handleChangeFiles(activeContent.id, nextFiles)}
                      disabled={activeState.status === 'loading'}
                      maxFiles={activeContent.maxFiles}
                      hideDropzoneWhenFilled={activeContent.hideDropzoneWhenFilled}
                      variant={activeContent.uploaderVariant}
                    />
                    {activeContent.id === 'performance-report' && activeState.files.length > 0 && (
                      <div className="project-management-performance">
                        <h3 className="project-management-performance__title">메모리(GB)·장비명 입력</h3>
                        <p className="project-management-performance__helper">
                          각 rawdata별 메모리 용량(GB)과 장비명을 입력해 주세요. 정확한 차트 생성을 위해 필수입니다.
                        </p>
                        <ul className="project-management-performance__list">
                          {activeState.files.map((file) => {
                            const key = getPerformanceFileKey(file)
                            const meta = activeState.performanceInputs[key] ?? { memoryGb: '', deviceName: '' }
                            return (
                              <li key={key} className="project-management-performance__item">
                                <div className="project-management-performance__file">{file.name}</div>
                                <label className="project-management-performance__field">
                                  <span>메모리(GB)</span>
                                  <input
                                    type="number"
                                    inputMode="decimal"
                                    min="0"
                                    step="0.01"
                                    value={meta.memoryGb}
                                    onChange={(event) =>
                                      handleUpdatePerformanceInput(activeContent.id, file, 'memoryGb', event.target.value)
                                    }
                                    placeholder="예: 16"
                                    disabled={activeState.status === 'loading'}
                                  />
                                </label>
                                <label className="project-management-performance__field">
                                  <span>장비명</span>
                                  <input
                                    type="text"
                                    value={meta.deviceName}
                                    onChange={(event) =>
                                      handleUpdatePerformanceInput(activeContent.id, file, 'deviceName', event.target.value)
                                    }
                                    placeholder="예: Windows 11 Desktop"
                                    disabled={activeState.status === 'loading'}
                                  />
                                </label>
                              </li>
                            )
                          })}
                        </ul>
                      </div>
                    )}
                  </section>
                )
              )}

              {!isDefectReport && !isSecurityReport && (
                <div className="project-management-content__actions">
                  {activeState.status !== 'success' && (
                    <>
                      <button
                        type="button"
                        className="project-management-content__button"
                        onClick={() => handleGenerate(activeContent.id)}
                        disabled={activeState.status === 'loading'}
                      >
                        {activeState.status === 'loading' ? '생성 중…' : activeContent.buttonLabel}
                      </button>
                      <p className="project-management-content__footnote">
                        업로드된 문서는 프로젝트 드라이브에 안전하게 보관되며, 생성된 결과는 별도의 탭에서 확인할 수 있습니다.
                      </p>
                    </>
                  )}

                  {activeState.status === 'loading' && (
                    <div
                      className="project-management-content__status project-management-content__status--loading"
                      role="status"
                    >
                      업로드한 자료를 기반으로 결과를 준비하고 있습니다…
                    </div>
                  )}

                  {activeState.status === 'error' && (
                    <div className="project-management-content__status project-management-content__status--error" role="alert">
                      {activeState.errorMessage}
                    </div>
                  )}

                  {activeState.status === 'success' && (
                    <div className="project-management-content__result">
                      <a
                        href={activeState.downloadUrl ?? undefined}
                        className="project-management-content__button project-management-content__download"
                        download={activeState.downloadName ?? undefined}
                      >
                        {activeState.downloadName?.toLowerCase().endsWith('.xlsx') ? '엑셀 다운로드' : 'CSV 다운로드'}
                      </a>
                      <button
                        type="button"
                        className="project-management-content__secondary"
                        onClick={() => handleReset(activeContent.id)}
                      >
                        다시 생성하기
                      </button>
                      <p className="project-management-content__footnote">
                        생성된 결과는 프로젝트 드라이브에도 저장되며 필요 시 언제든지 다시 다운로드할 수 있습니다.
                      </p>
                      {activeState.warnings.length > 0 && (
                        <div className="project-management-content__warnings" role="status">
                          <p className="project-management-content__footnote">주의 사항</p>
                          <ul className="project-management-content__footnote">
                            {activeState.warnings.map((warning, index) => (
                              <li key={`${warning}-${index}`}>{warning}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {performanceModalState && (
        <Modal
          open
          onClose={handlePerformanceModalClose}
          title="OS 종류 선택"
          description="자동 감지에 실패한 rawdata 파일의 운영체제를 선택해 주세요."
        >
          <div className="modal__body">
            <p className="modal__helper-text">
              Windows에서 수집한 Perfmon CSV는 Windows, Linux vmstat TXT 파일은 Linux를 선택해 주세요.
            </p>
            {performanceModalState.files.map((file) => {
              const fieldId = `performance-os-${file.index}`
              return (
                <div key={fieldId} className="modal__field">
                  <label className="modal__label" htmlFor={fieldId}>
                    {file.name}
                  </label>
                  <select
                    id={fieldId}
                    className="modal__input"
                    value={performanceModalState.selections[file.index] ?? ''}
                    onChange={(event) => handlePerformanceSelectionChange(file.index, event.target.value)}
                  >
                    <option value="">OS 선택</option>
                    {PERFORMANCE_OS_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              )
            })}
            {performanceModalState.error && (
              <p className="modal__error" role="alert">
                {performanceModalState.error}
              </p>
            )}
          </div>
          <footer className="modal__footer">
            <button type="button" className="modal__button" onClick={handlePerformanceModalClose}>
              취소
            </button>
            <button
              type="button"
              className="modal__button modal__button--primary"
              onClick={handlePerformanceModalSubmit}
            >
              확인
            </button>
          </footer>
        </Modal>
      )}
    </div>
  )
}

