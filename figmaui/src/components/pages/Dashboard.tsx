import { PageType } from "../../App";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { ExternalLink, FileText, Image, Video, Play } from "lucide-react";

interface DashboardProps {
  onNavigate: (page: PageType) => void;
}

const mockRuns = [
  {
    id: "run-001",
    title: "Quantum Computing Advances",
    status: "completed",
    duration: "12m 34s",
    successRate: "100%",
    timestamp: "2025-10-08 14:23",
    hasSlides: true,
    hasVideo: true,
  },
  {
    id: "run-002",
    title: "Neural Network Architectures",
    status: "running",
    duration: "5m 12s",
    successRate: "85%",
    timestamp: "2025-10-08 14:45",
    hasSlides: true,
    hasVideo: false,
  },
  {
    id: "run-003",
    title: "Climate Change Models",
    status: "failed",
    duration: "3m 45s",
    successRate: "40%",
    timestamp: "2025-10-08 13:12",
    hasSlides: false,
    hasVideo: false,
  },
  {
    id: "run-004",
    title: "Machine Learning Applications",
    status: "completed",
    duration: "15m 18s",
    successRate: "100%",
    timestamp: "2025-10-08 12:05",
    hasSlides: true,
    hasVideo: true,
  },
  {
    id: "run-005",
    title: "Renewable Energy Systems",
    status: "completed",
    duration: "10m 42s",
    successRate: "95%",
    timestamp: "2025-10-08 11:30",
    hasSlides: true,
    hasVideo: true,
  },
];

export function Dashboard({ onNavigate }: DashboardProps) {
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
    <div className="p-8 max-w-[1400px] mx-auto bg-[rgba(221,55,182,0)]">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1>Dashboard</h1>
          <p className="text-muted-foreground mt-1">Overview of recent pipeline runs</p>
        </div>
        <Button onClick={() => onNavigate("generate")}>
          <Play className="h-4 w-4 mr-2" />
          New Run
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <Card className="p-6">
          <div className="text-sm text-muted-foreground">Total Runs</div>
          <div className="text-3xl mt-2">127</div>
        </Card>
        <Card className="p-[21px]">
          <div className="text-sm text-muted-foreground">Success Rate</div>
          <div className="text-3xl mt-2">94%</div>
        </Card>
        <Card className="p-6">
          <div className="text-sm text-muted-foreground">Avg Duration</div>
          <div className="text-3xl mt-2">11m</div>
        </Card>
        <Card className="p-6">
          <div className="text-sm text-muted-foreground">Active Jobs</div>
          <div className="text-3xl mt-2">1</div>
        </Card>
      </div>

      {/* Recent Runs Table */}
      <Card className="p-6">
        <h2 className="mb-4">Recent Runs</h2>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Success Rate</TableHead>
                <TableHead>Timestamp</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockRuns.map((run) => (
                <TableRow key={run.id}>
                  <TableCell className="font-mono text-sm">{run.id}</TableCell>
                  <TableCell>{run.title}</TableCell>
                  <TableCell>{getStatusBadge(run.status)}</TableCell>
                  <TableCell>{run.duration}</TableCell>
                  <TableCell>{run.successRate}</TableCell>
                  <TableCell className="text-muted-foreground">{run.timestamp}</TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      {run.hasSlides && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onNavigate("slides")}
                        >
                          <Image className="h-4 w-4" />
                        </Button>
                      )}
                      {run.hasVideo && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onNavigate("video")}
                        >
                          <Video className="h-4 w-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onNavigate("logs")}
                      >
                        <FileText className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onNavigate("results")}
                      >
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>
    </div>
  );
}
