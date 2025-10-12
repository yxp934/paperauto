import { useState } from "react";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Progress } from "../ui/progress";
import { Separator } from "../ui/separator";
import { CheckCircle2, XCircle, AlertCircle, Trash2, RefreshCw, Activity } from "lucide-react";
import { toast } from "sonner@2.0.3";

export function HealthAdmin() {
  const [clearing, setClearing] = useState(false);

  const handleClearCache = () => {
    setClearing(true);
    setTimeout(() => {
      setClearing(false);
      toast.success("Cache cleared successfully");
    }, 1500);
  };

  const handleRefreshStats = () => {
    toast.success("Stats refreshed");
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto">
      <div className="mb-8">
        <h1>Health & Admin</h1>
        <p className="text-muted-foreground mt-1">System status and administrative tools</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Health */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2>System Health</h2>
            <Button variant="outline" size="sm" onClick={handleRefreshStats}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">API Server</span>
              </div>
              <Badge variant="outline" className="gap-1">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                Healthy
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">Database</span>
              </div>
              <Badge variant="outline" className="gap-1">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                Connected
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">Worker Queue</span>
              </div>
              <Badge variant="outline" className="gap-1">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                Active
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">File System</span>
              </div>
              <Badge variant="outline" className="gap-1">
                <AlertCircle className="h-3 w-3 text-yellow-500" />
                78% Full
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">LLM Provider</span>
              </div>
              <Badge variant="outline" className="gap-1">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                Available
              </Badge>
            </div>
          </div>
        </Card>

        {/* Version Info */}
        <Card className="p-6">
          <h2 className="mb-6">Version Information</h2>
          
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Application Version</span>
              <span className="font-mono">2.1.0</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Build Date</span>
              <span>2025-10-01</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Python Version</span>
              <span className="font-mono">3.11.5</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Core Library</span>
              <span className="font-mono">videogen-core@1.4.2</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Environment</span>
              <Badge variant="outline">Production</Badge>
            </div>
          </div>
        </Card>

        {/* Resource Usage */}
        <Card className="p-6">
          <h2 className="mb-6">Resource Usage</h2>
          
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">CPU Usage</span>
                <span>34%</span>
              </div>
              <Progress value={34} />
            </div>

            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">Memory Usage</span>
                <span>2.4 GB / 8 GB</span>
              </div>
              <Progress value={30} />
            </div>

            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">Disk Usage</span>
                <span>156 GB / 200 GB</span>
              </div>
              <Progress value={78} />
            </div>

            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">Cache Size</span>
                <span>4.2 GB</span>
              </div>
              <Progress value={42} />
            </div>
          </div>
        </Card>

        {/* Performance Stats */}
        <Card className="p-6">
          <h2 className="mb-6">Performance Statistics</h2>
          
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Avg Slide Generation Time</span>
              <span>1.2s</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Avg Video Encoding Time</span>
              <span>8.4s</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Avg Pipeline Duration</span>
              <span>11m 24s</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Cache Hit Rate</span>
              <span>67%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Success Rate (24h)</span>
              <span>94%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Jobs Completed (24h)</span>
              <span>47</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Cache Management */}
      <Card className="p-6 mt-6">
        <h2 className="mb-6">Cache Management</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <div className="text-sm text-muted-foreground mb-2">Slide Cache</div>
            <div className="text-2xl mb-3">2.8 GB</div>
            <Button
              variant="outline"
              className="w-full"
              onClick={handleClearCache}
              disabled={clearing}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Clear Slide Cache
            </Button>
          </div>

          <div>
            <div className="text-sm text-muted-foreground mb-2">Template Cache</div>
            <div className="text-2xl mb-3">856 MB</div>
            <Button
              variant="outline"
              className="w-full"
              onClick={handleClearCache}
              disabled={clearing}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Clear Template Cache
            </Button>
          </div>

          <div>
            <div className="text-sm text-muted-foreground mb-2">API Response Cache</div>
            <div className="text-2xl mb-3">542 MB</div>
            <Button
              variant="outline"
              className="w-full"
              onClick={handleClearCache}
              disabled={clearing}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Clear API Cache
            </Button>
          </div>
        </div>

        <Separator className="my-6" />

        <div className="flex justify-between items-center">
          <div>
            <div className="text-sm">Total Cache Size</div>
            <div className="text-xs text-muted-foreground mt-1">
              Last cleared: Oct 7, 2025 08:00
            </div>
          </div>
          <Button variant="destructive" onClick={handleClearCache} disabled={clearing}>
            <Trash2 className="h-4 w-4 mr-2" />
            Clear All Caches
          </Button>
        </div>
      </Card>

      {/* Recent Activity */}
      <Card className="p-6 mt-6">
        <h2 className="mb-6">Recent System Events</h2>
        
        <div className="space-y-3">
          {[
            { time: "14:45", event: "Pipeline job run-002 started", type: "info" },
            { time: "14:23", event: "Pipeline job run-001 completed successfully", type: "success" },
            { time: "13:12", event: "Pipeline job run-003 failed: API timeout", type: "error" },
            { time: "12:05", event: "Cache cleanup completed (2.1 GB freed)", type: "info" },
            { time: "11:30", event: "System health check passed", type: "success" },
          ].map((item, idx) => (
            <div key={idx} className="flex items-start gap-4 text-sm">
              <span className="text-muted-foreground font-mono min-w-[50px]">
                {item.time}
              </span>
              <div className="flex-1">{item.event}</div>
              {item.type === "success" && (
                <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5" />
              )}
              {item.type === "error" && (
                <XCircle className="h-4 w-4 text-red-500 mt-0.5" />
              )}
              {item.type === "info" && (
                <AlertCircle className="h-4 w-4 text-blue-500 mt-0.5" />
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
