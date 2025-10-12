import { useState } from "react";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";
import { Sidebar, SidebarContent, SidebarHeader, SidebarFooter } from "./ui/sidebar";
import { 
  Plus, 
  MessageSquare, 
  FolderOpen, 
  Sparkles, 
  Star, 
  Clock,
  ChevronDown,
  User
} from "lucide-react";

export interface ChatHistory {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: Date;
  messageCount: number;
}

interface ClaudeSidebarProps {
  chatHistory: ChatHistory[];
  currentChatId: string | null;
  onSelectChat: (chatId: string) => void;
  onNewChat: () => void;
  onDeleteChat: (chatId: string) => void;
}

export function ClaudeSidebar({ 
  chatHistory, 
  currentChatId, 
  onSelectChat, 
  onNewChat, 
  onDeleteChat 
}: ClaudeSidebarProps) {
  // Mock data for starred and recent items to match the image
  const starredItems = [
    "Lawsuit AI Product Documentation",
    "Lavin AI Documentation Strategy"
  ];

  const recentItems = [
    "Melplatlib System Architecture D...",
    "AI Internal Talent Matching System",
    "AI Video Planner App Development",
    "AI Prompt Generator Web App",
    "Sales Tip Tracking UI Mockup",
    "AI Sales Training Platform for Ba...",
    "VEO3 Prompt Generator Web App",
    "Remix of PPD to Prototype",
    "AI Storyboard App Development",
    "AI Storyboard Builder App",
    "App Development Concept",
    "Overhaul CV Finalization",
    "Digital Product Trends in Indonesia",
    "Gemini 2.0 Flash API Pricing Details"
  ];

  const formatTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) return "Today";
    if (days === 1) return "Yesterday";
    if (days < 7) return `${days}d`;
    return date.toLocaleDateString();
  };

  return (
    <Sidebar className="w-64 border-r border-sidebar-border">
      <SidebarHeader className="p-4 border-b border-sidebar-border">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 bg-orange-500 rounded flex items-center justify-center">
            <span className="text-white text-xs font-medium">C</span>
          </div>
          <h1 className="text-lg font-medium text-sidebar-foreground">Claude</h1>
        </div>
        
        <Button 
          onClick={onNewChat} 
          className="w-full justify-start bg-sidebar-accent hover:bg-sidebar-accent/80 text-sidebar-foreground border border-sidebar-border" 
          size="sm"
        >
          <Plus className="h-4 w-4 mr-2" />
          New chat
        </Button>
      </SidebarHeader>

      <SidebarContent className="p-0">
        <ScrollArea className="flex-1">
          <div className="p-2">
            {/* Navigation sections */}
            <div className="space-y-1 mb-4">
              <Button
                variant="ghost"
                className="w-full justify-start h-8 px-2 text-sm text-sidebar-foreground/70 hover:bg-sidebar-accent"
              >
                <MessageSquare className="h-4 w-4 mr-2" />
                Chats
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start h-8 px-2 text-sm text-sidebar-foreground/70 hover:bg-sidebar-accent"
              >
                <FolderOpen className="h-4 w-4 mr-2" />
                Projects
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start h-8 px-2 text-sm text-sidebar-foreground/70 hover:bg-sidebar-accent"
              >
                <Sparkles className="h-4 w-4 mr-2" />
                Artifacts
              </Button>
            </div>

            {/* Starred section */}
            <div className="mb-4">
              <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-sidebar-foreground/70 uppercase tracking-wider">
                <Star className="h-3 w-3" />
                Starred
              </div>
              <div className="space-y-1 mt-2">
                {starredItems.map((item, index) => (
                  <button
                    key={index}
                    className="w-full text-left px-2 py-1.5 text-sm text-sidebar-foreground hover:bg-sidebar-accent rounded-md truncate"
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>

            {/* Recents section */}
            <div>
              <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-sidebar-foreground/70 uppercase tracking-wider">
                <Clock className="h-3 w-3" />
                Recents
              </div>
              <div className="space-y-1 mt-2">
                {recentItems.map((item, index) => (
                  <button
                    key={index}
                    className="w-full text-left px-2 py-1.5 text-sm text-sidebar-foreground hover:bg-sidebar-accent rounded-md truncate"
                    onClick={() => {
                      // For demo purposes, create a new chat when clicking recent items
                      onNewChat();
                    }}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </ScrollArea>
      </SidebarContent>

      <SidebarFooter className="p-4 border-t border-sidebar-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-orange-500 rounded-full flex items-center justify-center">
            <User className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-sidebar-foreground">Esmondrio</p>
            <p className="text-xs text-sidebar-foreground/70">Pro plan</p>
          </div>
          <ChevronDown className="h-4 w-4 text-sidebar-foreground/70" />
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}