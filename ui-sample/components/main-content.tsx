"use client"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Upload, FileVideo } from "lucide-react"
import { useState } from "react"

interface MainContentProps {
  sidebarCollapsed?: boolean
}

export function MainContent({ sidebarCollapsed }: MainContentProps) {
  const [isDragging, setIsDragging] = useState(false)

  return (
    <main className="flex-1 overflow-auto bg-gradient-to-br from-blue-50/30 via-white to-blue-50/20">
      <div className="mx-auto max-w-5xl p-8">
        {/* Header Section */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
              형상 관리
            </div>
            <h1 className="mb-2 text-3xl font-bold text-foreground text-balance">형상 이미지 추출</h1>
            <p className="text-sm text-muted-foreground">
              프로그램 기능 시연 동영상을 업로드하면 장면 전환을 감지하여 주요 화면 이미지를 자동으로 추출합니다.
            </p>
          </div>
          <Button variant="outline" className="gap-2 bg-white hover:bg-accent">
            <span>다른 프로젝트 선택</span>
          </Button>
        </div>

        {/* Upload Section */}
        <Card className="border-border bg-white shadow-sm p-8">
          <h2 className="mb-6 text-lg font-semibold text-foreground">필수 문서 업로드</h2>

          <div className="space-y-6">
            <div>
              <label className="mb-3 block text-sm font-medium text-foreground">시연 동영상</label>

              <div
                onDragEnter={() => setIsDragging(true)}
                onDragLeave={() => setIsDragging(false)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault()
                  setIsDragging(false)
                }}
                className={`group relative flex min-h-[280px] cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed transition-all hover:border-primary/50 hover:bg-blue-50/30 ${
                  isDragging ? "border-primary bg-blue-50/50 shadow-inner" : "border-border bg-blue-50/10"
                }`}
              >
                <div className="flex flex-col items-center gap-4 text-center">
                  <div className="rounded-full bg-muted p-4 transition-colors group-hover:bg-primary/10">
                    <Upload className="h-8 w-8 text-muted-foreground transition-colors group-hover:text-primary" />
                  </div>

                  <div className="space-y-2">
                    <p className="text-sm font-medium text-foreground">
                      파일을 드래그 앤 드롭
                      <span className="text-muted-foreground">하거나 </span>
                      <span className="text-primary">클릭해서 선택하세요</span>
                    </p>

                    <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
                      <FileVideo className="h-4 w-4" />
                      <span>허용된 형식: MP4, MOV</span>
                    </div>
                  </div>

                  <Button variant="secondary" size="sm" className="mt-2">
                    파일 선택
                  </Button>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end gap-3 pt-4">
              <Button variant="outline">취소</Button>
              <Button className="gap-2 bg-primary hover:bg-primary/90">
                <Upload className="h-4 w-4" />
                <span>이미지 추출 시작</span>
              </Button>
            </div>
          </div>
        </Card>

        {/* Info Card */}
        <Card className="mt-6 border-blue-200 bg-blue-50/50 p-6 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-foreground">추출 프로세스 안내</h3>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li className="flex gap-2">
              <span className="text-primary">•</span>
              <span>동영상에서 장면 전환이 감지되면 자동으로 스크린샷을 생성합니다</span>
            </li>
            <li className="flex gap-2">
              <span className="text-primary">•</span>
              <span>추출된 이미지는 프로젝트 폴더에 자동 저장됩니다</span>
            </li>
            <li className="flex gap-2">
              <span className="text-primary">•</span>
              <span>AI가 중복 이미지를 자동으로 필터링하여 최적의 결과를 제공합니다</span>
            </li>
          </ul>
        </Card>
      </div>
    </main>
  )
}
