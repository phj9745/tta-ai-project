import './App.css'
import { useEffect, useState } from 'react'

import { listen, navigate } from './navigation'
import { DriveSetupPage } from './pages/DriveSetupPage'
import { LoginPage } from './pages/LoginPage'

const KNOWN_PATHS = new Set(['/', '/drive'])

function App() {
  const [pathname, setPathname] = useState<string>(() => window.location.pathname || '/')

  useEffect(() => {
    const unsubscribe = listen((nextPath) => {
      setPathname(nextPath)
    })
    return unsubscribe
  }, [])

  useEffect(() => {
    if (!KNOWN_PATHS.has(pathname)) {
      navigate('/', { replace: true })
      setPathname('/')
    }
  }, [pathname])

  if (pathname === '/drive') {
    return <DriveSetupPage />
  }

  return <LoginPage />
}

export default App
