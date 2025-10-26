import { FileUploader } from '../FileUploader'
import type { FileType } from '../fileUploaderTypes'
import type { AsyncStatus } from './types'
import { FEATURE_LIST_TYPES, TXT_ONLY } from './types'

interface SourceUploadPanelProps {
  featureFiles: File[]
  sourceFiles: File[]
  status: AsyncStatus
  error: string | null
  onChangeFeature: (files: File[]) => void
  onChangeSource: (files: File[]) => void
  onFormalize: () => void | Promise<void>
  showReset: boolean
  onReset: () => void
  isResetDisabled: boolean
}

const TXT_ALLOWED_TYPES = TXT_ONLY as unknown as FileType[]
const FEATURE_ALLOWED_TYPES = FEATURE_LIST_TYPES as unknown as FileType[]

export function SourceUploadPanel({
  featureFiles,
  sourceFiles,
  status,
  error,
  onChangeFeature,
  onChangeSource,
  onFormalize,
  showReset,
  onReset,
  isResetDisabled,
}: SourceUploadPanelProps) {
  return (
    <section className="defect-workflow__section" aria-labelledby="defect-upload">
      <h2 id="defect-upload" className="defect-workflow__title">
        1. 기능리스트 및 결함 메모 업로드
      </h2>
      <div className="defect-workflow__upload-group">
        <div className="defect-workflow__upload-block">
          <h3 className="defect-workflow__subtitle">기능리스트 업로드</h3>
          <p className="defect-workflow__helper">
            XLSX 또는 CSV 형식의 기능리스트를 업로드하면 프로그램 맥락을 이해한 뒤 결함 문장을 다듬습니다.
          </p>
          <FileUploader
            allowedTypes={FEATURE_ALLOWED_TYPES}
            files={featureFiles}
            onChange={onChangeFeature}
            multiple={false}
            maxFiles={1}
            hideDropzoneWhenFilled={false}
          />
        </div>
        <div className="defect-workflow__upload-block">
          <h3 className="defect-workflow__subtitle">결함 메모 업로드</h3>
          <p className="defect-workflow__helper">숫자 목록(1. 2. …) 형태의 TXT 파일을 업로드한 뒤 결함 문장을 정제하세요.</p>
          <FileUploader
            allowedTypes={TXT_ALLOWED_TYPES}
            files={sourceFiles}
            onChange={onChangeSource}
            multiple={false}
            maxFiles={1}
            hideDropzoneWhenFilled={false}
          />
        </div>
      </div>
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
