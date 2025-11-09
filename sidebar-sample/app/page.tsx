"use client"

import { useState } from "react"
import { ProjectSidebar } from "@/components/sidebar/project-sidebar"
import "@/styles/sidebar.css"
import { Menu, X } from "lucide-react"

export default function Page() {
  const [activeItem, setActiveItem] = useState("image-extraction")
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)

  return (
    <div
      className={`project-management-page${isSidebarOpen ? " project-management-page--sidebar-open" : " project-management-page--sidebar-collapsed"}`}
    >
      <style jsx global>{`
        :root {
          --project-management-sidebar-width: 280px;
          --viewport-height: 100vh;
          --app-shell-header-height: 0px;
        }
        
        body {
          margin: 0;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        .project-management-page {
          --project-management-available-height: calc(var(--viewport-height) - var(--app-shell-header-height, 0px));
          position: relative;
          display: grid;
          grid-template-columns: var(--project-management-sidebar-width) minmax(0, 1fr);
          align-self: stretch;
          min-width: 0;
          width: 100%;
          background: #f8fafc;
          height: var(--project-management-available-height);
          max-height: var(--project-management-available-height);
          min-height: 0;
          overflow: hidden;
          transition: grid-template-columns 0.3s ease;
        }

        .project-management-page--sidebar-collapsed {
          grid-template-columns: 0 minmax(0, 1fr);
        }
        
        .project-management-content {
          flex: 1 1 auto;
          display: flex;
          flex-direction: column;
          padding: 2rem;
          overflow-y: auto;
        }
        
        .project-management-header {
          display: flex;
          align-items: center;
          gap: 1rem;
          margin-bottom: 2rem;
        }
        
        .sidebar-toggle-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 40px;
          height: 40px;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          background: white;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        
        .sidebar-toggle-btn:hover {
          background: #f1f5f9;
          border-color: #cbd5e1;
        }
        
        .content-card {
          background: white;
          border-radius: 12px;
          padding: 2rem;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        
        .content-card h1 {
          margin: 0 0 1rem 0;
          font-size: 1.5rem;
          color: #0f172a;
        }
        
        .content-card p {
          margin: 0;
          color: #64748b;
          line-height: 1.6;
        }
        
        @media (max-width: 1024px) {
          .project-management-page {
            grid-template-columns: minmax(0, 1fr);
          }
        }
      `}</style>

      {/* Backdrop for mobile */}
      <button
        className="project-management-sidebar-backdrop"
        onClick={() => setIsSidebarOpen(false)}
        aria-label="사이드바 닫기"
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(15, 23, 42, 0.45)",
          opacity: isSidebarOpen ? 1 : 0,
          pointerEvents: isSidebarOpen ? "auto" : "none",
          transition: "opacity 0.3s ease",
          zIndex: 1,
          border: "none",
          cursor: "pointer",
        }}
      />

      <ProjectSidebar
        projectName="[GS-B-24-0188] 주식회사 알고리즘랩스 - AI Canvas"
        activeItem={activeItem}
        isSidebarOpen={isSidebarOpen}
        onSelectMenuItem={setActiveItem}
      />

      <div className="project-management-content">
        <div className="project-management-header">
          <button
            className="sidebar-toggle-btn"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            aria-label={isSidebarOpen ? "사이드바 닫기" : "사이드바 열기"}
          >
            {isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <h2 style={{ margin: 0, fontSize: "1.25rem", color: "#0f172a" }}>프로젝트 관리</h2>
        </div>

        <div className="content-card">
          <h1>형상 이미지 추출</h1>
          <p>프로그램 기능 시연 동영상을 업로드하면 장면 전환을 감지하여 주요 화면 이미지를 자동으로 추출합니다.</p>

          <div
            style={{
              marginTop: "2rem",
              padding: "2rem",
              background: "#f8fafc",
              borderRadius: "8px",
              border: "2px dashed #e2e8f0",
            }}
          >
            <p style={{ textAlign: "center", color: "#94a3b8" }}>파일을 드래그 앤 드롭하거나 클릭해서 선택하세요.</p>
            <p style={{ textAlign: "center", fontSize: "0.875rem", color: "#cbd5e1", marginTop: "0.5rem" }}>
              허용된 형식: MP4, MOV
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
