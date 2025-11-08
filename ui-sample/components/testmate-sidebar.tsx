"use client"

import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import {
  ImageIcon,
  FileText,
  TestTube,
  CheckCircle2,
  ChevronRight,
  PanelLeftClose,
  PanelLeft,
  Settings,
  Shield,
  Gauge,
} from "lucide-react"

const menuItems = [
  {
    id: "image-extract",
    icon: ImageIcon,
    label: "형상 이미지 추출",
    sublabel: "형상 관리",
  },
  {
    id: "functional-docs",
    icon: FileText,
    label: "기능리스트",
    sublabel: "계획",
  },
  {
    id: "test-case",
    icon: TestTube,
    label: "테스트케이스",
    sublabel: "설계",
  },
  {
    id: "result-report",
    icon: CheckCircle2,
    label: "결과리포트",
    sublabel: "수행",
  },
  {
    id: "security-report",
    icon: Shield,
    label: "보안성 결과리포트",
    sublabel: "수행",
  },
  {
    id: "performance-report",
    icon: Gauge,
    label: "성능시험 리포트",
    sublabel: "수행",
  },
]

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
  activePage: string
  onPageChange: (pageId: string) => void
}

export function Sidebar({ collapsed, onToggle, activePage, onPageChange }: SidebarProps) {
  return (
    <aside
      className={cn(
        "relative border-r border-border bg-white transition-all duration-300 flex flex-col",
        collapsed ? "w-16" : "w-72",
      )}
    >
      <Button
        variant="ghost"
        size="icon"
        onClick={onToggle}
        className="absolute -right-3 top-4 z-10 h-6 w-6 rounded-full border border-border bg-white shadow-sm hover:bg-accent"
      >
        {collapsed ? <PanelLeft className="h-3 w-3" /> : <PanelLeftClose className="h-3 w-3" />}
      </Button>

      <ScrollArea className="flex-1">
        <div className={cn("p-6", collapsed && "p-3")}>
          {!collapsed && (
            <div className="mb-6">
              <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">프로젝트</p>
              <div className="rounded-lg border border-blue-200 bg-gradient-to-br from-blue-50 to-white p-4 shadow-sm">
                <p className="mb-3 text-xl font-bold text-foreground leading-tight">SIMMETA Solid Recon V1.0</p>
                <div className="space-y-1.5 border-t border-blue-100 pt-3">
                  <p className="text-xs text-muted-foreground">프로젝트 번호</p>
                  <p className="text-sm font-medium text-foreground">GS-B-24-0178</p>
                  <p className="mt-2 text-xs text-muted-foreground">업체명</p>
                  <p className="text-sm font-medium text-foreground">주식회사 네오스펙트라</p>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-1">
            {menuItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onPageChange(item.id)}
                className={cn(
                  "group relative flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left transition-all",
                  activePage === item.id
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  collapsed && "justify-center",
                )}
                title={collapsed ? item.label : undefined}
              >
                <div
                  className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-lg transition-colors",
                    activePage === item.id ? "bg-primary/20" : "bg-muted group-hover:bg-primary/10",
                  )}
                >
                  <item.icon className="h-4 w-4" />
                </div>
                {!collapsed && (
                  <>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className={cn("text-sm font-medium truncate", activePage === item.id ? "text-primary" : "")}>
                          {item.label}
                        </p>
                      </div>
                      <p className="text-xs text-muted-foreground">{item.sublabel}</p>
                    </div>
                    {activePage === item.id && <ChevronRight className="h-4 w-4 text-primary" />}
                  </>
                )}
              </button>
            ))}
          </div>
        </div>
      </ScrollArea>

      <div className={cn("border-t border-border bg-white p-3", collapsed && "p-2")}>
        <button
          className={cn(
            "group flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left transition-all text-muted-foreground hover:bg-accent hover:text-foreground",
            collapsed && "justify-center",
          )}
          title={collapsed ? "프롬프트 관리자" : undefined}
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted transition-colors group-hover:bg-primary/10">
            <Settings className="h-4 w-4" />
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">프롬프트 관리자</p>
            </div>
          )}
        </button>
      </div>
    </aside>
  )
}
