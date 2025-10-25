import { useEffect } from 'react'

import type { AuthStatus } from '../../auth'
import { navigate } from '../../navigation'

const PROJECT_PATH_PATTERN = /^\/projects\/(.+)$/
const FEATURE_LIST_EDIT_PATH_PATTERN = /^\/projects\/[^/]+\/feature-list\/edit$/
const TESTCASE_EDIT_PATH_PATTERN = /^\/projects\/[^/]+\/testcases\/edit$/
const PROJECTS_ROOT_PATH = '/projects'
const LEGACY_DRIVE_PATH = '/drive'
const ADMIN_PROMPTS_PATH = '/admin/prompts'

function isKnownPathname(pathname: string): boolean {
  if (
    pathname === '/' ||
    pathname === PROJECTS_ROOT_PATH ||
    pathname === LEGACY_DRIVE_PATH ||
    pathname === ADMIN_PROMPTS_PATH
  ) {
    return true
  }
  return (
    PROJECT_PATH_PATTERN.test(pathname) ||
    FEATURE_LIST_EDIT_PATH_PATTERN.test(pathname) ||
    TESTCASE_EDIT_PATH_PATTERN.test(pathname)
  )
}

export function useRouteGuards(pathname: string, authStatus: AuthStatus) {
  useEffect(() => {
    if (!isKnownPathname(pathname)) {
      navigate('/', { replace: true })
    }
  }, [pathname])

  useEffect(() => {
    if (authStatus !== 'authenticated' && pathname !== '/') {
      navigate('/', { replace: true })
    }
  }, [authStatus, pathname])

  useEffect(() => {
    if (pathname === LEGACY_DRIVE_PATH) {
      navigate(PROJECTS_ROOT_PATH, { replace: true })
      return
    }

    if (authStatus === 'authenticated' && pathname === '/') {
      navigate(PROJECTS_ROOT_PATH, { replace: true })
    }
  }, [authStatus, pathname])
}
