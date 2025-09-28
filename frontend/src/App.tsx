import './App.css'
import { useCallback, useMemo } from 'react'

import { AppShell } from './app/components/AppShell'
import { useAuthStatus } from './app/hooks/useAuthStatus'
import { usePathname } from './app/hooks/usePathname'
import { resolvePage } from './app/routing/resolvePage'
import { useRouteGuards } from './app/routing/useRouteGuards'
import { clearAuthentication } from './auth'
import { openGoogleDriveWorkspace } from './drive'
import { navigate } from './navigation'

function App() {
  const authStatus = useAuthStatus()
  const pathname = usePathname()

  useRouteGuards(pathname, authStatus)

  const pageContent = useMemo(() => resolvePage({ pathname, authStatus }), [pathname, authStatus])

  const handleLogout = useCallback(() => {
    clearAuthentication()
    navigate('/', { replace: true })
  }, [])

  const handleOpenDrive = useCallback(() => {
    openGoogleDriveWorkspace()
  }, [])

  return (
    <AppShell
      isAuthenticated={authStatus === 'authenticated'}
      onLogout={handleLogout}
      onOpenDrive={handleOpenDrive}
    >
      {pageContent}
    </AppShell>
  )
}

export default App
