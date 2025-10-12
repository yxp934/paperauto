import { useState } from "react";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import { Switch } from "../ui/switch";
import { Textarea } from "../ui/textarea";
import { Progress } from "../ui/progress";
import { ScrollArea } from "../ui/scroll-area";
import { Play, Loader2 } from "lucide-react";

export function Generate() {
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [mode, setMode] = useState("complete");
  const [uploadVideo, setUploadVideo] = useState(false);
  const [exportPPTX, setExportPPTX] = useState(true);
  const [testMode, setTestMode] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(
    null,
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsRunning(true);
    setProgress(0);
    setLogs([]);

    // Simulate progress
    const mockLogs = [
      "[00:00] Starting pipeline...",
      "[00:01] Fetching paper metadata...",
      "[00:03] Extracting sections and content...",
      "[00:05] Generating slide layouts...",
      "[00:08] Applying slide provider: RevealJS",
      "[00:12] Creating transitions...",
      "[00:15] Rendering video frames...",
      "[00:20] Encoding video output...",
      "[00:25] Generating subtitles...",
      "[00:28] Pipeline completed successfully!",
    ];

    let currentLog = 0;
    const logInterval = setInterval(() => {
      if (currentLog < mockLogs.length) {
        setLogs((prev) => [...prev, mockLogs[currentLog]]);
        setProgress(((currentLog + 1) / mockLogs.length) * 100);
        currentLog++;
      } else {
        clearInterval(logInterval);
        setIsRunning(false);
      }
    }, 1200);
  };

  return (
    <div className="p-8 max-w-[1200px] mx-auto">
      <div className="mb-8">
        <h1>Generate Video</h1>
        <p className="text-muted-foreground mt-1">
          Start a new pipeline job
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Configuration Form */}
        <Card className="p-6">
          <h2 className="mb-6">Configuration</h2>
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Mode Selection */}
            <div className="space-y-2">
              <Label>Pipeline Mode</Label>
              <Select value={mode} onValueChange={setMode}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="complete">
                    Complete Pipeline (Paper → Video)
                  </SelectItem>
                  <SelectItem value="single">
                    Single Paper by ID
                  </SelectItem>
                  <SelectItem value="slides">
                    Slides Only
                  </SelectItem>
                  <SelectItem value="demo">
                    Demo Mode
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Paper ID/URL */}
            {mode === "single" && (
              <div className="space-y-2">
                <Label>Paper ID or URL</Label>
                <Input placeholder="arxiv:2401.12345 or full URL" />
              </div>
            )}

            {/* Slide Provider */}
            <div className="space-y-2">
              <Label>Slide Provider</Label>
              <Select defaultValue="revealjs">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="revealjs">
                    RevealJS
                  </SelectItem>
                  <SelectItem value="powerpoint">
                    PowerPoint
                  </SelectItem>
                  <SelectItem value="google-slides">
                    Google Slides
                  </SelectItem>
                  <SelectItem value="custom">
                    Custom Template
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Max Papers */}
            <div className="space-y-2">
              <Label>Max Papers</Label>
              <Input
                type="number"
                defaultValue="5"
                min="1"
                max="20"
              />
            </div>

            {/* Options */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Upload Video</Label>
                  <div className="text-sm text-muted-foreground">
                    Automatic uploading video to Bilibili
                  </div>
                </div>
                <Switch
                  checked={uploadVideo}
                  onCheckedChange={setUploadVideo}
                />
              </div>

              {uploadVideo && (
                <div className="space-y-2">
                  <Label>Select Video File</Label>
                  <Input
                    type="file"
                    accept="video/*"
                    onChange={(e) =>
                      setSelectedFile(
                        e.target.files?.[0] || null,
                      )
                    }
                    className="cursor-pointer"
                  />
                  {selectedFile && (
                    <div className="text-xs text-muted-foreground">
                      Selected: {selectedFile.name} (
                      {(
                        selectedFile.size /
                        1024 /
                        1024
                      ).toFixed(2)}{" "}
                      MB)
                    </div>
                  )}
                </div>
              )}

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Export PPTX</Label>
                  <div className="text-sm text-muted-foreground">
                    Auto-export PowerPoint file
                  </div>
                </div>
                <Switch
                  checked={exportPPTX}
                  onCheckedChange={setExportPPTX}
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Test Mode</Label>
                  <div className="text-sm text-muted-foreground">
                    Run with limited resources
                  </div>
                </div>
                <Switch
                  checked={testMode}
                  onCheckedChange={setTestMode}
                />
              </div>
            </div>

            <Button
              type="submit"
              className="w-full"
              disabled={isRunning}
            >
              {isRunning ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 mr-2" />
                  Start Pipeline
                </>
              )}
            </Button>
          </form>
        </Card>

        {/* Progress & Logs */}
        <Card className="p-6">
          <h2 className="mb-6">Progress & Logs</h2>

          {isRunning || logs.length > 0 ? (
            <div className="space-y-6">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">
                    Progress
                  </span>
                  <span>{Math.round(progress)}%</span>
                </div>
                <Progress value={progress} />
              </div>

              <div className="space-y-2">
                <div className="text-sm text-muted-foreground">
                  Live Logs
                </div>
                <ScrollArea className="h-[400px] rounded-md border bg-muted/30 p-4">
                  <div className="space-y-1 font-mono text-xs">
                    {logs.map((log, idx) => (
                      <div
                        key={idx}
                        className="text-foreground/90"
                      >
                        {log}
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            </div>
          ) : (
            <div className="h-[400px] flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <Play className="h-12 w-12 mx-auto mb-4 opacity-20" />
                <p>Start a pipeline to see live progress</p>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}