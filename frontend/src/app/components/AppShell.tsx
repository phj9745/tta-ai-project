import { useCallback, useMemo, useState, type PropsWithChildren, type ReactNode } from 'react'

import { navigate } from '../../navigation'
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

interface SidebarLink {
  label: string
  description: string
  path: string
  isActive: (currentPath: string) => boolean
}

const SIDEBAR_LINKS: SidebarLink[] = [
  {
    label: '프로젝트 허브',
    description: '프로젝트별 산출물과 히스토리를 관리합니다.',
    path: '/projects',
    isActive: (path) => path === '/projects' || path.startsWith('/projects/'),
  },
]

export function AppShell({
  isAuthenticated,
  currentPath,
  onLogout,
  onOpenDrive,
  onNavigateAdmin,
  onBrandClick,
  children,
}: PropsWithChildren<AppShellProps>) {
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
        <header className="app-shell__topbar">
          <div className="app-shell__topbar-left">
            <button
              type="button"
              className="app-shell__brand-button"
              onClick={onBrandClick}
              aria-label="프로젝트 선택 화면으로 이동"
            >
              <span className="app-shell__brand-mark" aria-hidden="true">
                <span className="app-shell__brand-mark-glow" />
                <span className="app-shell__brand-initials">TM</span>
              </span>
              <span className="app-shell__brand-wordmark">
                <span className="app-shell__brand-text">
                  <span className="app-shell__brand-primary">Test</span>
                  <span className="app-shell__brand-highlight">Mate</span>
                </span>
                <span className="app-shell__brand-tagline">QA Workspace</span>
              </span>
            </button>
            {leadingAction ? (
              <div className="app-shell__topbar-leading">{leadingAction}</div>
            ) : null}
          </div>
          <div className="app-shell__topbar-right">
            <BackgroundTaskTray />
            {isAuthenticated && (
              <div className="app-shell__account-actions">
                <button type="button" className="app-shell__drive" onClick={onOpenDrive}>
                  구글 드라이브
                </button>
                <button type="button" className="app-shell__logout" onClick={onLogout}>
                  로그아웃
                </button>
              </div>
            )}
          </div>
        </header>

        <div className="app-shell__layout">
          {isAuthenticated ? (
            <aside className="app-shell__sidebar" aria-label="주 메뉴">
              <div>
                <div className="app-shell__sidebar-heading">워크플로우</div>
                <div className="app-shell__sidebar-links">
                  {SIDEBAR_LINKS.map((link) => {
                    const isActive = link.isActive(currentPath)
                    return (
                      <button
                        key={link.path}
                        type="button"
                        className={`app-shell__sidebar-link${isActive ? ' app-shell__sidebar-link--active' : ''}`}
                        onClick={() => navigate(link.path)}
                      >
                        <span className="app-shell__sidebar-link-label">{link.label}</span>
                        <span className="app-shell__sidebar-link-description">{link.description}</span>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="app-shell__sidebar-footer">
                <button
                  type="button"
                  className="app-shell__sidebar-footer-link"
                  onClick={onNavigateAdmin}
                >
                  프롬프트 관리자
                </button>
              </div>
            </aside>
          ) : null}

          <main className="app-shell__main">{children}</main>
        </div>
      </div>
    </AppShellHeaderContext.Provider>
  )
}
