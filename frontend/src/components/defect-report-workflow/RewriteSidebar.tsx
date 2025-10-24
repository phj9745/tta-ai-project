import type {
  AsyncStatus,
  ConversationMessage,
  DefectReportColumn,
  DefectReportTableRow,
} from './types'

interface RewriteSidebarProps {
  selectedRow: DefectReportTableRow | null
  selectedColumn: DefectReportColumn | null
  selectedValue: string
  onUpdateValue: (value: string) => void
  rewriteMessages: ConversationMessage[]
  rewriteStatus: AsyncStatus
  rewriteError: string | null
  rewriteInput: string
  onRewriteInputChange: (value: string) => void
  onRewriteSubmit: () => void | Promise<void>
  isGenerating: boolean
  tableHasRows: boolean
}

export function RewriteSidebar({
  selectedRow,
  selectedColumn,
  selectedValue,
  onUpdateValue,
  rewriteMessages,
  rewriteStatus,
  rewriteError,
  rewriteInput,
  onRewriteInputChange,
  onRewriteSubmit,
  isGenerating,
  tableHasRows,
}: RewriteSidebarProps) {
  if (!tableHasRows) {
    return (
      <aside className="defect-workflow__editor defect-workflow__editor--empty">
        <p>
          {isGenerating
            ? '결함 리포트를 생성하는 중입니다. 잠시만 기다려 주세요.'
            : '생성된 리포트 데이터를 불러오지 못했습니다.'}
        </p>
      </aside>
    )
  }

  if (!selectedRow || !selectedColumn) {
    return (
      <aside className="defect-workflow__editor defect-workflow__editor--empty">
        <p>편집할 셀을 선택하면 내용과 GPT 대화창이 표시됩니다.</p>
      </aside>
    )
  }

  return (
    <aside className="defect-workflow__editor" aria-live="polite">
      <div className="defect-workflow__editor-header">
        <h3 className="defect-workflow__editor-title">셀 편집</h3>
        <p className="defect-workflow__editor-subtitle">
          {selectedRow.rowNumber}행 / {selectedColumn.label}
        </p>
      </div>
      <label
        className="defect-workflow__label"
        htmlFor={`cell-editor-${selectedRow.rowNumber}-${selectedColumn.key}`}
      >
        직접 수정
      </label>
      <textarea
        id={`cell-editor-${selectedRow.rowNumber}-${selectedColumn.key}`}
        value={selectedValue}
        onChange={(event) => onUpdateValue(event.target.value)}
      />
      <div className="defect-workflow__chat">
        <h4 className="defect-workflow__chat-title">GPT에게 수정 요청</h4>
        <p className="defect-workflow__chat-helper">
          바꾸고 싶은 방향을 입력하면 GPT 응답이 셀에 바로 반영됩니다.
        </p>
        <div className="defect-workflow__chat-log" role="log" aria-live="polite">
          {rewriteMessages.length === 0 && (
            <p className="defect-workflow__chat-helper">아직 대화가 없습니다.</p>
          )}
          {rewriteMessages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`defect-workflow__chat-message defect-workflow__chat-message--${message.role}`}
            >
              <span>{message.role === 'user' ? '요청' : 'GPT 응답'}</span>
              <p>{message.text}</p>
            </div>
          ))}
        </div>
        {rewriteError && (
          <p className="defect-workflow__status defect-workflow__status--error" role="alert">
            {rewriteError}
          </p>
        )}
        {rewriteStatus === 'success' && !rewriteError && (
          <p className="defect-workflow__status defect-workflow__status--success">
            GPT 응답이 셀에 반영되었습니다.
          </p>
        )}
        <form
          className="defect-workflow__chat-form"
          onSubmit={(event) => {
            event.preventDefault()
            void onRewriteSubmit()
          }}
        >
          <textarea
            value={rewriteInput}
            onChange={(event) => onRewriteInputChange(event.target.value)}
            placeholder="예: 문장을 더 간결하고 정중하게 바꿔줘"
          />
          <button type="submit" className="defect-workflow__primary" disabled={rewriteStatus === 'loading'}>
            {rewriteStatus === 'loading' ? '요청 중…' : 'GPT에게 수정 요청'}
          </button>
        </form>
      </div>
    </aside>
  )
}
