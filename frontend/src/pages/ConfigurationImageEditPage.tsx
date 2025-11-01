import './ConfigurationImageEditPage.css'

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { KeyboardEvent } from 'react'

import { getBackendUrl } from '../config'
import { navigate } from '../navigation'

type LoadState = 'idle' | 'loading' | 'error' | 'ready'

type ConfigurationImageEntry = {
  id: string
  name: string
  mimeType?: string
  timeSec?: number
  isStart?: boolean
  modifiedTime?: string
}

type ConfigurationEventsEntry = {
  id: string
  name: string
  mimeType?: string
  modifiedTime?: string
} | null

type ConfigurationImageListResponse = {
  folderId?: string
  files?: ConfigurationImageEntry[]
  eventsFile?: ConfigurationEventsEntry
}

interface ConfigurationImageEditPageProps {
  projectId: string
}

function formatTimestamp(value: string | undefined): string | null {
  if (!value) {
    return null
  }
  try {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) {
      return null
    }
    return new Intl.DateTimeFormat('ko-KR', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date)
  } catch {
    return null
  }
}

function formatTimecode(seconds?: number): string | null {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds)) {
    return null
  }
  if (seconds < 0) {
    return null
  }
  const total = Math.round(seconds)
  const minutes = Math.floor(total / 60)
  const remaining = total % 60
  return `${minutes}:${remaining.toString().padStart(2, '0')}`
}

function parseRecentIds(): Set<string> {
  if (typeof window === 'undefined') {
    return new Set()
  }
  const params = new URLSearchParams(window.location.search)
  const raw = params.get('recent')
  if (!raw) {
    return new Set()
  }
  const ids = raw
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
  return new Set(ids)
}

