import { useState } from "react";
import { PageType } from "../../App";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { Badge } from "../ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Search, ExternalLink, Image, Video, FileText } from "lucide-react";

interface ResultsProps {
  onNavigate: (page: PageType) => void;
}

const mockResults = [
  {
    id: "run-001",
    title: "Quantum Computing Advances",
    paperId: "arxiv:2401.12345",
    status: "completed",
    date: "2025-10-08 14:23",
    duration: "12m 34s",
    slides: 8,
    videoPath: "/output/quantum_computing_2024.mp4",
    subtitlesPath: "/output/quantum_computing_2024.srt",
  },
  {
    id: "run-002",
    title: "Neural Network Architectures",
    paperId: "arxiv:2401.54321",
    status: "running",
    date: "2025-10-08 14:45",
    duration: "5m 12s",
    slides: 5,
    videoPath: null,
    subtitlesPath: null,
  },
  {
    id: "run-003",
    title: "Climate Change Models",
    paperId: "arxiv:2401.98765",
    status: "failed",
    date: "2025-10-08 13:12",
    duration: "3m 45s",
    slides: 0,
    videoPath: null,
    subtitlesPath: null,
  },
  {
    id: "run-004",
    title: "Machine Learning Applications",
    paperId: "arxiv:2401.11111",
    status: "completed",
    date: "2025-10-08 12:05",
    duration: "15m 18s",
    slides: 12,
    videoPath: "/output/ml_applications_2024.mp4",
    subtitlesPath: "/output/ml_applications_2024.srt",
  },
  {
    id: "run-005",
    title: "Renewable Energy Systems",
    paperId: "arxiv:2401.22222",
    status: "completed",
    date: "2025-10-08 11:30",
    duration: "10m 42s",
    slides: 10,
    videoPath: "/output/renewable_energy_2024.mp4",
    subtitlesPath: "/output/renewable_energy_2024.srt",
  },
];

export function Results({ onNavigate }: ResultsProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedRun, setSelectedRun] = useState<typeof mockResults[0] | null>(null);

  const filteredResults = mockResults.filter((run) => {
    const matchesSearch =
      run.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      run.paperId.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || run.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status: string) => {
    const variants: Record<string, { variant: "default" | "secondary" | "destructive" | "outline", text: string }> = {
      completed: { variant: "default", text: "Completed" },
      running: { variant: "secondary", text: "Running" },
      failed: { variant: "destructive", text: "Failed" },
    };
    const config = variants[status] || variants.completed;
    return <Badge variant={config.variant}>{config.text}</Badge>;
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto">
      <div className="mb-8">
        <h1>Results</h1>
        <p className="text-muted-foreground mt-1">Browse all past pipeline runs</p>
      </div>

      {/* Search & Filters */}
      <Card className="p-6 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by title or paper ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full md:w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="running">Running</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </Card>

      {/* Results List */}
      <div className="space-y-4">
        {filteredResults.map((run) => (
          <Card key={run.id} className="p-6">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="truncate">{run.title}</h3>
                  {getStatusBadge(run.status)}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <div className="text-muted-foreground">Paper ID</div>
                    <div className="font-mono text-xs mt-1">{run.paperId}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Run ID</div>
                    <div className="font-mono text-xs mt-1">{run.id}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Duration</div>
                    <div className="mt-1">{run.duration}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Date</div>
                    <div className="mt-1">{run.date}</div>
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedRun(run)}
                >
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Details
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {filteredResults.length === 0 && (
        <Card className="p-12">
          <div className="text-center text-muted-foreground">
            <Search className="h-12 w-12 mx-auto mb-4 opacity-20" />
            <p>No results found</p>
            <p className="text-sm mt-2">Try adjusting your search or filters</p>
          </div>
        </Card>
      )}

      {/* Detail Dialog */}
      <Dialog open={!!selectedRun} onOpenChange={() => setSelectedRun(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{selectedRun?.title}</DialogTitle>
          </DialogHeader>
          {selectedRun && (
            <div className="space-y-6">
              {/* Paper Metadata */}
              <div>
                <h3 className="mb-3">Paper Metadata</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-muted-foreground">Paper ID</div>
                    <div className="font-mono mt-1">{selectedRun.paperId}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Run ID</div>
                    <div className="font-mono mt-1">{selectedRun.id}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Status</div>
                    <div className="mt-1">{getStatusBadge(selectedRun.status)}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Duration</div>
                    <div className="mt-1">{selectedRun.duration}</div>
                  </div>
                </div>
              </div>

              {/* Output Files */}
              <div>
                <h3 className="mb-3">Output Files</h3>
                <div className="space-y-2">
                  <div className="flex items-center justify-between p-3 rounded-lg border">
                    <div className="flex items-center gap-3">
                      <Image className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <div className="text-sm">Slides</div>
                        <div className="text-xs text-muted-foreground">
                          {selectedRun.slides} slides generated
                        </div>
                      </div>
                    </div>
                    <Button size="sm" variant="outline" onClick={() => onNavigate("slides")}>
                      View
                    </Button>
                  </div>
                  {selectedRun.videoPath && (
                    <div className="flex items-center justify-between p-3 rounded-lg border">
                      <div className="flex items-center gap-3">
                        <Video className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <div className="text-sm">Video</div>
                          <div className="text-xs text-muted-foreground font-mono">
                            {selectedRun.videoPath}
                          </div>
                        </div>
                      </div>
                      <Button size="sm" variant="outline" onClick={() => onNavigate("video")}>
                        View
                      </Button>
                    </div>
                  )}
                  {selectedRun.subtitlesPath && (
                    <div className="flex items-center justify-between p-3 rounded-lg border">
                      <div className="flex items-center gap-3">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <div className="text-sm">Subtitles</div>
                          <div className="text-xs text-muted-foreground font-mono">
                            {selectedRun.subtitlesPath}
                          </div>
                        </div>
                      </div>
                      <Button size="sm" variant="outline">
                        Download
                      </Button>
                    </div>
                  )}
                </div>
              </div>

              {/* Timestamps */}
              <div>
                <h3 className="mb-3">Timeline</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Started</span>
                    <span>{selectedRun.date}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Duration</span>
                    <span>{selectedRun.duration}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Status</span>
                    <span>{selectedRun.status}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
