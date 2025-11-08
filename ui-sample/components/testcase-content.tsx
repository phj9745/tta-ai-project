"use client"

import { Upload } from "lucide-react"

export function TestcaseContent() {
  return (
    <div className="h-full overflow-auto bg-slate-50 p-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-2">
          <span className="inline-block rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-600">생성</span>
        </div>

        <h1 className="mb-3 text-3xl font-bold text-slate-900">테스트케이스 생성</h1>

        <p className="mb-8 text-slate-600">
          기능리스트를 바탕으로 테스트 시나리오와 기대 결과를 정리한 테스트케이스 조항을 생성합니다.
        </p>

        <div className="space-y-6">
          <div className="rounded-xl bg-white p-6 shadow-sm">
            <h3 className="mb-4 font-semibold text-slate-900">기능리스트 불러오기</h3>

            <p className="mb-4 text-sm text-slate-600">
              테스트케이스 작성할 기능리스트 파일을 업로드하세요. 대/중/소분류 정보를 활용합니다.
            </p>

            <div className="flex min-h-[180px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-8 transition-colors hover:border-blue-400 hover:bg-blue-50/50">
              <Upload className="mb-3 h-10 w-10 text-slate-400" />
              <p className="mb-1 text-center text-slate-600">파일을 드래그 앤 드롭하거나 클릭해서 선택하세요.</p>
              <p className="text-sm text-slate-400">허용된 형식: XLSX, XLS, CSV</p>
            </div>
          </div>

          <p className="text-sm text-slate-500">
            XLSX, XLS 또는 CSV 형식의 기능리스트를 드래그 앤 드롭하세요. 업로드된 내용은 자동분류를 분류합니다.
          </p>
        </div>
      </div>
    </div>
  )
}
