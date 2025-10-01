import type { DriveProject } from '../../types/drive'
import { navigate } from '../../navigation'

interface DriveProjectsListProps {
  projects: DriveProject[]
}

export function DriveProjectsList({ projects }: DriveProjectsListProps) {
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

        return (
          <li key={project.id}>
            <button
              type="button"
              className="drive-projects__item"
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
          </li>
        )
      })}
    </ul>
  )
}
