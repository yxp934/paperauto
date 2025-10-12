import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { useState } from "react";
import { 
  Search, 
  Code, 
  PenTool, 
  Target, 
  GraduationCap, 
  Grid3X3,
  Send,
  Sparkles
} from "lucide-react";

interface ClaudeWelcomeProps {
  onSendMessage: (message: string) => void;
  userName?: string;
}

export function ClaudeWelcome({ onSendMessage, userName = "Esmondrio" }: ClaudeWelcomeProps) {
  const [inputValue, setInputValue] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim()) {
      onSendMessage(inputValue.trim());
      setInputValue("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const actionButtons = [
    { icon: Code, label: "Code", color: "bg-blue-500/10 text-blue-400 border-blue-500/20" },
    { icon: PenTool, label: "Write", color: "bg-green-500/10 text-green-400 border-green-500/20" },
    { icon: Target, label: "Strategize", color: "bg-purple-500/10 text-purple-400 border-purple-500/20" },
    { icon: GraduationCap, label: "Learn", color: "bg-orange-500/10 text-orange-400 border-orange-500/20" },
    { icon: Grid3X3, label: "From your apps", color: "bg-pink-500/10 text-pink-400 border-pink-500/20" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Trial notification */}
      <div className="flex justify-center p-4">
        <div className="text-sm text-muted-foreground">
          Your plan ends in 0 days. <span className="text-blue-400 hover:underline cursor-pointer">Resubscribe</span>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col items-center justify-center px-8 max-w-3xl mx-auto w-full">
        {/* Welcome message */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center gap-2 mb-4">
            <Sparkles className="h-6 w-6 text-orange-400" />
            <h1 className="text-2xl text-foreground">What's new, {userName}?</h1>
          </div>
        </div>

        {/* Input area */}
        <div className="w-full max-w-2xl">
          <form onSubmit={handleSubmit} className="relative mb-6">
            <Textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="How can I help you today?"
              className="min-h-[60px] pr-12 bg-input border-border resize-none text-base"
            />
            <Button
              type="submit"
              size="sm"
              className="absolute bottom-3 right-3 h-8 w-8 p-0"
              disabled={!inputValue.trim()}
            >
              <Send className="h-4 w-4" />
            </Button>
          </form>

          {/* Action buttons */}
          <div className="flex flex-wrap gap-3 justify-center">
            <Button
              variant="outline"
              size="sm"
              className="bg-gray-500/10 text-gray-400 border-gray-500/20 hover:bg-gray-500/20"
            >
              <Search className="h-4 w-4 mr-2" />
              Research
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="bg-blue-500/10 text-blue-400 border-blue-500/20 hover:bg-blue-500/20"
            >
              Claude Sonnet 4
              <span className="ml-2 bg-orange-500 text-white text-xs px-1.5 py-0.5 rounded">1</span>
            </Button>
            {actionButtons.map((action, index) => {
              const IconComponent = action.icon;
              return (
                <Button
                  key={index}
                  variant="outline"
                  size="sm"
                  className={`${action.color} hover:opacity-80`}
                  onClick={() => onSendMessage(`Help me with ${action.label.toLowerCase()}`)}
                >
                  <IconComponent className="h-4 w-4 mr-2" />
                  {action.label}
                </Button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}