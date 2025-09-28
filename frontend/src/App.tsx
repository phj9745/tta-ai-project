import './App.css'
import { useEffect, useState } from 'react'

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

  if (projectMatch) {
    return <ProjectManagementPage projectId={decodeURIComponent(projectMatch[1])} />
  }

  if (pathname === '/drive') {
    return <DriveSetupPage />
  }

  return <LoginPage />
}

export default App
