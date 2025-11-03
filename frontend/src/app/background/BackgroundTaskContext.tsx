import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react'

export type BackgroundTaskStatus = 'running' | 'succeeded' | 'failed' | 'cancelled'

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
  signal: AbortSignal
  update: (message: string | null) => void
  complete: (result: BackgroundTaskResult, message?: string | null) => void
  fail: (errorMessage: string | null) => void
  onCancel: (callback: () => void) => () => void
}

interface BackgroundTaskContextValue {
  tasks: BackgroundTask[]
  startTask: (menuId: string, label: string) => BackgroundTaskHandle
  cancelTask: (taskId: string) => void
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
  const cancelCallbacksRef = useRef<Map<string, Set<() => void>>>(new Map())
  const abortControllerRef = useRef<Map<string, AbortController>>(new Map())

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
      cancelCallbacksRef.current.clear()
      abortControllerRef.current.clear()
    }
  }, [])

  const cleanupTaskResources = useCallback((taskId: string) => {
    cancelCallbacksRef.current.delete(taskId)
    abortControllerRef.current.delete(taskId)
  }, [])

  const startTask = useCallback(
    (menuId: string, label: string): BackgroundTaskHandle => {
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

      const abortController = new AbortController()
      abortControllerRef.current.set(id, abortController)
      cancelCallbacksRef.current.set(id, new Set())

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
        signal: abortController.signal,
        update(message) {
          updateTask({ message })
        },
        complete(result, message = null) {
          if (abortController.signal.aborted) {
            cleanupTaskResources(id)
            return
          }
          updateTask({ status: 'succeeded', result, message, errorMessage: null })
          cleanupTaskResources(id)
        },
        fail(errorMessage) {
          if (abortController.signal.aborted) {
            cleanupTaskResources(id)
            return
          }
          updateTask({ status: 'failed', errorMessage, message: null })
          cleanupTaskResources(id)
        },
        onCancel(callback) {
          const callbacks = cancelCallbacksRef.current.get(id)
          if (!callbacks) {
            return () => {}
          }
          callbacks.add(callback)
          return () => {
            callbacks.delete(callback)
          }
        },
      }
    },
    [cleanupTaskResources],
  )

  const dismissTask = useCallback(
    (taskId: string) => {
      cleanupTaskResources(taskId)
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
    },
    [cleanupTaskResources],
  )

  const cancelTask = useCallback(
    (taskId: string) => {
      const task = tasksRef.current.find((entry) => entry.id === taskId)
      if (!task || task.status !== 'running') {
        dismissTask(taskId)
        return
      }

      setTasks((prev) =>
        prev.map((entry) =>
          entry.id === taskId
            ? {
                ...entry,
                status: 'cancelled',
                message: '사용자에 의해 작업이 중단되었습니다.',
                errorMessage: null,
                updatedAt: Date.now(),
              }
            : entry,
        ),
      )

      const controller = abortControllerRef.current.get(taskId)
      if (controller && !controller.signal.aborted) {
        controller.abort()
      }

      const callbacks = cancelCallbacksRef.current.get(taskId)
      if (callbacks) {
        callbacks.forEach((callback) => {
          try {
            callback()
          } catch {
            // ignore callback errors
          }
        })
      }

      cleanupTaskResources(taskId)
    },
    [cleanupTaskResources, dismissTask],
  )

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
    () => ({ tasks, startTask, cancelTask, dismissTask, getDownloadUrl }),
    [tasks, startTask, cancelTask, dismissTask, getDownloadUrl],
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
