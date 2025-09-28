import { DriveActionButton } from './DriveActionButton'

interface DriveEmptyStateProps {
  onCreateClick: () => void
}

export function DriveEmptyState({ onCreateClick }: DriveEmptyStateProps) {
  return (
    <div className="drive-empty">
      <p className="drive-empty__title">아직 프로젝트 폴더가 없어요.</p>
      <p className="drive-empty__subtitle">첫 프로젝트를 생성해 팀 작업을 시작해 보세요.</p>
      <DriveActionButton onClick={onCreateClick}>프로젝트 생성</DriveActionButton>
    </div>
  )
}
