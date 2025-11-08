"use client"

import { Button } from "@/components/ui/button"
import { X, Upload } from "lucide-react"

interface ProjectCreationModalProps {
  onClose: () => void
}

export function ProjectCreationModal({ onClose }: ProjectCreationModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-8 shadow-2xl">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-2xl font-bold text-slate-900">새 프로젝트 생성</h2>
          <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8 rounded-full hover:bg-slate-100">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <p className="mb-6 text-sm text-slate-600">
          DOCX 또는 PDF를 업로드하면 'GS-X-XX-XXXX' 형식의 필수 항목 추출을 더 기지 자동으로 입력해 줍니다.
        </p>

        <p className="mb-4 text-sm text-slate-700">
          업로드한 파일을 생성하면 프로젝트명 0, 시간 지금 값이어 정형화냅니다.
        </p>

        <div className="mb-6 rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 p-8 transition-colors hover:border-blue-400 hover:bg-blue-50/30">
          <div className="flex flex-col items-center justify-center text-center">
            <Upload className="mb-3 h-10 w-10 text-slate-400" />
            <p className="mb-1 text-sm text-slate-600">파일을 드래그 앤 드롭하거나 클릭해서 선택하세요.</p>
            <p className="text-xs text-slate-400">허용된 형식: DOCX, PDF</p>
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={onClose}>
            취소
          </Button>
          <Button className="bg-blue-600 hover:bg-blue-700">생성</Button>
        </div>
      </div>
    </div>
  )
}
