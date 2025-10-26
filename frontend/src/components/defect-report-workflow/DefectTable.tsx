import { useMemo } from 'react'

import { createFileKey } from './utils'
import {
  DEFECT_REPORT_COLUMNS,
  type DefectWorkItem,
} from './types'

const DISPLAY_COLUMN_KEYS = ['결함요약', '결함정도', '발생빈도', '품질특성', '결함 설명'] as const

const DISPLAY_COLUMNS = DEFECT_REPORT_COLUMNS.filter((column) =>
  DISPLAY_COLUMN_KEYS.includes(column.key as (typeof DISPLAY_COLUMN_KEYS)[number]),
)

interface DefectTableProps {
  items: DefectWorkItem[]
  onPolishedChange: (defectIndex: number, value: string) => void
  onAddAttachments: (defectIndex: number, files: FileList | File[]) => void
  onRemoveAttachment: (defectIndex: number, file: File) => void
  onGenerate: (defectIndex: number) => void
  onChatInputChange: (defectIndex: number, value: string) => void
  onChatSubmit: (defectIndex: number) => void
  onResultChange: (defectIndex: number, columnKey: string, value: string) => void
  onComplete: (defectIndex: number) => void
  onResume: (defectIndex: number) => void
}

export function DefectTable({
  items,
  onPolishedChange,
  onAddAttachments,
  onRemoveAttachment,
  onGenerate,
  onChatInputChange,
  onChatSubmit,
  onResultChange,
  onComplete,
  onResume,
}: DefectTableProps) {
  const hasItems = items.length > 0

  const canCompleteMap = useMemo(() => {
    const map = new Map<number, boolean>()
    items.forEach((item) => {
      const hasValue = DISPLAY_COLUMN_KEYS.some((key) => (item.result[key] ?? '').trim().length > 0)
      map.set(item.entry.index, hasValue)
    })
    return map
  }, [items])

  if (!hasItems) {
    return null
  }

  return (
    <section className="defect-workflow__section" aria-labelledby="defect-review">
      <div className="defect-workflow__section-heading">
        <h2 id="defect-review" className="defect-workflow__title">
          2. 결함 검토 및 증적 첨부
        </h2>
      </div>
      <p className="defect-workflow__helper">
        각 결함의 원문과 정제된 문장을 확인하고 증빙 이미지를 첨부한 뒤 “결함 생성”을 눌러 한 줄 요약을 받아보세요. 필요하면 GPT와 대화를 이어가며 결과를 조정한 뒤 완료 처리하세요.
      </p>
      <div className="defect-workflow__card-list">
        {items.map((item, index) => {
          const defectIndex = item.entry.index
          const files = item.attachments
          const canComplete = canCompleteMap.get(defectIndex) ?? false
          const isCollapsed = item.isCollapsed
          const hasGeneratedResult = DISPLAY_COLUMN_KEYS.some(
            (key) => (item.result[key] ?? '').trim().length > 0,
          )
          const shouldShowResult = hasGeneratedResult
          const shouldShowChat = hasGeneratedResult || item.messages.length > 0
          return (
            <article
              key={defectIndex}
              className={`defect-workflow__card${isCollapsed ? ' defect-workflow__card--collapsed' : ''}`}
              aria-expanded={!isCollapsed}
            >
              <header className="defect-workflow__card-header">
                <div className="defect-workflow__card-header-main">
                  <span className="defect-workflow__card-badge">결함 {index + 1}</span>
                  {isCollapsed ? (
                    <p className="defect-workflow__card-name">
                      <span className="defect-workflow__card-name-value">
                        {item.result['결함요약']?.trim() || '생성된 결함 요약이 없습니다.'}
                      </span>
                    </p>
                  ) : (
                    <>
                      <h3 className="defect-workflow__card-title">
                        원문
                      </h3>
                      <p className="defect-workflow__card-subtitle">
                        {item.entry.originalText || '원문 정보가 제공되지 않았습니다.'}
                      </p>
                    </>
                  )}
                </div>
                <div className="defect-workflow__card-meta" aria-live="polite">
                  {isCollapsed ? (
                    <button
                      type="button"
                      className="defect-workflow__secondary defect-workflow__button"
                      onClick={() => onResume(defectIndex)}
                    >
                      수정
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="defect-workflow__secondary defect-workflow__button"
                        onClick={() => onGenerate(defectIndex)}
                        disabled={item.status === 'loading'}
                      >
                        {item.status === 'loading' ? '결함 생성 중…' : '결함 생성'}
                      </button>
                      <button
                        type="button"
                        className="defect-workflow__secondary defect-workflow__button"
                        onClick={() => onComplete(defectIndex)}
                        disabled={!canComplete}
                      >
                        완료
                      </button>
                    </>
                  )}
                </div>
              </header>
              {!isCollapsed && (
                <div className="defect-workflow__card-body">
                  <div className="defect-workflow__card-grid defect-workflow__card-grid--defect">
                    <label className="defect-workflow__scenario-field">
                      <span>정제된 문장</span>
                      <textarea
                        className="defect-workflow__textarea"
                        value={item.entry.polishedText}
                        onChange={(event) => onPolishedChange(defectIndex, event.target.value)}
                      />
                    </label>
                    <div className="defect-workflow__scenario-field defect-workflow__scenario-field--attachments">
                      <div className="defect-workflow__attachment-header">
                        <span>증빙 이미지 (선택)</span>
                        <input
                          type="file"
                          accept="image/png,image/jpeg"
                          multiple
                          onChange={(event) => {
                            if (event.currentTarget.files) {
                              onAddAttachments(defectIndex, event.currentTarget.files)
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
                                className="defect-workflow__remove"
                                onClick={() => onRemoveAttachment(defectIndex, file)}
                              >
                                제거
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>

                  {shouldShowResult && (
                    <div className="defect-workflow__result-fields">
                      <h4 className="defect-workflow__chat-title">생성된 결함 요약</h4>
                      <div className="defect-workflow__result-grid">
                        {DISPLAY_COLUMNS.map((column) => (
                          <label key={column.key} className="defect-workflow__scenario-field">
                            <span>{column.label}</span>
                            <textarea
                              className="defect-workflow__textarea"
                              value={item.result[column.key] ?? ''}
                              onChange={(event) => onResultChange(defectIndex, column.key, event.target.value)}
                            />
                          </label>
                        ))}
                      </div>
                    </div>
                  )}

                  {item.status === 'error' && item.error && (
                    <p className="defect-workflow__status defect-workflow__status--error" role="alert">
                      {item.error}
                    </p>
                  )}
                  {item.status === 'success' && !item.error && (
                    <p className="defect-workflow__status defect-workflow__status--success" role="status">
                      결함 요약을 생성했습니다. 필요한 경우 GPT에게 수정 요청을 보내세요.
                    </p>
                  )}

                  {shouldShowChat && (
                    <div className="defect-workflow__chat">
                      <h4 className="defect-workflow__chat-title">GPT와 결함 요약 다듬기</h4>
                      <p className="defect-workflow__chat-helper">
                        수정이 필요한 방향을 설명하면 현재 결함 정보를 참고해 GPT가 새로운 안을 제안합니다.
                      </p>
                      <div className="defect-workflow__chat-log" role="log" aria-live="polite">
                        {item.messages.length === 0 && (
                          <p className="defect-workflow__chat-helper">아직 대화가 없습니다.</p>
                        )}
                        {item.messages.map((message, messageIndex) => (
                          <div
                            key={`${message.role}-${messageIndex}`}
                            className={`defect-workflow__chat-message defect-workflow__chat-message--${message.role}`}
                          >
                            <span>{message.role === 'user' ? '요청' : 'GPT 응답'}</span>
                            <p>{message.text}</p>
                          </div>
                        ))}
                      </div>
                      {item.inputError && (
                        <p className="defect-workflow__status defect-workflow__status--error" role="alert">
                          {item.inputError}
                        </p>
                      )}
                      <form
                        className="defect-workflow__chat-form"
                        onSubmit={(event) => {
                          event.preventDefault()
                          onChatSubmit(defectIndex)
                        }}
                      >
                        <textarea
                          className="defect-workflow__textarea"
                          value={item.input}
                          onChange={(event) => onChatInputChange(defectIndex, event.target.value)}
                          placeholder="예: 결함 요약을 두 문장으로 줄여줘"
                          disabled={item.status === 'loading'}
                        />
                        <div className="defect-workflow__chat-actions">
                          <button
                            type="submit"
                            className="defect-workflow__button"
                            disabled={item.status === 'loading'}
                          >
                            {item.status === 'loading' ? '요청 중…' : 'GPT에게 수정 요청'}
                          </button>
                        </div>
                      </form>
                    </div>
                  )}
                </div>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}
