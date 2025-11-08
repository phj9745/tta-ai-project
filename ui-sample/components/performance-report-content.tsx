"use client"

import { Upload } from "lucide-react"
import { Button } from "@/components/ui/button"

export function PerformanceReportContent() {
  return (
    <div className="h-full overflow-auto bg-slate-50 p-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-2">
          <span className="inline-block rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-600">수행</span>
        </div>

        <h1 className="mb-3 text-3xl font-bold text-slate-900">성능시험 리포트 생성</h1>

        <p className="mb-8 text-slate-600">성능 모니터링 데이터를 바탕으로 성능시험 리포트를 생성합니다.</p>

        <div className="space-y-6">
          <div>
            <h2 className="mb-4 text-lg font-semibold text-slate-900">자료 업로드</h2>

            <div className="rounded-xl bg-white p-6 shadow-sm">
              <p className="mb-4 text-sm text-slate-600">
                Windows 성능 모니터 및 Linux vmstat 성능 측정 rawdata를 여러 개 업로드할 수 있습니다.
              </p>

              <div className="mb-6 flex min-h-[180px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-8 transition-colors hover:border-blue-400 hover:bg-blue-50/50">
                <Upload className="mb-3 h-10 w-10 text-slate-400" />
                <p className="mb-1 text-center text-slate-600">파일을 드래그 앤 드롭하거나 클릭해서 선택하세요.</p>
                <p className="text-sm text-slate-400">허용된 형식: CSV, TXT</p>
              </div>

              <Button size="lg" className="bg-blue-600 font-medium hover:bg-blue-700">
                성능시험 리포트 생성하기
              </Button>

              <p className="mt-4 text-sm text-slate-500">
                업로드된 로우는 프로젝트 드라이브에 안전하게 보관되며, 생성된 결과는 팀의 문서와 함께 저장됩니다.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
