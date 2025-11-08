"use client"

import { Header } from "@/components/header"
import { Sidebar } from "@/components/testmate-sidebar"
import { ImageExtractionContent } from "@/components/image-extraction-content"
import { FeatureListContent } from "@/components/feature-list-content"
import { TestcaseContent } from "@/components/testcase-content"
import { DefectReportContent } from "@/components/defect-report-content"
import { SecurityReportContent } from "@/components/security-report-content"
import { PerformanceReportContent } from "@/components/performance-report-content"
import { useState } from "react"

export default function TestMatePage() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [activePage, setActivePage] = useState("image-extract")

  const renderContent = () => {
    switch (activePage) {
      case "image-extract":
        return <ImageExtractionContent />
      case "functional-docs":
        return <FeatureListContent />
      case "test-case":
        return <TestcaseContent />
      case "result-report":
        return <DefectReportContent />
      case "security-report":
        return <SecurityReportContent />
      case "performance-report":
        return <PerformanceReportContent />
      default:
        return <ImageExtractionContent />
    }
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
          activePage={activePage}
          onPageChange={setActivePage}
        />
        <main className="flex-1 overflow-hidden">{renderContent()}</main>
      </div>
    </div>
  )
}
