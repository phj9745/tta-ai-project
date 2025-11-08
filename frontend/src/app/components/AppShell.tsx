import {
  useCallback,
  useMemo,
  useState,
  type PropsWithChildren,
  type ReactNode,
} from 'react'

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

interface NavigationItem {
  id: string
  label: string
  description: string
  onClick: () => void
  isActive: boolean
}

interface TopbarContent {
  tag?: string
  title: string
  subtitle?: string
}

function resolveTopbarContent(path: string): TopbarContent {
  if (path.startsWith('/admin')) {
    return {
      tag: '운영 도구',
      title: '프롬프트 관리자',
      subtitle: '대화형 테스트 시나리오와 프롬프트 템플릿을 관리합니다.',
    }
  }

  if (path === '/projects' || path === '/drive') {
    return {
      tag: '워크스페이스',
      title: '프로젝트 허브',
      subtitle: '자동화할 프로젝트를 선택하고 필요한 산출물을 생성하세요.',
    }
  }

  if (/\/configuration-images\//.test(path)) {
    return {
      tag: '프로젝트',
      title: '형상 이미지 추출',
      subtitle: '환경 설정과 실행 화면을 자동으로 캡처하여 구성 리포트를 만듭니다.',
    }
  }

  if (/\/feature-list\//.test(path)) {
    return {
      tag: '프로젝트',
      title: '기능 목록 정리',
      subtitle: '업로드한 산출물을 바탕으로 테스트 대상 기능을 정리합니다.',
    }
  }

  if (/\/testcases\//.test(path)) {
    return {
      tag: '프로젝트',
      title: '테스트 케이스 생성',
      subtitle: '자동 생성된 테스트 케이스를 검토하고 내보낼 수 있습니다.',
    }
  }

  if (/\/defect-report\//.test(path)) {
    return {
      tag: '프로젝트',
      title: '결함 리포트 작성',
      subtitle: '발견된 결함을 정리하고 공유 가능한 리포트를 생성합니다.',
    }
  }

  if (/\/projects\//.test(path)) {
    return {
      tag: '워크플로',
      title: '프로젝트 제어 센터',
      subtitle: '형상 캡처부터 리포트 작성까지 전체 과정을 한곳에서 관리합니다.',
    }
  }

  return {
    tag: 'TTA AI',
    title: 'QA Workspace',
    subtitle: '품질 보증 자동화를 위한 통합 업무 공간입니다.',
  }
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

  const navigationItems = useMemo<NavigationItem[]>(() => {
    const items: NavigationItem[] = [
      {
        id: 'projects',
        label: '프로젝트 허브',
        description: '프로젝트별 산출물과 파일을 관리합니다.',
        onClick: onBrandClick,
        isActive:
          currentPath === '/projects' ||
          currentPath === '/drive' ||
          currentPath.startsWith('/projects/'),
      },
    ]

    if (isAuthenticated) {
      items.push({
        id: 'prompts',
        label: '프롬프트 관리자',
        description: '대화형 템플릿을 구성하고 배포합니다.',
        onClick: onNavigateAdmin,
        isActive: currentPath.startsWith('/admin'),
      })
    }

    return items
  }, [currentPath, isAuthenticated, onBrandClick, onNavigateAdmin])

  const topbarContent = useMemo(() => resolveTopbarContent(currentPath), [currentPath])

  return (
    <AppShellHeaderContext.Provider value={headerContextValue}>
      <div className="app-shell">
        <aside className="app-shell__sidebar" aria-label="주요 탐색">
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

          <div className="app-shell__workspace-card">
            <span className="app-shell__workspace-eyebrow">현재 워크스페이스</span>
            <strong className="app-shell__workspace-name">TTA AI Studio</strong>
            <p className="app-shell__workspace-helper">
              테스트 산출물을 수집하고 보고서를 생성하여 팀과 공유하세요.
            </p>
            {isAuthenticated ? (
              <button
                type="button"
                className="app-shell__workspace-drive"
                onClick={onOpenDrive}
              >
                워크스페이스 열기
              </button>
            ) : null}
          </div>

          <nav className="app-shell__sidebar-nav" aria-label="주요 메뉴">
            <ul className="app-shell__nav-list">
              {navigationItems.map((item) => (
                <li key={item.id} className="app-shell__nav-item">
                  <button
                    type="button"
                    className={`app-shell__nav-button${item.isActive ? ' app-shell__nav-button--active' : ''}`}
                    onClick={item.onClick}
                    aria-current={item.isActive ? 'page' : undefined}
                  >
                    <span className="app-shell__nav-label">{item.label}</span>
                    <span className="app-shell__nav-description">{item.description}</span>
                  </button>
                </li>
              ))}
            </ul>
          </nav>

          {isAuthenticated ? (
            <div className="app-shell__sidebar-footer">
              <button type="button" className="app-shell__sidebar-logout" onClick={onLogout}>
                로그아웃
              </button>
            </div>
          ) : null}
        </aside>

        <div className="app-shell__body">
          <header className="app-shell__topbar">
            <div className="app-shell__topbar-left">
              {leadingAction ? (
                <div className="app-shell__leading-action">{leadingAction}</div>
              ) : null}

              <div className="app-shell__topbar-copy">
                {topbarContent.tag ? (
                  <span className="app-shell__topbar-tag">{topbarContent.tag}</span>
                ) : null}
                <h1 className="app-shell__topbar-title">{topbarContent.title}</h1>
                {topbarContent.subtitle ? (
                  <p className="app-shell__topbar-subtitle">{topbarContent.subtitle}</p>
                ) : null}
              </div>
            </div>

            <div className="app-shell__topbar-right">
              <BackgroundTaskTray />
              {isAuthenticated ? (
                <div className="app-shell__profile">
                  <span className="app-shell__profile-avatar" aria-hidden="true">
                    TM
                  </span>
                  <div className="app-shell__profile-meta">
                    <span className="app-shell__profile-name">TestMate 운영 계정</span>
                    <span className="app-shell__profile-role">품질 자동화</span>
                  </div>
                </div>
              ) : null}
            </div>
          </header>

          <main className="app-shell__main">
            <div className="app-shell__content">{children}</div>
          </main>

          <footer className="app-shell__footer">© {new Date().getFullYear()} TTA AI Platform</footer>
        </div>
      </div>
    </AppShellHeaderContext.Provider>
  )
}
