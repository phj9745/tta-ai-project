"use client"

import { Upload, Download } from "lucide-react"
import { Button } from "@/components/ui/button"

export function DefectReportContent() {
  return (
    <div className="h-full overflow-auto bg-slate-50 p-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-2">
          <span className="inline-block rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-600">수행</span>
        </div>

        <h1 className="mb-3 text-3xl font-bold text-slate-900">결함리포트 생성</h1>

        <p className="mb-8 text-slate-600">기능리스트와 결함 메모를 바탕으로 결함 리포트 조항을 생성합니다.</p>

        <div className="space-y-6">
          <div className="rounded-xl bg-white p-6 shadow-sm">
            <h3 className="mb-4 font-semibold text-slate-900">1. 기능리스트 및 결함 메모 업로드</h3>

            <div className="mb-6 space-y-4">
              <div>
                <h4 className="mb-2 text-sm font-medium text-slate-700">기능리스트 업로드</h4>
                <p className="mb-3 text-sm text-slate-600">
                  XLSX, XLS 또는 CSV 형식의 기능리스트를 업로드하세요. 프로젝트 목록을 이용해 표를 분석합니다.
                </p>
                <div className="flex min-h-[130px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-6 transition-colors hover:border-blue-400 hover:bg-blue-50/50">
                  <Upload className="mb-2 h-8 w-8 text-slate-400" />
                  <p className="mb-1 text-center text-sm text-slate-600">
                    파일을 드래그 앤 드롭하거나 클릭해서 선택하세요.
                  </p>
                  <p className="text-xs text-slate-400">허용된 형식: XLSX, XLS, CSV</p>
                </div>
              </div>

              <div>
                <h4 className="mb-2 text-sm font-medium text-slate-700">결함 메모 업로드</h4>
                <p className="mb-3 text-sm text-slate-600">
                  숙자 톡쟁이(1...3) TXT 파일을 업로드하세요. 각 결함 문항을 경계로 잡아 표를 분석합니다.
                </p>
                <div className="flex min-h-[130px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-6 transition-colors hover:border-blue-400 hover:bg-blue-50/50">
                  <Upload className="mb-2 h-8 w-8 text-slate-400" />
                  <p className="mb-1 text-center text-sm text-slate-600">
                    파일을 드래그 앤 드롭하거나 클릭해서 선택하세요.
                  </p>
                  <p className="text-xs text-slate-400">허용된 형식: TXT</p>
                </div>
              </div>
            </div>

            <Button
              size="lg"
              variant="outline"
              className="mb-4 border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"
            >
              <Download className="mr-2 h-4 w-4" />
              결함 문서 다운로드
            </Button>
          </div>

          <Button size="lg" variant="outline" className="border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100">
            결함리포트 생성
          </Button>
        </div>
      </div>
    </div>
  )
}
