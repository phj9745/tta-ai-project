import { useMemo, useState } from 'react'

import { navigate } from '../../navigation'
import { useBackgroundTasks } from '../../app/background/BackgroundTaskContext'
import type { BackgroundTaskStatus } from '../../app/background/BackgroundTaskContext'

function formatStatus(status: BackgroundTaskStatus): string {
  switch (status) {
    case 'running':
      return '진행 중'
    case 'succeeded':
      return '완료'
    case 'failed':
      return '실패'
    case 'cancelled':
      return '중단됨'
    default:
      return status
  }
}

export function BackgroundTaskTray() {
  const { tasks, cancelTask, dismissTask, getDownloadUrl } = useBackgroundTasks()
  const [isOpen, setIsOpen] = useState(false)

  const sortedTasks = useMemo(
    () => [...tasks].sort((a, b) => b.createdAt - a.createdAt),
    [tasks],
  )

  const runningCount = sortedTasks.filter((task) => task.status === 'running').length

  return (
    <div className="app-shell__tasks">
      <button
        type="button"
        className={`app-shell__tasks-toggle${isOpen ? ' app-shell__tasks-toggle--open' : ''}`}
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
      >
        <span className="app-shell__tasks-label">작업 현황</span>
        <span className="app-shell__tasks-count" aria-live="polite">
          {runningCount}
        </span>
      </button>

      {isOpen && (
        <div className="app-shell__tasks-panel" role="dialog" aria-label="백그라운드 작업 현황">
          <ul className="app-shell__tasks-list">
            {sortedTasks.length === 0 ? (
              <li className="app-shell__task app-shell__task--empty">
                현재 진행 중인 작업이 없습니다.
              </li>
            ) : null}

            {sortedTasks.map((task) => {
              const statusLabel = formatStatus(task.status)
              const downloadResult =
                task.result && task.result.type === 'download' ? task.result : null
              const warningsCount = downloadResult?.warnings?.length ?? 0
              const hasWarnings = warningsCount > 0

              const handlePrimaryAction = () => {
                if (downloadResult) {
                  const url = getDownloadUrl(task.id)
                  if (!url) {
                    return
                  }
                  const link = document.createElement('a')
                  link.href = url
                  link.download = downloadResult.filename
                  document.body.appendChild(link)
                  link.click()
                  document.body.removeChild(link)
                } else if (task.result?.type === 'navigate') {
                  navigate(task.result.url)
                }
              }

              const primaryLabel = (() => {
                if (downloadResult) return '다운로드'
                if (task.result?.type === 'navigate')
                  return task.result.label ?? '열기'
                return null
              })()

              return (
                <li
                  key={task.id}
                  className={`app-shell__task app-shell__task--${task.status}`}
                >
                  <div className="app-shell__task-main">
                    <div className="app-shell__task-title">{task.label}</div>
                    <div className="app-shell__task-status">
                      <span
                        className={`app-shell__task-status-badge app-shell__task-status-badge--${task.status}`}
                      >
                        {statusLabel}
                      </span>
                      {task.message ? (
                        <span className="app-shell__task-message">
                          {task.message}
                        </span>
                      ) : null}
                      {task.status === 'failed' && task.errorMessage ? (
                        <span className="app-shell__task-error">
                          {task.errorMessage}
                        </span>
                      ) : null}
                      {hasWarnings ? (
                        <span className="app-shell__task-warning">
                          주의 사항 {warningsCount}건
                        </span>
                      ) : null}
                    </div>
                  </div>

                  <div className="app-shell__task-actions">
                    {primaryLabel && task.status === 'succeeded' ? (
                      <button
                        type="button"
                        className="app-shell__task-button"
                        onClick={handlePrimaryAction}
                      >
                        {primaryLabel}
                      </button>
                    ) : null}

                    {task.status === 'running' ? (
                      <button
                        type="button"
                        className="app-shell__task-button app-shell__task-button--cancel"
                        onClick={() => {
                          if (window.confirm('정말로 이 작업을 중단하시겠습니까?')) {
                            cancelTask(task.id)
                          }
                        }}
                        aria-label="작업 중단"
                        title="작업 중단"
                      >
                        작업 중단
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="app-shell__task-button app-shell__task-button--dismiss"
                        onClick={() => dismissTask(task.id)}
                        aria-label="목록에서 제거"
                        title="목록에서 제거"
                      >
                        <span aria-hidden="true">×</span>
                      </button>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
