import {
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PropsWithChildren,
  type ReactNode,
} from 'react'

type AppShellStyle = CSSProperties & {
  '--app-shell-header-height': string
}

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
    'app-shell__link',
    'app-shell__link-button',
    isAdminActive ? 'app-shell__link--active' : '',
  ]
    .filter(Boolean)
    .join(' ')

  const [leadingAction, setLeadingAction] = useState<ReactNode | null>(null)
  const [headerHeight, setHeaderHeight] = useState(0)
  const headerRef = useRef<HTMLElement | null>(null)

  const handleSetLeadingAction = useCallback((node: ReactNode | null) => {
    setLeadingAction(node)
  }, [])

  useLayoutEffect(() => {
    const headerElement = headerRef.current
    if (!headerElement) {
      return
    }

    const updateHeaderHeight = () => {
      const { height } = headerElement.getBoundingClientRect()
      setHeaderHeight((prev) => (Math.abs(prev - height) > 0.5 ? height : prev))
    }

    updateHeaderHeight()

    const resizeObserver = new ResizeObserver(updateHeaderHeight)
    resizeObserver.observe(headerElement)

    return () => {
      resizeObserver.disconnect()
    }
  }, [])

  const headerContextValue = useMemo(
    () => ({
      setLeadingAction: handleSetLeadingAction,
    }),
    [handleSetLeadingAction],
  )

  const shellStyle = useMemo<AppShellStyle>(
    () => ({
      '--app-shell-header-height': `-${headerHeight}px`,
    }),
    [headerHeight],
  )

  return (
    <AppShellHeaderContext.Provider value={headerContextValue}>
      <div className="app-shell" style={shellStyle}>
        <header ref={headerRef} className="app-shell__header">
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
              <span className="app-shell__brand-mark" aria-hidden="true">
                <img src="/logo.png" alt="Testmate 로고" className="app-shell__brand-img" />
              </span>
              <span className="app-shell__brand-text">Testmate</span>
            </button>
          </div>
          <div className="app-shell__header-right">
            <BackgroundTaskTray />
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
          </div>
        </header>

        <main className="app-shell__main">{children}</main>
      </div>
    </AppShellHeaderContext.Provider>
  )
}
