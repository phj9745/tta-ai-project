"use client"

import { FileText } from "lucide-react"
import { Button } from "@/components/ui/button"

export function SecurityReportContent() {
  return (
    <div className="h-full overflow-auto bg-slate-50 p-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-2">
          <span className="inline-block rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-600">수행</span>
        </div>

        <h1 className="mb-3 text-3xl font-bold text-slate-900">보안성 결함리포트 생성</h1>

        <p className="mb-8 text-slate-600">Invicti 상세 스캔 보고서를 바탕으로 결함리포트를 생성합니다.</p>

        <div className="space-y-6">
          <div className="rounded-xl bg-white p-6 shadow-sm">
            <h3 className="mb-4 font-semibold text-slate-900">1. Invicti 상세 스캔 보고서 업로드</h3>

            <p className="mb-4 text-sm text-slate-600">
              Invicti 상세 스캔 보고서(HTML)를 업로드하면 결과를 분석해 표를 생성합니다. 표는 아래에서 바로 확인과
              수정을 수 있습니다.
            </p>

            <div className="mb-4 flex min-h-[150px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-8 transition-colors hover:border-blue-400 hover:bg-blue-50/50">
              <FileText className="mb-3 h-10 w-10 text-slate-400" />
              <p className="mb-1 text-center text-slate-600">파일을 드래그 앤 드롭하거나 클릭해서 선택하세요.</p>
              <p className="text-sm text-slate-400">허용된 형식: HTML</p>
            </div>

            <Button size="lg" className="bg-blue-600 font-medium hover:bg-blue-700">
              보안성 결함 분석하기
            </Button>
          </div>

          <Button size="lg" variant="outline" className="border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100">
            보안성 결함 저장
          </Button>
        </div>
      </div>
    </div>
  )
}
