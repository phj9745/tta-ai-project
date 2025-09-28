import { useMemo, useState } from 'react'

import { FileUploader } from '../components/FileUploader'
import {
  ALL_FILE_TYPES,
  type FileType,
} from '../components/fileUploaderTypes'

type MenuItemId = 'feature-tc' | 'defect-report' | 'security-report' | 'performance-report'
type MenuGroupId = 'defect-group'

type PrimaryMenuEntry =
  | {
      type: 'item'
      itemId: MenuItemId
    }
  | {
      type: 'group'
      id: MenuGroupId
      label: string
      itemIds: MenuItemId[]
    }

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

const PRIMARY_MENU: PrimaryMenuEntry[] = [
  { type: 'item', itemId: 'feature-tc' },
  { type: 'group', id: 'defect-group', label: '결함리포트 생성', itemIds: ['defect-report', 'security-report'] },
  { type: 'item', itemId: 'performance-report' },
]

interface ProjectManagementPageProps {
  projectId: string
}

export function ProjectManagementPage({ projectId }: ProjectManagementPageProps) {
  const projectName = useMemo(() => {
    const searchParams = new URLSearchParams(window.location.search)
    const name = searchParams.get('name')
    return name ?? projectId
  }, [projectId])

  const [activeItem, setActiveItem] = useState<MenuItemId>('feature-tc')
  const [openGroups, setOpenGroups] = useState<Record<MenuGroupId, boolean>>({
    'defect-group': true,
  })
  const [filesByItem, setFilesByItem] = useState<Record<MenuItemId, File[]>>(() => {
    return MENU_ITEM_IDS.reduce((acc, id) => {
      acc[id as MenuItemId] = []
      return acc
    }, {} as Record<MenuItemId, File[]>)
  })

  const activeContent = MENU_ITEMS.find((item) => item.id === activeItem) ?? MENU_ITEMS[0]

  const handleChangeFiles = (id: MenuItemId, nextFiles: File[]) => {
    setFilesByItem((prev) => ({
      ...prev,
      [id]: nextFiles,
    }))
  }

  const handleSelectGroup = (entry: Extract<PrimaryMenuEntry, { type: 'group' }>) => {
    const wasOpen = !!openGroups[entry.id]
    const nextOpen = !wasOpen

    setOpenGroups((prev) => ({
      ...prev,
      [entry.id]: nextOpen,
    }))

    if (nextOpen && !entry.itemIds.includes(activeItem)) {
      setActiveItem(entry.itemIds[0])
    }
  }

  return (
    <div className="project-management-page">
      <aside className="project-management-sidebar">
        <div className="project-management-overview">
          <span className="project-management-overview__label">프로젝트</span>
          <strong className="project-management-overview__name">{projectName}</strong>
        </div>

        <nav aria-label="프로젝트 관리 메뉴" className="project-management-menu">
          <ul className="project-management-menu__list">
            {PRIMARY_MENU.map((entry) => {
              if (entry.type === 'item') {
                const item = MENU_ITEMS.find((menuItem) => menuItem.id === entry.itemId)
                if (!item) {
                  return null
                }

                const isActive = activeItem === item.id

                return (
                  <li
                    key={item.id}
                    className={`project-management-menu__item project-management-menu__item--primary${
                      isActive ? ' project-management-menu__item--active' : ''
                    }`}
                  >
                    <button
                      type="button"
                      className="project-management-menu__button"
                      onClick={() => setActiveItem(item.id)}
                      aria-current={isActive ? 'page' : undefined}
                    >
                      <span className="project-management-menu__button-leading" aria-hidden="true">
                        <span className="project-management-menu__indicator" />
                      </span>
                      <span className="project-management-menu__label">{item.label}</span>
                    </button>
                  </li>
                )
              }

              const isOpen = openGroups[entry.id]
              const groupActive = entry.itemIds.includes(activeItem)

              return (
                <li
                  key={entry.id}
                  className={`project-management-menu__item project-management-menu__item--primary project-management-menu__item--group${
                    groupActive ? ' project-management-menu__item--active' : ''
                  }${isOpen ? ' project-management-menu__item--expanded' : ''}`}
                >
                  <button
                    type="button"
                    className="project-management-menu__button project-management-menu__button--group"
                    onClick={() => handleSelectGroup(entry)}
                    aria-expanded={isOpen}
                  >
                    <span className="project-management-menu__button-leading" aria-hidden="true">
                      <span className="project-management-menu__indicator" />
                    </span>
                    <span className="project-management-menu__label">{entry.label}</span>
                    <span
                      className={`project-management-menu__chevron${isOpen ? ' project-management-menu__chevron--open' : ''}`}
                      aria-hidden="true"
                    />
                  </button>
                  <ul
                    className={`project-management-menu__sublist${
                      isOpen ? '' : ' project-management-menu__sublist--collapsed'
                    }`}
                    hidden={!isOpen}
                  >
                    {entry.itemIds.map((itemId) => {
                      const item = MENU_ITEMS.find((menuItem) => menuItem.id === itemId)
                      if (!item) {
                        return null
                      }

                      const isActive = activeItem === item.id

                      return (
                        <li
                          key={item.id}
                          className={`project-management-menu__item project-management-menu__item--secondary${
                            isActive ? ' project-management-menu__item--active' : ''
                          }`}
                        >
                          <button
                            type="button"
                            className="project-management-menu__button"
                            onClick={() => setActiveItem(item.id)}
                            aria-current={isActive ? 'page' : undefined}
                          >
                            <span className="project-management-menu__button-leading" aria-hidden="true">
                              <span className="project-management-menu__indicator" />
                            </span>
                            <span className="project-management-menu__label">{item.label}</span>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                </li>
              )
            })}
          </ul>
        </nav>
      </aside>

      <main className="project-management-content" aria-label="프로젝트 관리 컨텐츠">
        <div className="project-management-content__inner">
          <div className="project-management-content__header">
            <span className="project-management-content__eyebrow">{activeContent.eyebrow}</span>
            <h1 className="project-management-content__title">{activeContent.title}</h1>
            <p className="project-management-content__description">{activeContent.description}</p>
          </div>

          <section aria-labelledby="upload-section" className="project-management-content__section">
            <h2 id="upload-section" className="project-management-content__section-title">
              자료 업로드
            </h2>
            <p className="project-management-content__helper">{activeContent.helper}</p>
            <FileUploader
              allowedTypes={activeContent.allowedTypes}
              files={filesByItem[activeContent.id]}
              onChange={(nextFiles) => handleChangeFiles(activeContent.id, nextFiles)}
            />
          </section>

          <div className="project-management-content__actions">
            <button type="button" className="project-management-content__button">
              {activeContent.buttonLabel}
            </button>
            <p className="project-management-content__footnote">
              업로드된 문서는 프로젝트 드라이브에 안전하게 보관되며, 생성된 결과는 별도의 탭에서 확인할 수 있습니다.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}

