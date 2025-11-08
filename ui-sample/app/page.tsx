"use client"

import { Header } from "@/components/header"
import { Sidebar } from "@/components/testmate-sidebar"
import { MainContent } from "@/components/main-content"
import { useState } from "react"

export default function TestMatePage() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className="flex h-screen flex-col bg-background">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} />
        <MainContent sidebarCollapsed={sidebarCollapsed} />
      </div>
    </div>
  )
}
