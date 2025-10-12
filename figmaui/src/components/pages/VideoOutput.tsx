import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Play, Download, FileText, Image, ExternalLink } from "lucide-react";
import { Badge } from "../ui/badge";

export function VideoOutput() {
  return (
    <div className="p-8 max-w-[1200px] mx-auto">
      <div className="mb-8">
        <h1>Video Output</h1>
        <p className="text-muted-foreground mt-1">Final video and related assets</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Video Player */}
        <div className="lg:col-span-2">
          <Card className="p-6">
            <h2 className="mb-4">Video Player</h2>
            <div className="aspect-video bg-muted rounded-lg flex items-center justify-center mb-4">
              <div className="text-center">
                <Play className="h-16 w-16 mx-auto mb-4 text-muted-foreground" />
                <p className="text-muted-foreground">Video player preview</p>
                <p className="text-sm text-muted-foreground mt-2">
                  /output/quantum_computing_2024.mp4
                </p>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <Badge variant="outline">1920x1080 • 60fps</Badge>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">
                  <Play className="h-4 w-4 mr-2" />
                  Play
                </Button>
                <Button variant="outline" size="sm">
                  <Download className="h-4 w-4 mr-2" />
                  Download Video
                </Button>
              </div>
            </div>
          </Card>

          {/* Subtitles Preview */}
          <Card className="p-6 mt-6">
            <h2 className="mb-4">Subtitles</h2>
            <div className="space-y-3 max-h-[300px] overflow-y-auto">
              {[
                { time: "00:00 - 00:05", text: "Welcome to our presentation on Quantum Computing Advances" },
                { time: "00:05 - 00:12", text: "In this video, we'll explore the latest breakthroughs in quantum technology" },
                { time: "00:12 - 00:18", text: "First, let's discuss the fundamental principles of quantum mechanics" },
                { time: "00:18 - 00:25", text: "Quantum computers leverage superposition and entanglement" },
                { time: "00:25 - 00:32", text: "Our research focuses on error correction and qubit stability" },
              ].map((subtitle, idx) => (
                <div key={idx} className="flex gap-4 text-sm">
                  <div className="text-muted-foreground font-mono min-w-[120px]">
                    {subtitle.time}
                  </div>
                  <div>{subtitle.text}</div>
                </div>
              ))}
            </div>
            <Button variant="outline" size="sm" className="w-full mt-4">
              <Download className="h-4 w-4 mr-2" />
              Download Subtitles (.srt)
            </Button>
          </Card>
        </div>

        {/* Metadata & Actions */}
        <div className="space-y-6">
          <Card className="p-6">
            <h3 className="mb-4">Video Details</h3>
            <div className="space-y-3 text-sm">
              <div>
                <div className="text-muted-foreground">File Path</div>
                <div className="font-mono text-xs mt-1 break-all">
                  /output/quantum_computing_2024.mp4
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">File Size</div>
                <div className="mt-1">127.4 MB</div>
              </div>
              <div>
                <div className="text-muted-foreground">Duration</div>
                <div className="mt-1">2m 45s</div>
              </div>
              <div>
                <div className="text-muted-foreground">Resolution</div>
                <div className="mt-1">1920x1080 (Full HD)</div>
              </div>
              <div>
                <div className="text-muted-foreground">Frame Rate</div>
                <div className="mt-1">60 fps</div>
              </div>
              <div>
                <div className="text-muted-foreground">Codec</div>
                <div className="mt-1">H.264 / AAC</div>
              </div>
              <div>
                <div className="text-muted-foreground">Generated</div>
                <div className="mt-1">Oct 8, 2025 14:23</div>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="mb-4">Related Assets</h3>
            <div className="space-y-2">
              <Button variant="outline" className="w-full justify-start">
                <Image className="h-4 w-4 mr-2" />
                Cover Image
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <FileText className="h-4 w-4 mr-2" />
                Subtitle File (.srt)
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <FileText className="h-4 w-4 mr-2" />
                Video Metadata (.json)
              </Button>
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="mb-4">Quick Actions</h3>
            <div className="space-y-2">
              <Button variant="outline" className="w-full justify-start">
                <ExternalLink className="h-4 w-4 mr-2" />
                View Source Slides
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <Download className="h-4 w-4 mr-2" />
                Re-export PPTX
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <Play className="h-4 w-4 mr-2" />
                Generate New Run
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
