import { Avatar, AvatarFallback } from "./ui/avatar";
import { Bot, User } from "lucide-react";

interface ChatMessageProps {
  message: string;
  isUser: boolean;
  timestamp: Date;
}

export function ChatMessage({ message, isUser, timestamp }: ChatMessageProps) {
  return (
    <div className={`px-6 py-6 ${isUser ? "bg-background" : "bg-muted/30"}`}>
      <div className="flex gap-4 max-w-none">
        <Avatar className="h-8 w-8 flex-shrink-0">
          <AvatarFallback className={isUser ? "bg-blue-500 text-white" : "bg-orange-500 text-white"}>
            {isUser ? <User className="h-4 w-4" /> : "C"}
          </AvatarFallback>
        </Avatar>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-medium text-foreground">
              {isUser ? "You" : "Claude"}
            </span>
            <span className="text-xs text-muted-foreground">
              {timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
          <div className="text-foreground whitespace-pre-wrap break-words leading-relaxed">
            {message}
          </div>
        </div>
      </div>
    </div>
  );
}