export type AsyncStatus = 'idle' | 'loading' | 'success' | 'error'

export interface DefectEntry {
  index: number
  originalText: string
  polishedText: string
}

export type AttachmentMap = Record<number, File[]>

export type ConversationRole = 'user' | 'assistant'

export interface ConversationMessage {
  role: ConversationRole
  text: string
}

export interface DefectReportColumn {
  key: string
  label: string
}

export interface DefectReportTableRow {
  rowNumber: number
  cells: Record<string, string>
}

export interface DefectReportWorkflowProps {
  backendUrl: string
  projectId: string
  onPreviewModeChange?: (isPreviewVisible: boolean) => void
}

export interface SelectedCell {
  rowIndex: number
  columnKey: string
}

export const TXT_ONLY = ['txt'] as const
export const FEATURE_LIST_TYPES = ['xlsx', 'xls', 'csv'] as const

export const ATTACHMENT_ACCEPT = new Set(['image/jpeg', 'image/png'])

export const DEFECT_REPORT_START_ROW = 6

export const DEFECT_REPORT_COLUMNS: DefectReportColumn[] = [
  { key: '순번', label: '순번' },
  { key: '시험환경(OS)', label: '시험환경(OS)' },
  { key: '결함요약', label: '결함요약' },
  { key: '결함정도', label: '결함정도' },
  { key: '발생빈도', label: '발생빈도' },
  { key: '품질특성', label: '품질특성' },
  { key: '결함 설명', label: '결함 설명' },
  { key: '업체 응답', label: '업체 응답' },
  { key: '수정여부', label: '수정여부' },
  { key: '비고', label: '비고' },
]
