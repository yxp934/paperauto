import { PageType } from "../App";
import { LayoutDashboard, Play, Image, Video, FolderOpen, Settings, FileText, Activity, Menu, X } from "lucide-react";
import { Button } from "./ui/button";

interface VideoGenSidebarProps {
  currentPage: PageType;
  onNavigate: (page: PageType) => void;
  isOpen: boolean;
  onToggle: () => void;
}

const navItems = [
  { id: "dashboard" as PageType, label: "Dashboard", icon: LayoutDashboard },
  { id: "generate" as PageType, label: "Generate", icon: Play },
  { id: "slides" as PageType, label: "Slides Preview", icon: Image },
  { id: "video" as PageType, label: "Video Output", icon: Video },
  { id: "results" as PageType, label: "Results", icon: FolderOpen },
  { id: "settings" as PageType, label: "Settings", icon: Settings },
  { id: "logs" as PageType, label: "Logs", icon: FileText },
  { id: "health" as PageType, label: "Health & Admin", icon: Activity },
];

export function VideoGenSidebar({ currentPage, onNavigate, isOpen, onToggle }: VideoGenSidebarProps) {
  return (
    <>
      {/* Mobile menu button */}
      <Button
        variant="ghost"
        size="icon"
        className="fixed top-4 left-4 z-50 md:hidden"
        onClick={onToggle}
      >
        {isOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </Button>

      {/* Sidebar */}
      <aside
        className={`${
          isOpen ? "translate-x-0" : "-translate-x-full"
        } md:translate-x-0 fixed md:relative z-40 h-full w-64 bg-sidebar border-r border-sidebar-border transition-transform duration-200 flex flex-col`}
      >
        <div className="p-6 border-b border-sidebar-border">
          <h1 className="text-sidebar-foreground">Video Generator</h1>
          <p className="text-sm text-muted-foreground mt-1">Pipeline Management</p>
        </div>

        <nav className="flex-1 overflow-y-auto p-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/50"
                }`}
              >
                <Icon className="h-5 w-5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-sidebar-border">
          <div className="text-xs text-muted-foreground">
            <div>Version 2.1.0</div>
            <div className="mt-1">© 2025 Video Gen</div>
          </div>
        </div>
      </aside>

      {/* Overlay for mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={onToggle}
        />
      )}
    </>
  );
}
