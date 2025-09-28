import '../App.css'
import { useEffect, useMemo, useState } from 'react'

import { DRIVE_AUTH_STORAGE_KEY, getBackendUrl } from '../config'

interface DriveProject {
  id: string
  name: string
  createdTime?: string
  modifiedTime?: string
}

interface DriveSetupResponse {
  folderCreated: boolean
  folderId: string
  folderName: string
  projects: DriveProject[]
  account?: {
    googleId: string
    displayName: string
    email?: string | null
  }
}

type ViewState = 'loading' | 'ready' | 'error'

function formatDateTime(value?: string) {
  if (!value) {
    return null
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return null
  }

  return new Intl.DateTimeFormat('ko-KR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed)
}

export function DriveSetupPage() {
  const backendUrl = useMemo(() => getBackendUrl(), [])
  const [viewState, setViewState] = useState<ViewState>('loading')
  const [errorMessage, setErrorMessage] = useState<string>('')
  const [result, setResult] = useState<DriveSetupResponse | null>(null)
  const [reloadIndex, setReloadIndex] = useState(0)

  // B) 마운트 시점에 세션 키만 조용히 정리
  useEffect(() => {
    try {
      sessionStorage.removeItem(DRIVE_AUTH_STORAGE_KEY)
    } catch (e) {
      console.error('failed to clear auth message', e)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    let isMounted = true

    async function ensureFolder() {
      setViewState('loading')
      setErrorMessage('')

      try {
        const response = await fetch(`${backendUrl}/drive/gs/setup`, {
          method: 'POST',
          signal: controller.signal,
        })

        if (!response.ok) {
          let detail = 'Google Drive 상태를 확인하는 중 오류가 발생했습니다.'
          try {
            const payload = await response.json()
            if (payload && typeof payload.detail === 'string') {
              detail = payload.detail
            }
          } catch {
            const text = await response.text()
            if (text) {
              detail = text
            }
          }
          throw new Error(detail)
        }

        const data = (await response.json()) as DriveSetupResponse
        if (!isMounted) {
          return
        }
        setResult(data)
        setViewState('ready')
      } catch (error) {
        if (!isMounted || controller.signal.aborted) {
          return
        }

        const fallback =
          error instanceof Error
            ? error.message
            : '알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
        setErrorMessage(fallback)
        setViewState('error')
      }
    }

    ensureFolder()

    return () => {
      isMounted = false
      controller.abort()
    }
  }, [backendUrl, reloadIndex])

  const handleRetry = () => {
    setReloadIndex((index) => index + 1)
  }

  const projects = result?.projects ?? []

  return (
    <div className="page drive-page">
      <header className="page__header">
        <span className="page__eyebrow">Google Drive 프로젝트</span>
        <h1 className="page__title">프로젝트</h1>
      </header>

      {result?.account && (
        <div className="drive-page__account" role="note">
          <span className="drive-page__account-name">{result.account.displayName}</span>
          {result.account.email && (
            <span className="drive-page__account-email">{result.account.email}</span>
          )}
        </div>
      )}

      {viewState === 'loading' && (
        <section className="drive-card drive-card--loading" aria-busy="true">
          <div className="drive-card__spinner" aria-hidden="true" />
          <p className="drive-card__loading-text">Google Drive에서 폴더 상태를 확인하는 중입니다…</p>
        </section>
      )}

      {viewState === 'error' && (
        <section className="drive-card drive-card--error" role="alert">
          <h2 className="drive-card__title">Drive 상태를 불러오지 못했습니다</h2>
          <p className="drive-card__description">{errorMessage}</p>
          <button type="button" className="drive-create drive-create--primary" onClick={handleRetry}>
            다시 시도
          </button>
        </section>
      )}

      {viewState === 'ready' && result && (
        <section className="drive-card">
          {result.folderCreated && (
            <div className="drive-card__banner drive-card__banner--success" role="status">
              '{result.folderName}' 폴더를 Google Drive에 새로 만들었습니다.
            </div>
          )}

          <h2 className="drive-card__title">프로젝트 선택</h2>
          <p className="drive-card__description">
            {projects.length > 0
              ? '사용할 프로젝트를 선택하거나 새 프로젝트를 생성해 주세요.'
              : `현재 '${result.folderName}' 폴더 안에 프로젝트가 없습니다.`}
          </p>

          {projects.length > 0 ? (
            <>
              <ul className="drive-projects__list">
                {projects.map((project) => {
                  const modified = formatDateTime(project.modifiedTime)
                  return (
                    <li key={project.id}>
                      <button type="button" className="drive-projects__item">
                        <span className="drive-projects__name">{project.name}</span>
                        {modified && (
                          <span className="drive-projects__meta">최근 수정 {modified}</span>
                        )}
                      </button>
                    </li>
                  )
                })}
              </ul>

              <button type="button" className="drive-create drive-create--compact">
                새 프로젝트 만들기
              </button>
            </>
          ) : (
            <div className="drive-empty">
              <p className="drive-empty__title">아직 프로젝트 폴더가 없어요.</p>
              <p className="drive-empty__subtitle">첫 프로젝트를 생성해 팀 작업을 시작해 보세요.</p>
              <button type="button" className="drive-create drive-create--primary">
                프로젝트 생성
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
