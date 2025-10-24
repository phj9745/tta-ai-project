import { createFileKey } from './utils'
import type { AttachmentMap, DefectEntry } from './types'

interface DefectTableProps {
  defects: DefectEntry[]
  attachments: AttachmentMap
  onUpdatePolished: (index: number, value: string) => void
  onAddAttachments: (index: number, files: FileList | File[]) => void
  onRemoveAttachment: (index: number, file: File) => void
  showReset: boolean
  onReset: () => void
  isResetDisabled: boolean
}

export function DefectTable({
  defects,
  attachments,
  onUpdatePolished,
  onAddAttachments,
  onRemoveAttachment,
  showReset,
  onReset,
  isResetDisabled,
}: DefectTableProps) {
  if (defects.length === 0) {
    return null
  }

  return (
    <section className="defect-workflow__section" aria-labelledby="defect-review">
      <div className="defect-workflow__section-heading">
        <h2 id="defect-review" className="defect-workflow__title">
          2. 결함 검토 및 증적 첨부
        </h2>
        {showReset && (
          <div className="defect-workflow__section-actions">
            <button
              type="button"
              className="defect-workflow__secondary"
              onClick={onReset}
              disabled={isResetDisabled}
            >
              초기화
            </button>
          </div>
        )}
      </div>
      <p className="defect-workflow__helper">
        필요 시 문장을 수정하고 결함별 증빙 이미지를 첨부한 뒤 리포트를 생성하세요.
      </p>
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
                onChange={(event) => onUpdatePolished(item.index, event.target.value)}
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
                        onAddAttachments(item.index, event.currentTarget.files)
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
                          onClick={() => onRemoveAttachment(item.index, file)}
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
  )
}
