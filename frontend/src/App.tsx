import './App.css'
import { useEffect, useMemo, useState } from 'react'

import { listen, navigate } from './navigation'
import { DriveSetupPage } from './pages/DriveSetupPage'
import { LoginPage } from './pages/LoginPage'
import { ProjectManagementPage } from './pages/ProjectManagementPage'

function App() {
  const [pathname, setPathname] = useState<string>(() => window.location.pathname || '/')

  useEffect(() => {
    const unsubscribe = listen((nextPath) => {
      setPathname(nextPath)
    })
    return unsubscribe
  }, [])

  useEffect(() => {
    const isKnownPath = pathname === '/' || pathname === '/drive' || pathname.startsWith('/projects/')

    if (!isKnownPath) {
      navigate('/', { replace: true })
      setPathname('/')
    }
  }, [pathname])

  const projectMatch = pathname.match(/^\/projects\/([^/]+)$/)

  const pageContent = useMemo(() => {
    if (projectMatch) {
      return <ProjectManagementPage projectId={decodeURIComponent(projectMatch[1])} />
    }

    if (pathname === '/drive') {
      return <DriveSetupPage />
    }

    return <LoginPage />
  }, [pathname, projectMatch])

  return (
    <div className="app-shell">
      <header className="app-shell__header">
        <div className="app-shell__brand">TTA AI 프로젝트 허브</div>
        <nav aria-label="주요 메뉴" className="app-shell__nav">
          <a href="/" className={`app-shell__link${pathname === '/' ? ' app-shell__link--active' : ''}`}>로그인</a>
          <a href="/drive" className={`app-shell__link${pathname === '/drive' ? ' app-shell__link--active' : ''}`}>
            Drive 연동
          </a>
        </nav>
      </header>

      <main className="app-shell__main">{pageContent}</main>

      <footer className="app-shell__footer">© {new Date().getFullYear()} TTA AI Platform</footer>
    </div>
  )
}

export default App
