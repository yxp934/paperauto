import { useState } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { ScrollArea } from "./ui/scroll-area";
import { Sidebar, SidebarContent, SidebarHeader, SidebarMenu, SidebarMenuItem, SidebarMenuButton } from "./ui/sidebar";
import { Plus, Search, MessageSquare, Trash2 } from "lucide-react";

export interface ChatHistory {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: Date;
  messageCount: number;
}

interface ChatSidebarProps {
  chatHistory: ChatHistory[];
  currentChatId: string | null;
  onSelectChat: (chatId: string) => void;
  onNewChat: () => void;
  onDeleteChat: (chatId: string) => void;
}

export function ChatSidebar({ 
  chatHistory, 
  currentChatId, 
  onSelectChat, 
  onNewChat, 
  onDeleteChat 
}: ChatSidebarProps) {
  const [searchTerm, setSearchTerm] = useState("");

  const filteredChats = chatHistory.filter(chat =>
    chat.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    chat.lastMessage.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatDate = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) return "Today";
    if (days === 1) return "Yesterday";
    if (days < 7) return `${days} days ago`;
    return date.toLocaleDateString();
  };

  return (
    <Sidebar className="w-80">
      <SidebarHeader className="p-4">
        <Button onClick={onNewChat} className="w-full" size="sm">
          <Plus className="h-4 w-4 mr-2" />
          New Chat
        </Button>
        
        <div className="relative mt-4">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search chats..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
      </SidebarHeader>

      <SidebarContent>
        <ScrollArea className="flex-1">
          <div className="p-2">
            {filteredChats.length === 0 ? (
              <div className="p-4 text-center text-muted-foreground">
                {searchTerm ? "No chats found" : "No chat history"}
              </div>
            ) : (
              <SidebarMenu>
                {filteredChats.map((chat) => (
                  <SidebarMenuItem key={chat.id}>
                    <div className="relative group">
                      <SidebarMenuButton
                        onClick={() => onSelectChat(chat.id)}
                        isActive={currentChatId === chat.id}
                        className="w-full justify-start p-3 h-auto"
                      >
                        <div className="flex items-start gap-3 w-full min-w-0">
                          <MessageSquare className="h-4 w-4 mt-1 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between mb-1">
                              <h4 className="truncate pr-2 text-sm font-medium">{chat.title}</h4>
                              <span className="text-xs text-muted-foreground flex-shrink-0">
                                {formatDate(chat.timestamp)}
                              </span>
                            </div>
                            <p className="text-sm text-muted-foreground truncate">
                              {chat.lastMessage}
                            </p>
                            <div className="flex items-center justify-between mt-1">
                              <span className="text-xs text-muted-foreground">
                                {chat.messageCount} messages
                              </span>
                            </div>
                          </div>
                        </div>
                      </SidebarMenuButton>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="absolute top-3 right-3 h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteChat(chat.id);
                        }}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            )}
          </div>
        </ScrollArea>
      </SidebarContent>
    </Sidebar>
  );
}