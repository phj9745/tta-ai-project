import './App.css'
import { useEffect, useMemo, useState } from 'react'

import { getAuthStatus, subscribeToAuth, clearAuthentication } from './auth'
import { listen, navigate } from './navigation'
import { DriveSetupPage } from './pages/DriveSetupPage'
import { LoginPage } from './pages/LoginPage'
import { ProjectManagementPage } from './pages/ProjectManagementPage'

function App() {
  const [pathname, setPathname] = useState<string>(() => window.location.pathname || '/')
  const [authStatus, setAuthStatus] = useState(() => getAuthStatus())

  useEffect(() => {
    const unsubscribe = listen((nextPath) => {
      setPathname(nextPath)
    })
    return unsubscribe
  }, [])

  useEffect(() => {
    const unsubscribe = subscribeToAuth((nextStatus) => {
      setAuthStatus(nextStatus)
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

  useEffect(() => {
    if (authStatus !== 'authenticated' && pathname !== '/') {
      navigate('/', { replace: true })
    }
  }, [authStatus, pathname])

  const projectMatch = pathname.match(/^\/projects\/([^/]+)$/)

  const pageContent = useMemo(() => {
    if (authStatus !== 'authenticated') {
      return <LoginPage />
    }

    if (projectMatch) {
      return <ProjectManagementPage projectId={decodeURIComponent(projectMatch[1])} />
    }

    if (pathname === '/drive') {
      return <DriveSetupPage />
    }

    return <LoginPage />
  }, [authStatus, pathname, projectMatch])

  const handleLogout = () => {
    clearAuthentication()
    navigate('/', { replace: true })
  }

  const isAuthenticated = authStatus === 'authenticated'

  return (
    <div className="app-shell">
      <header className="app-shell__header">
        <div className="app-shell__brand">TTA AI 프로젝트 허브</div>
        {isAuthenticated && (
          <nav aria-label="계정 메뉴" className="app-shell__nav">
            <button type="button" className="app-shell__logout" onClick={handleLogout}>
              로그아웃
            </button>
          </nav>
        )}
      </header>

      <main className="app-shell__main">{pageContent}</main>

      <footer className="app-shell__footer">© {new Date().getFullYear()} TTA AI Platform</footer>
    </div>
  )
}

export default App
