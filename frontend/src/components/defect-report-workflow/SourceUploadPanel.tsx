import { FileUploader } from '../FileUploader'
import type { FileType } from '../fileUploaderTypes'
import type { AsyncStatus } from './types'
import { TXT_ONLY } from './types'

interface SourceUploadPanelProps {
  sourceFiles: File[]
  status: AsyncStatus
  error: string | null
  onChangeSource: (files: File[]) => void
  onFormalize: () => void | Promise<void>
  showReset: boolean
  onReset: () => void
  isResetDisabled: boolean
}

const TXT_ALLOWED_TYPES = TXT_ONLY as unknown as FileType[]

export function SourceUploadPanel({
  sourceFiles,
  status,
  error,
  onChangeSource,
  onFormalize,
  showReset,
  onReset,
  isResetDisabled,
}: SourceUploadPanelProps) {
  return (
    <section className="defect-workflow__section" aria-labelledby="defect-upload">
      <h2 id="defect-upload" className="defect-workflow__title">
        1. 결함 메모 업로드
      </h2>
      <p className="defect-workflow__helper">숫자 목록(1. 2. …) 형태의 TXT 파일을 업로드한 뒤 결함 문장을 정제하세요.</p>
      <FileUploader
        allowedTypes={TXT_ALLOWED_TYPES}
        files={sourceFiles}
        onChange={onChangeSource}
        multiple={false}
        maxFiles={1}
        hideDropzoneWhenFilled={false}
      />
      <div className="defect-workflow__actions">
        <button
          type="button"
          className="defect-workflow__primary"
          onClick={() => {
            void onFormalize()
          }}
          disabled={status === 'loading'}
        >
          {status === 'loading' ? '정제 중…' : '결함 문장 다듬기'}
        </button>
        {showReset && (
          <button
            type="button"
            className="defect-workflow__secondary"
            onClick={onReset}
            disabled={isResetDisabled}
          >
            초기화
          </button>
        )}
        {status === 'error' && error && (
          <p className="defect-workflow__status defect-workflow__status--error" role="alert">
            {error}
          </p>
        )}
      </div>
    </section>
  )
}
