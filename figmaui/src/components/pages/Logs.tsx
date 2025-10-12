import { useState, useEffect } from "react";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { ScrollArea } from "../ui/scroll-area";
import { Badge } from "../ui/badge";
import { Download, RefreshCw, Pause, Play } from "lucide-react";

const mockLogs = [
  { time: "14:23:01", level: "info", message: "Pipeline started for job run-001" },
  { time: "14:23:02", level: "info", message: "Fetching paper metadata from arxiv:2401.12345" },
  { time: "14:23:05", level: "info", message: "Paper successfully retrieved: Quantum Computing Advances" },
  { time: "14:23:06", level: "info", message: "Extracting sections: Introduction, Methods, Results, Discussion" },
  { time: "14:23:10", level: "info", message: "Starting slide generation with RevealJS provider" },
  { time: "14:23:12", level: "warn", message: "Image resolution below recommended threshold for slide 3" },
  { time: "14:23:15", level: "info", message: "LLM call: Generating title slide content" },
  { time: "14:23:18", level: "info", message: "LLM call: Generating methodology slide content" },
  { time: "14:23:20", level: "info", message: "MCP tool invoked: diagram_generator" },
  { time: "14:23:22", level: "info", message: "Slide 1/8 rendered successfully" },
  { time: "14:23:24", level: "info", message: "Slide 2/8 rendered successfully" },
  { time: "14:23:26", level: "error", message: "Failed to load external resource for slide 3, using fallback" },
  { time: "14:23:28", level: "info", message: "Slide 3/8 rendered with fallback content" },
  { time: "14:23:30", level: "info", message: "Slide 4/8 rendered successfully" },
  { time: "14:23:32", level: "info", message: "Starting video encoding at 1080p 60fps" },
  { time: "14:23:35", level: "info", message: "Video frame 0-120 encoded" },
  { time: "14:23:38", level: "info", message: "Video frame 120-240 encoded" },
  { time: "14:23:41", level: "info", message: "Generating subtitle track" },
  { time: "14:23:43", level: "info", message: "Exporting PPTX file" },
  { time: "14:23:45", level: "info", message: "Pipeline completed successfully in 12m 34s" },
];

export function Logs() {
  const [selectedJob, setSelectedJob] = useState("run-001");
  const [filterLevel, setFilterLevel] = useState("all");
  const [autoScroll, setAutoScroll] = useState(true);
  const [logs, setLogs] = useState(mockLogs);

  // Simulate live log updates
  useEffect(() => {
    if (!autoScroll) return;
    
    const interval = setInterval(() => {
      const newLog = {
        time: new Date().toLocaleTimeString(),
        level: ["info", "warn", "error"][Math.floor(Math.random() * 3)],
        message: [
          "Processing frame batch...",
          "LLM call completed",
          "Cache hit for slide template",
          "Rendering slide transition",
        ][Math.floor(Math.random() * 4)],
      };
      setLogs((prev) => [...prev, newLog]);
    }, 3000);

    return () => clearInterval(interval);
  }, [autoScroll]);

  const filteredLogs = logs.filter((log) => {
    if (filterLevel === "all") return true;
    return log.level === filterLevel;
  });

  const getLevelBadge = (level: string) => {
    const config: Record<string, { variant: "default" | "secondary" | "destructive" | "outline", className: string }> = {
      info: { variant: "outline", className: "text-blue-500" },
      warn: { variant: "outline", className: "text-yellow-500" },
      error: { variant: "destructive", className: "" },
    };
    const { variant, className } = config[level] || config.info;
    return (
      <Badge variant={variant} className={className}>
        {level.toUpperCase()}
      </Badge>
    );
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto">
      <div className="mb-8">
        <h1>Logs</h1>
        <p className="text-muted-foreground mt-1">Live log viewer for pipeline jobs</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Controls */}
        <div className="space-y-4">
          <Card className="p-4">
            <h3 className="mb-4">Job Selection</h3>
            <div className="space-y-2">
              <Label>Job ID</Label>
              <Input
                value={selectedJob}
                onChange={(e) => setSelectedJob(e.target.value)}
                placeholder="run-001"
              />
            </div>
          </Card>

          <Card className="p-4">
            <h3 className="mb-4">Filters</h3>
            <div className="space-y-2">
              <Label>Log Level</Label>
              <div className="space-y-2">
                {["all", "info", "warn", "error"].map((level) => (
                  <button
                    key={level}
                    onClick={() => setFilterLevel(level)}
                    className={`w-full px-3 py-2 rounded-md text-left text-sm transition-colors ${
                      filterLevel === level
                        ? "bg-accent text-accent-foreground"
                        : "hover:bg-accent/50"
                    }`}
                  >
                    {level === "all" ? "All Levels" : level.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          </Card>

          <Card className="p-4">
            <h3 className="mb-4">Actions</h3>
            <div className="space-y-2">
              <Button
                variant="outline"
                className="w-full justify-start"
                onClick={() => setAutoScroll(!autoScroll)}
              >
                {autoScroll ? (
                  <>
                    <Pause className="h-4 w-4 mr-2" />
                    Pause Live
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Resume Live
                  </>
                )}
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <Download className="h-4 w-4 mr-2" />
                Download
              </Button>
            </div>
          </Card>

          <Card className="p-4">
            <h3 className="mb-4">Statistics</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total Logs</span>
                <span>{logs.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Info</span>
                <span>{logs.filter((l) => l.level === "info").length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Warnings</span>
                <span className="text-yellow-500">
                  {logs.filter((l) => l.level === "warn").length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Errors</span>
                <span className="text-red-500">
                  {logs.filter((l) => l.level === "error").length}
                </span>
              </div>
            </div>
          </Card>
        </div>

        {/* Log Viewer */}
        <div className="lg:col-span-3">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2>Live Logs - {selectedJob}</h2>
              {autoScroll && (
                <Badge variant="secondary" className="gap-1">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                  </span>
                  Live
                </Badge>
              )}
            </div>
            
            <ScrollArea className="h-[700px] rounded-md border bg-muted/30 p-4">
              <div className="space-y-2 font-mono text-xs">
                {filteredLogs.map((log, idx) => (
                  <div key={idx} className="flex gap-3 items-start">
                    <span className="text-muted-foreground min-w-[70px]">
                      {log.time}
                    </span>
                    <span className="min-w-[60px]">{getLevelBadge(log.level)}</span>
                    <span className="flex-1">{log.message}</span>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </Card>
        </div>
      </div>
    </div>
  );
}
