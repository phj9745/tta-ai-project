import { useCallback, useMemo, useState, type PropsWithChildren, type ReactNode } from 'react'

import { BackgroundTaskTray } from '../../components/layout/BackgroundTaskTray'
import { AppShellHeaderContext } from './AppShellHeaderContext'

interface AppShellProps {
  isAuthenticated: boolean
  currentPath: string
  onLogout: () => void
  onOpenDrive: () => void
  onNavigateAdmin: () => void
  onBrandClick: () => void
}

export function AppShell({
  isAuthenticated,
  currentPath,
  onLogout,
  onOpenDrive,
  onNavigateAdmin,
  onBrandClick,
  children,
}: PropsWithChildren<AppShellProps>) {
  const isAdminActive = currentPath.startsWith('/admin')

  const adminClasses = [
    'app-shell__nav-button',
    'app-shell__nav-button--ghost',
    isAdminActive ? 'app-shell__nav-button--active' : '',
  ]
    .filter(Boolean)
    .join(' ')

  const [leadingAction, setLeadingAction] = useState<ReactNode | null>(null)

  const handleSetLeadingAction = useCallback((node: ReactNode | null) => {
    setLeadingAction(node)
  }, [])

  const headerContextValue = useMemo(
    () => ({
      setLeadingAction: handleSetLeadingAction,
    }),
    [handleSetLeadingAction],
  )

  return (
    <AppShellHeaderContext.Provider value={headerContextValue}>
      <div className="app-shell">
        <header className="app-shell__header">
          <div className="app-shell__header-inner">
            <div className="app-shell__header-left">
              {leadingAction ? (
                <div className="app-shell__leading-action">{leadingAction}</div>
              ) : null}
              <button
                type="button"
                className="app-shell__brand-button"
                onClick={onBrandClick}
                aria-label="프로젝트 선택 화면으로 이동"
              >
                <span className="app-shell__brand-icon" aria-hidden="true">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    className="app-shell__brand-icon-mark"
                  >
                    <path
                      d="M4 12.5L9 17.5L20 6.5"
                      stroke="currentColor"
                      strokeWidth="2.2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
                <span className="app-shell__brand-copy">
                  <span className="app-shell__brand-title">TestMate</span>
                  <span className="app-shell__brand-subtitle">QA Workspace</span>
                </span>
              </button>
            </div>
            <div className="app-shell__header-right">
              <BackgroundTaskTray />
              {isAuthenticated && (
                <nav aria-label="계정 메뉴" className="app-shell__nav">
                  <button
                    type="button"
                    className="app-shell__nav-button app-shell__nav-button--ghost"
                    onClick={onOpenDrive}
                  >
                    구글 드라이브
                  </button>
                  <button type="button" className={adminClasses} onClick={onNavigateAdmin}>
                    프롬프트 관리자
                  </button>
                  <button
                    type="button"
                    className="app-shell__nav-button app-shell__nav-button--primary"
                    onClick={onLogout}
                  >
                    로그아웃
                  </button>
                </nav>
              )}
            </div>
          </div>
        </header>

        <main className="app-shell__main">{children}</main>
      </div>
    </AppShellHeaderContext.Provider>
  )
}
