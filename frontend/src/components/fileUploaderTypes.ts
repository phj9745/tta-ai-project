export type FileType = 'pdf' | 'txt' | 'jpg' | 'csv' | 'html'

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
  txt: {
    label: 'TXT',
    accept: ['.txt', 'text/plain'],
    extensions: ['txt'],
  },
  jpg: {
    label: 'JPG',
    accept: ['.jpg', '.jpeg', 'image/jpeg'],
    extensions: ['jpg', 'jpeg'],
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
