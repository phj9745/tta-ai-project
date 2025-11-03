import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react'

export type BackgroundTaskStatus = 'running' | 'succeeded' | 'failed'

export type BackgroundTaskResult =
  | {
      type: 'download'
      blob: Blob
      filename: string
      contentType: string
      warnings?: string[]
    }
  | {
      type: 'navigate'
      url: string
      label?: string
    }
  | {
      type: 'data'
      payload: unknown
    }
  | null

export interface BackgroundTask {
  id: string
  menuId: string
  label: string
  status: BackgroundTaskStatus
  message: string | null
  errorMessage: string | null
  result: BackgroundTaskResult
  createdAt: number
  updatedAt: number
}

export interface BackgroundTaskHandle {
  id: string
  update: (message: string | null) => void
  complete: (result: BackgroundTaskResult, message?: string | null) => void
  fail: (errorMessage: string | null) => void
}

interface BackgroundTaskContextValue {
  tasks: BackgroundTask[]
  startTask: (menuId: string, label: string) => BackgroundTaskHandle
  dismissTask: (taskId: string) => void
  getDownloadUrl: (taskId: string) => string | null
}

const BackgroundTaskContext = createContext<BackgroundTaskContextValue | null>(null)

function createTaskId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `task_${Math.random().toString(36).slice(2)}`
}

export function BackgroundTaskProvider({ children }: PropsWithChildren) {
  const [tasks, setTasks] = useState<BackgroundTask[]>([])
  const tasksRef = useRef<BackgroundTask[]>(tasks)
  const downloadUrlMapRef = useRef<Map<string, string>>(new Map())

  useEffect(() => {
    tasksRef.current = tasks
  }, [tasks])

  useEffect(() => {
    return () => {
      downloadUrlMapRef.current.forEach((url) => {
        try {
          URL.revokeObjectURL(url)
        } catch {
          // ignore revoke errors
        }
      })
      downloadUrlMapRef.current.clear()
    }
  }, [])

  const startTask = useCallback((menuId: string, label: string): BackgroundTaskHandle => {
    const id = createTaskId()
    const timestamp = Date.now()
    const task: BackgroundTask = {
      id,
      menuId,
      label,
      status: 'running',
      message: null,
      errorMessage: null,
      result: null,
      createdAt: timestamp,
      updatedAt: timestamp,
    }

    setTasks((prev) => [...prev, task])

    const updateTask = (partial: Partial<Omit<BackgroundTask, 'id' | 'menuId' | 'label'>>) => {
      setTasks((prev) =>
        prev.map((entry) =>
          entry.id === id
            ? {
                ...entry,
                ...partial,
                updatedAt: Date.now(),
              }
            : entry,
        ),
      )
    }

    return {
      id,
      update(message) {
        updateTask({ message })
      },
      complete(result, message = null) {
        updateTask({ status: 'succeeded', result, message, errorMessage: null })
      },
      fail(errorMessage) {
        updateTask({ status: 'failed', errorMessage, message: null })
      },
    }
  }, [])

  const dismissTask = useCallback((taskId: string) => {
    setTasks((prev) => prev.filter((task) => task.id !== taskId))
    const url = downloadUrlMapRef.current.get(taskId)
    if (url) {
      try {
        URL.revokeObjectURL(url)
      } catch {
        // ignore revoke errors
      }
      downloadUrlMapRef.current.delete(taskId)
    }
  }, [])

  const getDownloadUrl = useCallback(
    (taskId: string) => {
      const existing = downloadUrlMapRef.current.get(taskId)
      if (existing) {
        return existing
      }
      const task = tasksRef.current.find((entry) => entry.id === taskId)
      if (!task || task.result?.type !== 'download') {
        return null
      }
      try {
        const objectUrl = URL.createObjectURL(task.result.blob)
        downloadUrlMapRef.current.set(taskId, objectUrl)
        return objectUrl
      } catch {
        return null
      }
    },
    [],
  )

  const value = useMemo<BackgroundTaskContextValue>(
    () => ({ tasks, startTask, dismissTask, getDownloadUrl }),
    [tasks, startTask, dismissTask, getDownloadUrl],
  )

  return <BackgroundTaskContext.Provider value={value}>{children}</BackgroundTaskContext.Provider>
}

export function useBackgroundTasks(): BackgroundTaskContextValue {
  const context = useContext(BackgroundTaskContext)
  if (!context) {
    throw new Error('useBackgroundTasks must be used within a BackgroundTaskProvider')
  }
  return context
}
