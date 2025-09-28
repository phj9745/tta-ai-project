import { useMemo } from 'react'

interface ProjectManagementPageProps {
  projectId: string
}

export function ProjectManagementPage({ projectId }: ProjectManagementPageProps) {
  const projectName = useMemo(() => {
    const searchParams = new URLSearchParams(window.location.search)
    const name = searchParams.get('name')
    return name ?? projectId
  }, [projectId])

  return (
    <div className="project-management-page">
      <aside className="project-management-sidebar">
        <div className="project-management-overview">
          <span className="project-management-overview__label">프로젝트</span>
          <strong className="project-management-overview__name">{projectName}</strong>
        </div>

        <nav aria-label="프로젝트 관리 메뉴" className="project-management-menu">
          <ul className="project-management-menu__list">
            <li className="project-management-menu__item project-management-menu__item--primary">
              <span aria-hidden="true" className="project-management-menu__prefix">
                -
              </span>
              <span className="project-management-menu__label">기능 및 TC 생성 메뉴</span>
            </li>
            <li className="project-management-menu__item project-management-menu__item--primary">
              <span aria-hidden="true" className="project-management-menu__prefix">
                -
              </span>
              <div className="project-management-menu__group">
                <span className="project-management-menu__label">결함리포트 생성</span>
                <ul className="project-management-menu__sublist">
                  <li className="project-management-menu__item project-management-menu__item--secondary">
                    <span aria-hidden="true" className="project-management-menu__prefix">
                      &gt;
                    </span>
                    <span className="project-management-menu__label">결함</span>
                  </li>
                  <li className="project-management-menu__item project-management-menu__item--secondary">
                    <span aria-hidden="true" className="project-management-menu__prefix">
                      &gt;
                    </span>
                    <span className="project-management-menu__label">보안성</span>
                  </li>
                </ul>
              </div>
            </li>
            <li className="project-management-menu__item project-management-menu__item--primary">
              <span aria-hidden="true" className="project-management-menu__prefix">
                -
              </span>
              <span className="project-management-menu__label">성능평가리포트 생성</span>
            </li>
          </ul>
        </nav>
      </aside>

      <main className="project-management-content" aria-label="프로젝트 관리 컨텐츠" />
    </div>
  )
}

