"use client";
import { useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";

export default function GeneratePage() {
  const [model, setModel] = useState<string>("sdxl");
  return (
    <div className="space-y-4">
      <h1>Generate</h1>
      <div className="max-w-sm">
        <label className="text-sm text-muted-foreground">Model</label>
        <Select onValueChange={setModel}>
          <SelectTrigger className="mt-1">
            <SelectValue placeholder="Select a model" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="sdxl">SDXL</SelectItem>
            <SelectItem value="flux">FLUX</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <Button className="bg-primary text-primary-foreground">Start Job</Button>
    </div>
  );
}

