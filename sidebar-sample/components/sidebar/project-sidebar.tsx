"use client"

import { ImageIcon, ListIcon, TestTubeIcon, FileTextIcon, FolderIcon, ActivityIcon } from "lucide-react"

const MENU_ITEMS = [
  { id: "image-extraction", label: "형상 이미지 추출", icon: ImageIcon },
  { id: "feature-list", label: "기능리스트", icon: ListIcon },
  { id: "test-cases", label: "테스트케이스", icon: TestTubeIcon },
  { id: "result-report", label: "결함리포트", icon: FileTextIcon },
  { id: "safety-report", label: "보안성 결함리포트", icon: FolderIcon },
  { id: "safety-import", label: "성능시험 리포트", icon: ActivityIcon },
]

interface ProjectSidebarProps {
  projectName: string
  activeItem: string
  isSidebarOpen: boolean
  onSelectMenuItem: (id: string) => void
}

export function ProjectSidebar({ projectName, activeItem, isSidebarOpen, onSelectMenuItem }: ProjectSidebarProps) {
  const handleSelectMenuItem = (id: string) => {
    onSelectMenuItem(id)
  }

  return (
    <aside id="project-management-sidebar" className="project-management-sidebar" aria-hidden={!isSidebarOpen}>
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
                className={`project-management-menu__item${isActive ? " project-management-menu__item--active" : ""}`}
              >
                <button
                  type="button"
                  className="project-management-menu__button"
                  onClick={() => handleSelectMenuItem(item.id)}
                  aria-current={isActive ? "page" : undefined}
                >
                  <div className="project-management-menu__icon">
                    <Icon size={20} strokeWidth={2} />
                  </div>
                  <span className="project-management-menu__label">{item.label}</span>
                </button>
              </li>
            )
          })}
        </ul>
      </nav>
    </aside>
  )
}
