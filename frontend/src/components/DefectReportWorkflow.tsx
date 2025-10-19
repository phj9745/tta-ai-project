import { useCallback, useEffect, useState } from 'react'

import { FileUploader } from './FileUploader'
import type { FileType } from './fileUploaderTypes'

interface DefectEntry {
  index: number
  originalText: string
  polishedText: string
}

interface DefectReportWorkflowProps {
  backendUrl: string
  projectId: string
}

type AsyncStatus = 'idle' | 'loading' | 'success' | 'error'

type AttachmentMap = Record<number, File[]>

const TXT_ONLY: FileType[] = ['txt']
const ATTACHMENT_ACCEPT = new Set(['image/jpeg', 'image/png'])

function sanitizeFileName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}

function buildAttachmentFileName(index: number, original: string): string {
  const safeOriginal = sanitizeFileName(original)
  const padded = index.toString().padStart(2, '0')
  return `defect-${padded}-${safeOriginal}`
}

function createFileKey(file: File): string {
  return `${file.name}-${file.size}-${file.lastModified}`
}

export function DefectReportWorkflow({ backendUrl, projectId }: DefectReportWorkflowProps) {
  const [sourceFiles, setSourceFiles] = useState<File[]>([])
  const [formalizeStatus, setFormalizeStatus] = useState<AsyncStatus>('idle')
  const [formalizeError, setFormalizeError] = useState<string | null>(null)
  const [defects, setDefects] = useState<DefectEntry[]>([])
  const [attachments, setAttachments] = useState<AttachmentMap>({})
  const [generateStatus, setGenerateStatus] = useState<AsyncStatus>('idle')
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [downloadName, setDownloadName] = useState<string | null>(null)

  useEffect(() => {
    return () => {
      if (downloadUrl) {
        URL.revokeObjectURL(downloadUrl)
      }
    }
  }, [downloadUrl])

  const handleChangeSource = useCallback((files: File[]) => {
    setSourceFiles(files.slice(0, 1))
    setFormalizeStatus('idle')
    setFormalizeError(null)
  }, [])

  const handleFormalize = useCallback(async () => {
    if (sourceFiles.length === 0) {
      setFormalizeStatus('error')
      setFormalizeError('TXT 파일을 업로드해 주세요.')
      return
    }

    const formData = new FormData()
    formData.append('file', sourceFiles[0])

    setFormalizeStatus('loading')
    setFormalizeError(null)
    setGenerateStatus('idle')
    setGenerateError(null)
    setDownloadName(null)
    if (downloadUrl) {
      URL.revokeObjectURL(downloadUrl)
      setDownloadUrl(null)
    }

    try {
      const response = await fetch(
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/defect-report/formalize`,
        {
          method: 'POST',
          body: formData,
        },
      )

      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        const detail = payload && typeof payload.detail === 'string' ? payload.detail : '결함 문장을 정제하는 중 오류가 발생했습니다.'
        setFormalizeStatus('error')
        setFormalizeError(detail)
        return
      }

      const payload = (await response.json()) as { defects?: Array<{ index: number; originalText: string; polishedText: string }> }
      const items = Array.isArray(payload?.defects) ? payload.defects : []
      if (items.length === 0) {
        setFormalizeStatus('error')
        setFormalizeError('결함 문장을 찾을 수 없습니다. TXT 파일의 형식을 확인해 주세요.')
        return
      }

      const sorted = [...items]
        .filter((item) => typeof item.index === 'number' && typeof item.polishedText === 'string')
        .sort((a, b) => a.index - b.index)
        .map((item) => ({
          index: item.index,
          originalText: item.originalText ?? '',
          polishedText: item.polishedText,
        }))

      setDefects(sorted)
      setAttachments({})
      setFormalizeStatus('success')
    } catch (error) {
      console.error('Failed to formalize defects', error)
      setFormalizeStatus('error')
      setFormalizeError('결함 문장을 정제하는 중 예기치 않은 오류가 발생했습니다.')
    }
  }, [backendUrl, downloadUrl, projectId, sourceFiles])

  const handleUpdatePolished = useCallback((index: number, value: string) => {
    setDefects((prev) => prev.map((item) => (item.index === index ? { ...item, polishedText: value } : item)))
  }, [])

  const handleAddAttachments = useCallback((index: number, files: FileList | File[]) => {
    const list = Array.from(files)
    if (list.length === 0) {
      return
    }

    const filtered = list.filter((file) => {
      if (file.type && ATTACHMENT_ACCEPT.has(file.type.toLowerCase())) {
        return true
      }
      const ext = file.name.split('.').pop()?.toLowerCase()
      return ext === 'png' || ext === 'jpg' || ext === 'jpeg'
    })

    if (filtered.length === 0) {
      return
    }

    setAttachments((prev) => {
      const existing = prev[index] ?? []
      const existingKeys = new Set(existing.map(createFileKey))
      const next = [...existing]
      filtered.forEach((file) => {
        const key = createFileKey(file)
        if (!existingKeys.has(key)) {
          next.push(file)
          existingKeys.add(key)
        }
      })
      return { ...prev, [index]: next }
    })
  }, [])

  const handleRemoveAttachment = useCallback((index: number, target: File) => {
    setAttachments((prev) => {
      const existing = prev[index]
      if (!existing) {
        return prev
      }
      const next = existing.filter((file) => file !== target)
      const nextMap: AttachmentMap = { ...prev }
      if (next.length === 0) {
        delete nextMap[index]
      } else {
        nextMap[index] = next
      }
      return nextMap
    })
  }, [])

  const handleReset = useCallback(() => {
    setSourceFiles([])
    setFormalizeStatus('idle')
    setFormalizeError(null)
    setDefects([])
    setAttachments({})
    setGenerateStatus('idle')
    setGenerateError(null)
    setDownloadName(null)
    if (downloadUrl) {
      URL.revokeObjectURL(downloadUrl)
      setDownloadUrl(null)
    }
  }, [downloadUrl])

  const canGenerate = defects.length > 0 && formalizeStatus === 'success'

  const handleGenerate = useCallback(async () => {
    if (!canGenerate) {
      setGenerateStatus('error')
      setGenerateError('먼저 결함 문장을 정제해 주세요.')
      return
    }

    setGenerateStatus('loading')
    setGenerateError(null)
    if (downloadUrl) {
      URL.revokeObjectURL(downloadUrl)
      setDownloadUrl(null)
    }

    const summary = {
      defects: defects.map((item) => ({
        index: item.index,
        originalText: item.originalText,
        polishedText: item.polishedText,
        attachments: (attachments[item.index] ?? []).map((file) => ({
          fileName: buildAttachmentFileName(item.index, file.name),
          originalFileName: file.name,
        })),
      })),
    }

    const formData = new FormData()
    formData.append('menu_id', 'defect-report')

    const summaryFile = new File([JSON.stringify(summary, null, 2)], '정제된-결함-목록.json', {
      type: 'application/json',
    })
    const metadataEntries: Array<Record<string, unknown>> = [
      {
        role: 'additional',
        description: '정제된 결함 목록',
        label: '정제된 결함 목록',
        notes: '결함 문장 정제 결과(JSON)',
      },
    ]
    formData.append('files', summaryFile)

    defects.forEach((item) => {
      const files = attachments[item.index] ?? []
      files.forEach((file) => {
        const normalizedName = buildAttachmentFileName(item.index, file.name)
        const renamed = file.name === normalizedName ? file : new File([file], normalizedName, { type: file.type })
        formData.append('files', renamed)
        metadataEntries.push({
          role: 'additional',
          description: `결함 ${item.index} 이미지`,
          label: `결함 ${item.index} 이미지`,
          notes: `원본 파일명: ${file.name}`,
          defect_index: item.index,
        })
      })
    })

    formData.append('file_metadata', JSON.stringify(metadataEntries))

    try {
      const response = await fetch(
        `${backendUrl}/drive/projects/${encodeURIComponent(projectId)}/generate`,
        {
          method: 'POST',
          body: formData,
        },
      )

      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        const detail = payload && typeof payload.detail === 'string' ? payload.detail : '결함 리포트를 생성하는 중 오류가 발생했습니다.'
        setGenerateStatus('error')
        setGenerateError(detail)
        return
      }

      const blob = await response.blob()
      const disposition = response.headers.get('content-disposition')
      let filename = 'defect-report.xlsx'
      if (disposition) {
        const match = disposition.match(/filename\*?=([^;]+)/i)
        if (match) {
          const value = match[1].replace(/^UTF-8''/i, '')
          try {
            filename = decodeURIComponent(value.replace(/"/g, ''))
          } catch {
            filename = value.replace(/"/g, '')
          }
        }
      }

      const objectUrl = URL.createObjectURL(blob)
      setDownloadUrl(objectUrl)
      setDownloadName(filename)
      setGenerateStatus('success')
    } catch (error) {
      console.error('Failed to generate defect report', error)
      setGenerateStatus('error')
      setGenerateError('결함 리포트를 생성하는 중 예기치 않은 오류가 발생했습니다.')
    }
  }, [attachments, backendUrl, canGenerate, defects, downloadUrl, projectId])

  return (
    <div className="defect-workflow">
      <section className="defect-workflow__section" aria-labelledby="defect-upload">
        <h2 id="defect-upload" className="defect-workflow__title">
          1. 결함 메모 업로드
        </h2>
        <p className="defect-workflow__helper">숫자 목록(1. 2. …) 형태의 TXT 파일을 업로드한 뒤 결함 문장을 정제하세요.</p>
        <FileUploader
          allowedTypes={TXT_ONLY}
          files={sourceFiles}
          onChange={handleChangeSource}
          multiple={false}
          maxFiles={1}
          hideDropzoneWhenFilled={false}
        />
        <div className="defect-workflow__actions">
          <button
            type="button"
            className="defect-workflow__primary"
            onClick={handleFormalize}
            disabled={formalizeStatus === 'loading'}
          >
            {formalizeStatus === 'loading' ? '정제 중…' : '결함 문장 다듬기'}
          </button>
          {formalizeStatus === 'error' && formalizeError && (
            <p className="defect-workflow__status defect-workflow__status--error" role="alert">
              {formalizeError}
            </p>
          )}
          {formalizeStatus === 'success' && (
            <p className="defect-workflow__status defect-workflow__status--success">결함 문장이 정제되었습니다.</p>
          )}
        </div>
      </section>

      {defects.length > 0 && (
        <section className="defect-workflow__section" aria-labelledby="defect-review">
          <h2 id="defect-review" className="defect-workflow__title">
            2. 결함 검토 및 증적 첨부
          </h2>
          <p className="defect-workflow__helper">필요 시 문장을 수정하고 결함별 증빙 이미지를 첨부한 뒤 리포트를 생성하세요.</p>
          <ol className="defect-workflow__list">
            {defects.map((item) => {
              const files = attachments[item.index] ?? []
              return (
                <li key={item.index} className="defect-workflow__item">
                  <header className="defect-workflow__item-header">
                    <span className="defect-workflow__badge">#{item.index}</span>
                    <span className="defect-workflow__label">원문</span>
                    <p className="defect-workflow__original">{item.originalText || '원문 정보 없음'}</p>
                  </header>
                  <label className="defect-workflow__label" htmlFor={`polished-${item.index}`}>
                    정제된 문장
                  </label>
                  <textarea
                    id={`polished-${item.index}`}
                    value={item.polishedText}
                    onChange={(event) => handleUpdatePolished(item.index, event.target.value)}
                  />
                  <div className="defect-workflow__attachments">
                    <div className="defect-workflow__attachment-header">
                      <span>증빙 이미지 (선택)</span>
                      <input
                        type="file"
                        accept="image/png,image/jpeg"
                        multiple
                        onChange={(event) => {
                          if (event.currentTarget.files) {
                            handleAddAttachments(item.index, event.currentTarget.files)
                            event.currentTarget.value = ''
                          }
                        }}
                      />
                    </div>
                    {files.length > 0 && (
                      <ul className="defect-workflow__attachment-list">
                        {files.map((file) => (
                          <li key={createFileKey(file)} className="defect-workflow__attachment-item">
                            <span>{file.name}</span>
                            <button
                              type="button"
                              onClick={() => handleRemoveAttachment(item.index, file)}
                              className="defect-workflow__remove"
                            >
                              제거
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </li>
              )
            })}
          </ol>
        </section>
      )}

      <div className="defect-workflow__footer">
        <div className="defect-workflow__buttons">
          <button
            type="button"
            className="defect-workflow__primary"
            onClick={handleGenerate}
            disabled={!canGenerate || generateStatus === 'loading'}
          >
            {generateStatus === 'loading' ? '리포트 생성 중…' : '결함 리포트 생성'}
          </button>
          <button type="button" className="defect-workflow__secondary" onClick={handleReset}>
            초기화
          </button>
        </div>

        {generateStatus === 'error' && generateError && (
          <p className="defect-workflow__status defect-workflow__status--error" role="alert">
            {generateError}
          </p>
        )}

        {generateStatus === 'success' && downloadUrl && (
          <div className="defect-workflow__result">
            <a className="defect-workflow__primary" href={downloadUrl} download={downloadName ?? undefined}>
              결함 리포트 다운로드
            </a>
            <p className="defect-workflow__helper defect-workflow__helper--small">
              생성된 리포트는 프로젝트 드라이브의 결함 리포트 템플릿에도 반영되었습니다.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
