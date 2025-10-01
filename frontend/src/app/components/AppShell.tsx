import type { PropsWithChildren } from 'react'

interface AppShellProps {
  isAuthenticated: boolean
  onLogout: () => void
  onOpenDrive: () => void
}

export function AppShell({
  isAuthenticated,
  onLogout,
  onOpenDrive,
  children,
}: PropsWithChildren<AppShellProps>) {
  return (
    <div className="app-shell">
      <header className="app-shell__header">
        <div className="app-shell__brand">TTA AI 프로젝트 허브</div>
        {isAuthenticated && (
          <nav aria-label="계정 메뉴" className="app-shell__nav">
            <button type="button" className="app-shell__drive" onClick={onOpenDrive}>
              구글 드라이브
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
