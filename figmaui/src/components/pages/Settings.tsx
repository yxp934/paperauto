import { useState } from "react";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";
import { Separator } from "../ui/separator";
import { Badge } from "../ui/badge";
import { CheckCircle2, XCircle, Loader2, Save } from "lucide-react";
import { toast } from "sonner@2.0.3";

export function Settings() {
  const [slideSystemEnabled, setSlideSystemEnabled] = useState(true);
  const [autoPPTXExport, setAutoPPTXExport] = useState(true);
  const [searchAPIKey, setSearchAPIKey] = useState("");
  const [plantUMLServer, setPlantUMLServer] = useState("http://www.plantuml.com/plantuml");
  const [testingAPI, setTestingAPI] = useState<string | null>(null);

  const handleTestConnection = (service: string) => {
    setTestingAPI(service);
    setTimeout(() => {
      setTestingAPI(null);
      toast.success(`${service} connection successful`);
    }, 1500);
  };

  const handleSave = () => {
    toast.success("Settings saved successfully");
  };

  return (
    <div className="p-8 max-w-[900px] mx-auto">
      <div className="mb-8">
        <h1>Settings</h1>
        <p className="text-muted-foreground mt-1">Configure runtime behavior and integrations</p>
      </div>

      <div className="space-y-6">
        {/* General Settings */}
        <Card className="p-6">
          <h2 className="mb-6">General Settings</h2>
          
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>Enable Slide System</Label>
                <div className="text-sm text-muted-foreground">
                  Toggle the slide generation pipeline
                </div>
              </div>
              <Switch
                checked={slideSystemEnabled}
                onCheckedChange={setSlideSystemEnabled}
              />
            </div>

            <Separator />

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>Auto-Export PPTX</Label>
                <div className="text-sm text-muted-foreground">
                  Automatically export PowerPoint files after generation
                </div>
              </div>
              <Switch
                checked={autoPPTXExport}
                onCheckedChange={setAutoPPTXExport}
              />
            </div>
          </div>
        </Card>

        {/* API Configuration */}
        <Card className="p-6">
          <h2 className="mb-6">API Configuration</h2>
          
          <div className="space-y-6">
            {/* Search API */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>Search API Key</Label>
                <Badge variant="outline" className="text-xs">Optional</Badge>
              </div>
              <Input
                type="password"
                placeholder="Enter your search API key"
                value={searchAPIKey}
                onChange={(e) => setSearchAPIKey(e.target.value)}
              />
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleTestConnection("Search API")}
                  disabled={!searchAPIKey || testingAPI === "search"}
                >
                  {testingAPI === "search" ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Testing...
                    </>
                  ) : (
                    <>Test Connection</>
                  )}
                </Button>
              </div>
            </div>

            <Separator />

            {/* PlantUML Server */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>PlantUML Server</Label>
                <Badge variant="outline" className="text-xs">Optional</Badge>
              </div>
              <Input
                placeholder="http://www.plantuml.com/plantuml"
                value={plantUMLServer}
                onChange={(e) => setPlantUMLServer(e.target.value)}
              />
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleTestConnection("PlantUML Server")}
                  disabled={!plantUMLServer || testingAPI === "plantuml"}
                >
                  {testingAPI === "plantuml" ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Testing...
                    </>
                  ) : (
                    <>Test Connection</>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </Card>

        {/* Model Configuration */}
        <Card className="p-6">
          <h2 className="mb-6">Model Configuration</h2>
          
          <div className="space-y-6">
            <div className="space-y-2">
              <Label>Default LLM Provider</Label>
              <Input defaultValue="OpenAI GPT-4" />
            </div>

            <div className="space-y-2">
              <Label>Temperature</Label>
              <Input type="number" defaultValue="0.7" min="0" max="2" step="0.1" />
              <div className="text-xs text-muted-foreground">
                Controls randomness in model outputs (0-2)
              </div>
            </div>

            <div className="space-y-2">
              <Label>Max Tokens</Label>
              <Input type="number" defaultValue="4096" />
            </div>
          </div>
        </Card>

        {/* Performance Settings */}
        <Card className="p-6">
          <h2 className="mb-6">Performance Settings</h2>
          
          <div className="space-y-6">
            <div className="space-y-2">
              <Label>Max Concurrent Jobs</Label>
              <Input type="number" defaultValue="3" min="1" max="10" />
            </div>

            <div className="space-y-2">
              <Label>Cache TTL (minutes)</Label>
              <Input type="number" defaultValue="60" min="5" max="1440" />
              <div className="text-xs text-muted-foreground">
                How long to cache slide generation results
              </div>
            </div>

            <div className="space-y-2">
              <Label>Video Quality</Label>
              <select className="w-full px-3 py-2 rounded-md border border-input bg-input-background">
                <option>High (1080p, 60fps)</option>
                <option>Medium (720p, 30fps)</option>
                <option>Low (480p, 30fps)</option>
              </select>
            </div>
          </div>
        </Card>

        {/* Connection Status */}
        <Card className="p-6">
          <h2 className="mb-6">Connection Status</h2>
          
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm">Database</span>
              <Badge variant="outline" className="gap-1">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                Connected
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">File System</span>
              <Badge variant="outline" className="gap-1">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                Ready
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Search API</span>
              <Badge variant="outline" className="gap-1">
                <XCircle className="h-3 w-3 text-muted-foreground" />
                Not Configured
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">PlantUML Server</span>
              <Badge variant="outline" className="gap-1">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                Connected
              </Badge>
            </div>
          </div>
        </Card>

        {/* Save Button */}
        <div className="flex justify-end gap-3">
          <Button variant="outline">Reset to Defaults</Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Settings
          </Button>
        </div>
      </div>
    </div>
  );
}
