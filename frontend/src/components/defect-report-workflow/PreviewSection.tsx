import type { RefObject } from 'react'

import { RewriteSidebar } from './RewriteSidebar'
import type {
  AsyncStatus,
  ConversationMessage,
  DefectReportColumn,
  DefectReportTableRow,
  SelectedCell,
} from './types'

interface PreviewSectionProps {
  columns: DefectReportColumn[]
  tableRows: DefectReportTableRow[]
  selectedCell: SelectedCell | null
  onSelectCell: (rowIndex: number, columnKey: string) => void
  selectedRow: DefectReportTableRow | null
  selectedColumn: DefectReportColumn | null
  selectedValue: string
  onUpdateSelectedValue: (value: string) => void
  rewriteMessages: ConversationMessage[]
  rewriteStatus: AsyncStatus
  rewriteError: string | null
  rewriteInput: string
  onRewriteInputChange: (value: string) => void
  onRewriteSubmit: () => void | Promise<void>
  isGenerating: boolean
  showReset: boolean
  onReset: () => void
  isResetDisabled: boolean
  sectionRef: RefObject<HTMLElement | null>
}

export function PreviewSection({
  columns,
  tableRows,
  selectedCell,
  onSelectCell,
  selectedRow,
  selectedColumn,
  selectedValue,
  onUpdateSelectedValue,
  rewriteMessages,
  rewriteStatus,
  rewriteError,
  rewriteInput,
  onRewriteInputChange,
  onRewriteSubmit,
  isGenerating,
  showReset,
  onReset,
  isResetDisabled,
  sectionRef,
}: PreviewSectionProps) {
  const tableHasRows = tableRows.length > 0

  return (
    <section className="defect-workflow__section" aria-labelledby="defect-preview" ref={sectionRef}>
      <div className="defect-workflow__section-heading">
        <h2 id="defect-preview" className="defect-workflow__title">
          3. 결함 리포트 미리보기 및 편집
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
        생성된 표를 확인하고 수정할 칸을 선택하세요. 오른쪽 패널에서 직접 편집하거나 GPT에게 수정 요청을 보낼 수 있습니다.
      </p>
      <div className="defect-workflow__preview">
        <div className="defect-workflow__table-wrapper" role="region" aria-live="polite">
          <table className="defect-workflow__table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column.key} scope="col">
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.length === 0 ? (
                <tr>
                  <td colSpan={columns.length}>
                    <div className="defect-workflow__loading" role="status">
                      {isGenerating
                        ? '결함 리포트를 생성하는 중입니다…'
                        : '생성된 리포트 데이터를 불러오지 못했습니다.'}
                    </div>
                  </td>
                </tr>
              ) : (
                tableRows.map((row, rowIndex) => (
                  <tr key={row.rowNumber}>
                    {columns.map((column) => {
                      const value = row.cells[column.key]
                      const isSelected =
                        selectedCell?.rowIndex === rowIndex && selectedCell.columnKey === column.key
                      return (
                        <td key={column.key}>
                          <button
                            type="button"
                            className={`defect-workflow__cell-button${
                              isSelected ? ' defect-workflow__cell-button--selected' : ''
                            }`}
                            onClick={() => onSelectCell(rowIndex, column.key)}
                          >
                            {value ? <span>{value}</span> : <span className="defect-workflow__cell-placeholder">내용 없음</span>}
                          </button>
                        </td>
                      )
                    })}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <RewriteSidebar
          selectedRow={selectedRow}
          selectedColumn={selectedColumn}
          selectedValue={selectedValue}
          onUpdateValue={onUpdateSelectedValue}
          rewriteMessages={rewriteMessages}
          rewriteStatus={rewriteStatus}
          rewriteError={rewriteError}
          rewriteInput={rewriteInput}
          onRewriteInputChange={onRewriteInputChange}
          onRewriteSubmit={onRewriteSubmit}
          isGenerating={isGenerating}
          tableHasRows={tableHasRows}
        />
      </div>
    </section>
  )
}
