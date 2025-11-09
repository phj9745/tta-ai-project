import type { DriveProject } from '../../types/drive'
import { navigate } from '../../navigation'

interface DriveProjectsListProps {
  projects: DriveProject[]
  onDeleteProject?: (project: DriveProject) => void
  deletingProjectId?: string | null
}

export function DriveProjectsList({
  projects,
  onDeleteProject,
  deletingProjectId,
}: DriveProjectsListProps) {
  return (
    <ul className="drive-projects__list">
      {projects.map((project) => {
        const modified = project.modifiedTime ? new Date(project.modifiedTime) : null
        const formatted = modified && !Number.isNaN(modified.getTime())
          ? new Intl.DateTimeFormat('ko-KR', {
              dateStyle: 'medium',
              timeStyle: 'short',
            }).format(modified)
          : null

        const isDeleting = deletingProjectId === project.id

        return (
          <li key={project.id}>
            <div className="drive-projects__item">
              <button
                type="button"
                className="drive-projects__main"
                onClick={() => {
                  const params = new URLSearchParams()
                  if (project.name) {
                    params.set('name', project.name)
                  }
                  navigate(
                    `/projects/${encodeURIComponent(project.id)}${
                      params.size > 0 ? `?${params.toString()}` : ''
                    }`,
                  )
                }}
              >
                <span className="drive-projects__name">{project.name}</span>
                {formatted && <span className="drive-projects__meta">최근 수정 {formatted}</span>}
              </button>

              {onDeleteProject && (
                <div className="drive-projects__actions">
                  <button
                    type="button"
                    className="drive-projects__delete-button"
                    onClick={(event) => {
                      event.stopPropagation()
                      event.preventDefault()
                      onDeleteProject(project)
                    }}
                    disabled={isDeleting}
                    aria-label={`${project.name} 프로젝트 삭제`}
                    title={`${project.name} 프로젝트 삭제`}
                  >
                    {isDeleting ? '삭제 중…' : '삭제'}
                  </button>
                </div>
              )}
            </div>
          </li>
        )
      })}
    </ul>
  )
}