export function ConfigurationImageEditPage({ projectId }: ConfigurationImageEditPageProps) {
  const backendUrl = useMemo(() => getBackendUrl(), [])
  const [images, setImages] = useState<ConfigurationImageEntry[]>([])
  const [eventsFile, setEventsFile] = useState<ConfigurationEventsEntry>(null)
  const [folderId, setFolderId] = useState<string | null>(null)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [reloadToken, setReloadToken] = useState(0)
  const [isDeleting, setIsDeleting] = useState(false)

  const recentIds = useMemo(() => parseRecentIds(), [])

  useEffect(() => {
    const controller = new AbortController()
    setLoadState('loading')
    setErrorMessage(null)

    const fetchData = async () => {
      try {
        const response = await fetch(
          `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/configuration-images`,
          { signal: controller.signal },
        )

        if (!response.ok) {
          const payload = await response.json().catch(() => null)
          const detail =
            payload && typeof payload.detail === 'string'
              ? payload.detail
              : '형상 이미지를 불러오는 중 오류가 발생했습니다.'
          throw new Error(detail)
        }

        const payload = (await response.json()) as ConfigurationImageListResponse
        if (controller.signal.aborted) {
          return
        }

        const nextImages = Array.isArray(payload.files)
          ? payload.files.filter(
              (item): item is ConfigurationImageEntry =>
                typeof item?.id === 'string' && typeof item?.name === 'string',
            )
          : []

        setImages(nextImages)
        setEventsFile(
          payload.eventsFile && typeof payload.eventsFile === 'object'
            ? payload.eventsFile
            : null,
        )
        setFolderId(typeof payload.folderId === 'string' ? payload.folderId : null)
        setSelectedIds((prev) => {
          if (prev.size === 0) {
            return prev
          }
          const available = new Set(nextImages.map((item) => item.id))
          const retained = new Set<string>()
          prev.forEach((id) => {
            if (available.has(id)) {
              retained.add(id)
            }
          })
          return retained
        })
        setLoadState('ready')
      } catch (error) {
        if (controller.signal.aborted) {
          return
        }
        const message =
          error instanceof Error && error.message
            ? error.message
            : '형상 이미지를 불러오는 중 예기치 않은 오류가 발생했습니다.'
        setErrorMessage(message)
        setLoadState('error')
      }
    }

    fetchData()

    return () => {
      controller.abort()
    }
  }, [backendUrl, projectId, reloadToken])

  const handleRetry = useCallback(() => {
    setReloadToken((token) => token + 1)
  }, [])

  const handleBack = useCallback(() => {
    const params = new URLSearchParams(window.location.search)
    params.delete('recent')
    params.delete('folderId')
    const query = params.toString()
    navigate(`/projects/${encodeURIComponent(projectId)}${query ? `?${query}` : ''}`)
  }, [projectId])

  const handleToggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const handleSelectAll = useCallback(() => {
    setSelectedIds(new Set(images.map((item) => item.id)))
  }, [images])

  const handleClearSelection = useCallback(() => {
    setSelectedIds(new Set())
  }, [])

  const handleCardKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>, id: string) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        handleToggleSelect(id)
      }
    },
    [handleToggleSelect],
  )

  const handleDeleteSelected = useCallback(async () => {
    if (selectedIds.size === 0 || isDeleting) {
      return
    }

    setIsDeleting(true)
    setSuccessMessage(null)
    setErrorMessage(null)

    try {
      const response = await fetch(
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/configuration-images`,
        {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ fileIds: Array.from(selectedIds) }),
        },
      )

      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        const detail =
          payload && typeof payload.detail === 'string'
            ? payload.detail
            : '선택한 이미지를 삭제하지 못했습니다.'
        throw new Error(detail)
      }

      const payload = (await response.json().catch(() => null)) as
        | { removed?: number }
        | null
      const removedCount =
        payload && typeof payload.removed === 'number'
          ? payload.removed
          : selectedIds.size

      setSuccessMessage(`선택한 ${removedCount}개의 이미지를 삭제했습니다.`)
      setSelectedIds(new Set())
      setReloadToken((token) => token + 1)
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : '선택한 이미지를 삭제하는 중 예기치 않은 오류가 발생했습니다.'
      setErrorMessage(message)
    } finally {
      setIsDeleting(false)
    }
  }, [backendUrl, isDeleting, projectId, selectedIds])

  const isReady = loadState === 'ready'
  const hasSelection = selectedIds.size > 0

  return (
    <div className="configuration-images">
      <header className="configuration-images__header">
        <button type="button" className="configuration-images__back" onClick={handleBack}>
          프로젝트로 돌아가기
        </button>
        <h1 className="configuration-images__title">형상 이미지 검토</h1>
        <p className="configuration-images__description">
          시연 동영상에서 추출된 화면 이미지를 검토하고 필요 없는 장면을 제거하세요.
          {recentIds.size > 0 && (
            <span className="configuration-images__highlight-note">
              최근 추가된 {recentIds.size}개의 이미지가 강조 표시됩니다.
            </span>
          )}
        </p>
        {folderId && (
          <p className="configuration-images__folder">드라이브 폴더 ID: {folderId}</p>
        )}
      </header>

      {errorMessage && (
        <div className="configuration-images__alert" role="alert">
          <p>{errorMessage}</p>
          {loadState === 'error' && (
            <button type="button" onClick={handleRetry} className="configuration-images__retry">
              다시 시도
            </button>
          )}
        </div>
      )}

      {successMessage && (
        <div className="configuration-images__success" role="status">
          {successMessage}
        </div>
      )}

      {loadState === 'loading' && (
        <div className="configuration-images__loading">형상 이미지를 불러오는 중…</div>
      )}

      {isReady && (
        <>
          <div className="configuration-images__actions">
            <div className="configuration-images__action-group">
              <button type="button" onClick={handleSelectAll} disabled={images.length === 0}>
                전체 선택
              </button>
              <button type="button" onClick={handleClearSelection} disabled={!hasSelection}>
                선택 해제
              </button>
            </div>
            <div className="configuration-images__action-group">
              <button
                type="button"
                className="configuration-images__delete"
                onClick={handleDeleteSelected}
                disabled={!hasSelection || isDeleting}
              >
                선택한 이미지 삭제
              </button>
              <button type="button" onClick={handleRetry} disabled={isDeleting}>
                새로 고침
              </button>
            </div>
          </div>

          {eventsFile && (
            <div className="configuration-images__events">
              <span>장면 변화 로그:</span>
              <a
                href={`${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/configuration-images/${encodeURIComponent(eventsFile.id)}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                {eventsFile.name || 'events.csv'}
              </a>
              {eventsFile.modifiedTime && (
                <span className="configuration-images__events-time">
                  {formatTimestamp(eventsFile.modifiedTime) ?? ''}
                </span>
              )}
            </div>
          )}

          {images.length === 0 ? (
            <p className="configuration-images__empty">표시할 형상 이미지가 없습니다.</p>
          ) : (
            <div className="configuration-images__grid">
              {images.map((image) => {
                const isSelected = selectedIds.has(image.id)
                const isRecent = recentIds.has(image.id)
                const timecode = formatTimecode(image.timeSec)
                const timestampLabel = formatTimestamp(image.modifiedTime)

                const classes = [
                  'configuration-images__card',
                  isSelected ? 'configuration-images__card--selected' : '',
                  isRecent ? 'configuration-images__card--recent' : '',
                ]
                  .filter(Boolean)
                  .join(' ')

                return (
                  <div
                    key={image.id}
                    className={classes}
                    role="button"
                    tabIndex={0}
                    aria-pressed={isSelected}
                    onClick={() => handleToggleSelect(image.id)}
                    onKeyDown={(event) => handleCardKeyDown(event, image.id)}
                  >
                    <div className="configuration-images__thumb">
                      <img
                        src={`${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/configuration-images/${encodeURIComponent(image.id)}`}
                        alt={`${image.name} 미리보기`}
                      />
                    </div>
                    <div className="configuration-images__info">
                      <div className="configuration-images__name" title={image.name}>
                        {image.name}
                      </div>
                      <div className="configuration-images__meta">
                        {timecode && <span>장면 시각: {timecode}</span>}
                        {image.isStart && <span className="configuration-images__badge">시작 화면</span>}
                        {timestampLabel && <span>{timestampLabel}</span>}
                      </div>
                      <label
                        className="configuration-images__select"
                        onClick={(event) => event.stopPropagation()}
                        onKeyDown={(event) => event.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onClick={(event) => event.stopPropagation()}
                          onChange={() => handleToggleSelect(image.id)}
                        />
                        <span>선택</span>
                      </label>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}
