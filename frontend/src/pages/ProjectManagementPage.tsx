import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { FileUploader } from '../components/FileUploader'
import { ALL_FILE_TYPES, type FileType } from '../components/fileUploaderTypes'
import { getBackendUrl } from '../config'
import { navigate } from '../navigation'

type MenuItemId =
  | 'feature-list'
  | 'testcase-generation'
  | 'defect-report'
  | 'security-report'
  | 'performance-report'

interface RequiredDocument {
  id: string
  label: string
  allowedTypes?: FileType[]
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

const IMAGE_FILE_TYPES = new Set<FileType>(['jpg', 'png'])

interface ItemState {
  files: File[]
  requiredFiles: Record<string, File[]>
  additionalFiles: AdditionalFileEntry[]
  status: GenerationStatus
  errorMessage: string | null
  downloadUrl: string | null
  downloadName: string | null
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

const MENU_ITEMS: MenuItemContent[] = [
  {
    id: 'feature-list',
    label: '기능리스트 생성',
    eyebrow: '기능 정의',
    title: '요구사항에서 기능 목록 추출',
    description:
      '요구사항 명세나 기획 문서를 업로드하면 AI가 주요 기능과 설명을 정리한 기능 정의서를 제안합니다.',
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
      },
      {
        id: 'vendor-feature-list',
        label: '기능리스트',
        allowedTypes: ['pdf', 'docx', 'xlsx'],
      },
    ],
  },
  {
    id: 'testcase-generation',
    label: '테스트케이스 생성',
    eyebrow: '테스트 설계',
    title: '요구사항에서 테스트 케이스 생성',
    description:
      '업로드된 요구사항을 바탕으로 테스트 시나리오와 기대 결과를 정리한 테스트 케이스 초안을 생성합니다.',
    helper: '테스트 대상 기능이 담긴 문서를 업로드해 주세요. 필요한 자료를 하나만 올리면 됩니다.',
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
      },
      {
        id: 'vendor-feature-list',
        label: '기능리스트',
        allowedTypes: ['pdf', 'docx', 'xlsx'],
      },
    ],
  },
  {
    id: 'defect-report',
    label: '결함 리포트',
    eyebrow: '결함 리포트',
    title: '결함 리포트 초안 만들기',
    description:
      '시험 결과와 로그 파일을 업로드하면 결함 리포트 초안을 빠르게 구성할 수 있습니다.',
    helper: '테스트 로그, 정리된 표, 스크린샷 등 결함 관련 증적 자료를 첨부해 주세요.',
    buttonLabel: '결함 리포트 생성하기',
    allowedTypes: ['pdf', 'txt', 'csv', 'jpg'],
    uploaderVariant: 'grid',
    maxFiles: 12,
    hideDropzoneWhenFilled: true,
  },
  {
    id: 'security-report',
    label: '보안성 리포트',
    eyebrow: '보안성 분석',
    title: '보안성 분석 리포트 생성',
    description:
      '보안 점검 결과와 취약점 목록을 업로드하면 AI가 요약과 개선 권고안을 정리합니다.',
    helper: '취약점 점검표, 분석 보고서, 스크린샷 등을 첨부해 주세요. 필요한 자료를 하나만 올리면 됩니다.',
    buttonLabel: '보안성 리포트 생성하기',
    allowedTypes: ['pdf', 'txt', 'csv'],
    maxFiles: 1,
    hideDropzoneWhenFilled: true,
  },
  {
    id: 'performance-report',
    label: '성능 평가 리포트',
    eyebrow: '성능 평가',
    title: '성능 평가 리포트 완성하기',
    description:
      '벤치마크 결과나 모니터링 데이터를 업로드하면 성능 분석 리포트를 구조화해 드립니다.',
    helper: '성능 측정 결과 표, CSV 데이터, 스크린샷 등을 업로드해 주세요. 필요한 자료를 하나만 올리면 됩니다.',
    buttonLabel: '성능평가 리포트 생성하기',
    allowedTypes: ['pdf', 'csv', 'txt'],
    maxFiles: 1,
    hideDropzoneWhenFilled: true,
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
  const controllersRef = useRef<Record<MenuItemId, AbortController | null>>(
    Object.fromEntries(MENU_ITEM_IDS.map((id) => [id, null])) as Record<MenuItemId, AbortController | null>,
  )
  const downloadUrlsRef = useRef<Record<MenuItemId, string | null>>(
    Object.fromEntries(MENU_ITEM_IDS.map((id) => [id, null])) as Record<MenuItemId, string | null>,
  )

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

  const activeState = itemStates[activeContent.id] ?? createItemState(activeContent)
  const hasRequiredDocuments = (activeContent.requiredDocuments?.length ?? 0) > 0
  const handleSelectAnotherProject = useCallback(() => {
    navigate('/projects')
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
          },
        }
      })
    },
    [releaseDownloadUrl],
  )

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
          (doc) => (current.requiredFiles[doc.id]?.length ?? 0) === 0,
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
          },
        }))
        return
      }

      setItemStates((prev) => ({
        ...prev,
        [id]: {
          ...prev[id],
          status: 'loading',
          errorMessage: null,
        },
      }))

      controllersRef.current[id]?.abort()
      const controller = new AbortController()
      controllersRef.current[id] = controller

      const formData = new FormData()
      formData.append('menu_id', id)
      uploads.forEach((file) => {
        formData.append('files', file)
      })
      if (metadataEntries.length > 0) {
        formData.append('file_metadata', JSON.stringify(metadataEntries))
      }

      try {
        const response = await fetch(
          `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/generate`,
          {
            method: 'POST',
            body: formData,
            signal: controller.signal,
          },
        )

        if (!response.ok) {
          let detail = '자료를 생성하는 중 오류가 발생했습니다.'
          try {
            const payload = (await response.json()) as { detail?: unknown }
            if (payload && typeof payload.detail === 'string') {
              detail = payload.detail
            }
          } catch {
            const text = await response.text()
            if (text) {
              detail = text
            }
          }

          if (!controller.signal.aborted) {
            setItemStates((prev) => ({
              ...prev,
              [id]: {
                ...prev[id],
                status: 'error',
                errorMessage: detail,
              },
            }))
          }
          return
        }

        const blob = await response.blob()
        if (controller.signal.aborted) {
          return
        }

        const disposition = response.headers.get('content-disposition')
        const parsedName = parseFileNameFromDisposition(disposition)
        const safeName = sanitizeFileName(parsedName ?? `${id}-result.csv`)
        const objectUrl = URL.createObjectURL(blob)

        setItemStates((prev) => {
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
            },
          }
        })
        downloadUrlsRef.current[id] = objectUrl
      } catch (error) {
        if (controller.signal.aborted) {
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
          },
        }))
      } finally {
        if (controllersRef.current[id] === controller) {
          controllersRef.current[id] = null
        }
      }
    },
    [backendUrl, itemStates, menuById, projectId, releaseDownloadUrl],
  )

  const handleReset = useCallback(
    (id: MenuItemId) => {
      controllersRef.current[id]?.abort()
      controllersRef.current[id] = null

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
        const controller = controllersRef.current[id as MenuItemId]
        controller?.abort()
        controllersRef.current[id as MenuItemId] = null

        const downloadUrl = downloadUrlsRef.current[id as MenuItemId]
        if (downloadUrl) {
          URL.revokeObjectURL(downloadUrl)
          downloadUrlsRef.current[id as MenuItemId] = null
        }
      })
    }
  }, [])

  return (
    <div className="project-management-page">
      <aside className="project-management-sidebar">
        <div className="project-management-overview">
          <span className="project-management-overview__label">프로젝트</span>
          <strong className="project-management-overview__name">{projectName}</strong>
        </div>

        <nav aria-label="프로젝트 관리 메뉴" className="project-management-menu">
          <ul className="project-management-menu__list">
            {MENU_ITEMS.map((item) => {
              const isActive = activeItem === item.id

              return (
                <li
                  key={item.id}
                  className={`project-management-menu__item${
                    isActive ? ' project-management-menu__item--active' : ''
                  }`}
                >
                  <button
                    type="button"
                    className="project-management-menu__button"
                    onClick={() => setActiveItem(item.id)}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <span className="project-management-menu__label">{item.label}</span>
                    <span className="project-management-menu__helper">{item.eyebrow}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>
      </aside>

      <main className="project-management-content" aria-label="프로젝트 관리 컨텐츠">
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

          {activeState.status !== 'success' && (
            <>
              {hasRequiredDocuments ? (
                <>
                  <section
                    aria-labelledby="required-upload-section"
                    className="project-management-content__section"
                  >
                    <h2 id="required-upload-section" className="project-management-content__section-title">
                      필수 문서 업로드
                    </h2>
                    <div className="project-management-required__list">
                      {(activeContent.requiredDocuments ?? []).map((doc) => {
                        const fileList = activeState.requiredFiles[doc.id] ?? []
                        const resolvedTypes = doc.allowedTypes ?? activeContent.allowedTypes
                        const allowMultiple = resolvedTypes.every((type) => IMAGE_FILE_TYPES.has(type))

                        return (
                          <div key={doc.id} className="project-management-required__item">
                            <span className="project-management-required__label">{doc.label}</span>
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
                </section>
              )}
            </>
          )}

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
                  CSV 다운로드
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
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

