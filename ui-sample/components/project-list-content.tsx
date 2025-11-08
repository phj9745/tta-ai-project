"use client"

import { Plus, Clock } from "lucide-react"
import { Button } from "@/components/ui/button"

export function ProjectListContent() {
  const projects = [
    {
      id: 1,
      code: "[GS-B-24-0178]",
      client: "주식회사 네오스펙트라",
      name: "SIMMETA Solid Recon V1.0",
      lastModified: "최근 수정 2025. 11. 4. 오전 9:40",
    },
    {
      id: 2,
      code: "[GS-B-24-0194]",
      client: "주식회사에이티지(ATG)",
      name: "A.Eyes C V1.0",
      lastModified: "최근 수정 2025. 11. 4. 오전 11:08",
    },
    {
      id: 3,
      code: "[GS-B-25-0149]",
      client: "주식회사 노아시스템즈",
      name: "Tmanager v1.5",
      lastModified: "최근 수정 2025. 11. 3. 오후 2:40",
    },
    {
      id: 4,
      code: "[GS-B-25-0155]",
      client: "㈜ 지에스디랩",
      name: "EVGUARD SW v1.0",
      lastModified: "최근 수정 2025. 11. 6. 오후 5:08",
    },
    {
      id: 5,
      code: "[GS-B-25-0166]",
      client: "주식회사 아토즈",
      name: "SEMA CMS v1.0",
      lastModified: "최근 수정 2025. 11. 4. 오후 4:12",
    },
  ]

  return (
    <div className="h-full overflow-auto bg-slate-50 p-8">
      <div className="mx-auto max-w-4xl">
        <div className="mb-2">
          <span className="inline-block rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-600">
            GOOGLE DRIVE 프로젝트
          </span>
        </div>

        <h1 className="mb-8 text-3xl font-bold text-slate-900">프로젝트</h1>

        <div className="mb-6 rounded-xl bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100">
              <span className="text-sm font-semibold text-blue-700">박</span>
            </div>
            <div>
              <p className="font-medium text-slate-900">박현준 철산양소프트웨어시험센터</p>
              <p className="text-sm text-slate-500">1022pbj@tta.or.kr</p>
            </div>
          </div>

          <div className="border-t border-slate-100 pt-4">
            <h2 className="mb-3 font-semibold text-slate-900">프로젝트 선택</h2>
            <p className="mb-4 text-sm text-slate-600">사용할 프로젝트를 선택하거나 새 프로젝트를 생성해 주세요.</p>

            <div className="space-y-2">
              {projects.map((project) => (
                <div
                  key={project.id}
                  className="flex cursor-pointer items-center justify-between rounded-lg border border-slate-200 bg-white p-4 transition-all hover:border-blue-300 hover:bg-blue-50/50"
                >
                  <div className="flex-1">
                    <p className="font-medium text-slate-900">
                      {project.code} {project.client} - {project.name}
                    </p>
                    <p className="mt-1 flex items-center gap-1 text-xs text-slate-500">
                      <Clock className="h-3 w-3" />
                      {project.lastModified}
                    </p>
                  </div>
                  <span className="rounded-full bg-red-50 px-3 py-1 text-sm font-medium text-red-600">선택</span>
                </div>
              ))}
            </div>

            <Button
              size="lg"
              variant="outline"
              className="mt-6 w-full border-blue-300 bg-white text-blue-700 hover:bg-blue-50"
            >
              <Plus className="mr-2 h-4 w-4" />새 프로젝트 만들기
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
