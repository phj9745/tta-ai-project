import type { ReactNode } from 'react'

import type { AuthStatus } from '../../auth'
import { DriveSetupPage } from '../../pages/DriveSetupPage'
import { LoginPage } from '../../pages/LoginPage'
import { ProjectManagementPage } from '../../pages/ProjectManagementPage'

const PROJECT_PATH_PATTERN = /^\/projects\/([^/]+)$/
const PROJECTS_ROOT_PATH = '/projects'
const LEGACY_DRIVE_PATH = '/drive'

interface ResolvePageOptions {
  pathname: string
  authStatus: AuthStatus
}

export function resolvePage({ pathname, authStatus }: ResolvePageOptions): ReactNode {
  if (authStatus !== 'authenticated') {
    return <LoginPage />
  }

  if (pathname === PROJECTS_ROOT_PATH || pathname === LEGACY_DRIVE_PATH) {
    return <DriveSetupPage />
  }

  const projectMatch = pathname.match(PROJECT_PATH_PATTERN)
  if (projectMatch) {
    return <ProjectManagementPage projectId={decodeURIComponent(projectMatch[1])} />
  }

  return <LoginPage />
}
