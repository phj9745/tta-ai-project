import type { ReactNode } from 'react'

import type { AuthStatus } from '../../auth'
import { DriveSetupPage } from '../../pages/DriveSetupPage'
import { LoginPage } from '../../pages/LoginPage'
import { ProjectManagementPage } from '../../pages/ProjectManagementPage'
import { FeatureListEditPage } from '../../pages/FeatureListEditPage'
import { AdminPromptsPage } from '../../pages/AdminPromptsPage'

const PROJECT_PATH_PATTERN = /^\/projects\/([^/]+)$/
const FEATURE_LIST_EDIT_PATTERN = /^\/projects\/([^/]+)\/feature-list\/edit$/
const PROJECTS_ROOT_PATH = '/projects'
const LEGACY_DRIVE_PATH = '/drive'
const ADMIN_PROMPTS_PATH = '/admin/prompts'

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

  if (pathname === ADMIN_PROMPTS_PATH) {
    return <AdminPromptsPage />
  }

  const featureListMatch = pathname.match(FEATURE_LIST_EDIT_PATTERN)
  if (featureListMatch) {
    return <FeatureListEditPage projectId={decodeURIComponent(featureListMatch[1])} />
  }

  const projectMatch = pathname.match(PROJECT_PATH_PATTERN)
  if (projectMatch) {
    return <ProjectManagementPage projectId={decodeURIComponent(projectMatch[1])} />
  }

  return <LoginPage />
}
