import type { PropsWithChildren } from 'react'

interface AppShellProps {
  isAuthenticated: boolean
  currentPath: string
  onLogout: () => void
  onOpenDrive: () => void
  onNavigateAdmin: () => void
}

export function AppShell({
  isAuthenticated,
  currentPath,
  onLogout,
  onOpenDrive,
  onNavigateAdmin,
  children,
}: PropsWithChildren<AppShellProps>) {
  const isAdminActive = currentPath.startsWith('/admin')

  const adminClasses = [
    'app-shell__link',
    'app-shell__link-button',
    isAdminActive ? 'app-shell__link--active' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className="app-shell">
      <header className="app-shell__header">
        <div className="app-shell__brand">TTA AI 프로젝트 허브</div>
        {isAuthenticated && (
          <nav aria-label="계정 메뉴" className="app-shell__nav">
            <button type="button" className="app-shell__drive" onClick={onOpenDrive}>
              구글 드라이브
            </button>
            <button type="button" className={adminClasses} onClick={onNavigateAdmin}>
              프롬프트 관리자
            </button>
            <button type="button" className="app-shell__logout" onClick={onLogout}>
              로그아웃
            </button>
          </nav>
        )}
      </header>

      <main className="app-shell__main">{children}</main>

      <footer className="app-shell__footer">© {new Date().getFullYear()} TTA AI Platform</footer>
    </div>
  )
}
