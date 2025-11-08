import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

export function Header() {
  return (
    <header className="border-b border-border bg-white/80 backdrop-blur-sm">
      <div className="flex h-16 items-center justify-between px-6">
        <div className="flex items-center gap-3">
          <div className="group flex h-10 w-10 cursor-pointer items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-blue-400 shadow-sm shadow-blue-500/20 transition-all duration-300 hover:scale-105 hover:shadow-md hover:shadow-blue-500/30">
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              className="transition-transform duration-300 group-hover:rotate-12"
            >
              {/* Simple, iconic checkmark - represents testing/QA approval */}
              <path
                d="M4 12.5L9 17.5L20 6.5"
                stroke="white"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>

          <h1 className="text-xl font-bold tracking-tight text-foreground">TestMate</h1>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            className="gap-2 border-blue-200 bg-blue-50/50 hover:bg-blue-100/80 hover:border-blue-300"
          >
            <span className="text-sm font-medium text-blue-700">작업 현황</span>
            <Badge className="h-5 min-w-[20px] rounded-full bg-blue-600 px-1.5 text-xs font-semibold text-white hover:bg-blue-600">
              0
            </Badge>
          </Button>
          <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground">
            구글 드라이브
          </Button>
          <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground">
            프로젝트 관리자
          </Button>
        </div>
      </div>
    </header>
  )
}
