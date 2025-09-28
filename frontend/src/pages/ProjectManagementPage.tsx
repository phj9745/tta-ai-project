import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { FileUploader } from '../components/FileUploader'
import {
  ALL_FILE_TYPES,
  type FileType,
} from '../components/fileUploaderTypes'
import { getBackendUrl } from '../config'
import { navigate } from '../navigation'

type MenuItemId = 'feature-tc' | 'defect-report' | 'security-report' | 'performance-report'
interface MenuItemContent {
  id: MenuItemId
  label: string
  eyebrow: string
  title: string
  description: string
  helper: string
  buttonLabel: string
  allowedTypes: FileType[]
}

type GenerationStatus = 'idle' | 'loading' | 'success' | 'error'

interface ItemState {
  files: File[]
  status: GenerationStatus
  errorMessage: string | null
  downloadUrl: string | null
  downloadName: string | null
}

function createItemState(): ItemState {
  return {
    files: [],
    status: 'idle',
    errorMessage: null,
    downloadUrl: null,
    downloadName: null,
  }
}

function createInitialItemStates(): Record<MenuItemId, ItemState> {
  return MENU_ITEM_IDS.reduce((acc, id) => {
    acc[id as MenuItemId] = createItemState()
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
    id: 'feature-tc',
    label: '기능 및 TC 생성',
    eyebrow: '기능 & 테스트',
    title: '요구사항에서 기능과 테스트 케이스 생성',
    description:
      '요구사항 명세나 기획 문서를 업로드하면 AI가 기능 정의서와 테스트 케이스 초안을 자동으로 제안합니다.',
    helper: 'PDF, TXT, CSV 등 요구사항 관련 문서를 업로드해 주세요. 여러 파일을 동시에 첨부할 수 있습니다.',
    buttonLabel: '기능 및 TC 생성하기',
    allowedTypes: ALL_FILE_TYPES,
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
  },
  {
    id: 'security-report',
    label: '보안성 리포트',
    eyebrow: '보안성 분석',
    title: '보안성 분석 리포트 생성',
    description:
      '보안 점검 결과와 취약점 목록을 업로드하면 AI가 요약과 개선 권고안을 정리합니다.',
    helper: '취약점 점검표, 분석 보고서, 스크린샷 등을 첨부해 주세요.',
    buttonLabel: '보안성 리포트 생성하기',
    allowedTypes: ['pdf', 'txt', 'csv'],
  },
  {
    id: 'performance-report',
    label: '성능 평가 리포트',
    eyebrow: '성능 평가',
    title: '성능 평가 리포트 완성하기',
    description:
      '벤치마크 결과나 모니터링 데이터를 업로드하면 성능 분석 리포트를 구조화해 드립니다.',
    helper: '성능 측정 결과 표, CSV 데이터, 스크린샷 등을 업로드해 주세요.',
    buttonLabel: '성능평가 리포트 생성하기',
    allowedTypes: ['pdf', 'csv', 'txt'],
  },
]

const MENU_ITEM_IDS = MENU_ITEMS.map((item) => item.id)

const FIRST_MENU_ITEM = MENU_ITEMS[0]?.id ?? 'feature-tc'

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

  const activeContent = MENU_ITEMS.find((item) => item.id === activeItem) ?? MENU_ITEMS[0]

  const activeState = itemStates[activeContent.id] ?? createItemState()

  const handleSelectAnotherProject = useCallback(() => {
    navigate('/drive')
  }, [])

  const handleChangeFiles = useCallback(
    (id: MenuItemId, nextFiles: File[]) => {
      setItemStates((prev) => {
        const current = prev[id]
        if (!current || current.status === 'loading') {
          return prev
        }

        if (current.downloadUrl) {
          URL.revokeObjectURL(current.downloadUrl)
          downloadUrlsRef.current[id] = null
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
    [],
  )

  const handleGenerate = useCallback(
    async (id: MenuItemId) => {
      const current = itemStates[id]
      if (!current || current.status === 'loading') {
        return
      }

      if (current.files.length === 0) {
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
      current.files.forEach((file) => {
        formData.append('files', file)
      })

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

        downloadUrlsRef.current[id] = objectUrl

        setItemStates((prev) => {
          const previous = prev[id]
          if (previous?.downloadUrl) {
            URL.revokeObjectURL(previous.downloadUrl)
          }

          return {
            ...prev,
            [id]: {
              files: [],
              status: 'success',
              errorMessage: null,
              downloadUrl: objectUrl,
              downloadName: safeName,
            },
          }
        })
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
    [backendUrl, itemStates, projectId],
  )

  const handleReset = useCallback((id: MenuItemId) => {
    controllersRef.current[id]?.abort()
    controllersRef.current[id] = null

    setItemStates((prev) => {
      const current = prev[id]
      if (current?.downloadUrl) {
        URL.revokeObjectURL(current.downloadUrl)
        downloadUrlsRef.current[id] = null
      }

      return {
        ...prev,
        [id]: createItemState(),
      }
    })
  }, [])

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
              />
            </section>
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

