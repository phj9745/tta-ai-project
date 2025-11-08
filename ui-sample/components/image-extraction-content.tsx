"use client"

import { Upload, FileVideo } from "lucide-react"
import { Button } from "@/components/ui/button"

export function ImageExtractionContent() {
  return (
    <div className="h-full overflow-auto bg-slate-50 p-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-2">
          <span className="inline-block rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-600">형상 관리</span>
        </div>

        <h1 className="mb-3 text-3xl font-bold text-slate-900">형상 이미지 추출</h1>

        <p className="mb-8 text-slate-600">
          프로그램 기능 시연 동영상을 업로드하면 장면 전환을 감지하여 주요 화면 이미지를 자동으로 추출합니다.
        </p>

        <div className="space-y-6">
          <div>
            <h2 className="mb-4 text-lg font-semibold text-slate-900">필수 문서 업로드</h2>

            <div className="rounded-xl bg-white p-6 shadow-sm">
              <h3 className="mb-4 font-medium text-slate-900">시연 동영상</h3>

              <div className="flex min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-8 transition-colors hover:border-blue-400 hover:bg-blue-50/50">
                <FileVideo className="mb-3 h-12 w-12 text-slate-400" />
                <p className="mb-1 text-center text-slate-600">파일을 드래그 앤 드롭하거나 클릭해서 선택하세요.</p>
                <p className="text-sm text-slate-400">허용된 형식: MP4, MOV</p>
              </div>
            </div>
          </div>

          <div>
            <h2 className="mb-4 text-lg font-semibold text-slate-900">추가 파일 업로드 (선택)</h2>

            <div className="rounded-xl bg-white p-6 shadow-sm">
              <div className="flex min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-8 transition-colors hover:border-blue-400 hover:bg-blue-50/50">
                <Upload className="mb-3 h-12 w-12 text-slate-400" />
                <p className="mb-1 text-center text-slate-600">파일을 드래그 앤 드롭하거나 클릭해서 선택하세요.</p>
                <p className="text-sm text-slate-400">허용된 형식: MP4, MOV</p>
              </div>
            </div>
          </div>

          <Button size="lg" className="w-full bg-blue-600 text-base font-medium hover:bg-blue-700 sm:w-auto">
            형상 이미지 추출하기
          </Button>

          <p className="text-sm text-slate-500">
            업로드된 로우는 프로젝트 드라이브에 안전하게 보관되며, 생성된 결과는 팀의 문서와 함께 저장됩니다.
          </p>
        </div>
      </div>
    </div>
  )
}
