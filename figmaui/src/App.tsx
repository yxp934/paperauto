import { useState } from "react";
import { VideoGenSidebar } from "./components/VideoGenSidebar";
import { Dashboard } from "./components/pages/Dashboard";
import { Generate } from "./components/pages/Generate";
import { SlidesPreview } from "./components/pages/SlidesPreview";
import { VideoOutput } from "./components/pages/VideoOutput";
import { Results } from "./components/pages/Results";
import { Settings } from "./components/pages/Settings";
import { Logs } from "./components/pages/Logs";
import { HealthAdmin } from "./components/pages/HealthAdmin";

export type PageType =
  | "dashboard"
  | "generate"
  | "slides"
  | "video"
  | "results"
  | "settings"
  | "logs"
  | "health";

export default function App() {
  const [currentPage, setCurrentPage] =
    useState<PageType>("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const renderPage = () => {
    switch (currentPage) {
      case "dashboard":
        return <Dashboard onNavigate={setCurrentPage} />;
      case "generate":
        return <Generate />;
      case "slides":
        return <SlidesPreview />;
      case "video":
        return <VideoOutput />;
      case "results":
        return <Results onNavigate={setCurrentPage} />;
      case "settings":
        return <Settings />;
      case "logs":
        return <Logs />;
      case "health":
        return <HealthAdmin />;
      default:
        return <Dashboard onNavigate={setCurrentPage} />;
    }
  };

  return (
    <div className="h-screen w-full bg-background flex overflow-hidden">
      <VideoGenSidebar
        currentPage={currentPage}
        onNavigate={setCurrentPage}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />
      <main className="flex-1 overflow-auto">
        {renderPage()}
      </main>
    </div>
  );
}