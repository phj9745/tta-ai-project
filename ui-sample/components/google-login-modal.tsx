"use client"

import { Button } from "@/components/ui/button"
import { Check } from "lucide-react"
import Image from "next/image"

export function GoogleLoginModal() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200 p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-12 shadow-2xl">
        <div className="mb-8 flex items-center justify-center">
          <Image src="/testmate-logo.png" alt="TestMate Logo" width={200} height={70} className="object-contain" />
        </div>

        <div className="mb-3 text-center">
          <span className="inline-block rounded-full bg-blue-50 px-4 py-1.5 text-sm font-medium text-blue-600">
            GOOGLE DRIVE 연결
          </span>
        </div>

        <h1 className="mb-4 text-center text-3xl font-bold text-slate-900">먼저 구글 계정으로 로그인하세요</h1>

        <p className="mb-8 text-center text-slate-600">
          프로젝트에서 Google Drive 권한을 사용하려면 Google 계정을 통해 인증을 완료해야 합니다. 아래 버튼을 눌러
          안전하게 로그인하세요.
        </p>

        <div className="mb-8 rounded-xl bg-slate-50 p-8">
          <h2 className="mb-6 text-center text-xl font-semibold text-slate-900">Google 로그인</h2>

          <p className="mb-6 text-center text-sm text-slate-600">
            Google 계정을 인증하면 프로젝트가 아래의 Drive 권한을 요청하여 파일을 읽고, 생성하고, 수정하거나 삭제할 수
            있습니다. 승인된 액세스/인프라치 토큰은 안전하게 백엔드에 저장됩니다.
          </p>

          <div className="mb-6 space-y-3">
            <div className="flex items-start gap-3 text-sm text-slate-700">
              <Check className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-600" />
              <span>Google 프로필 기본 정보 (이름, 이메일)</span>
            </div>
            <div className="flex items-start gap-3 text-sm text-slate-700">
              <Check className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-600" />
              <span>Google Drive 전체 읽기 및 쓰기 권한</span>
            </div>
            <div className="flex items-start gap-3 text-sm text-slate-700">
              <Check className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-600" />
              <span>사용자가 만든 파일 관리 (생성/수정/삭제)</span>
            </div>
          </div>

          <Button size="lg" className="w-full bg-blue-600 text-base font-semibold hover:bg-blue-700">
            Google 계정으로 로그인
          </Button>

          <p className="mt-4 text-center text-xs text-slate-500">
            로그인 버튼을 누르면 Google 인증 화면으로 이동하며, 완료 후에는 계정 이름과 함께 토큰이 안전하게 저장됩니다.
          </p>
        </div>
      </div>
    </div>
  )
}
