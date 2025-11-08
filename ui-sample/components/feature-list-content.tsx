"use client"

import { Upload } from "lucide-react"

export function FeatureListContent() {
  return (
    <div className="h-full overflow-auto bg-slate-50 p-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-2">
          <span className="inline-block rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-600">계획</span>
        </div>

        <h1 className="mb-3 text-3xl font-bold text-slate-900">기능리스트 생성</h1>

        <p className="mb-8 text-slate-600">사용자 매뉴얼 및 요구사항 명세 문서를 분석해 기능 리스트를 생성합니다.</p>

        <div className="space-y-6">
          <div>
            <h2 className="mb-4 text-lg font-semibold text-slate-900">필수 문서 업로드</h2>

            <div className="space-y-4">
              <div className="rounded-xl bg-white p-6 shadow-sm">
                <h3 className="mb-4 font-medium text-slate-900">사용자 매뉴얼</h3>

                <div className="flex min-h-[150px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-6 transition-colors hover:border-blue-400 hover:bg-blue-50/50">
                  <Upload className="mb-2 h-10 w-10 text-slate-400" />
                  <p className="mb-1 text-center text-sm text-slate-600">
                    파일을 드래그 앤 드롭하거나 클릭해서 선택하세요.
                  </p>
                  <p className="text-xs text-slate-400">허용된 형식: PDF, DOCX, XLSX</p>
                </div>
              </div>

              <div className="rounded-xl bg-white p-6 shadow-sm">
                <h3 className="mb-4 font-medium text-slate-900">형상 이미지 (선택)</h3>

                <div className="flex min-h-[150px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-6 transition-colors hover:border-blue-400 hover:bg-blue-50/50">
                  <Upload className="mb-2 h-10 w-10 text-slate-400" />
                  <p className="mb-1 text-center text-sm text-slate-600">
                    파일을 드래그 앤 드롭하거나 클릭해서 선택하세요.
                  </p>
                  <p className="text-xs text-slate-400">허용된 형식: PNG, JPG/JPEG</p>
                </div>
              </div>

              <div className="rounded-xl bg-white p-6 shadow-sm">
                <h3 className="mb-4 font-medium text-slate-900">기능리스트 (선택)</h3>

                <div className="flex min-h-[150px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-6 transition-colors hover:border-blue-400 hover:bg-blue-50/50">
                  <Upload className="mb-2 h-10 w-10 text-slate-400" />
                  <p className="mb-1 text-center text-sm text-slate-600">
                    파일을 드래그 앤 드롭하거나 클릭해서 선택하세요.
                  </p>
                  <p className="text-xs text-slate-400">허용된 형식: PDF, DOCX, XLSX</p>
                </div>
              </div>
            </div>
          </div>

          <div>
            <h2 className="mb-4 text-lg font-semibold text-slate-900">추가 파일 업로드 (선택)</h2>

            <div className="rounded-xl bg-white p-6 shadow-sm">
              <div className="flex min-h-[150px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-6 transition-colors hover:border-blue-400 hover:bg-blue-50/50">
                <Upload className="mb-2 h-10 w-10 text-slate-400" />
                <p className="mb-1 text-center text-sm text-slate-600">
                  파일을 드래그 앤 드롭하거나 클릭해서 선택하세요.
                </p>
                <p className="text-xs text-slate-400">허용된 형식: PDF, DOCX, XLSX</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
