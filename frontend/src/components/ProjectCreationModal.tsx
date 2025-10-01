import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'

import { getBackendUrl } from '../config'
import { Modal } from './Modal'
import { FileUploader } from './FileUploader'
import type { FileType } from './fileUploaderTypes'

interface ProjectCreationModalProps {
  open: boolean
  folderId?: string
  onClose: () => void
  onSuccess?: () => void
  backendUrl?: string
}

const PDF_ONLY: FileType[] = ['pdf']

export function ProjectCreationModal({
  open,
  folderId,
  onClose,
  onSuccess,
  backendUrl,
}: ProjectCreationModalProps) {
  const [files, setFiles] = useState<File[]>([])
  const [formError, setFormError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const resolvedBackendUrl = useMemo(() => backendUrl ?? getBackendUrl(), [backendUrl])

  useEffect(() => {
    if (!open) {
      setFiles([])
      setFormError(null)
      setSubmitError(null)
      setIsSubmitting(false)
    }
  }, [open])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError(null)
    setSubmitError(null)

    if (files.length === 0) {
      setFormError('최소 한 개의 PDF 파일을 업로드해주세요.')
      return
    }

    const formData = new FormData()
    if (folderId) {
      formData.append('folder_id', folderId)
    }
    files.forEach((file) => {
      formData.append('files', file)
    })

    setIsSubmitting(true)
    try {
      const response = await fetch(`${resolvedBackendUrl}/drive/projects`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        let detail = '프로젝트 생성에 실패했습니다. 잠시 후 다시 시도해주세요.'
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

      onClose()
      onSuccess?.()
    } catch (error) {
      const fallback =
        error instanceof Error
          ? error.message
          : '프로젝트 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
      setSubmitError(fallback)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={isSubmitting ? () => {} : onClose}
      title="새 프로젝트 생성"
      description="PDF를 업로드하면 'GS-X-X-XXXX' 폴더와 필수 하위 폴더가 자동으로 만들어집니다."
    >
      <form className="modal__form" onSubmit={handleSubmit} aria-busy={isSubmitting}>
        <div className="modal__body">
          <p className="modal__helper-text">
            업로드한 파일은 생성되는 프로젝트의 ‘0. 사전 자료’ 폴더에 저장됩니다.
          </p>

          <FileUploader
            allowedTypes={PDF_ONLY}
            files={files}
            onChange={setFiles}
            hideDropzoneWhenFilled
          />

          {formError && (
            <p className="modal__error" role="alert">
              {formError}
            </p>
          )}
          {submitError && (
            <p className="modal__error" role="alert">
              {submitError}
            </p>
          )}
        </div>

        <footer className="modal__footer">
          <button type="button" className="modal__button" onClick={onClose} disabled={isSubmitting}>
            취소
          </button>
          <button type="submit" className="modal__button modal__button--primary" disabled={isSubmitting}>
            {isSubmitting ? '생성 중…' : '생성'}
          </button>
        </footer>

        {isSubmitting && (
          <div className="modal__loading-overlay" role="status" aria-live="assertive">
            <div className="modal__loading-spinner" aria-hidden="true" />
            <p className="modal__loading-text">프로젝트를 생성하는 중입니다…</p>
          </div>
        )}
      </form>
    </Modal>
  )
}
