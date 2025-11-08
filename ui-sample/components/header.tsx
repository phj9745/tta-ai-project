import Image from "next/image"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

export function Header() {
  return (
    <header className="border-b border-border bg-white/80 backdrop-blur-sm">
      <div className="flex h-16 items-center justify-between px-6">
        <div className="flex items-center">
          <div className="flex h-14 items-center justify-center">
            <Image src="/testmate-logo.png" alt="TestMate Logo" width={180} height={60} className="object-contain" />
          </div>
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
        </div>
      </div>
    </header>
  )
}
