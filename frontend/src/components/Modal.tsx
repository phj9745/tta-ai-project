import { useEffect, useId } from 'react'
import type { PropsWithChildren } from 'react'

interface ModalProps extends PropsWithChildren {
  open: boolean
  title: string
  description?: string
  onClose: () => void
}

export function Modal({ open, title, description, onClose, children }: ModalProps) {
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    if (!open) {
      return
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, onClose])

  if (!open) {
    return null
  }

  return (
    <div className="modal" role="presentation">
      <div className="modal__overlay" onClick={onClose} aria-hidden="true" />
      <div
        className="modal__content"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
      >
        <header className="modal__header">
          <h2 className="modal__title" id={titleId}>
            {title}
          </h2>
          {description && (
            <p className="modal__description" id={descriptionId}>
              {description}
            </p>
          )}
        </header>
        {children}
      </div>
    </div>
  )
}
