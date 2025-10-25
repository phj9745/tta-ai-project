export type FileType =
  | 'pdf'
  | 'docx'
  | 'xlsx'
  | 'xls'
  | 'txt'
  | 'jpg'
  | 'png'
  | 'csv'
  | 'html'

interface FileTypeInfo {
  label: string
  accept: string[]
  extensions: string[]
}

export const FILE_TYPE_OPTIONS: Record<FileType, FileTypeInfo> = {
  pdf: {
    label: 'PDF',
    accept: ['.pdf', 'application/pdf'],
    extensions: ['pdf'],
  },
  docx: {
    label: 'DOCX',
    accept: [
      '.docx',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ],
    extensions: ['docx'],
  },
  xlsx: {
    label: 'XLSX',
    accept: [
      '.xlsx',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ],
    extensions: ['xlsx'],
  },
  xls: {
    label: 'XLS',
    accept: ['.xls', 'application/vnd.ms-excel'],
    extensions: ['xls'],
  },
  txt: {
    label: 'TXT',
    accept: ['.txt', 'text/plain'],
    extensions: ['txt'],
  },
  jpg: {
    label: 'JPG/JPEG',
    accept: ['.jpg', '.jpeg', 'image/jpeg'],
    extensions: ['jpg', 'jpeg'],
  },
  png: {
    label: 'PNG',
    accept: ['.png', 'image/png'],
    extensions: ['png'],
  },
  csv: {
    label: 'CSV',
    accept: ['.csv', 'text/csv'],
    extensions: ['csv'],
  },
  html: {
    label: 'HTML',
    accept: ['.html', '.htm', 'text/html'],
    extensions: ['html', 'htm'],
  },
}

export const ALL_FILE_TYPES = Object.keys(FILE_TYPE_OPTIONS) as FileType[]
